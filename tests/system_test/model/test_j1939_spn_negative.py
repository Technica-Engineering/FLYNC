"""Workspace-level J1939 / CAN rules.

* SPN is only allowed on J1939 PDUs (``FLYNC-GEN-MAJ-CONS-367``): a PDU packed by a CAN frame must never carry SPN.
* A bus carrying J1939 frames must be attached to a J1939-capable CANInterface (``FLYNC-GEN-MAJ-CONS-368``).
* A J1939 bus may also carry plain CAN frames alongside its J1939 frames.

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


def _make_j1939_frame(name: str, pdu_name: str, pdu_specific: int = 0x01) -> J1939Frame:
    return J1939Frame(
        name=name,
        length=8,
        priority=6,
        pdu_format=0xF0,
        pdu_specific=pdu_specific,
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


def test_positive_j1939_bus_may_carry_can_frames():
    """A J1939 bus (one carrying J1939 frames) may also carry plain CAN frames alongside them."""
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
    model = _wrap(pdus=[pdu, j1939_pdu], buses=[bus], can_interfaces=[_j1939_iface("J1939BusCAN")])
    assert model is not None


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


def test_positive_j1939_frames_same_pgn_same_bus_different_names_allowed():
    """Two J1939 frames sharing a PGN on the same bus are allowed as long as their names differ.

    J1939 messages are referenced by frame name, so several messages that share a Parameter Group Number
    (e.g. different source addresses, or a different destination for PDU1) can coexist on one bus.
    """
    pdu_a = _make_pdu("PDU_A", spn=521)
    pdu_b = _make_pdu("PDU_B", spn=522)
    bus = CANBus(
        name="J1939BusCAN",
        baud_rate=250000,
        frames=[
            _make_j1939_frame("Frame_A", pdu_a.name),
            _make_j1939_frame("Frame_B", pdu_b.name),
        ],
    )
    model = _wrap(pdus=[pdu_a, pdu_b], buses=[bus], can_interfaces=[_j1939_iface("J1939BusCAN")])
    assert model is not None


def test_positive_j1939_frames_same_pgn_different_buses_allowed():
    """The same PGN may appear once per bus; a second bus may reuse it."""
    pdu = _make_pdu("PDU_EBC1", spn=521)
    bus_a = CANBus(name="J1939BusA", baud_rate=250000, frames=[_make_j1939_frame("Frame_A", pdu.name)])
    bus_b = CANBus(name="J1939BusB", baud_rate=250000, frames=[_make_j1939_frame("Frame_B", pdu.name)])
    model = _wrap(pdus=[pdu], buses=[bus_a, bus_b], can_interfaces=[_j1939_iface("J1939BusA"), _j1939_iface("J1939BusB")])
    assert model is not None


def test_positive_j1939_sender_receiver_frame_refs_resolve():
    """A J1939 interface referencing a frame name that exists on its bus is accepted."""
    from flync.model.flync_4_ecu.can_interface import J1939FrameRef

    pdu = _make_pdu("PDU_EBC1", spn=521)
    bus = CANBus(name="J1939BusCAN", baud_rate=250000, frames=[_make_j1939_frame("Frame_EBC1", pdu.name)])
    iface = CANInterface(
        name="J1939Node",
        bus_ref="J1939BusCAN",
        j1939_name=1,
        source_address=0,
        j1939_sender_frames=[J1939FrameRef(frame_ref="Frame_EBC1")],
    )
    model = _wrap(pdus=[pdu], buses=[bus], can_interfaces=[iface])
    assert model is not None


def test_positive_j1939_sender_frame_ref_by_can_id_resolves():
    """A J1939 interface referencing a frame by its full on-bus CAN id (frame base OR node SA) is accepted."""
    from flync.model.flync_4_ecu.can_interface import J1939FrameRef

    pdu = _make_pdu("PDU_EBC1", spn=521)
    bus = CANBus(name="J1939BusCAN", baud_rate=250000, frames=[_make_j1939_frame("Frame_EBC1", pdu.name)])
    # priority=6, PF=0xF0, PS=0x01 -> base can_id 0x18F00100; node SA=0x20 -> on-bus id 0x18F00120
    iface = CANInterface(
        name="J1939Node",
        bus_ref="J1939BusCAN",
        j1939_name=1,
        source_address=0x20,
        j1939_sender_frames=[J1939FrameRef(can_id=0x18F00120)],
    )
    model = _wrap(pdus=[pdu], buses=[bus], can_interfaces=[iface])
    assert model is not None


def test_negative_j1939_unresolved_can_id_ref_rejected():
    """A J1939 sender frame referencing an on-bus CAN id that matches no frame on the bus is rejected: FLYNC-CMN-MAJ-REF-424."""
    from flync.model.flync_4_ecu.can_interface import J1939FrameRef

    pdu = _make_pdu("PDU_EBC1", spn=521)
    bus = CANBus(name="J1939BusCAN", baud_rate=250000, frames=[_make_j1939_frame("Frame_EBC1", pdu.name)])
    iface = CANInterface(
        name="J1939Node",
        bus_ref="J1939BusCAN",
        j1939_name=1,
        source_address=0x20,
        j1939_sender_frames=[J1939FrameRef(can_id=0x18F00200)],
    )
    with pytest.raises(ValidationError) as exc_info:
        _wrap(pdus=[pdu], buses=[bus], can_interfaces=[iface])
    assert_single_error(exc_info, "FLYNC-CMN-MAJ-REF-424", "does not resolve to any J1939 frame")


def test_negative_j1939_unresolved_frame_ref_rejected():
    """A J1939 sender frame referencing a name that matches no frame on the bus is rejected: FLYNC-CMN-MAJ-REF-424."""
    from flync.model.flync_4_ecu.can_interface import J1939FrameRef

    pdu = _make_pdu("PDU_EBC1", spn=521)
    bus = CANBus(name="J1939BusCAN", baud_rate=250000, frames=[_make_j1939_frame("Frame_EBC1", pdu.name)])
    iface = CANInterface(
        name="J1939Node",
        bus_ref="J1939BusCAN",
        j1939_name=1,
        source_address=0,
        j1939_sender_frames=[J1939FrameRef(frame_ref="GhostFrame")],
    )
    with pytest.raises(ValidationError) as exc_info:
        _wrap(pdus=[pdu], buses=[bus], can_interfaces=[iface])
    assert_single_error(exc_info, "FLYNC-CMN-MAJ-REF-424", "frame reference GhostFrame does not resolve to any J1939 frame")


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


def test_positive_j1939_effective_can_id_distinct_per_node():
    """The same frame sent by two nodes with different SAs yields distinct on-bus ids, so it is accepted."""
    from flync.model.flync_4_ecu.can_interface import J1939FrameRef

    pdu = _make_pdu("PDU_EBC1", spn=521)
    bus = CANBus(name="J1939BusCAN", baud_rate=250000, frames=[_make_j1939_frame("Frame_EBC1", pdu.name)])
    # base can_id 0x18F00100; NodeA SA=0x10 -> 0x18F00110, NodeB SA=0x20 -> 0x18F00120 (distinct)
    sender = J1939FrameRef(frame_ref="Frame_EBC1")
    model = _wrap(
        pdus=[pdu],
        buses=[bus],
        can_interfaces=[
            CANInterface(name="NodeA", bus_ref="J1939BusCAN", j1939_name=1, source_address=0x10, j1939_sender_frames=[sender]),
            CANInterface(name="NodeB", bus_ref="J1939BusCAN", j1939_name=2, source_address=0x20, j1939_sender_frames=[sender]),
        ],
    )
    assert model is not None


def test_positive_j1939_same_node_distinct_frames_distinct_ids_allowed():
    """One node sending two frames whose base ids differ keeps distinct on-bus ids after OR-ing its SA."""
    from flync.model.flync_4_ecu.can_interface import J1939FrameRef

    pdu_a = _make_pdu("PDU_A", spn=521)
    pdu_b = _make_pdu("PDU_B", spn=522)
    bus = CANBus(
        name="J1939BusCAN",
        baud_rate=250000,
        frames=[_make_j1939_frame("Frame_A", pdu_a.name, pdu_specific=0x10), _make_j1939_frame("Frame_B", pdu_b.name, pdu_specific=0x11)],
    )
    iface = CANInterface(
        name="NodeA",
        bus_ref="J1939BusCAN",
        j1939_name=1,
        source_address=0x20,
        j1939_sender_frames=[
            J1939FrameRef(frame_ref="Frame_A"),
            J1939FrameRef(frame_ref="Frame_B"),
        ],
    )
    model = _wrap(pdus=[pdu_a, pdu_b], buses=[bus], can_interfaces=[iface])
    assert model is not None


def test_negative_j1939_duplicate_effective_can_id_same_bus_rejected():
    """Two frames on a shared bus collapsing to the same on-bus id after OR-ing the node SA are rejected.

    A node with SA=0x20 sends two frames whose derived base ids are both 0x18F00100; once OR'd with the node's
    SA each becomes 0x18F00120, so two messages would claim the same wire identifier. The bus-level 054 rule
    cannot see the SA (it compares the bare frames, which are distinct); this duplicate is caught here at the
    reference level instead: FLYNC-CMN-MAJ-UNIQ-427.
    """
    from flync.model.flync_4_ecu.can_interface import J1939FrameRef

    pdu_a = _make_pdu("PDU_A", spn=521)
    pdu_b = _make_pdu("PDU_B", spn=522)
    bus = CANBus(
        name="J1939BusCAN",
        baud_rate=250000,
        frames=[_make_j1939_frame("Frame_A", pdu_a.name), _make_j1939_frame("Frame_B", pdu_b.name)],
    )
    iface = CANInterface(
        name="NodeA",
        bus_ref="J1939BusCAN",
        j1939_name=1,
        source_address=0x20,
        j1939_sender_frames=[
            J1939FrameRef(frame_ref="Frame_A"),
            J1939FrameRef(frame_ref="Frame_B"),
        ],
    )
    with pytest.raises(ValidationError) as exc_info:
        _wrap(pdus=[pdu_a, pdu_b], buses=[bus], can_interfaces=[iface])
    assert_single_error(exc_info, "FLYNC-CMN-MAJ-UNIQ-427", "yields CAN identifier 0x18f00120 on bus 'J1939BusCAN', already used by")


def test_positive_j1939_emitter_and_receiver_same_frame_allowed():
    """An emitter and its receivers referencing the same frame share its on-bus id legitimately (no 378)."""
    from flync.model.flync_4_ecu.can_interface import J1939FrameRef

    pdu = _make_pdu("PDU_EBC1", spn=521)
    bus = CANBus(name="J1939BusCAN", baud_rate=250000, frames=[_make_j1939_frame("Frame_EBC1", pdu.name)])
    sender = CANInterface(
        name="J1939Sender",
        bus_ref="J1939BusCAN",
        j1939_name=1,
        source_address=0x20,
        j1939_sender_frames=[J1939FrameRef(frame_ref="Frame_EBC1")],
    )
    receiver = CANInterface(
        name="J1939Receiver",
        bus_ref="J1939BusCAN",
        j1939_name=2,
        j1939_receiver_frames=[J1939FrameRef(frame_ref="Frame_EBC1")],
    )
    model = _wrap(pdus=[pdu], buses=[bus], can_interfaces=[sender, receiver])
    assert model is not None


def test_positive_j1939_multi_emitter_distinct_sas_allowed():
    """Two nodes emitting the same PGN base with distinct SAs keep distinct on-bus ids (gateway/multi-node)."""
    from flync.model.flync_4_ecu.can_interface import J1939FrameRef

    pdu = _make_pdu("PDU_EBC1", spn=521)
    bus = CANBus(name="J1939BusCAN", baud_rate=250000, frames=[_make_j1939_frame("Frame_EBC1", pdu.name)])
    node_a = CANInterface(
        name="NodeA",
        bus_ref="J1939BusCAN",
        j1939_name=1,
        source_address=0x20,
        j1939_sender_frames=[J1939FrameRef(frame_ref="Frame_EBC1")],
    )
    node_b = CANInterface(
        name="NodeB",
        bus_ref="J1939BusCAN",
        j1939_name=2,
        source_address=0x21,
        j1939_sender_frames=[J1939FrameRef(frame_ref="Frame_EBC1")],
    )
    model = _wrap(pdus=[pdu], buses=[bus], can_interfaces=[node_a, node_b])
    assert model is not None


def test_positive_j1939_receiver_frame_by_name_with_can_id_allowed():
    """A receiver frame reference by name, optionally with the emitter's on-bus CAN id, is accepted."""
    from flync.model.flync_4_ecu.can_interface import J1939FrameRef

    pdu = _make_pdu("PDU_EBC1", spn=521)
    bus = CANBus(name="J1939BusCAN", baud_rate=250000, frames=[_make_j1939_frame("Frame_EBC1", pdu.name)])
    iface = CANInterface(
        name="J1939Receiver",
        bus_ref="J1939BusCAN",
        j1939_name=1,
        j1939_receiver_frames=[J1939FrameRef(frame_ref="Frame_EBC1", can_id=0x18F00120)],
    )
    model = _wrap(pdus=[pdu], buses=[bus], can_interfaces=[iface])
    assert model is not None


