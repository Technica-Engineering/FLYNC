"""Decode DBC databases into a FLYNC model (DBC to FLYNC direction)."""

import hashlib
import importlib.metadata
import logging
from collections import defaultdict
from typing import Dict, List, Literal, Optional, Tuple, cast

from cantools.database.can.message import Message
from cantools.database.can.signal import Signal
from cantools.database.utils import start_bit
from cantools.j1939 import frame_id_unpack, pgn_from_frame_id
from pydantic import ValidationError

from flync.model import FLYNCModel
from flync.model.flync_4_bus.can_bus import CANBaudRate, CANBus
from flync.model.flync_4_communication.flync_channels import FLYNCChannelConfig
from flync.model.flync_4_communication.flync_communication import FLYNCCommunicationConfig
from flync.model.flync_4_ecu.can_interface import CANFrameRef, CANInterface, J1939FrameRef
from flync.model.flync_4_ecu.controller import Controller
from flync.model.flync_4_ecu.ecu import ECU
from flync.model.flync_4_metadata.metadata import BaseVersion, ECUMetadata, EmbeddedMetadata, SystemMetadata
from flync.model.flync_4_signal import MultiplexedPDU, SignalInstance, StandardPDU
from flync.model.flync_4_signal.frame import CANFDFrame, CANFrame, J1939Frame
from flync.model.flync_4_signal.pdu import MuxGroup, PDUInstance
from flync.model.flync_4_signal.signal import Signal as FLYNCSignal
from flync.model.flync_4_signal.signal import SignalDataType
from flync.model.flync_4_signal.value_encoding import TextEntry, TextTable

from ...base.converter_report import INACTIVE_REPORT, ConverterReport
from .dbc_config import DbcConverterConfig
from .loading import _fd_baud_rate, _nominal_baud_rate, is_j1939_database

logger = logging.getLogger(__name__)


def _comment_text(comment) -> Optional[str]:
    """Normalize a cantools comment (``str`` or language-keyed ``dict``) to text."""
    if isinstance(comment, dict):
        return comment.get("EN") or (next(iter(comment.values())) if comment else None)
    return comment


def _bit_width_index(bit_length: int) -> int:
    """Return the bucket index (0..3) for a 8/16/32/64-bit signal width."""
    index = 3
    match bit_length:
        case n if n <= 8:
            index = 0
        case n if n <= 16:
            index = 1
        case n if n <= 32:
            index = 2
    return index


_UG_INT_TYPES = (SignalDataType.UINT8, SignalDataType.UINT16, SignalDataType.UINT32, SignalDataType.UINT64)
_SG_INT_TYPES = (SignalDataType.INT8, SignalDataType.INT16, SignalDataType.INT32, SignalDataType.INT64)


def map_data_type(bit_length: int, is_signed: bool, is_float: bool) -> SignalDataType:
    """Map DBC signal length/sign/floatness to the smallest fitting FLYNC data type.

    Integer signals wider than 64 bits (diagnostic/crypto blobs) cannot be
    represented as a fixed-width integer, so they map to ``bytearray`` (which
    accepts any multiple-of-8 bit length).
    """
    if is_float:
        return SignalDataType.FLOAT32 if bit_length <= 32 else SignalDataType.FLOAT64
    if bit_length > 64:
        return SignalDataType.BYTEARRAY
    types = _SG_INT_TYPES if is_signed else _UG_INT_TYPES
    return types[_bit_width_index(bit_length)]


def _coerce_initial_value(raw_initial, data_type: SignalDataType) -> bytes | int | float | None:
    """Return a FLYNC-compatible ``initial_value`` or ``None`` when it cannot be represented."""
    result: bytes | int | float | None = None
    if data_type == SignalDataType.BYTEARRAY:
        if isinstance(raw_initial, bytes):
            result = raw_initial
    elif data_type.is_float() and raw_initial is not None:
        result = raw_initial
    elif isinstance(raw_initial, int) and not isinstance(raw_initial, bool):
        result = raw_initial
    elif isinstance(raw_initial, float) and raw_initial.is_integer():
        result = int(raw_initial)
    return result


