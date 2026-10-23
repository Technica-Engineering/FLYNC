"""
J1939 helpers for the consistency validators of :class:`~flync.model.flync_model.FLYNCModel`.

The ``model_validator`` passes themselves stay on the top-level model (Pydantic only registers validators
declared on model classes, and their order matters); the computation and the per-bus / per-frame checks they
delegate to live here. Error ids raised here resolve to the ``GEN`` module code through this package's ``KEY``.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from typing import List, Tuple

from flync.core.utils.exceptions import Category, err_major
from flync.model._model_parts._protocol import FLYNCModelProtocol
from flync.model.flync_4_bus.can_bus import CANBus
from flync.model.flync_4_signal import (
    PDU,
    ContainerPDU,
    J1939Frame,
    MultiplexedPDU,
    SignalInstance,
    StandardPDU,
)
from flync.model.flync_4_signal.frame import CANFrameBase


def compute_j1939_pgn(frame: J1939Frame) -> int:
    """Return the 18-bit J1939 Parameter Group Number (PGN) of *frame*.

    The PGN is formed from the Extended Data Page (EDP), Data Page (DP), PDU Format (PF) and PDU Specific (PS)
    fields: ``(EDP << 17) | (DP << 16) | (PF << 8) | PS``. For PDU1 (``pdu_format`` < 240) the ``pdu_specific``
    byte is a Destination Address, not part of the PGN, so it contributes 0.
    """

    ps = frame.pdu_specific if frame.pdu_format >= 240 else 0
    return (frame.extended_data_page << 17) | (frame.data_page << 16) | (frame.pdu_format << 8) | ps


def j1939_buses(model: FLYNCModelProtocol) -> set[str]:
    """Return the set of CAN bus names attached through a J1939-capable ``CANInterface``.

    A CAN interface participates in J1939 when it declares a ``j1939_name`` or a source ``address``. Those buses
    must only carry ``J1939Frame`` frames (and, conversely, ``J1939Frame`` frames may only live on one of them).
    """
    buses: set[str] = set()
    for controller in model.get_all_controllers():
        for can_iface in controller.can_interfaces or []:
            if can_iface.is_j1939():
                buses.add(can_iface.bus_ref)
    return buses


def signal_spn_names(signals: Iterable[SignalInstance]) -> List[str]:
    """Return the name of each signal instance in *signals* that carries an SPN."""
    names: list[str] = []
    for si in signals:
        if si.signal.spn is not None:
            names.append(si.signal.name)
    return names


def pdu_own_spn_signal_names(pdu: PDU) -> List[Tuple[str, str]]:
    """Return ``(pdu_name, signal_name)`` for the SPN-bearing signals declared directly by *pdu*."""
    name = pdu.name
    found: list[Tuple[str, str]] = []
    if isinstance(pdu, StandardPDU):
        found.extend((name, signal_name) for signal_name in signal_spn_names(pdu.signals))
        for sgi in pdu.signal_groups:
            found.extend((name, signal_name) for signal_name in signal_spn_names(sgi.signal_group.signals))
    elif isinstance(pdu, MultiplexedPDU):
        selector = pdu.selector_signal.signal
        if selector.spn is not None:
            found.append((name, selector.name))
    return found


def enqueue_pdu_children(stack: list[PDU], pdu_registry: Mapping[str, PDU], pdu: PDU) -> None:
    """Push the child PDUs referenced by *pdu* (located in *pdu_registry*) onto *stack*."""
    if isinstance(pdu, MultiplexedPDU):
        refs = [inst.pdu_ref for inst in pdu.static_group or []]
        refs.extend(group.pdu.pdu_ref for group in pdu.mux_groups)
    elif isinstance(pdu, ContainerPDU):
        refs = [inst.pdu_ref for inst in pdu.contained_pdus]
    else:
        refs = []
    for ref in refs:
        child = pdu_registry.get(ref)
        if child is not None:
            stack.append(child)


def iter_pdu_spn_signal_names(pdu: PDU, pdu_registry: Mapping[str, PDU]) -> Iterator[tuple[str, str]]:
    """Yield ``(pdu_name, signal_name)`` for every SPN-bearing signal instance in a PDU subtree."""
    seen_pdus: set[int] = set()
    stack = [pdu]
    while stack:
        current = stack.pop()
        if id(current) in seen_pdus:
            continue
        seen_pdus.add(id(current))
        yield from pdu_own_spn_signal_names(current)
        enqueue_pdu_children(stack, pdu_registry, current)


def check_can_frame_spn(frame: CANFrameBase, pdu_registry: Mapping[str, PDU], checked: set[str]) -> None:
    """Raise ``err_major`` if a CAN (non-J1939) *frame* packs a PDU that carries an SPN."""
    for inst in frame.packed_pdus:
        if inst.pdu_ref not in pdu_registry or inst.pdu_ref in checked:
            continue
        checked.add(inst.pdu_ref)
        pdu = pdu_registry[inst.pdu_ref]
        offenders = list(iter_pdu_spn_signal_names(pdu, pdu_registry))
        if offenders:
            names = ", ".join(f"{pdu}.{signal}" for pdu, signal in offenders)
            raise err_major(
                "CAN PDU '{pdu}' must not carry SPN (SPN is only allowed on J1939 PDUs): {names}.",
                pdu=inst.pdu_ref,
                names=names,
                category=Category.CONSISTENCY,
                error_number="367",
            )


def check_j1939_bus_pgn_uniqueness(bus: CANBus) -> None:
    """Raise ``err_major`` if *bus* carries two J1939 frames sharing the same PGN."""
    seen: dict[int, str] = {}
    duplicate_frames: list[str] = []
    for frame in bus.frames or []:
        if not isinstance(frame, J1939Frame):
            continue
        pgn = compute_j1939_pgn(frame)
        if pgn in seen:
            duplicate_frames.append(frame.name)
        else:
            seen[pgn] = frame.name
    if duplicate_frames:
        raise err_major(
            "CANBus '{bus}' carries J1939 frame(s) with a duplicated PGN {pgn}: {frames}. Each J1939 frame on a bus must have a unique PGN.",
            bus=bus.name,
            pgn=pgn,
            frames=", ".join(duplicate_frames),
            category=Category.UNIQUENESS,
            error_number="346",
        )
