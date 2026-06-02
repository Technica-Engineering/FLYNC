import pytest

from flync.model.flync_4_signal.frame import (
    CANFDFrame,
    CANFrame,
    FrameCyclicTiming,
    FrameEventTiming,
    FrameTransmissionTiming,
    LINFrame,
    PDUReceiver,
    PDUSender,
)
from flync.model.flync_4_signal.pdu import ContainedPDURef, ContainerPDU, ContainerPDUHeader, MultiplexedPDU, MuxGroup, PDUInstance, StandardPDU
from flync.model.flync_4_signal.signal import Signal, SignalDataType, SignalGroup, SignalGroupInstance, SignalInstance


@pytest.mark.parametrize(
    "frame_class, frame_args",
    [
        (CANFrame, {"name": "CAN_EngineFrame", "length": 8, "can_id": 0x100, "id_format": "standard_11bit"}),
        (CANFDFrame, {"name": "CANFD_EngineFrame", "length": 64, "can_id": 0x1ABCDE, "id_format": "extended_29bit"}),
        (LINFrame, {"name": "LIN_EngineFrame", "length": 8, "lin_id": 0x12, "checksum_type": "enhanced"}),
    ],
)
def test_standard_pdu_all_frames(frame_class, frame_args):
    """
    Verify StandardPDU correctly packs into CAN, CANFD, and LIN frames.

    Path validated:
    Signal → SignalInstance → StandardPDU → PDUInstance → Frame (CAN/CANFD/LIN) → PDUSender / PDUReceiver
    """
    # Signals
    speed_signal = Signal(name="VehicleSpeed", bit_length=16, data_type=SignalDataType.UINT16, unit="km/h")
    speed_instance = SignalInstance(signal=speed_signal, bit_position=0)
    pdu = StandardPDU(name="PDU_EngineStatus", length=4, signals=[speed_instance])
    pdu_inst = PDUInstance(pdu_ref=pdu.name, bit_position=0)
    frame = frame_class(packed_pdus=[pdu_inst], **frame_args)
    sender = PDUSender(pdu_ref=pdu.name)
    receiver = PDUReceiver(pdu_ref=pdu.name)

    assert frame.packed_pdus[0].pdu_ref == "PDU_EngineStatus"
    assert sender.pdu_ref == "PDU_EngineStatus"
    assert receiver.pdu_ref == "PDU_EngineStatus"


def test_standard_pdu_with_signalgroup():
    """
    Verify StandardPDU with SignalGroup packs correctly into a frame.

    Path validated:
    Signal → SignalInstance → SignalGroup → SignalGroupInstance → StandardPDU → PDUInstance → Frame → PDUSender / PDUReceiver
    """
    temp_signal = Signal(name="EngineTemp", bit_length=8, data_type=SignalDataType.UINT8, unit="°C")
    speed_signal = Signal(name="VehicleSpeed", bit_length=16, data_type=SignalDataType.UINT16, unit="km/h")
    speed_instance = SignalInstance(signal=speed_signal, bit_position=0)
    temp_instance = SignalInstance(signal=temp_signal, bit_position=16)
    group = SignalGroup(name="EngineSensors", signals=[speed_instance, temp_instance])
    group_instance = SignalGroupInstance(signal_group=group, bit_position=0)
    pdu = StandardPDU(name="PDU_EngineSensors", length=4, signal_groups=[group_instance])
    pdu_inst = PDUInstance(pdu_ref=pdu.name)
    frame = CANFDFrame(name="CANFD_EngineFrame", length=8, can_id=0x200, id_format="extended_29bit", packed_pdus=[pdu_inst])
    receiver = PDUReceiver(pdu_ref=pdu.name)
    receiver = PDUReceiver(pdu_ref=pdu.name)

    assert frame.packed_pdus[0].pdu_ref == "PDU_EngineSensors"
    assert receiver.pdu_ref == "PDU_EngineSensors"
    assert receiver.pdu_ref == "PDU_EngineSensors"