def _to_flync_signal(s: Signal, report: ConverterReport = INACTIVE_REPORT, where: str = "") -> FLYNCSignal:
    """Convert a cantools Signal into a FLYNC Signal.

    ``where`` locates the signal's message (``<bus>.<message>``) in what is
    recorded in ``report``.
    """
    data_type = map_data_type(s.length, s.is_signed, s.is_float)
    kwargs: dict = {
        "name": s.name,
        "description": _comment_text(s.comment),
        "bit_length": s.length,
        "data_type": data_type,
        "factor": s.scale,
        "offset": s.offset,
        "unit": s.unit or None,
        "initial_value": _coerce_initial_value(s.raw_initial, data_type),
    }
    if s.minimum is not None:
        kwargs["lower_limit"] = s.minimum
    if s.maximum is not None:
        kwargs["upper_limit"] = s.maximum

    choices = _in_range_choices(s, data_type, report, f"{where}.{s.name}")
    if choices:
        kwargs["value_encoding"] = TextTable(
            type="text_table",
            entries=[TextEntry(value=int(value), label=getattr(label, "name", str(label))) for value, label in choices.items()],
        )
    return FLYNCSignal(**kwargs)


def _in_range_choices(
    s: Signal, data_type: SignalDataType, report: ConverterReport = INACTIVE_REPORT, item: str = ""
) -> Optional[Dict[int, object]]:
    """Return ``s.choices`` filtered to entries representable by the FLYNC signal.

    Complex types (``bytearray``) have no text-table encoding, and raw values
    that fall outside the signal's bit range (common in hand-edited DBCs, e.g.
    a ``7-bit`` signal with a ``VAL_`` entry at ``127``) are dropped since FLYNC
    cannot represent them. Drops are logged as warnings and recorded in
    ``report`` under ``item``: a dropped table as ``unsupported``, dropped
    entries as ``skipped``.
    """
    if not s.choices:
        return None
    item = item or s.name
    if data_type.is_complex_datattype():
        logger.warning("Value table dropped for bytearray signal '%s'", s.name)
        report.unsupported(f"{item}.value_table", reason="bytearray signals have no value table in FLYNC")
        return None
    if s.is_signed:
        lo, hi = -(1 << (s.length - 1)), (1 << (s.length - 1)) - 1
    else:
        lo, hi = 0, (1 << s.length) - 1
    dropped = [int(v) for v in s.choices if not (lo <= int(v) <= hi)]
    if dropped:
        logger.warning(
            "Value table entries for signal '%s' outside bit range [%d, %d] dropped: %s",
            s.name,
            lo,
            hi,
            sorted(dropped),
        )
        report.skipped(f"{item}.value_table", reason=f"entries {sorted(dropped)} outside the bit range [{lo}, {hi}]")
    return {value: label for value, label in s.choices.items() if lo <= int(value) <= hi}


def _to_flync_signal_instance(s: Signal, report: ConverterReport = INACTIVE_REPORT, where: str = "") -> SignalInstance:
    """Convert a cantools Signal into a FLYNC SignalInstance, keeping its absolute bit start.

    ``s.start`` is Motorola-numbered (MSB-in-byte position) for big-endian
      signals, not a linear bit offset, so it is normalized via cantools'
      ``start_bit`` helper before being stored as the FLYNC ``bit_position``.

    """
    return SignalInstance(
        signal=_to_flync_signal(s, report, where),
        bit_position=start_bit(s),
        endianness="BE" if s.byte_order == "big_endian" else "LE",
    )


