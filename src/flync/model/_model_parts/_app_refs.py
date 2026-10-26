"""
Application reference helpers for the consistency validators of :class:`~flync.model.flync_model.FLYNCModel`.

The ``model_validator`` passes stay on the top-level model; the checks they delegate to — CAN / J1939 frame and PDU
references of apps and the ECU-internal IPC channels — live here.
"""

from __future__ import annotations

from collections.abc import Iterator

from flync.core.utils.exceptions import Category, err_major, warn
from flync.model._model_parts._j1939 import compute_j1939_pgn
from flync.model._model_parts._protocol import FLYNCModelProtocol
from flync.model.flync_4_app import App, AppCANFrameRef, AppCANPDURef, AppJ1939FrameRef, AppJ1939PDURef
from flync.model.flync_4_bus.can_bus import CANBus
from flync.model.flync_4_ecu import ECU, ComputeNode, Controller
from flync.model.flync_4_ecu.can_interface import CANInterface
from flync.model.flync_4_signal import J1939Frame
from flync.model.flync_4_signal.frame import CANFrameBase


def _iter_ecu_app_owners(ecu: ECU) -> Iterator[Controller | ComputeNode]:
    """Yield every controller of *ecu* and every compute node beneath it."""
    for controller in ecu.controllers:
        yield controller
        yield from controller.iter_subtree_compute_nodes()


def _iter_controller_apps(ecu: ECU) -> Iterator[tuple[Controller, list[App]]]:
    """Yield every controller of *ecu* that binds apps, together with those apps."""
    for owner in _iter_ecu_app_owners(ecu):
        if owner.app_bindings and isinstance(owner, Controller):
            yield owner, owner.app_bindings.apps


def _bus_has_pdu(bus: CANBus, pdu_ref: str, j1939: bool) -> bool:
    """Whether a J1939 (``j1939=True``) or CAN / CAN FD frame on *bus* packs the PDU named *pdu_ref*."""
    for frame in bus.frames or []:
        if isinstance(frame, J1939Frame) != j1939:
            continue
        if any(instance.pdu_ref == pdu_ref for instance in frame.packed_pdus):
            return True
    return False


def _bus_has_can_frame(bus: CANBus, ref: AppCANFrameRef) -> bool:
    """Whether *bus* carries the CAN / CAN FD frame identified by *ref*."""
    return any(isinstance(f, CANFrameBase) and f.can_id == ref.frame_ref and f.id_format == ref.id_format for f in bus.frames or [])


def _bus_has_pgn(bus: CANBus, ref: AppJ1939FrameRef) -> bool:
    """Whether *bus* carries a J1939 frame with the PGN of *ref*."""
    return any(isinstance(f, J1939Frame) and compute_j1939_pgn(f) == ref.pgn for f in bus.frames or [])


def _resolve_bus(app: App, buses: dict[str, CANBus], bus_ref: str) -> CANBus:
    bus = buses.get(bus_ref)
    if bus is None:
        raise err_major(
            "App '{app}' references CAN bus '{bus}' that is not defined in the system's channels.",
            app=app.name,
            bus=bus_ref,
            category=Category.REFERENCE,
            error_number="409",
        )
    return bus


def _check_can_frame_refs(app: App, buses: dict[str, CANBus]) -> None:
    for can_ref in app.can_frame_refs:
        bus = _resolve_bus(app, buses, can_ref.bus_ref)
        if not _bus_has_can_frame(bus, can_ref):
            raise err_major(
                "App '{app}' references CAN frame {frame_id} ({fmt}) that does not exist on bus '{bus}'.",
                app=app.name,
                frame_id=f"{can_ref.frame_ref:#x}",
                fmt=can_ref.id_format,
                bus=bus.name,
                category=Category.REFERENCE,
                error_number="416",
            )


def _check_j1939_frame_refs(app: App, buses: dict[str, CANBus]) -> None:
    for j1939_ref in app.j1939_frame_refs:
        bus = _resolve_bus(app, buses, j1939_ref.bus_ref)
        if not _bus_has_pgn(bus, j1939_ref):
            raise err_major(
                "App '{app}' references J1939 PGN {pgn} that does not exist on bus '{bus}'.",
                app=app.name,
                pgn=f"{j1939_ref.pgn:#x}",
                bus=bus.name,
                category=Category.REFERENCE,
                error_number="417",
            )


def _check_pdu_refs(app: App, buses: dict[str, CANBus], pdu_names: set[str]) -> None:
    for pdu_refs, is_j1939 in ((app.can_pdu_refs, False), (app.j1939_pdu_refs, True)):
        for pdu_ref in pdu_refs:
            bus = _resolve_bus(app, buses, pdu_ref.bus_ref)
            if pdu_ref.pdu_ref not in pdu_names or not _bus_has_pdu(bus, pdu_ref.pdu_ref, is_j1939):
                raise err_major(
                    "App '{app}' references PDU '{pdu}' that no {kind} frame on bus '{bus}' packs.",
                    app=app.name,
                    pdu=pdu_ref.pdu_ref,
                    kind="J1939" if is_j1939 else "CAN",
                    bus=bus.name,
                    category=Category.REFERENCE,
                    error_number="410",
                )


