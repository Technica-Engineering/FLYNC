"""
Converter between the FLYNC model and CAN database (DBC) files.

:func:`load_dbc_files` reads DBC files into cantools databases and :func:`write_dbc_files` writes a FLYNC
model back out; the ``decode_*`` helpers translate cantools signals and messages into FLYNC signals and
PDUs (standard, multiplexed and container). :class:`DbcConverter` registers this conversion as a plugin.
"""

import logging
from pathlib import Path
from typing import List, Literal, Optional

import cantools.database
from cantools.database.can.database import Database
from cantools.database.can.message import Message
from cantools.database.can.signal import Signal
from cantools.database.conversion import LinearConversion

from flync.model import FLYNCModel  # type: ignore[import-untyped]
from flync.model.flync_4_signal import (
    ContainerPDU,
    MultiplexedPDU,
    SignalInstance,
    StandardPDU,
)
from flync.model.flync_4_signal.pdu import PDU

from ..base.base_converter import BaseConverter
from ..registry import hookimpl

logger = logging.getLogger(__name__)


def load_dbc_files(root_folder):
    """Recursively load all DBC files from a folder.

    Args:
        root_folder: Root folder path to search for DBC files.

    Returns:
        List of loaded cantools Database objects (one per DBC file).
    """

    dbc_files = []

    root = Path(root_folder)
    logger.debug("Scanning for DBC files under: %s", root_folder)

    for dbc_file in root.rglob("*.dbc"):
        logger.debug("Loading DBC file: %s", dbc_file)
        tmp = cantools.database.load_file(dbc_file)
        dbc_files.append(tmp)

    logger.debug("Finished loading DBC files: %d total files found", len(dbc_files))

    return dbc_files


def decode_signal(
    signal,
    bit_pos: int,
    byte_order: Literal["little_endian", "big_endian"] = "little_endian",
    receivers: Optional[List[str]] = None,
    is_multiplexer: bool = False,
    multiplexer_signal=None,
    multiplexer_ids=None,
):
    """Convert a FLYNC signal definition to a cantools Signal object."""
    ret = Signal(
        name=signal.name,
        start=bit_pos,
        length=signal.bit_length,
        byte_order=byte_order,
        is_signed=signal.data_type.is_signed_integer(),
        conversion=LinearConversion(
            scale=signal.factor,
            offset=signal.offset,
            is_float=signal.data_type.is_float(),
        ),
        receivers=receivers,
        is_multiplexer=is_multiplexer,
        multiplexer_signal=multiplexer_signal,
        multiplexer_ids=multiplexer_ids,
        unit=signal.unit or "",
        comment={"EN": signal.description} if signal.description else None,
    )

    return ret


def decode_signal_instance(
    s: SignalInstance,
    bit_pos: int,
    receivers: Optional[List[str]] = None,
    is_multiplexer: bool = False,
    multiplexer_ids=None,
    multiplexer_signal=None,
):
    """Convert a SignalInstance to a cantools Signal, offsetting bit position."""
    ret = decode_signal(
        s.signal,
        bit_pos + (s.bit_position or 0),
        receivers=receivers,
        is_multiplexer=is_multiplexer,
        multiplexer_signal=multiplexer_signal,
        multiplexer_ids=multiplexer_ids,
    )

    return ret


def _decode_standard_pdu(pdu: StandardPDU, bit_pos: int, receivers: Optional[List[str]]) -> List[Signal]:
    """Decode a StandardPDU into a flat list of cantools Signal objects."""
    ret: List[Signal] = []
    for s in pdu.signals:
        ret.append(decode_signal_instance(s, bit_pos, receivers=receivers))
    for _ in pdu.signal_groups:
        logger.warning("Signal Group not supported yet!")
    return ret


def _pdus_by_name(flync_model: FLYNCModel) -> dict:
    """Return a ``name -> PDU`` lookup from the model (or ``{}`` when not derivable)."""
    pdus: dict = {}
    if flync_model is not None:
        communication = getattr(flync_model, "communication", None)
        declared = getattr(getattr(communication, "channels", None), "pdus", None)
        if declared:
            try:
                pdus = {p.name: p for p in declared}
            except TypeError:
                pdus = {}
    return pdus


def _decode_multiplexed_pdu(
    flync_model: FLYNCModel,
    pdu: MultiplexedPDU,
    bit_pos: int,
    receivers: Optional[List[str]],
    pdus: Optional[dict] = None,
) -> List[Signal]:
    """Decode a MultiplexedPDU into a flat list of cantools Signal objects."""
    if pdus is None:
        pdus = _pdus_by_name(flync_model)
    sel = pdu.selector_signal
    selector_name = sel.signal.name
    ret: List[Signal] = [decode_signal_instance(sel, bit_pos, receivers=receivers)]

    if pdu.static_group is not None:
        static_ref = pdu.static_group.pdu_ref
        static_pdu = pdus.get(static_ref, None)
        static_offset = bit_pos + (pdu.static_group.bit_position or 0)
        if static_pdu is None:
            logger.warning("Referenced static PDU '%s' not found", static_ref)
        else:
            ret.extend(_decode_standard_pdu(static_pdu, static_offset, receivers))

    for group in pdu.mux_groups:
        mux_ref = group.pdu.pdu_ref
        mux_pdu = pdus.get(mux_ref, None)
        mux_offset = bit_pos + (group.pdu.bit_position or 0)
        if mux_pdu is None:
            logger.warning("Referenced mux PDU '%s' not found", mux_ref)
            continue
        for s in mux_pdu.signals:
            ret.append(
                decode_signal_instance(
                    s,
                    mux_offset,
                    receivers=receivers,
                    multiplexer_signal=selector_name,
                    multiplexer_ids=[group.selector_value],
                )
            )
        for _ in mux_pdu.signal_groups:
            logger.warning("Signal Group inside MuxGroup not supported yet!")

    return ret


