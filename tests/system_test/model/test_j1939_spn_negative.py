"""Workspace-level J1939 / CAN rules.

* SPN is only allowed on J1939 PDUs (``FLYNC-GEN-MAJ-CONS-367``): a PDU packed by a CAN frame must never carry SPN.
* A bus carrying J1939 frames must be attached to a J1939-capable CANInterface (``FLYNC-GEN-MAJ-CONS-368``).
* A J1939 bus may only carry J1939 frames (``FLYNC-GEN-MAJ-CONS-369``).

A plain (SPN-free) PDU may be shared between a J1939 frame and a CAN frame; only SPN-bearing PDUs are restricted to J1939.
"""

import pytest
from pydantic import ValidationError

from flync.model.flync_4_bus.can_bus import CANBus
from flync.model.flync_4_communication.flync_channels import FLYNCChannelConfig
from flync.model.flync_4_communication.flync_communication import FLYNCCommunicationConfig
from flync.model.flync_4_ecu.can_interface import CANInterface
from flync.model.flync_4_ecu.controller import Controller
from flync.model.flync_4_ecu.ecu import ECU
from flync.model.flync_4_ecu.internal_topology import InternalTopology
from flync.model.flync_4_metadata.metadata import BaseVersion, ECUMetadata, EmbeddedMetadata, SystemMetadata
from flync.model.flync_4_signal.frame import CANFrame, J1939Frame
from flync.model.flync_4_signal.pdu import PDUInstance, StandardPDU
from flync.model.flync_4_signal.signal import Signal, SignalDataType, SignalInstance
from flync.model.flync_4_topology import EthernetTopology, FLYNCTopology
from flync.model.flync_model import FLYNCModel
from tests.error_assertions import assert_single_error

FLYNC_VERSION = "0.13.0"


def _make_version() -> BaseVersion:
    return BaseVersion(version=FLYNC_VERSION)


def _make_pdu(name: str, spn: int | None) -> StandardPDU:
    """Return a StandardPDU packing a single 8-bit signal, optionally SPN-bearing."""
    si = SignalInstance(signal=Signal(name=f"{name}_Sig", bit_length=8, data_type=SignalDataType.UINT8), bit_position=0)
    if spn is not None:
        si.signal.spn = spn
    return StandardPDU(name=name, length=1, signals=[si])


def _make_j1939_frame(name: str, pdu_name: str) -> J1939Frame:
    return J1939Frame(
        name=name,
        length=8,
        priority=6,
        pdu_format=0xF0,
        pdu_specific=0x01,
        data_page=0,
        extended_data_page=0,
        destination_type="global",
        packed_pdus=[PDUInstance(pdu_ref=pdu_name)],
    )


def _j1939_iface(bus_ref: str) -> CANInterface:
    """Return a CAN interface that participates in J1939 on *bus_ref*."""
    return CANInterface(name=f"J1939If_{bus_ref}", bus_ref=bus_ref, j1939_name=1, source_address=0)


def _wrap(pdus: list, buses: list, can_interfaces: list | None = None) -> FLYNCModel:
    """Bundle PDUs, buses and interfaces into the smallest valid workspace."""
    can_interfaces = can_interfaces if can_interfaces is not None else []
    controller = Controller(
        name="CTRL1",
        controller_metadata=EmbeddedMetadata(type="embedded", author="TestTeam", target_system="Device1", compatible_flync_version=_make_version()),
        can_interfaces=can_interfaces,
    )
    ecu = ECU(
        name="ECU1",
        controllers=[controller],
        topology=InternalTopology(),
        ecu_metadata=ECUMetadata(type="ecu", author="TestTeam", compatible_flync_version=_make_version()),
    )
    return FLYNCModel(
        ecus=[ecu],
        topology=FLYNCTopology(system_topology=EthernetTopology(connections=[])),
        metadata=SystemMetadata(type="system", release=_make_version(), author="TestTeam", compatible_flync_version=_make_version()),
        communication=FLYNCCommunicationConfig(channels=FLYNCChannelConfig(pdus=pdus, can_buses=buses)),
    )