def test_positive_j1939_receiver_frame_by_name_without_can_id_allowed():
    """A receiver frame referenced by name alone (no can_id) is now accepted: rule 379 is removed."""
    from flync.model.flync_4_ecu.can_interface import J1939FrameRef

    pdu = _make_pdu("PDU_EBC1", spn=521)
    bus = CANBus(name="J1939BusCAN", baud_rate=250000, frames=[_make_j1939_frame("Frame_EBC1", pdu.name)])
    iface = CANInterface(
        name="J1939Receiver",
        bus_ref="J1939BusCAN",
        j1939_name=1,
        j1939_receiver_frames=[J1939FrameRef(frame_ref="Frame_EBC1")],
    )
    model = _wrap(pdus=[pdu], buses=[bus], can_interfaces=[iface])
    assert model is not None


def test_positive_j1939_receiver_frame_ref_by_can_id():
    """A receiver frame referenced by its full on-bus CAN id resolves against the frame found by stripping the SA.

    The receiver is declared by an interface that itself declares no ``source_address``; the on-bus id
    0x18F00120 (frame base 0x18F00100 with emitter SA 0x20) resolves by stripping the SA: FLYNC-CMN-MAJ-REF-424
    is not raised.
    """
    from flync.model.flync_4_ecu.can_interface import J1939FrameRef

    pdu = _make_pdu("PDU_EBC1", spn=521)
    bus = CANBus(name="J1939BusCAN", baud_rate=250000, frames=[_make_j1939_frame("Frame_EBC1", pdu.name)])
    iface = CANInterface(
        name="J1939Receiver",
        bus_ref="J1939BusCAN",
        j1939_name=1,
        j1939_receiver_frames=[J1939FrameRef(can_id=0x18F00120)],
    )
    model = _wrap(pdus=[pdu], buses=[bus], can_interfaces=[iface])
    assert model is not None


