"""End-to-end tests converting a FLYNCModel with StandardPDU and MultiplexedPDU CAN messages to DBC."""

from pathlib import Path

import cantools.database

from flync.model.flync_4_bus.can_bus import CANBus
from flync.model.flync_4_communication.flync_channels import FLYNCChannelConfig
from flync.model.flync_4_communication.flync_communication import FLYNCCommunicationConfig
from flync.model.flync_4_ecu.can_interface import CANFrameRef, CANInterface
from flync.model.flync_4_ecu.controller import Controller
from flync.model.flync_4_ecu.ecu import ECU
from flync.model.flync_4_ecu.internal_topology import InternalTopology
from flync.model.flync_4_metadata.metadata import BaseVersion, ECUMetadata, EmbeddedMetadata, SystemMetadata
from flync.model.flync_4_signal import CANFrame, MultiplexedPDU, MuxGroup, PDUInstance, SignalInstance, StandardPDU
from flync.model.flync_4_signal.signal import Signal
from flync.model.flync_4_topology.ethernet_topology import EthernetTopology, FLYNCTopology
from flync.model.flync_model import FLYNCModel
from flync_converter.converters.dbc.encoder import write_dbc_files

FLYNC_VERSION = "0.13.0"


def _make_version() -> BaseVersion:
    """Return the FLYNC version used by this test module."""
    return BaseVersion(version=FLYNC_VERSION)


def _build_model() -> FLYNCModel:
    """Build a minimal FLYNCModel with one StandardPDU frame and one MultiplexedPDU frame on a single CAN bus."""

    # -- StandardPDU: EngineStatus, EngineSpeed(uint16 @0, factor 0.125) + EngineTemp(int8 @16) --
    engine_speed = Signal(name="EngineSpeed", bit_length=16, data_type="uint16", factor=0.125, offset=0)
    engine_temp = Signal(name="EngineTemp", bit_length=8, data_type="int8", factor=1.0, offset=-40)
    engine_status_pdu = StandardPDU(
        name="PDU_EngineStatus",
        length=8,
        signals=[
            SignalInstance(signal=engine_speed, bit_position=0),
            SignalInstance(signal=engine_temp, bit_position=16),
        ],
    )
    engine_status_frame = CANFrame(
        name="Frame_EngineStatus",
        length=8,
        can_id=0x100,
        id_format="standard_11bit",
        packed_pdus=[PDUInstance(pdu_ref="PDU_EngineStatus", bit_position=0)],
    )

    # -- MultiplexedPDU: TransmissionStatus, selector GearInfoMux(uint8, 4 bits) @0 --
    gear_info_mux = Signal(name="GearInfoMux", bit_length=4, data_type="uint8")
    current_gear = Signal(name="CurrentGear", bit_length=8, data_type="uint8")
    torque_converter_slip_speed = Signal(name="TorqueConverterSlipSpeed", bit_length=16, data_type="uint16", factor=0.1, offset=0.0)

    gear_pdu = StandardPDU(
        name="PDU_Gear",
        length=8,
        signals=[SignalInstance(signal=current_gear, bit_position=8)],
    )
    torque_pdu = StandardPDU(
        name="PDU_Torque",
        length=8,
        signals=[SignalInstance(signal=torque_converter_slip_speed, bit_position=8)],
    )
    transmission_status_pdu = MultiplexedPDU(
        name="PDU_TransmissionStatus",
        length=8,
        selector_signal=SignalInstance(signal=gear_info_mux, bit_position=0),
        mux_groups=[
            MuxGroup(selector_value=0, pdu=PDUInstance(pdu_ref="PDU_Gear")),
            MuxGroup(selector_value=1, pdu=PDUInstance(pdu_ref="PDU_Torque")),
        ],
    )
    transmission_status_frame = CANFrame(
        name="Frame_TransmissionStatus",
        length=8,
        can_id=0x101,
        id_format="standard_11bit",
        packed_pdus=[PDUInstance(pdu_ref="PDU_TransmissionStatus", bit_position=0)],
    )

    can_bus = CANBus(
        name="CAN1_BUS",
        baud_rate=500000,
        frames=[engine_status_frame, transmission_status_frame],
    )
    can_interface = CANInterface(
        name="CAN_IF_1",
        bus_ref="CAN1_BUS",
        sender_frames=[
            CANFrameRef(bus_ref="CAN1_BUS", frame_ref=0x100),
            CANFrameRef(bus_ref="CAN1_BUS", frame_ref=0x101),
        ],
        receiver_frames=[],
        forwarder_frames=[],
    )
    controller = Controller(
        name="CTRL1",
        controller_metadata=EmbeddedMetadata(type="embedded", author="TestTeam", target_system="Device1", compatible_flync_version=_make_version()),
        can_interfaces=[can_interface],
        ethernet_interfaces=[],
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
        communication=FLYNCCommunicationConfig(
            channels=FLYNCChannelConfig(
                can_buses=[can_bus],
                pdus=[engine_status_pdu, gear_pdu, torque_pdu, transmission_status_pdu],
            )
        ),
    )


