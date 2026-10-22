"""Encode a FLYNC model into DBC files (FLYNC to DBC direction)."""

import logging
from collections import OrderedDict
from pathlib import Path
from typing import List, Literal, Optional

import cantools.database
from cantools.database.can.database import Database
from cantools.database.can.formats.dbc.dbc_loader import ATTRIBUTE_DEFINITION_VFRAMEFORMAT
from cantools.database.can.formats.dbc.dbc_specifics import DbcSpecifics
from cantools.database.can.message import Message
from cantools.database.can.node import Node
from cantools.database.can.signal import Signal
from cantools.database.conversion import LinearConversion
from cantools.database.namedsignalvalue import NamedSignalValue
from cantools.j1939 import frame_id_pack, pgn_from_frame_id

from flync.model import FLYNCModel
from flync.model.flync_4_signal import ContainerPDU, MultiplexedPDU, SignalInstance, StandardPDU
from flync.model.flync_4_signal.frame import J1939Frame
from flync.model.flync_4_signal.pdu import PDU
from flync.model.flync_4_signal.value_encoding import TextTable

from ...base.converter_report import INACTIVE_REPORT, ConverterReport

logger = logging.getLogger(__name__)

_PDU_NOT_FOUND = "referenced PDU not found"

#: J1939 source address used when a FLYNC node models no SA (address claiming
#: assigns SA at runtime); 0xFE (254) is the J1939 NULL address.
_DEFAULT_J1939_SA = 0xFE


def _j1939_frame_id(frame: J1939Frame) -> int:
    """Reconstruct the 29-bit J1939 arbitration ID from a J1939Frame's fields."""
    return frame_id_pack(
        frame.priority,
        frame.extended_data_page,
        frame.data_page,
        frame.pdu_format,
        frame.pdu_specific,
        _DEFAULT_J1939_SA,
    )


def _pgn_from_frame(frame: J1939Frame) -> int:
    """Return the J1939 Parameter Group Number (PGN) of ``frame``."""
    return pgn_from_frame_id(_j1939_frame_id(frame))


def _value_encoding_choices(signal) -> Optional[OrderedDict[int, str | NamedSignalValue]]:
    """Convert a FLYNC signal ``value_encoding`` into a cantools ``VAL_`` choices dict.

    Returns ``None`` when the signal carries no value encoding.  Range entries
    are expanded to one choice per raw integer value to match the DBC ``VAL_``
    format (which has no range concept).
    """
    encoding = getattr(signal, "value_encoding", None)
    if not isinstance(encoding, TextTable):
        return None
    choices: OrderedDict[int, str | NamedSignalValue] = OrderedDict()
    for entry in encoding.entries:
        for value in range(entry.from_value, entry.to_value + 1):
            choices[value] = entry.label
    return choices


_SCIENTIFIC_NOTATION_THRESHOLD = 10**16


def _as_dbc_number(value: Optional[float | int]) -> Optional[float | int]:
    """Render integral values without a trailing ``.0`` in the DBC output.

    Cantools serializes the linear conversion as ``(scale,offset)`` using plain
    ``str()``, so a float ``1.0``/``0.0`` becomes ``(1.0,0.0)``.  Erasing the
    redundant fractional part for whole numbers gives the conventional
    ``(1,0)`` used by most DBC tools.

    Very large whole values (e.g. raw bounds of wide bitfields/BYTEARRAY blobs)
    stay as floats so they render in scientific notation — ``0|1.34e+154`` —
    rather than an unwieldy run of digits.
    """
    ret: Optional[float | int] = value

    if value is None:
        ret = None
    elif isinstance(value, int) and not isinstance(value, bool):
        ret = value if abs(value) < _SCIENTIFIC_NOTATION_THRESHOLD else float(value)
    elif isinstance(value, float) and value.is_integer():
        ret = int(value) if abs(value) < _SCIENTIFIC_NOTATION_THRESHOLD else value

    return ret