def test_negative_j1939_can_id_only_ambiguous_rejected():
    """A can_id-only reference matching several frames on the bus is ambiguous: FLYNC-CMN-MAJ-CONS-425."""
    from flync.model.flync_4_ecu.can_interface import J1939FrameRef

    pdu = _make_pdu("PDU_EBC1", spn=521)
    bus = CANBus(
        name="J1939BusCAN",
        baud_rate=250000,
        frames=[
            _make_j1939_frame("Frame_EBC1", pdu.name, pdu_specific=0x01),
            _make_j1939_frame("Frame_EBC1_alt", pdu.name, pdu_specific=0x01),  # same base 0x18F00100
        ],
    )
    iface = CANInterface(
        name="J1939Sender",
        bus_ref="J1939BusCAN",
        j1939_name=1,
        source_address=0x20,
        j1939_sender_frames=[J1939FrameRef(can_id=0x18F00120)],  # base matches both
    )
    with pytest.raises(ValidationError) as exc_info:
        _wrap(pdus=[pdu], buses=[bus], can_interfaces=[iface])
    assert_single_error(exc_info, "FLYNC-CMN-MAJ-CONS-425", "ambiguous")


def test_negative_j1939_frame_ref_name_can_id_mismatch_rejected():
    """A reference with both name and can_id must resolve to the same frame; a mismatch is a consistency error (381)."""
    from flync.model.flync_4_ecu.can_interface import J1939FrameRef

    pdu = _make_pdu("PDU_EBC1", spn=521)
    bus = CANBus(
        name="J1939BusCAN",
        baud_rate=250000,
        frames=[
            _make_j1939_frame("Frame_EBC1", pdu.name, pdu_specific=0x01),
            _make_j1939_frame("Frame_EBC2", pdu.name, pdu_specific=0x02),
        ],
    )
    iface = CANInterface(
        name="J1939Sender",
        bus_ref="J1939BusCAN",
        j1939_name=1,
        source_address=0x20,
        j1939_sender_frames=[J1939FrameRef(frame_ref="Frame_EBC1", can_id=0x18F00220)],  # resolves to Frame_EBC2
    )
    with pytest.raises(ValidationError) as exc_info:
        _wrap(pdus=[pdu], buses=[bus], can_interfaces=[iface])
    assert_single_error(exc_info, "FLYNC-CMN-MAJ-CONS-423", "do not agree")