def test_positive_j1939_pdu_with_spn_on_j1939_bus():
    """A J1939Frame packing an SPN-bearing PDU on a J1939-capable CANInterface bus is accepted."""
    pdu = _make_pdu("PDU_EBC1", spn=521)
    bus = CANBus(name="J1939BusCAN", baud_rate=250000, frames=[_make_j1939_frame("Frame_EBC1", pdu.name)])
    model = _wrap(pdus=[pdu], buses=[bus], can_interfaces=[_j1939_iface("J1939BusCAN")])
    assert model is not None


def test_positive_j1939_nm_pdu_without_spn_allowed():
    """A J1939 NM PDU (address claiming) with no SPN is accepted: SPN is not required on J1939 PDUs."""
    pdu = _make_pdu("PDU_AddressClaim", spn=None)
    bus = CANBus(name="J1939BusCAN", baud_rate=250000, frames=[_make_j1939_frame("Frame_AddressClaim", pdu.name)])
    model = _wrap(pdus=[pdu], buses=[bus], can_interfaces=[_j1939_iface("J1939BusCAN")])
    assert model is not None


def test_positive_can_pdu_without_spn_on_can_bus():
    """A CAN frame packing a plain PDU on a non-J1939-referenced bus is accepted."""
    pdu = _make_pdu("PDU_EngineStatus", spn=None)
    bus = CANBus(
        name="PowertrainCAN",
        baud_rate=500000,
        frames=[
            CANFrame(name="Frame_EngineStatus", length=8, can_id=0x100, id_format="standard_11bit", packed_pdus=[PDUInstance(pdu_ref=pdu.name)])
        ],
    )
    model = _wrap(pdus=[pdu], buses=[bus], can_interfaces=[CANInterface(name="CAN_IF_1", bus_ref="PowertrainCAN")])
    assert model is not None


def test_negative_can_pdu_with_spn_rejected():
    """A PDU carrying SPN that is packed by a CAN (non-J1939) frame is rejected: FLYNC-GEN-MAJ-CONS-367."""
    pdu = _make_pdu("PDU_Bad", spn=521)
    bus = CANBus(
        name="PowertrainCAN",
        baud_rate=500000,
        frames=[CANFrame(name="Frame_Bad", length=8, can_id=0x100, id_format="standard_11bit", packed_pdus=[PDUInstance(pdu_ref=pdu.name)])],
    )
    can_interfaces = [CANInterface(name="CAN_IF_1", bus_ref="PowertrainCAN")]
    with pytest.raises(ValidationError) as exc_info:
        _wrap(pdus=[pdu], buses=[bus], can_interfaces=can_interfaces)
    assert_single_error(exc_info, "FLYNC-GEN-MAJ-CONS-367", "must not carry SPN (SPN is only allowed on J1939 PDUs)")


def test_positive_plain_pdu_shared_between_j1939_and_can():
    """An SPN-free PDU packed by both a J1939 frame and a CAN frame is accepted."""
    pdu = _make_pdu("PDU_EngineStatus", spn=None)
    j1939_bus = CANBus(name="J1939BusCAN", baud_rate=250000, frames=[_make_j1939_frame("Frame_EBC1", pdu.name)])
    can_bus = CANBus(
        name="PowertrainCAN",
        baud_rate=500000,
        frames=[
            CANFrame(name="Frame_EngineStatus", length=8, can_id=0x100, id_format="standard_11bit", packed_pdus=[PDUInstance(pdu_ref=pdu.name)])
        ],
    )
    model = _wrap(pdus=[pdu], buses=[j1939_bus, can_bus], can_interfaces=[_j1939_iface("J1939BusCAN")])
    assert model is not None


def test_negative_j1939_frame_on_non_j1939_bus_rejected():
    """A J1939Frame on a bus NOT attached to a J1939-capable CANInterface is rejected: FLYNC-GEN-MAJ-CONS-368."""
    pdu = _make_pdu("PDU_EBC1", spn=521)
    bus = CANBus(name="J1939BusCAN", baud_rate=250000, frames=[_make_j1939_frame("Frame_EBC1", pdu.name)])
    other = CANBus(name="OtherCAN", baud_rate=500000)
    can_interfaces = [_j1939_iface("OtherCAN")]
    with pytest.raises(ValidationError) as exc_info:
        _wrap(pdus=[pdu], buses=[bus, other], can_interfaces=can_interfaces)
    assert_single_error(exc_info, "FLYNC-GEN-MAJ-CONS-368", "not attached through any J1939-capable CAN interface, but it carries J1939 frame")