def _raw_value_bounds(signal) -> tuple[int, int]:
    """Inclusive ``(lo, hi)`` raw representable range for a signal.

    Unsigned integers and ``BYTEARRAY`` blobs range over ``0 .. 2**N - 1``;
    signed integers range over ``-(2**(N-1)) .. 2**(N-1) - 1``.  This mirrors
    the DBC ``[minimum|maximum]`` convention (a 512-bit BYTEARRAY renders as
    ``0|1.34e+154``, i.e. the full unsigned width).
    """
    if signal.data_type.is_signed_integer():
        return -(1 << (signal.bit_length - 1)), (1 << (signal.bit_length - 1)) - 1
    return 0, (1 << signal.bit_length) - 1


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
    raw_min, raw_max = _raw_value_bounds(signal)
    minimum = _as_dbc_number(signal.lower_limit) if signal.lower_limit is not None else _as_dbc_number(raw_min)
    maximum = _as_dbc_number(signal.upper_limit) if signal.upper_limit is not None else _as_dbc_number(raw_max)
    ret = Signal(
        name=signal.name,
        start=bit_pos,
        length=signal.bit_length,
        byte_order=byte_order,
        is_signed=signal.data_type.is_signed_integer(),
        conversion=LinearConversion(
            scale=_as_dbc_number(signal.factor),  # type: ignore[arg-type]
            offset=_as_dbc_number(signal.offset),  # type: ignore[arg-type]
            is_float=signal.data_type.is_float(),
        ),
        receivers=receivers,
        is_multiplexer=is_multiplexer,
        multiplexer_signal=multiplexer_signal,
        multiplexer_ids=multiplexer_ids,
        unit=signal.unit or "",
        comment={"EN": signal.description} if signal.description else None,
        minimum=minimum,
        maximum=maximum,
    )
    choices = _value_encoding_choices(signal)
    if choices:
        ret.choices = choices

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


def _report_signal_groups(pdu: StandardPDU, report: ConverterReport) -> None:
    """Log and report the signal groups of ``pdu``, which DBC output does not support."""
    for group in pdu.signal_groups:
        logger.warning("Signal group '%s' of PDU '%s' not supported, skipped", group.signal_group.name, pdu.name)
        report.unsupported(f"pdus.{pdu.name}.signal_groups.{group.signal_group.name}", reason="signal groups are not supported in DBC output")


def _decode_standard_pdu(pdu: StandardPDU, bit_pos: int, receivers: Optional[List[str]], report: ConverterReport = INACTIVE_REPORT) -> List[Signal]:
    """Decode a StandardPDU into a flat list of cantools Signal objects."""
    ret: List[Signal] = []
    for s in pdu.signals:
        ret.append(decode_signal_instance(s, bit_pos, receivers=receivers))
    _report_signal_groups(pdu, report)
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
    report: ConverterReport = INACTIVE_REPORT,
) -> List[Signal]:
    """Decode a MultiplexedPDU into a flat list of cantools Signal objects."""
    if pdus is None:
        pdus = _pdus_by_name(flync_model)
    sel = pdu.selector_signal
    selector_name = sel.signal.name
    ret: List[Signal] = [decode_signal_instance(sel, bit_pos, receivers=receivers, is_multiplexer=True)]

    for static in pdu.static_group or []:
        static_ref = static.pdu_ref
        static_pdu = pdus.get(static_ref, None)
        static_offset = bit_pos + (static.bit_position or 0)
        if static_pdu is None:
            logger.warning("Referenced static PDU '%s' not found", static_ref)
            report.skipped(f"pdus.{pdu.name}.static_group.{static_ref}", reason=_PDU_NOT_FOUND)
        else:
            ret.extend(decode_pdu(flync_model, static_pdu, static_offset, receivers, pdus, report=report))

    for group in pdu.mux_groups:
        mux_ref = group.pdu.pdu_ref
        mux_pdu = pdus.get(mux_ref, None)
        mux_offset = bit_pos + (group.pdu.bit_position or 0)
        if mux_pdu is None:
            logger.warning("Referenced mux PDU '%s' not found", mux_ref)
            report.skipped(f"pdus.{pdu.name}.mux_groups.{mux_ref}", reason=_PDU_NOT_FOUND)
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
        _report_signal_groups(mux_pdu, report)

    return ret


def decode_pdu(  # NOSONAR
    flync_model: FLYNCModel,
    pdu: PDU,
    bit_pos: int,
    receivers: Optional[List[str]] = None,
    pdus: Optional[dict] = None,
    report: ConverterReport = INACTIVE_REPORT,
) -> List[Signal]:
    """Recursively decode a PDU and its nested signals into a flat list of cantools Signal objects.

    Content DBC output cannot hold is logged and recorded in ``report``.
    """
    if pdu is None:
        return []
    if isinstance(pdu, StandardPDU):
        return _decode_standard_pdu(pdu, bit_pos, receivers, report)
    if isinstance(pdu, MultiplexedPDU):
        return _decode_multiplexed_pdu(flync_model, pdu, bit_pos, receivers, pdus, report)
    if isinstance(pdu, ContainerPDU):
        logger.warning("Container PDU '%s' not supported, skipped", pdu.name)
        report.unsupported(f"pdus.{pdu.name}", reason="container PDUs are not supported in DBC output")
    else:
        logger.warning("Unknown PDU type: %s", type(pdu))
        report.unsupported(f"pdus.{getattr(pdu, 'name', '?')}", reason=f"unknown PDU type {type(pdu).__name__}")
    return []