def validate_app_signal_refs(model: FLYNCModelProtocol) -> None:
    """Every CAN / J1939 frame and PDU reference of every app must resolve on the referenced CAN bus."""
    channels = model.communication.channels if model.communication else None
    buses = {bus.name: bus for bus in (channels.can_buses if channels else None) or []}
    pdu_names = {pdu.name for pdu in (channels.pdus if channels else None) or []}

    for app in model.apps or []:
        _check_can_frame_refs(app, buses)
        _check_j1939_frame_refs(app, buses)
        _check_pdu_refs(app, buses, pdu_names)


def _index_can_interfaces(owner: Controller) -> dict[str, list[CANInterface]]:
    """Group the CAN interfaces of *owner* by the bus they sit on."""
    interfaces: dict[str, list[CANInterface]] = {}
    for iface in owner.can_interfaces or []:
        interfaces.setdefault(iface.bus_ref, []).append(iface)
    return interfaces


def _warn_uncovered_can_frames(app: App, owner: Controller, interfaces: dict[str, list[CANInterface]]) -> None:
    for can_ref in app.can_frame_refs:
        attr = "sender_frames" if can_ref.direction == "sender" else "receiver_frames"
        covered = any(
            (f.frame_ref, f.id_format) == (can_ref.frame_ref, can_ref.id_format)
            for iface in interfaces.get(can_ref.bus_ref, [])
            for f in getattr(iface, attr)
        )
        if not covered:
            _warn_missing_interface(app, owner, f"CAN frame {can_ref.frame_ref:#x}", can_ref.bus_ref)


def _warn_uncovered_j1939_frames(app: App, owner: Controller, interfaces: dict[str, list[CANInterface]]) -> None:
    for j1939_ref in app.j1939_frame_refs:
        attr = "j1939_sender_frames" if j1939_ref.direction == "sender" else "j1939_receiver_frames"
        covered = any(f.pgn == j1939_ref.pgn for iface in interfaces.get(j1939_ref.bus_ref, []) for f in getattr(iface, attr))
        if not covered:
            _warn_missing_interface(app, owner, f"J1939 PGN {j1939_ref.pgn:#x}", j1939_ref.bus_ref)


def _warn_uncovered_pdus(app: App, owner: Controller, interfaces: dict[str, list[CANInterface]]) -> None:
    pdu_refs: list[AppCANPDURef | AppJ1939PDURef] = [*app.can_pdu_refs, *app.j1939_pdu_refs]
    for pdu_ref in pdu_refs:
        if pdu_ref.bus_ref not in interfaces:
            _warn_missing_interface(app, owner, f"PDU '{pdu_ref.pdu_ref}'", pdu_ref.bus_ref)


def warn_app_signal_refs_without_interface(model: FLYNCModelProtocol) -> None:
    """Warn when a controller binding an app has no CAN interface covering the app's frame references."""
    for ecu in model.ecus:
        for owner, apps in _iter_controller_apps(ecu):
            interfaces = _index_can_interfaces(owner)
            for app in apps:
                _warn_uncovered_can_frames(app, owner, interfaces)
                _warn_uncovered_j1939_frames(app, owner, interfaces)
                _warn_uncovered_pdus(app, owner, interfaces)


def _warn_missing_interface(app: App, owner: Controller, what: str, bus_ref: str) -> None:
    warn(
        f"App '{app.name}' bound to controller '{owner.name}' uses {what} on bus '{bus_ref}', "
        "but the controller has no CAN interface on that bus declaring it.",
        category=Category.CONSISTENCY,
        error_number="411",
    )


def _collect_ipc_roles(ecu: ECU) -> dict[str, set[str]]:
    """Map each IPC channel of *ecu* to the roles its bound apps take; reject references to undefined channels."""
    roles: dict[str, set[str]] = {channel.name: set() for channel in ecu.ipc_channels or []}
    for owner in _iter_ecu_app_owners(ecu):
        if not owner.app_bindings:
            continue
        for app in owner.app_bindings.apps:
            for ref in app.ipc_refs:
                if ref.channel_ref not in roles:
                    raise err_major(
                        "App '{app}' bound in ECU '{ecu}' references IPC channel '{channel}' that the ECU does not define.",
                        app=app.name,
                        ecu=ecu.name,
                        channel=ref.channel_ref,
                        category=Category.REFERENCE,
                        error_number="413",
                    )
                roles[ref.channel_ref].add(ref.role)
    return roles


def _warn_unpaired_ipc_channels(ecu: ECU, roles: dict[str, set[str]]) -> None:
    for name, seen in roles.items():
        can_produce = bool(seen & {"producer", "bidirectional"})
        can_consume = bool(seen & {"consumer", "bidirectional"})
        if can_produce and can_consume:
            continue
        missing = "producer" if not can_produce else "consumer"
        warn(
            f"IPC channel '{name}' of ECU '{ecu.name}' lacks a {missing} among its bound apps.",
            category=Category.CONSISTENCY,
            error_number="414",
        )


def validate_app_ipc_refs(model: FLYNCModelProtocol) -> None:
    """Every IPC reference of an app bound inside an ECU must name an IPC channel of that ECU."""
    for ecu in model.ecus:
        _warn_unpaired_ipc_channels(ecu, _collect_ipc_roles(ecu))