def decode_pdu(  # NOSONAR
    flync_model: FLYNCModel,
    pdu: PDU,
    bit_pos: int,
    receivers: Optional[List[str]] = None,
    pdus: Optional[dict] = None,
) -> List[Signal]:
    """Recursively decode a PDU and its nested signals into a flat list of cantools Signal objects."""
    if pdu is None:
        return []
    if isinstance(pdu, StandardPDU):
        return _decode_standard_pdu(pdu, bit_pos, receivers)
    if isinstance(pdu, MultiplexedPDU):
        return _decode_multiplexed_pdu(flync_model, pdu, bit_pos, receivers, pdus)
    if isinstance(pdu, ContainerPDU):
        logger.warning("ContainerPDU not implemented yet!")
    else:
        logger.warning("Unknown PDU type: %s", type(pdu))
    return []


def _collect_frame_participants(flync_model: FLYNCModel):
    """Return (frame_senders, frame_receivers) dicts built from all ECU CAN interfaces."""
    frame_senders: dict[tuple, list] = {}
    frame_receivers: dict[tuple, list] = {}
    for ecu in flync_model.ecus:
        for ctrl in ecu.controllers:
            for iface in ctrl.can_interfaces or []:
                for f in iface.sender_frames:
                    frame_senders.setdefault((f.bus_ref, f.frame_ref), []).append(ecu.name)
                for f in iface.receiver_frames:
                    frame_receivers.setdefault((f.bus_ref, f.frame_ref), []).append(ecu.name)
    return frame_senders, frame_receivers


def _build_can_messages(flync_model: FLYNCModel, can_bus, pdus: dict, frame_senders: dict, frame_receivers: dict) -> list:
    """Build a list of cantools Message objects for all frames in one CAN bus."""
    messages = []
    for frame in can_bus.frames:
        sigs: List[Signal] = []
        for pdu_inst in frame.packed_pdus:
            pdu_obj = pdus.get(pdu_inst.pdu_ref, None)
            sigs += decode_pdu(
                flync_model,
                pdu_obj,  # type: ignore[arg-type]
                pdu_inst.bit_position or 0,
                frame_receivers.get((can_bus.name, frame.can_id), None),
                pdus,
            )
        messages.append(
            Message(
                frame_id=frame.can_id,
                name=frame.name,
                length=frame.length,
                signals=sigs,
                comment=frame.description,
                senders=frame_senders.get((can_bus.name, frame.can_id), None),
                is_extended_frame=frame.id_format == "extended_29bit",
                is_fd=frame.type == "can_fd",
            )
        )
    return messages


def write_dbc_files(flync_model: FLYNCModel, root_folder: str):
    """Write one DBC file per CAN bus defined in the FLYNCModel to root_folder."""
    if flync_model.communication is None or flync_model.communication.channels is None:
        logger.warning("Could not find communication/channels!")
        return

    pdus = {pdu.name: pdu for pdu in flync_model.communication.channels.pdus or []}
    frame_senders, frame_receivers = _collect_frame_participants(flync_model)

    for can_bus in flync_model.communication.channels.can_buses or []:
        messages = _build_can_messages(flync_model, can_bus, pdus, frame_senders, frame_receivers)
        db = Database(messages=messages)
        fn = Path(root_folder) / Path(f"{can_bus.name}.dbc")
        cantools.database.dump_file(
            db,
            str(fn),
            database_format="dbc",
            sort_signals=lambda signals: sorted(signals, key=lambda sig: sig.start),
        )


class DbcConverter(BaseConverter):
    """Converter between FLYNCModel and DBC format.

    Currently only supports encoding (FLYNC to DBC). Decoding is not yet
    implemented.
    """

    name = "dbc"

    def can_decode(self):
        """Return False — DBC decode is not yet implemented."""
        return False

    def encode(self, source: FLYNCModel):
        """Encode a FLYNCModel into target representation.

        Args:
            source (FLYNCModel): The model to encode.
        """

        if self.config is None:
            raise ValueError("config must be set before encoding")

        logger.debug("Encoding FLYNCModel to DBC at: %s", self.config.config_path)
        Path(self.config.config_path).mkdir(parents=True, exist_ok=True)

        write_dbc_files(source, self.config.config_path)

        logger.debug("JSON encode complete: %s", self.config.config_path)

    def decode(self) -> FLYNCModel:
        """Decode data into a FLYNCBaseModel.

        Returns:
            FLYNCBaseModel: The decoded model.
        """

        if self.config is None:
            raise ValueError("config must be set before decoding")
        logger.debug(
            "Decoding FLYNCModel from DBC path: %s",
            self.config.config_path,
        )

        dbc_models = load_dbc_files(self.config.config_path)
        logger.debug("Validating FLYNCModel from %d keys", len(dbc_models))

        # Here we will add the DBC to FLYNC Conversion later
        model = None
        logger.debug("DBC decode complete")
        return model  # type: ignore[return-value]


@hookimpl
def register_converters():
    """Register the DbcConverter with the pluggy plugin manager."""
    return [DbcConverter()]