def _index_frame_participants(index: dict, ecu_name: str, refs, key) -> None:
    """Index ``ecu_name`` under ``index[key(ref)]`` for every member of ``refs``."""
    for ref in refs or []:
        index.setdefault(key(ref), []).append(ecu_name)


def _collect_interface_frames(
    iface,
    ecu_name: str,
    frame_senders: dict,
    frame_receivers: dict,
    j1939_senders: dict,
    j1939_receivers: dict,
) -> None:
    """Index the send/receive frame and J1939 references of one CAN interface."""
    _index_frame_participants(frame_senders, ecu_name, iface.sender_frames, lambda f: (iface.bus_ref, f.id_format, f.frame_ref))
    _index_frame_participants(frame_receivers, ecu_name, iface.receiver_frames, lambda f: (iface.bus_ref, f.id_format, f.frame_ref))
    _index_frame_participants(j1939_senders, ecu_name, iface.j1939_sender_frames, lambda f: (iface.bus_ref, f.pgn))
    _index_frame_participants(j1939_receivers, ecu_name, iface.j1939_receiver_frames, lambda f: (iface.bus_ref, f.pgn))


def _collect_frame_participants(flync_model: FLYNCModel):
    """Return frame/j1939 sender and receiver dicts built from all ECU CAN interfaces.

    ``frame_senders``/``frame_receivers`` are keyed by ``(bus_ref, id_format, frame_ref)`` for
    classical CAN frames; ``j1939_senders``/``j1939_receivers`` are keyed by
    ``(bus_ref, pgn)`` for J1939 nodes.
    """
    frame_senders: dict[tuple, list] = {}
    frame_receivers: dict[tuple, list] = {}
    j1939_senders: dict[tuple, list] = {}
    j1939_receivers: dict[tuple, list] = {}
    for ecu in flync_model.ecus:
        for ctrl in ecu.controllers:
            for iface in ctrl.can_interfaces or []:
                _collect_interface_frames(iface, ecu.name, frame_senders, frame_receivers, j1939_senders, j1939_receivers)
    return frame_senders, frame_receivers, j1939_senders, j1939_receivers


def _build_can_messages(
    flync_model: FLYNCModel,
    can_bus,
    pdus: dict,
    frame_senders: dict,
    frame_receivers: dict,
    j1939_senders: dict,
    j1939_receivers: dict,
    report: ConverterReport = INACTIVE_REPORT,
) -> list:
    """Build a list of cantools Message objects for all frames in one CAN bus."""
    messages = []
    for frame in can_bus.frames:
        messages.append(
            _build_one_message(
                flync_model,
                frame,
                can_bus,
                pdus,
                frame_senders,
                frame_receivers,
                j1939_senders,
                j1939_receivers,
                report,
            )
        )
    return messages


def _build_one_message(
    flync_model: FLYNCModel,
    frame,
    can_bus,
    pdus: dict,
    frame_senders: dict,
    frame_receivers: dict,
    j1939_senders: dict,
    j1939_receivers: dict,
    report: ConverterReport,
) -> Message:
    """Build the cantools Message for a single frame on ``can_bus``."""
    is_j1939 = isinstance(frame, J1939Frame)
    if is_j1939:
        frame_id = _j1939_frame_id(frame)
        pgn = _pgn_from_frame(frame)
        receivers = j1939_receivers.get((can_bus.name, pgn), None)
        senders = j1939_senders.get((can_bus.name, pgn), None)
    else:
        frame_id = frame.can_id
        receivers = frame_receivers.get((can_bus.name, frame.id_format, frame.can_id), None)
        senders = frame_senders.get((can_bus.name, frame.id_format, frame.can_id), None)
    sigs = _decode_frame_pdus(flync_model, frame, can_bus, pdus, receivers, report)
    if is_j1939:
        return Message(
            frame_id=frame_id,
            name=frame.name,
            length=frame.length,
            signals=sigs,
            comment=frame.description,
            senders=senders,
            is_extended_frame=True,
            protocol="j1939",
        )
    return Message(
        frame_id=frame_id,
        name=frame.name,
        length=frame.length,
        signals=sigs,
        comment=frame.description,
        senders=senders,
        is_extended_frame=frame.id_format == "extended_29bit",
        is_fd=frame.type == "can_fd",
    )