def test_negative_can_frame_on_j1939_referenced_bus_rejected():
    """A regular CAN frame on a J1939 bus is rejected: FLYNC-GEN-MAJ-CONS-369."""
    pdu = _make_pdu("PDU_Plain", spn=None)
    j1939_pdu = _make_pdu("PDU_EBC1", spn=521)
    bus = CANBus(
        name="J1939BusCAN",
        baud_rate=250000,
        frames=[
            _make_j1939_frame("Frame_EBC1", j1939_pdu.name),
            CANFrame(name="Frame_Plain", length=8, can_id=0x200, id_format="standard_11bit", packed_pdus=[PDUInstance(pdu_ref=pdu.name)]),
        ],
    )
    can_interfaces = [_j1939_iface("J1939BusCAN")]
    with pytest.raises(ValidationError) as exc_info:
        _wrap(pdus=[pdu, j1939_pdu], buses=[bus], can_interfaces=can_interfaces)
    assert_single_error(exc_info, "FLYNC-GEN-MAJ-CONS-369", "attached through a J1939-capable CAN interface but carries non-J1939 frame(s)")


def test_negative_j1939_interface_unresolved_bus_ref_rejected():
    """A J1939-capable CANInterface whose bus_ref names no declared CAN bus is rejected: FLYNC-CMN-MAJ-REF-215.

    The generic CAN bus_ref check already resolves every CAN interface (J1939 ones included) against the CAN
    catalog, so an unresolvable bus_ref is reported there rather than by the J1939-specific pass.
    """
    bus = CANBus(
        name="RealCAN",
        baud_rate=500000,
        frames=[
            CANFrame(
                name="Frame_Plain",
                length=8,
                can_id=0x100,
                id_format="standard_11bit",
                packed_pdus=[PDUInstance(pdu_ref=_make_pdu("PDU_Plain", None).name)],
            )
        ],
    )
    pdus = [_make_pdu("PDU_Plain", None)]
    can_interfaces = [_j1939_iface("GhostBus")]
    with pytest.raises(ValidationError) as exc_info:
        _wrap(pdus=pdus, buses=[bus], can_interfaces=can_interfaces)
    assert_single_error(
        exc_info, "FLYNC-CMN-MAJ-REF-215", "bus_ref 'GhostBus' does not name any bus declared under communication.channels.can_buses"
    )


def test_negative_j1939_duplicate_pgn_rejected():
    """Two J1939 frames on the same bus with the same PGN are rejected: FLYNC-GEN-MAJ-UNIQ-346."""
    pdu = _make_pdu("PDU_EBC1", spn=521)
    bus = CANBus(
        name="J1939BusCAN",
        baud_rate=250000,
        frames=[_make_j1939_frame("Frame_A", pdu.name), _make_j1939_frame("Frame_B", pdu.name)],
    )
    can_interfaces = [_j1939_iface("J1939BusCAN")]
    with pytest.raises(ValidationError) as exc_info:
        _wrap(pdus=[pdu], buses=[bus], can_interfaces=can_interfaces)
    assert_single_error(exc_info, "FLYNC-GEN-MAJ-UNIQ-346", "duplicated PGN")


def test_positive_j1939_frames_same_pgn_different_buses_allowed():
    """The same PGN may appear once per bus; a second bus may reuse it."""
    pdu = _make_pdu("PDU_EBC1", spn=521)
    bus_a = CANBus(name="J1939BusA", baud_rate=250000, frames=[_make_j1939_frame("Frame_A", pdu.name)])
    bus_b = CANBus(name="J1939BusB", baud_rate=250000, frames=[_make_j1939_frame("Frame_B", pdu.name)])
    model = _wrap(pdus=[pdu], buses=[bus_a, bus_b], can_interfaces=[_j1939_iface("J1939BusA"), _j1939_iface("J1939BusB")])
    assert model is not None


def test_positive_j1939_sender_receiver_frame_refs_resolve():
    """A J1939 interface referencing a frame PGN that exists on its bus is accepted."""
    from flync.model.flync_4_ecu.can_interface import J1939FrameRef

    pdu = _make_pdu("PDU_EBC1", spn=521)
    bus = CANBus(name="J1939BusCAN", baud_rate=250000, frames=[_make_j1939_frame("Frame_EBC1", pdu.name)])
    iface = CANInterface(
        name="J1939Node",
        bus_ref="J1939BusCAN",
        j1939_name=1,
        source_address=0,
        j1939_sender_frames=[J1939FrameRef(bus_ref="J1939BusCAN", pgn=0xF001)],
    )
    model = _wrap(pdus=[pdu], buses=[bus], can_interfaces=[iface])
    assert model is not None