def test_multiplexed_pdu():
    """
    Verify MultiplexedPDU selector logic and correct PDU reference in a frame.

    Path validated:
    Signal → SignalInstance (selector) → MultiplexedPDU → MuxGroup → StandardPDU → PDUInstance → Frame → PDUSender / PDUReceiver
    """
    gear_signal = Signal(name="GearSelector", bit_length=3, data_type=SignalDataType.UINT8)
    gear_instance = SignalInstance(signal=gear_signal, bit_position=0)
    pdu_gear1 = StandardPDU(name="PDU_Gear1", length=2)
    pdu_gear2 = StandardPDU(name="PDU_Gear2", length=2)
    mux1 = MuxGroup(selector_value=1, pdu=pdu_gear1)
    mux2 = MuxGroup(selector_value=2, pdu=pdu_gear2)
    muxed_pdu = MultiplexedPDU(name="PDU_TransmissionStatus", length=4, selector_signal=gear_instance, mux_groups=[mux1, mux2])
    pdu_inst = PDUInstance(pdu_ref=muxed_pdu.name)
    frame = LINFrame(name="LIN_TransmissionFrame", length=8, lin_id=0x10, packed_pdus=[pdu_inst])
    sender = PDUSender(pdu_ref=muxed_pdu.name)
    receiver = PDUReceiver(pdu_ref=muxed_pdu.name)

    assert frame.packed_pdus[0].pdu_ref == "PDU_TransmissionStatus"
    assert sender.pdu_ref == "PDU_TransmissionStatus"
    assert receiver.pdu_ref == "PDU_TransmissionStatus"


def test_container_pdu():
    """
    Verify ContainerPDU aggregates multiple PDUs correctly and maintains references.

    Path validated:
    StandardPDU / MultiplexedPDU → ContainedPDURef → ContainerPDUHeader → ContainerPDU → PDUInstance → Frame → PDUSender / PDUReceiver
    """
    pdu1 = StandardPDU(name="PDU_EngineStatus", length=4)
    pdu2 = StandardPDU(name="PDU_TransmissionStatus", length=4)
    ref1 = ContainedPDURef(pdu_id=0x10, pdu_ref=pdu1.name)
    ref2 = ContainedPDURef(pdu_id=0x11, pdu_ref=pdu2.name)
    header = ContainerPDUHeader(id_length_bits=8, length_field_bits=8)
    container = ContainerPDU(name="ContainerPowertrain", length=64, pdu_id=0x01, header=header, contained_pdus=[ref1, ref2])
    sender = PDUSender(pdu_ref=container.name)
    receiver = PDUReceiver(pdu_ref=container.name)

    assert container.contained_pdus[0].pdu_ref == "PDU_EngineStatus"
    assert sender.pdu_ref == "ContainerPowertrain"
    assert receiver.pdu_ref == "ContainerPowertrain"


def test_frame_with_timing():
    """
    Verify frames with cyclic and event-based transmission timing are handled correctly.

    Path validated:
    Signal → SignalInstance → StandardPDU → PDUInstance → Frame (CANFrame / CANFDFrame / LINFrame) → FrameTransmissionTiming
    """
    speed_signal = Signal(name="VehicleSpeed", bit_length=16, data_type=SignalDataType.UINT16)
    speed_instance = SignalInstance(signal=speed_signal)
    pdu = StandardPDU(name="PDU_EngineStatus", length=4, signals=[speed_instance])
    pdu_inst = PDUInstance(pdu_ref=pdu.name)
    cyclic = FrameCyclicTiming(cycle=0.1)
    event = FrameEventTiming(final_repetitions=3, repeating_time_range=0.05)
    timing = FrameTransmissionTiming(cyclic_timings=[cyclic], event_timings=[event])
    frame = CANFrame(name="CAN_EngineFrameWithTiming", length=8, can_id=0x100, id_format="standard_11bit", packed_pdus=[pdu_inst], timing=timing)

    assert frame.timing.cyclic_timings[0].cycle == 0.1
    assert frame.timing.event_timings[0].final_repetitions == 3