def _decode_frame_pdus(
    flync_model: FLYNCModel,
    frame,
    can_bus,
    pdus: dict,
    receivers,
    report: ConverterReport,
) -> List[Signal]:
    """Decode every packed PDU of ``frame`` into a flat DBC signal list."""
    sigs: List[Signal] = []
    for pdu_inst in frame.packed_pdus:
        pdu_obj = pdus.get(pdu_inst.pdu_ref, None)
        if pdu_obj is None:
            logger.warning("PDU '%s' packed in frame '%s' not found, skipped", pdu_inst.pdu_ref, frame.name)
            report.skipped(f"can_buses.{can_bus.name}.frames.{frame.name}.{pdu_inst.pdu_ref}", reason=_PDU_NOT_FOUND)
            continue
        sigs += decode_pdu(
            flync_model,
            pdu_obj,
            pdu_inst.bit_position or 0,
            receivers,
            pdus,
            report=report,
        )
    return sigs


def _report_non_can_content(channels, report: ConverterReport) -> None:
    """Log and report the channels content that DBC, a CAN-only format, cannot hold."""
    for lin_bus in channels.lin_buses or []:
        logger.warning("LIN bus '%s' not supported, skipped", lin_bus.name)
        report.unsupported(f"lin_buses.{lin_bus.name}", reason="DBC describes CAN buses only")
    for container in channels.ethernet_pdu_containers or []:
        logger.warning("Ethernet PDU container '%s' not supported, skipped", container.name)
        report.unsupported(f"ethernet_pdu_containers.{container.name}", reason="DBC describes CAN buses only")


def write_dbc_files(flync_model: FLYNCModel, destination_path: str, report: ConverterReport = INACTIVE_REPORT) -> List[Path]:
    """Write DBC output to an exact file path or to a destination folder.

    If an exact ``.dbc`` path is provided and the model contains one CAN bus,
    that exact file name is used. For multiple CAN buses, files are named
    ``<selected_stem>_<bus_name>.dbc`` next to the selected file.

    Model content that DBC cannot hold (LIN buses, Ethernet PDU containers,
    container PDUs, signal groups) and references that cannot be resolved are
    logged and recorded in ``report``, as are the files written
    (``output_files``).

    Args:
        flync_model: The model to write.
        destination_path: A ``.dbc`` file path or a destination folder.
        report: The converter's report.

    Returns:
        The DBC files written, one per CAN bus.
    """
    if flync_model.communication is None or flync_model.communication.channels is None:
        logger.warning("Model has no communication channels, no DBC file written")
        report.skipped("communication", reason="model has no communication channels")
        return []

    channels = flync_model.communication.channels
    _report_non_can_content(channels, report)
    pdus = {pdu.name: pdu for pdu in channels.pdus or []}
    frame_senders, frame_receivers, j1939_senders, j1939_receivers = _collect_frame_participants(flync_model)
    nodes = [Node(ecu.name) for ecu in flync_model.ecus]
    can_buses = list(channels.can_buses or [])
    configured_path = Path(destination_path)
    exact_file = configured_path.suffix.casefold() == ".dbc"

    output_directory = configured_path.parent if exact_file else configured_path
    output_directory.mkdir(parents=True, exist_ok=True)

    written: List[Path] = []
    for can_bus in can_buses:
        messages = _build_can_messages(flync_model, can_bus, pdus, frame_senders, frame_receivers, j1939_senders, j1939_receivers, report)
        has_j1939 = any(isinstance(frame, J1939Frame) for frame in can_bus.frames or [])
        dbc_specifics = None
        if has_j1939:
            # Emitting J1939PG requires the DBC to declare the VFrameFormat attribute
            # definition; the writer only auto-adds it for CAN-FD buses, so declare it
            # ourselves for J1939 buses.
            dbc_specifics = DbcSpecifics(attribute_definitions=OrderedDict({"VFrameFormat": ATTRIBUTE_DEFINITION_VFRAMEFORMAT}))
        db = Database(messages=messages, nodes=nodes, dbc_specifics=dbc_specifics)
        if exact_file and len(can_buses) == 1:
            output_file = configured_path
        elif exact_file:
            output_file = output_directory / f"{configured_path.stem}_{can_bus.name}.dbc"
        else:
            output_file = output_directory / f"{can_bus.name}.dbc"
        cantools.database.dump_file(
            db,
            str(output_file),
            database_format="dbc",
            sort_signals=lambda signals: sorted(signals, key=lambda sig: sig.start, reverse=True),
        )
        logger.info("Wrote CAN bus '%s' to %s: %d message(s)", can_bus.name, output_file, len(messages))
        written.append(output_file)

    if not can_buses:
        logger.warning("Model has no CAN bus, no DBC file written")
    report.add("output_files", written)
    return written