def test_positive_j1939_frame_ref_name_can_id_agrees_shared_base_allowed():
    """Two frames may share the same derived CAN id (same PGN/priority, only name differs); the named frame
    is matched against its own derived id, so a ref naming one of them alongside its on-bus id is accepted."""
    from flync.model.flync_4_ecu.can_interface import J1939FrameRef

    pdu = _make_pdu("PDU_EBC1", spn=521)
    bus = CANBus(
        name="J1939BusCAN",
        baud_rate=250000,
        frames=[
            _make_j1939_frame("EBC1_ECUx0B_oCAN1_J1939_SCM", pdu.name, pdu_specific=0x01),
            _make_j1939_frame("EBC1_SCM_oCAN1_J1939_SCM", pdu.name, pdu_specific=0x01),
        ],
    )
    iface = CANInterface(
        name="SCMNET1",
        bus_ref="J1939BusCAN",
        j1939_name=1,
        source_address=0x5B,
        j1939_sender_frames=[
            # can_id = 0x18F0015B (base 0x18F00100, SA 0x5B); both frames share base 0x18F00100
            J1939FrameRef(frame_ref="EBC1_SCM_oCAN1_J1939_SCM", can_id=0x18F0015B)
        ],
    )
    model = _wrap(pdus=[pdu], buses=[bus], can_interfaces=[iface])
    assert model is not None