def _build_sub_pdu(
    name: str, sig_list: List[Signal], report: ConverterReport = INACTIVE_REPORT, where: str = ""
) -> Tuple[Optional[StandardPDU], Optional[int]]:
    """Build a StandardPDU from signals, re-basing them relative to their lowest start bit.

    FLYNC's :class:`MultiplexedPDU` placement model expects a static/mux-group PDU to
    occupy ``[bit_position, bit_position + length * 8)`` starting at the placement's
    ``bit_position``.  DBC signals carry absolute bit offsets, so this helper shifts
    them to be relative to the group's lowest start and places the PDU at that offset
    with a length covering exactly the group footprint.

    Returns:
        ``(pdu, base_bit_position)`` or ``(None, None)`` when ``sig_list`` is empty.
    """
    if not sig_list:
        return None, None
    base = min(s.start for s in sig_list)
    instances = [_to_flync_signal_instance(s, report, where) for s in sig_list]
    for si in instances:
        si.bit_position = (si.bit_position or 0) - base
    footprint = max((si.bit_position or 0) + si.signal.bit_length for si in instances)
    length = max(1, -(-footprint // 8))
    pdu = StandardPDU(name=name, type="standard", length=length, signals=instances)
    return pdu, base


def _collect_mux_groups(signals: List[Signal]) -> Dict[int, List[Signal]]:
    """Group multiplexed signals by their multiplexer id."""
    groups: Dict[int, List[Signal]] = {}
    for s in signals:
        if s.multiplexer_signal:
            for mid in s.multiplexer_ids or []:
                groups.setdefault(mid, []).append(s)
    return groups


def _build_static_group(
    extra: List[StandardPDU | MultiplexedPDU],
    main_name: str,
    static_signals: List[Signal],
    report: ConverterReport = INACTIVE_REPORT,
    where: str = "",
) -> Optional[List[PDUInstance]]:
    """Build the static-group placement and register its PDU in ``extra``."""
    if not static_signals:
        return None
    static_name = f"{main_name}_static"
    static_pdu, static_base = _build_sub_pdu(static_name, static_signals, report, where)
    assert static_pdu is not None and static_base is not None
    extra.append(static_pdu)
    return [PDUInstance(pdu_ref=static_name, bit_position=static_base)]


def _build_mux_placements(
    extra: List[StandardPDU | MultiplexedPDU],
    main_name: str,
    mux_groups: Dict[int, List[Signal]],
    report: ConverterReport = INACTIVE_REPORT,
    where: str = "",
) -> List[MuxGroup]:
    """Build the per-id mux-group placements and register their PDUs in ``extra``."""
    placements = []
    for mid in sorted(mux_groups.keys()):
        group_name = f"{main_name}_mux{mid}"
        group_pdu, group_base = _build_sub_pdu(group_name, mux_groups[mid], report, where)
        assert group_pdu is not None and group_base is not None
        extra.append(group_pdu)
        placements.append(MuxGroup(selector_value=mid, pdu=PDUInstance(pdu_ref=group_name, bit_position=group_base)))
    return placements


def _build_pdu_for_message(
    message: Message, prefix: str, report: ConverterReport = INACTIVE_REPORT
) -> Tuple[StandardPDU | MultiplexedPDU, List[StandardPDU | MultiplexedPDU]]:
    """Build the top-level PDU for a message plus any auxiliary PDUs it needs.

    A message without a multiplexer signal maps to a single :class:`StandardPDU`.
    A message with a multiplexer (``M``) signal maps to a :class:`MultiplexedPDU`
    whose static and mux-group signal sets are extracted into referenced
    :class:`StandardPDU` instances (returned in the second tuple element so the
    caller can register them).
    """
    signals = list(message.signals or [])
    selector = next((s for s in signals if s.is_multiplexer), None)

    main_name = f"{prefix}_{message.name}"
    where = f"{prefix}.{message.name}"
    pdu: StandardPDU | MultiplexedPDU
    if selector is None:
        instances = [_to_flync_signal_instance(s, report, where) for s in signals]
        if message.length > 0:
            length = message.length
        else:
            # J1939 "standalone" messages often declare DLC 0 while packing many signals;
            # derive a positive PDU length from the signal footprint instead.
            footprint = max((si.bit_position or 0) + si.signal.bit_length for si in instances) if instances else 0
            length = max(1, -(-footprint // 8))
        pdu = StandardPDU(
            name=main_name,
            type="standard",
            length=length,
            signals=instances,
        )
        return pdu, []

    extra: List[StandardPDU | MultiplexedPDU] = []
    mux_groups = _collect_mux_groups(signals)
    static_signals = [s for s in signals if not s.is_multiplexer and not s.multiplexer_signal]
    static_group = _build_static_group(extra, main_name, static_signals, report, where)
    mux_placements = _build_mux_placements(extra, main_name, mux_groups, report, where)

    pdu = MultiplexedPDU(
        name=main_name,
        type="multiplexed",
        length=max(1, message.length),
        selector_signal=_to_flync_signal_instance(selector, report, where),
        static_group=static_group,
        mux_groups=mux_placements,
    )
    return pdu, extra


def _j1939_frame_fields(message: Message) -> dict:
    """Decompose a J1939 message's 29-bit arbitration ID into J1939Frame fields.

    cantools exposes the raw extended ``frame_id``; ``cantools.j1939`` unpacks it
    into priority / reserved (the extended data page) / data page / PDU format /
    PDU specific / source address. ``destination_type`` is derived from PDU1 vs
    PDU2 semantics: PDU2 (``pdu_format`` >= 240) is always a group broadcast
    (``global``); PDU1 is ``global`` only for the broadcast address 255, else
    ``specific``.
    """
    unpacked = frame_id_unpack(message.frame_id)
    pf = unpacked.pdu_format
    ps = unpacked.pdu_specific
    if pf >= 240:
        destination_type = "global"
    else:
        destination_type = "global" if ps == 255 else "specific"
    return {
        "priority": unpacked.priority,
        "pdu_format": pf,
        "pdu_specific": ps,
        "data_page": unpacked.data_page,
        "extended_data_page": unpacked.reserved,
        "destination_type": destination_type,
    }


def _message_pgn(message: Message) -> int:
    """Return the J1939 Parameter Group Number (PGN) of *message*."""
    return pgn_from_frame_id(message.frame_id)


def _to_flync_frame(message: Message, pdu_name: str, is_j1939: bool = False, length: Optional[int] = None):
    """Convert a cantools Message into a FLYNC CAN/CAN-FD/J1939 frame referencing ``pdu_name``.

    For J1939, ``length`` carries the PDU payload length: an ordinary parameter
    group is 8 bytes, while a Transport Protocol message may span the whole
    J1939 payload (up to 1785 bytes), all shipped inside a single PDU.
    """
    packed = [PDUInstance(pdu_ref=pdu_name, bit_position=0)]
    description = _comment_text(message.comment)
    if is_j1939:
        return J1939Frame(
            name=message.name,
            length=length if length is not None else 8,
            description=description,
            packed_pdus=packed,
            **_j1939_frame_fields(message),
        )
    id_format: Literal["standard_11bit", "extended_29bit"] = "extended_29bit" if message.is_extended_frame else "standard_11bit"
    if message.is_fd:
        return CANFDFrame(
            name=message.name,
            length=message.length,
            can_id=message.frame_id,
            id_format=id_format,
            description=description,
            packed_pdus=packed,
            type="can_fd",
        )
    return CANFrame(
        name=message.name,
        length=message.length,
        can_id=message.frame_id,
        id_format=id_format,
        description=description,
        packed_pdus=packed,
        type="can",
    )


def _flync_version() -> str:
    """Return a valid semver for generated metadata (installed flync version when parseable)."""
    try:
        version = importlib.metadata.version("flync")
        # ensure it parses as semver; fall back otherwise
        BaseVersion(version=version)
        return version
    except Exception:
        return "0.0.0"


def _register_frame_participants(
    message: Message,
    bus_name: str,
    frame_senders: Dict[Tuple[str, int], set],
    frame_receivers: Dict[Tuple[str, int], set],
) -> None:
    """Record which nodes send/receive a message's frame."""
    for sender in message.senders or []:
        frame_senders[(bus_name, message.frame_id)].add(sender)
    for sig in message.signals or []:
        for receiver in sig.receivers or []:
            frame_receivers[(bus_name, message.frame_id)].add(receiver)


def _build_and_validate_message(
    message: Message,
    bus_name: str,
    baud_rate: int,
    fd_enabled: bool,
    fd_baud_rate: Optional[int],
    is_j1939: bool,
    report: ConverterReport = INACTIVE_REPORT,
) -> Tuple[StandardPDU | MultiplexedPDU, List[StandardPDU | MultiplexedPDU], CANFrame | CANFDFrame | J1939Frame]:
    """Build and channel-validate the PDU(s) and frame for a single DBC message.

    Replicates the channel-level frame- and multiplexed-placement checks for this
    message alone, so an unrepresentable layout (an overlapping J1939 Transport
    Protocol message, or a PDU that does not fit the J1939 frame) can be dropped
    for this message by the caller instead of failing the whole conversion.
    """
    pdu, extra = _build_pdu_for_message(message, bus_name, report)
    frame = _to_flync_frame(message, pdu.name, is_j1939=is_j1939, length=pdu.length)
    tmp_bus = CANBus(
        name=bus_name,
        baud_rate=cast(CANBaudRate, baud_rate),
        fd_enabled=fd_enabled,
        fd_baud_rate=fd_baud_rate,
        frames=[frame],
    )
    FLYNCChannelConfig(pdus=[pdu, *extra], can_buses=[tmp_bus])
    return pdu, extra, frame


def _decode_one_database(
    db,
    path,
    config: DbcConverterConfig,
    report: ConverterReport,
    pdus: List[StandardPDU | MultiplexedPDU],
    buses: List[CANBus],
    frame_senders: Dict[Tuple[str, int], set],
    frame_receivers: Dict[Tuple[str, int], set],
    declared_nodes: set,
    j1939_nodes: List[Tuple[str, int]],
) -> bool:
    """Decode a single DBC database into PDUs, a CANBus and participant metadata.

    Appends the resulting objects to the caller's shared accumulators and returns
    whether the database is a J1939 one.
    """
    bus_name = path.stem
    baud_rate = _nominal_baud_rate(db, config, bus_name, report)
    fd_enabled = any(m.is_fd for m in db.messages)
    is_j1939 = is_j1939_database(db)
    fd_baud_rate = _fd_baud_rate(db, config, bus_name, report) if fd_enabled else None

    declared_nodes.update(node.name for node in db.nodes)

    frames = []
    for message in db.messages:
        try:
            pdu, extra, frame = _build_and_validate_message(message, bus_name, baud_rate, fd_enabled, fd_baud_rate, is_j1939=is_j1939, report=report)
        except ValidationError as exc:
            logger.warning("Message '%s' of bus '%s' cannot be represented, skipped: %s", message.name, bus_name, exc)
            report.unsupported(
                f"{bus_name}.messages.{message.name}",
                reason=f"signal layout cannot be represented in the FLYNC model ({exc})",
            )
            continue
        pdus.append(pdu)
        pdus.extend(extra)
        frames.append(frame)
        if is_j1939:
            j1939_nodes.append((bus_name, _message_pgn(message)))
        else:
            _register_frame_participants(message, bus_name, frame_senders, frame_receivers)

    if is_j1939:
        report.skipped(
            f"{bus_name}.spn",
            reason="numeric J1939 SPNs are not present in the DBC and could not be assigned to signals",
        )

    buses.append(
        CANBus(
            name=bus_name,
            baud_rate=cast(CANBaudRate, baud_rate),
            fd_enabled=fd_enabled,
            fd_baud_rate=fd_baud_rate,
            frames=frames,
        )
    )
    return is_j1939


def decode_dbc_files(dbc_files, config: Optional[DbcConverterConfig] = None, report: ConverterReport = INACTIVE_REPORT) -> FLYNCModel:
    """Build and validate a FLYNCModel from loaded ``(Database, Path)`` tuples.

    DBC content FLYNC cannot represent (value tables of bytearray signals,
    value table entries outside the signal range, bit rates outside the
    allow-list, nodes taking part in no message) is logged and recorded in
    ``report``.

    Args:
        dbc_files: Output of :func:`load_dbc_files`.
        config: Optional DBC converter configuration (baud defaults).
        report: The converter's report.

    Returns:
        The validated FLYNCModel with one ``CANBus`` per DBC file and one
        synthesized ``ECU`` per node declared in ``BU_:``. A J1939 database
        (``VFrameFormat=J1939PG``) additionally collapses all of its frames
        onto a single synthesized J1939 node per bus.
    """
    config = config or DbcConverterConfig(config_path="")

    pdus: List[StandardPDU | MultiplexedPDU] = []
    buses: List[CANBus] = []
    frame_senders: Dict[Tuple[str, int], set] = defaultdict(set)
    frame_receivers: Dict[Tuple[str, int], set] = defaultdict(set)
    declared_nodes: set = set()
    j1939_nodes: List[Tuple[str, int]] = []
    any_j1939 = False

    for db, path in dbc_files:
        any_j1939 = (
            _decode_one_database(
                db,
                path,
                config,
                report,
                pdus,
                buses,
                frame_senders,
                frame_receivers,
                declared_nodes,
                j1939_nodes,
            )
            or any_j1939
        )

    ecus = _to_flync_ecus(frame_senders, frame_receivers, None if any_j1939 else declared_nodes, report)
    ecus.extend(_to_j1939_ecus(j1939_nodes, declared_nodes if any_j1939 else None))
    version = _flync_version()

    return FLYNCModel(
        metadata=SystemMetadata(
            type="system",
            author="dbc-converter",
            compatible_flync_version=BaseVersion(version=version),
            release=BaseVersion(version=version),
        ),
        communication=FLYNCCommunicationConfig(
            channels=FLYNCChannelConfig(
                pdus=pdus,
                can_buses=buses,
            )
        ),
        ecus=ecus,
    )


def _to_flync_ecus(
    frame_senders: Dict[Tuple[str, int], set],
    frame_receivers: Dict[Tuple[str, int], set],
    declared_nodes: Optional[set] = None,
    report: ConverterReport = INACTIVE_REPORT,
) -> List[ECU]:
    """Synthesize one ECU per DBC node with a single CAN controller and per-bus interfaces.

    The node set is the union of every node declared in the ``BU_:`` line and
    every participant observed on a frame, so a node that is declared but never
    participates in a message is still retained and not silently dropped.
    """
    membership: Dict[str, Dict[str, Dict[str, set]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(set)))
    for (bus, fid), nodes in frame_senders.items():
        for node in nodes:
            membership[node][bus]["send"].add(fid)
    for (bus, fid), nodes in frame_receivers.items():
        for node in nodes:
            membership[node][bus]["recv"].add(fid)

    node_names = set(membership)
    if declared_nodes:
        node_names |= declared_nodes

    version = _flync_version()
    ecus = []
    for node in sorted(node_names):
        can_interfaces = []
        for bus in sorted(membership[node].keys()):
            roles = membership[node][bus]
            can_interfaces.append(
                CANInterface(
                    name=bus,
                    bus_ref=bus,
                    sender_frames=[CANFrameRef(bus_ref=bus, frame_ref=fid) for fid in sorted(roles.get("send", set()))],
                    receiver_frames=[CANFrameRef(bus_ref=bus, frame_ref=fid) for fid in sorted(roles.get("recv", set()))],
                )
            )
        if not can_interfaces:
            logger.warning(
                "Node '%s' is declared in BU_: but participates in no message/interface; "
                "cannot represent it as a FLYNC ECU and it will be omitted.",
                node,
            )
            report.skipped(f"nodes.{node}", reason="declared in BU_ but sends and receives no message")
            continue
        controller = Controller(
            name="CONTROLLER",
            controller_metadata=EmbeddedMetadata(
                type="embedded",
                author="dbc-converter",
                compatible_flync_version=BaseVersion(version=version),
                target_system="DBC",
            ),
            can_interfaces=can_interfaces,
        )
        ecus.append(
            ECU(
                name=node,
                controllers=[controller],
                ecu_metadata=ECUMetadata(
                    type="ecu",
                    author="dbc-converter",
                    compatible_flync_version=BaseVersion(version=version),
                ),
            )
        )
    return ecus


def _j1939_name(name: str) -> int:
    """Derive a deterministic 64-bit J1939 NAME for a node/bus."""
    return int.from_bytes(hashlib.sha256(name.encode()).digest()[:8], "big")


def _j1939_ecu(name: str, version, interface: CANInterface) -> ECU:
    """Build a J1939 ECU wrapping a single CAN interface."""
    return _j1939_receiver_ecu(name, version, [interface])


def _to_j1939_ecus(bus_pgns: List[Tuple[str, int]], declared_nodes: Optional[set] = None) -> List[ECU]:
    """Synthesize J1939 ECUs preserving the node names declared in ``BU_:``.

    J1939 DBCs (e.g. Vector/CANoe ``VFrameFormat=J1939PG``) usually attribute every
    message to a single placeholder sender (``Vector__XXX``) rather than to named
    per-ECU source addresses, so no per-node SA or NAME is available. One
    synthesized sender node is created per bus that sends every PGN on it, and the
    nodes originally declared in ``BU_:`` are retained as receivers of those PGNs so
    the round-trip keeps the original network. The model requires a unique 64-bit
    ``j1939_name`` for every node that references J1939 frames, so a deterministic
    NAME is derived from each node name; no ``source_address`` is set (address
    claiming assigns SA at runtime).
    """
    by_bus: Dict[str, set] = defaultdict(set)
    for bus_name, pgn in bus_pgns:
        by_bus[bus_name].add(pgn)

    version = _flync_version()
    ecus = []
    sender_names: set = set()
    for bus_name in sorted(by_bus):
        # J1939 DBCs attribute every message to the Vector placeholder sender
        # (which is not itself declared in ``BU_:``); reuse that name so the
        # per-message sender round-trips.
        node_name = "Vector__XXX"
        interface = CANInterface(
            name=bus_name,
            bus_ref=bus_name,
            j1939_name=_j1939_name(node_name),
            j1939_sender_frames=[J1939FrameRef(bus_ref=bus_name, pgn=pgn) for pgn in sorted(by_bus[bus_name])],
        )
        ecus.append(_j1939_ecu(node_name, version, interface))
        sender_names.add(node_name)

    if declared_nodes:
        for node in sorted(declared_nodes):
            if node in sender_names:
                continue
            interfaces = [
                CANInterface(
                    name=bus_name,
                    bus_ref=bus_name,
                    j1939_name=_j1939_name(node),
                    j1939_receiver_frames=[J1939FrameRef(bus_ref=bus_name, pgn=pgn) for pgn in sorted(pgns)],
                )
                for bus_name, pgns in by_bus.items()
            ]
            if interfaces:
                ecus.append(_j1939_receiver_ecu(node, version, interfaces))
    return ecus


def _j1939_receiver_ecu(name: str, version, can_interfaces) -> ECU:
    """Build a J1939 ECU with the given CAN interfaces (receivers)."""
    return ECU(
        name=name,
        controllers=[
            Controller(
                name="CONTROLLER",
                controller_metadata=EmbeddedMetadata(
                    type="embedded",
                    author="dbc-converter",
                    compatible_flync_version=BaseVersion(version=version),
                    target_system="DBC",
                ),
                can_interfaces=can_interfaces,
            )
        ],
        ecu_metadata=ECUMetadata(
            type="ecu",
            author="dbc-converter",
            compatible_flync_version=BaseVersion(version=version),
        ),
    )