def test_negative_j1939_unresolved_pgn_rejected():
    """A J1939 sender frame referencing a PGN that names no frame on the bus is rejected: FLYNC-CMN-MAJ-REF-372."""
    from flync.model.flync_4_ecu.can_interface import J1939FrameRef

    pdu = _make_pdu("PDU_EBC1", spn=521)
    bus = CANBus(name="J1939BusCAN", baud_rate=250000, frames=[_make_j1939_frame("Frame_EBC1", pdu.name)])
    iface = CANInterface(
        name="J1939Node",
        bus_ref="J1939BusCAN",
        j1939_name=1,
        source_address=0,
        j1939_sender_frames=[J1939FrameRef(bus_ref="J1939BusCAN", pgn=0x1234)],
    )
    with pytest.raises(ValidationError) as exc_info:
        _wrap(pdus=[pdu], buses=[bus], can_interfaces=[iface])
    assert_single_error(exc_info, "FLYNC-CMN-MAJ-REF-372", "pgn 4660 does not name any J1939 frame")


def test_negative_j1939_duplicate_sa_same_bus_rejected():
    """Two J1939 nodes on the same bus claiming the same source address are rejected: FLYNC-GEN-MAJ-UNIQ-373."""
    bus = CANBus(name="J1939BusCAN", baud_rate=250000)
    dupe_a = CANInterface(name="NodeA", bus_ref="J1939BusCAN", j1939_name=1, source_address=0)
    dupe_b = CANInterface(name="NodeB", bus_ref="J1939BusCAN", j1939_name=2, source_address=0)
    with pytest.raises(ValidationError) as exc_info:
        _wrap(pdus=[], buses=[bus], can_interfaces=[dupe_a, dupe_b])
    assert_single_error(exc_info, "FLYNC-GEN-MAJ-UNIQ-373", "more than one J1939 node claiming source address (SA) 0")


def test_positive_j1939_same_sa_different_buses_allowed():
    """The same source address may be reused on a different bus."""
    bus_a = CANBus(name="J1939BusA", baud_rate=250000)
    bus_b = CANBus(name="J1939BusB", baud_rate=250000)
    model = _wrap(pdus=[], buses=[bus_a, bus_b], can_interfaces=[_j1939_iface("J1939BusA"), _j1939_iface("J1939BusB")])
    assert model is not None


def test_negative_plain_can_node_on_j1939_bus_rejected():
    """A plain CAN interface attached to a J1939 bus (one carrying J1939 frames) is rejected: FLYNC-GEN-MAJ-CONS-361."""
    pdu = _make_pdu("PDU_EBC1", spn=521)
    bus = CANBus(name="J1939BusCAN", baud_rate=250000, frames=[_make_j1939_frame("Frame_EBC1", pdu.name)])
    can_interfaces = [
        _j1939_iface("J1939BusCAN"),
        CANInterface(name="Plain_Node", bus_ref="J1939BusCAN"),
    ]
    with pytest.raises(ValidationError) as exc_info:
        _wrap(pdus=[pdu], buses=[bus], can_interfaces=can_interfaces)
    assert_single_error(exc_info, "FLYNC-GEN-MAJ-CONS-361", "node(s) Plain_Node attached to them are missing j1939_name")


def test_positive_j1939_bus_all_nodes_identify_node():
    """A J1939 bus whose every node carries j1939_name and source_address is accepted."""
    pdu = _make_pdu("PDU_EBC1", spn=521)
    bus = CANBus(name="J1939BusCAN", baud_rate=250000, frames=[_make_j1939_frame("Frame_EBC1", pdu.name)])
    model = _wrap(
        pdus=[pdu],
        buses=[bus],
        can_interfaces=[
            CANInterface(name="NodeA", bus_ref="J1939BusCAN", j1939_name=1, source_address=0),
            CANInterface(name="NodeB", bus_ref="J1939BusCAN", j1939_name=2, source_address=33),
        ],
    )
    assert model is not None
