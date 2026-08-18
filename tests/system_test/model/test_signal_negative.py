import pytest
from pydantic import ValidationError

from flync.model.flync_4_bus.can_bus import CANBus
from flync.model.flync_4_bus.lin_bus import LINBus
from flync.model.flync_4_communication.flync_channels import FLYNCChannelConfig
from flync.model.flync_4_communication.flync_communication import FLYNCCommunicationConfig
from flync.model.flync_4_ecu.can_interface import CANFrameRef, CANInterface
from flync.model.flync_4_ecu.controller import Controller
from flync.model.flync_4_ecu.ecu import ECU
from flync.model.flync_4_ecu.internal_topology import InternalTopology
from flync.model.flync_4_ecu.lin_interface import LINMasterInterface
from flync.model.flync_4_metadata.metadata import BaseVersion, ECUMetadata, EmbeddedMetadata, SystemMetadata
from flync.model.flync_4_signal.frame import CANFrame, FrameCyclicTiming, FrameEventTiming, FrameTransmissionTiming, LINFrame
from flync.model.flync_4_signal.pdu import ContainedPDURef, ContainerPDU, ContainerPDUHeader, MultiplexedPDU, MuxGroup, PDUInstance, StandardPDU
from flync.model.flync_4_signal.pdu_deployment import PDUReceiver, PDUSender
from flync.model.flync_4_signal.signal import Signal, SignalDataType, SignalInstance
from flync.model.flync_4_topology import EthernetTopology, FLYNCTopology
from flync.model.flync_model import FLYNCModel
from tests.error_assertions import assert_single_error


def test_standard_pdu_invalid_signal_bit_position():
    """Test SignalInstance bit range exceeds PDU length."""
    speed_signal = Signal(name="VehicleSpeed", bit_length=16, data_type=SignalDataType.UINT16)
    speed_instance = SignalInstance(signal=speed_signal, bit_position=32)  # PDU length < 32

    with pytest.raises(ValidationError):
        StandardPDU(name="PDU_EngineStatus", length=4, signals=[speed_instance])


@pytest.mark.xfail(reason="FLYNC-1126")
def test_frame_duplicate_pdu_instances():
    """Test Frame contains duplicate PDUInstances."""
    pdu = StandardPDU(name="PDU_EngineStatus", length=4)
    pdu_inst1 = PDUInstance(pdu_ref=pdu.name)
    pdu_inst2 = PDUInstance(pdu_ref=pdu.name)  # duplicate

    with pytest.raises(ValidationError):
        CANFrame(name="CAN_Frame", length=8, can_id=0x100, id_format="standard_11bit", packed_pdus=[pdu_inst1, pdu_inst2])


@pytest.mark.xfail(reason="FLYNC-1127")
def test_multiplexed_pdu_invalid_selector_value():
    """Test creating a MultiplexedPDU with an invalid selector value range."""

    selector_signal = Signal(name="GearSelector", bit_length=3, data_type=SignalDataType.UINT8)
    selector_instance = SignalInstance(signal=selector_signal, bit_position=0)

    pdu1 = StandardPDU(name="PDU_Gear1", length=2)
    mux_group = MuxGroup(selector_value=1, pdu=pdu1)
    with pytest.raises(ValidationError):
        MultiplexedPDU(
            name="PDU_TransmissionStatus", length=2, selector_signal=selector_instance, mux_groups=[mux_group]  # smaller than selector requires
        )


@pytest.mark.xfail(reason="FLYNC-1129")
def test_container_pdu_invalid_contained_ref():
    """Test ContainerPDU references non-existent contained PDU."""
    header = ContainerPDUHeader(id_length_bits=8, length_field_bits=8)
    contained_ref = ContainedPDURef(header_id=0x10, pdu_ref="NonExistentPDU")

    with pytest.raises(ValueError):
        ContainerPDU(name="ContainerPowertrain", length=64, pdu_id=0x01, header=header, contained_pdus=[contained_ref])


def test_standard_pdu_signal_overlap():
    """Test StandardPDU with overlapping signals."""
    sig1 = Signal(name="Signal1", bit_length=8, data_type=SignalDataType.UINT8)
    sig2 = Signal(name="Signal2", bit_length=8, data_type=SignalDataType.UINT8)
    inst1 = SignalInstance(signal=sig1, bit_position=0)
    inst2 = SignalInstance(signal=sig2, bit_position=4)  # overlaps with inst1

    with pytest.raises(ValidationError):
        StandardPDU(name="PDU_Overlap", length=2, signals=[inst1, inst2])


@pytest.mark.xfail(reason="FLYNC-1128")
def test_receiver_invalid_pdu():
    """Test PDUReceiver references a PDU that does not exist."""
    with pytest.raises(ValidationError):
        PDUReceiver(pdu_ref="NonExistentPDU")


