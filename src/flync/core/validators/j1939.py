"""
J1939 SPN validation: a PDU packed by a CAN (non-J1939) frame must never carry an SPN.

Used by :class:`~flync.model.flync_4_communication.FLYNCChannelConfig`, which owns both the CAN buses and the PDU registry.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from typing import List, Tuple

from flync.core.utils.exceptions import Category, err_major
from flync.model.flync_4_signal import (
    PDU,
    ContainerPDU,
    MultiplexedPDU,
    SignalInstance,
    StandardPDU,
)
from flync.model.flync_4_signal.frame import CANFrameBase


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