def test_standard_and_multiplexed_pdu_convert_to_valid_dbc(tmp_path):
    """
    End-to-end: a FLYNCModel with one StandardPDU CAN message and one MultiplexedPDU CAN message is written to
    a DBC file, the DBC file is reloaded with cantools, and the resulting messages/signals/mux layout and decoded
    physical values are checked against the source model.
    """
    flync_model = _build_model()

    write_dbc_files(flync_model, str(tmp_path))

    dbc_files = list(Path(tmp_path).glob("*.dbc"))
    assert len(dbc_files) == 1
    assert dbc_files[0].name == "CAN1_BUS.dbc"

    db = cantools.database.load_file(dbc_files[0])
    assert {m.name for m in db.messages} == {"Frame_EngineStatus", "Frame_TransmissionStatus"}

    # -- StandardPDU message --
    engine_status = db.get_message_by_name("Frame_EngineStatus")
    assert engine_status.frame_id == 0x100
    assert engine_status.length == 8
    assert engine_status.senders == ["ECU1"]

    speed_signal = engine_status.get_signal_by_name("EngineSpeed")
    assert speed_signal.start == 0
    assert speed_signal.length == 16
    assert not speed_signal.is_signed
    assert speed_signal.conversion.scale == 0.125

    temp_signal = engine_status.get_signal_by_name("EngineTemp")
    assert temp_signal.start == 16
    assert temp_signal.length == 8
    assert temp_signal.is_signed
    assert temp_signal.conversion.offset == -40

    decoded = engine_status.decode(engine_status.encode({"EngineSpeed": 1000 * 0.125, "EngineTemp": 25}))
    assert decoded["EngineSpeed"] == 125.0
    assert decoded["EngineTemp"] == 25

    # -- MultiplexedPDU message --
    transmission_status = db.get_message_by_name("Frame_TransmissionStatus")
    assert transmission_status.frame_id == 0x101
    assert transmission_status.length == 8
    assert transmission_status.senders == ["ECU1"]

    selector = transmission_status.get_signal_by_name("GearInfoMux")
    assert selector.is_multiplexer
    assert selector.start == 0
    assert selector.length == 4

    current_gear_signal = transmission_status.get_signal_by_name("CurrentGear")
    assert current_gear_signal.multiplexer_ids == [0]
    assert current_gear_signal.multiplexer_signal == "GearInfoMux"
    assert current_gear_signal.start == 8

    slip_speed_signal = transmission_status.get_signal_by_name("TorqueConverterSlipSpeed")
    assert slip_speed_signal.multiplexer_ids == [1]
    assert slip_speed_signal.multiplexer_signal == "GearInfoMux"
    assert slip_speed_signal.start == 8
    assert slip_speed_signal.conversion.scale == 0.1

    gear_payload = transmission_status.encode({"GearInfoMux": 0, "CurrentGear": 3})
    decoded_gear = transmission_status.decode(gear_payload)
    assert decoded_gear["GearInfoMux"] == 0
    assert decoded_gear["CurrentGear"] == 3
    assert "TorqueConverterSlipSpeed" not in decoded_gear

    torque_payload = transmission_status.encode({"GearInfoMux": 1, "TorqueConverterSlipSpeed": 200.0})
    decoded_torque = transmission_status.decode(torque_payload)
    assert decoded_torque["GearInfoMux"] == 1
    assert decoded_torque["TorqueConverterSlipSpeed"] == 200.0
    assert "CurrentGear" not in decoded_torque