@pytest.mark.xfail(reason="FLYNC-663")
def test_sender_invalid_pdu():
    """Test PDUSender references a PDU that does not exist."""
    with pytest.raises(ValidationError):
        PDUSender(pdu_ref="NonExistentPDU")


@pytest.mark.xfail(reason="FLYNC-1125")
def test_overlaps_frame_timing():
    """Test event repeating_time_range bigger than cyclic cycle."""
    cyclic = FrameCyclicTiming(cycle=0.1)
    event = FrameEventTiming(final_repetitions=5, repeating_time_range=0.2)

    with pytest.raises(ValidationError):
        FrameTransmissionTiming(cyclic_timings=[cyclic], event_timings=[event])


def test_invalid_lin_frame_in_can_interface():
    """Test CAN interface incorrectly configured with a LIN frame

    The frame id only resolves on the LIN bus, so referencing it from a CAN interface must not resolve. The check
    is workspace-level (it needs the bus catalog), hence the full model.
    """
    speed_signal = Signal(name="VehicleSpeed", bit_length=16, data_type=SignalDataType.UINT16)
    speed_instance = SignalInstance(signal=speed_signal, bit_position=0)
    pdu = StandardPDU(name="PDU_EngineStatus", length=4, signals=[speed_instance])
    pdu_inst = PDUInstance(pdu_ref=pdu.name)
    lin_frame = LINFrame(name="LIN_EngineFrame", length=8, lin_id=0x12, packed_pdus=[pdu_inst])
    can_frame = CANFrame(name="CAN_EngineFrame", length=8, can_id=0x100, id_format="standard_11bit", packed_pdus=[pdu_inst])

    can_bus = CANBus(name="CAN0", baud_rate=500000, frames=[can_frame])
    lin_bus = LINBus(name="LIN0", lin_protocol_version="2.0", lin_language_version="2.0", baud_rate=19200, frames=[lin_frame])

    # The LIN frame id is declared on LIN0 only - asking for it on the CAN bus cannot resolve.
    can_interface = CANInterface(name="CAN0_IF", bus_ref="CAN0", receiver_frames=[CANFrameRef(bus_ref="CAN0", frame_ref=lin_frame.lin_id)])
    controller = Controller(
        name="EngineController",
        controller_metadata=EmbeddedMetadata(
            type="embedded",
            author="test_team",
            compatible_flync_version=BaseVersion(version_schema="semver", version="0.11.0"),
            target_system="my_system",
        ),
        can_interfaces=[can_interface],
    )
    ecu = ECU(
        name="ECU1",
        controllers=[controller],
        topology=InternalTopology(),
        ecu_metadata=ECUMetadata(type="ecu", author="test_team", compatible_flync_version=BaseVersion(version="0.11.0")),
    )
    topology = FLYNCTopology(system_topology=EthernetTopology(connections=[]))
    metadata = SystemMetadata(
        type="system",
        release=BaseVersion(version="0.11.0"),
        author="test_team",
        compatible_flync_version=BaseVersion(version="0.11.0"),
    )
    communication = FLYNCCommunicationConfig(channels=FLYNCChannelConfig(can_buses=[can_bus], lin_buses=[lin_bus], pdus=[pdu]))

    with pytest.raises(ValidationError) as exc_info:
        FLYNCModel(ecus=[ecu], topology=topology, metadata=metadata, communication=communication)
    assert_single_error(exc_info, "FLYNC-CMN-MAJ-REF-217", "does not name any frame declared on bus 'CAN0'")


def test_invalid_can_frame_in_lin_interface():
    """Test LIN interface incorrectly configured with a CAN frame"""
    speed_signal = Signal(name="VehicleSpeed", bit_length=16, data_type=SignalDataType.UINT16)
    speed_instance = SignalInstance(signal=speed_signal, bit_position=0)
    pdu = StandardPDU(name="PDU_EngineStatus", length=4, signals=[speed_instance])
    pdu_inst = PDUInstance(pdu_ref=pdu.name)
    can_frame = CANFrame(name="CAN_EngineFrame", length=8, can_id=0x100, id_format="standard_11bit", packed_pdus=[pdu_inst])
    can_frame_ref = CANFrameRef(bus_ref="LIN0", frame_ref=can_frame.can_id)  # invalid: a CAN ref on a LIN interface

    # The rejection happens when the LIN interface itself is built, so that is the call under test.
    with pytest.raises(ValidationError) as exc_info:
        LINMasterInterface(
            name="LIN0_IF",
            node_type="master",
            bus_ref="LIN0",
            lin_protocol="2.0",
            p2_min=0.001,
            st_min=0.001,
            sender_frames=[can_frame_ref],
        )
    # No error id: the mismatch is reported by the Pydantic union discrimination, not by a FLYNC validator.
    assert_single_error(exc_info, None, "LINFrameRef")
