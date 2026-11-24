"""Workspace-level negatives for CAN / LIN interface bus and frame references.

Covers the three reference rules a bus interface is subject to once the workspace declares buses of its kind:

* the interface's own ``bus_ref`` must name a declared bus of that kind (``FLYNC-CMN-MAJ-REF-215``),
* every ``sender_frames`` / ``receiver_frames`` frame id must resolve on that bus (``FLYNC-CMN-MAJ-REF-217``), and
* a frame a node sends or receives must be covered by a schedule table of its bus
  (``FLYNC-TOP-MAJ-CONS-490``).
"""

import pytest
from pydantic import ValidationError

from flync.model.flync_4_bus.can_bus import CANBus
from flync.model.flync_4_bus.lin_bus import LINBus, LINScheduleEntry, LINScheduleTable
from flync.model.flync_4_communication.flync_channels import FLYNCChannelConfig
from flync.model.flync_4_communication.flync_communication import FLYNCCommunicationConfig
from flync.model.flync_4_ecu.can_interface import CANFrameRef, CANInterface
from flync.model.flync_4_ecu.controller import Controller
from flync.model.flync_4_ecu.ecu import ECU
from flync.model.flync_4_ecu.internal_topology import InternalTopology
from flync.model.flync_4_ecu.lin_interface import LINFrameRef, LINMasterInterface, LINSlaveInterface
from flync.model.flync_4_metadata.metadata import BaseVersion, ECUMetadata, EmbeddedMetadata, SystemMetadata
from flync.model.flync_4_signal.frame import CANFrame, LINFrame
from flync.model.flync_4_topology import EthernetTopology, FLYNCTopology
from flync.model.flync_model import FLYNCModel
from tests.error_assertions import assert_single_error

FLYNC_VERSION = "0.13.0"
CAN_ID = 0x100
LIN_ID = 0x12


def _make_version() -> BaseVersion:
    """Return the FLYNC version used by every test in this module."""
    return BaseVersion(version=FLYNC_VERSION)


def _make_can_bus(name: str = "CAN0") -> CANBus:
    """Return a CAN bus declaring a single frame at :data:`CAN_ID`."""
    frame = CANFrame(name="CAN_EngineFrame", length=8, can_id=CAN_ID, id_format="standard_11bit")
    return CANBus(name=name, baud_rate=500000, frames=[frame])


def _make_lin_bus(name: str = "LIN0") -> LINBus:
    """Return a LIN bus declaring a single frame at :data:`LIN_ID`, scheduled so a master interface on it is valid."""
    frame = LINFrame(name="LIN_BodyFrame", length=8, lin_id=LIN_ID)
    schedule_table = LINScheduleTable(name="Schedule", entries=[LINScheduleEntry(frame_name="LIN_BodyFrame", period=20.0)])
    return LINBus(
        name=name, lin_protocol_version="2.0", lin_language_version="2.0", baud_rate=19200, frames=[frame], schedule_tables=[schedule_table]
    )


UNSCHEDULED_LIN_ID = 0x13


def _make_lin_bus_with_unscheduled_frame(name: str = "LIN0") -> LINBus:
    """Return a LIN bus whose schedule table covers :data:`LIN_ID` but not :data:`UNSCHEDULED_LIN_ID`."""
    scheduled = LINFrame(name="LIN_BodyFrame", length=8, lin_id=LIN_ID)
    unscheduled = LINFrame(name="LIN_UnscheduledFrame", length=8, lin_id=UNSCHEDULED_LIN_ID)
    schedule_table = LINScheduleTable(name="Schedule", entries=[LINScheduleEntry(frame_name="LIN_BodyFrame", period=20.0)])
    return LINBus(
        name=name,
        lin_protocol_version="2.0",
        lin_language_version="2.0",
        baud_rate=19200,
        frames=[scheduled, unscheduled],
        schedule_tables=[schedule_table],
    )


def _make_model(channels: FLYNCChannelConfig, can_interfaces=None, lin_interfaces=None) -> FLYNCModel:
    """Wrap the given interfaces in the smallest workspace that reaches the bus interface checks."""
    controller = Controller(
        name="CTRL1",
        controller_metadata=EmbeddedMetadata(type="embedded", author="TestTeam", target_system="Device1", compatible_flync_version=_make_version()),
        can_interfaces=can_interfaces or [],
        lin_interfaces=lin_interfaces or [],
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
        communication=FLYNCCommunicationConfig(channels=channels),
    )


def test_can_interface_unknown_bus_ref_rejected():
    """A CAN interface whose bus_ref names no declared CAN bus is rejected."""
    channels = FLYNCChannelConfig(can_buses=[_make_can_bus("CAN0")])
    can_interface = CANInterface(name="CAN_IF_1", bus_ref="CAN_DOES_NOT_EXIST")

    with pytest.raises(ValidationError) as exc_info:
        _make_model(channels, can_interfaces=[can_interface])
    assert_single_error(exc_info, "FLYNC-CMN-MAJ-REF-215", "does not name any bus declared under communication.channels.can_buses")


def test_can_interface_pointing_at_lin_bus_rejected():
    """A CAN interface must resolve against can_buses only, so naming a LIN bus is rejected."""
    channels = FLYNCChannelConfig(can_buses=[_make_can_bus("CAN0")], lin_buses=[_make_lin_bus("LIN0")])
    can_interface = CANInterface(name="CAN_IF_1", bus_ref="LIN0")

    with pytest.raises(ValidationError) as exc_info:
        _make_model(channels, can_interfaces=[can_interface])
    assert_single_error(exc_info, "FLYNC-CMN-MAJ-REF-215", "bus_ref 'LIN0' does not name any bus declared under communication.channels.can_buses")


def test_can_interface_dangling_frame_ref_rejected():
    """A CAN sender frame id that is not declared on the referenced bus is rejected."""
    channels = FLYNCChannelConfig(can_buses=[_make_can_bus("CAN0")])
    can_interface = CANInterface(name="CAN_IF_1", bus_ref="CAN0", sender_frames=[CANFrameRef(frame_ref=0x999, id_format="standard_11bit")])

    with pytest.raises(ValidationError) as exc_info:
        _make_model(channels, can_interfaces=[can_interface])
    assert_single_error(exc_info, "FLYNC-CMN-MAJ-REF-217", "frame_ref id=2457 does not name any frame declared on bus 'CAN0'")


def test_lin_interface_dangling_frame_ref_rejected():
    """A LIN sender frame id that is not declared on the referenced bus is rejected."""
    channels = FLYNCChannelConfig(lin_buses=[_make_lin_bus("LIN0")])
    lin_interface = LINMasterInterface(
        name="LIN_IF_1",
        bus_ref="LIN0",
        lin_protocol="2.0",
        p2_min=0.001,
        st_min=0.001,
        sender_frames=[LINFrameRef(frame_ref=0x33)],
    )

    with pytest.raises(ValidationError) as exc_info:
        _make_model(channels, lin_interfaces=[lin_interface])
    assert_single_error(exc_info, "FLYNC-CMN-MAJ-REF-217", "does not name any frame declared on bus 'LIN0'")


def _lin_master(**frames) -> LINMasterInterface:
    """Return a master interface on ``LIN0`` with the given frame references."""
    return LINMasterInterface(name="LIN_IF_M", bus_ref="LIN0", lin_protocol="2.0", p2_min=0.001, st_min=0.001, **frames)


def _lin_slave(name: str = "LIN_IF_S", **frames) -> LINSlaveInterface:
    """Return a slave interface named ``name`` on ``LIN0`` with the given frame references."""
    return LINSlaveInterface(name=name, bus_ref="LIN0", lin_protocol="2.0", configured_nad=1, initial_nad=1, **frames)


@pytest.mark.parametrize(
    "lin_interfaces, field",
    [
        ([_lin_master(receiver_frames=[LINFrameRef(frame_ref=0x33)])], "receiver_frames"),
        ([_lin_master(), _lin_slave(sender_frames=[LINFrameRef(frame_ref=0x33)])], "sender_frames"),
    ],
    ids=["master_receiver", "slave_sender"],
)
def test_lin_slave_sender_and_master_receiver_refs_rejected_when_dangling(lin_interfaces, field):
    """A master's receiver_frames and a slave's sender_frames resolve against the bus like the other directions."""
    channels = FLYNCChannelConfig(lin_buses=[_make_lin_bus("LIN0")])

    with pytest.raises(ValidationError) as exc_info:
        _make_model(channels, lin_interfaces=lin_interfaces)
    assert_single_error(exc_info, "FLYNC-CMN-MAJ-REF-217", f"{field}: frame_ref id=51 does not name any frame declared on bus 'LIN0'")


BODY_FRAME = [LINFrameRef(frame_ref=LIN_ID)]


@pytest.mark.parametrize(
    "lin_interfaces",
    [
        [_lin_master(sender_frames=BODY_FRAME), _lin_slave(receiver_frames=BODY_FRAME)],
        [_lin_master(receiver_frames=BODY_FRAME), _lin_slave(sender_frames=BODY_FRAME)],
        [_lin_master(), _lin_slave("LIN_IF_A", sender_frames=BODY_FRAME), _lin_slave("LIN_IF_B", receiver_frames=BODY_FRAME)],
    ],
    ids=["master_to_slave", "slave_to_master", "slave_to_slave"],
)
def test_lin_frame_directions_accepted(lin_interfaces):
    """A LIN frame is published by the master or by one slave, and received by any other node."""
    model = _make_model(FLYNCChannelConfig(lin_buses=[_make_lin_bus("LIN0")]), lin_interfaces=lin_interfaces)

    assert len(model.ecus[0].controllers[0].lin_interfaces) == len(lin_interfaces)


@pytest.mark.parametrize(
    "lin_interfaces, owner, prior",
    [
        (
            [_lin_master(sender_frames=BODY_FRAME), _lin_slave(sender_frames=BODY_FRAME)],
            "LINSlaveInterface(name=LIN_IF_S)",
            "LINMasterInterface(name=LIN_IF_M)",
        ),
        (
            [_lin_master(), _lin_slave("LIN_IF_A", sender_frames=BODY_FRAME), _lin_slave("LIN_IF_B", sender_frames=BODY_FRAME)],
            "LINSlaveInterface(name=LIN_IF_B)",
            "LINSlaveInterface(name=LIN_IF_A)",
        ),
    ],
    ids=["master_and_slave", "two_slaves"],
)
def test_lin_frame_with_two_publishers_rejected(lin_interfaces, owner, prior):
    """Only one interface may list a LIN frame in its sender_frames."""
    channels = FLYNCChannelConfig(lin_buses=[_make_lin_bus("LIN0")])

    with pytest.raises(ValidationError) as exc_info:
        _make_model(channels, lin_interfaces=lin_interfaces)
    assert_single_error(
        exc_info, "FLYNC-CMN-MAJ-UNIQ-489", f"{owner}: sender_frames: LIN frame id={LIN_ID} on bus 'LIN0' is already published by {prior}"
    )


UNSCHEDULED_FRAME_REF = [LINFrameRef(frame_ref=UNSCHEDULED_LIN_ID)]


@pytest.mark.parametrize(
    "lin_interfaces",
    [
        [_lin_master(sender_frames=UNSCHEDULED_FRAME_REF)],
        [_lin_master(), _lin_slave(sender_frames=UNSCHEDULED_FRAME_REF)],
        [_lin_master(receiver_frames=UNSCHEDULED_FRAME_REF)],
        [_lin_master(), _lin_slave(receiver_frames=UNSCHEDULED_FRAME_REF)],
    ],
    ids=["master_sender", "slave_sender", "master_receiver", "slave_receiver"],
)
def test_lin_frame_missing_from_schedule_rejected(lin_interfaces):
    """A frame a node sends or receives in either direction must appear in a schedule table of its bus."""
    channels = FLYNCChannelConfig(lin_buses=[_make_lin_bus_with_unscheduled_frame("LIN0")])

    with pytest.raises(ValidationError) as exc_info:
        _make_model(channels, lin_interfaces=lin_interfaces)
    assert_single_error(
        exc_info,
        "FLYNC-TOP-MAJ-CONS-490",
        f"references frame 'LIN_UnscheduledFrame' (id={UNSCHEDULED_LIN_ID}), which appears in none of the bus's schedule tables",
    )


@pytest.mark.parametrize(
    "lin_interfaces",
    [
        [_lin_master(sender_frames=BODY_FRAME)],
        [_lin_master(), _lin_slave(sender_frames=BODY_FRAME)],
        [_lin_master(receiver_frames=BODY_FRAME)],
        [_lin_master(), _lin_slave(receiver_frames=BODY_FRAME)],
    ],
    ids=["master_sender", "slave_sender", "master_receiver", "slave_receiver"],
)
def test_lin_scheduled_frame_accepted_while_other_frames_unscheduled(lin_interfaces):
    """Only frames a node references must be scheduled; the rest of the bus may stay out of every table."""
    model = _make_model(FLYNCChannelConfig(lin_buses=[_make_lin_bus_with_unscheduled_frame("LIN0")]), lin_interfaces=lin_interfaces)

    assert len(model.ecus[0].controllers[0].lin_interfaces) == len(lin_interfaces)


def test_bus_interface_refs_accepted_when_declared():
    """The positive counterpart: interfaces whose bus and frame ids are declared are accepted."""
    channels = FLYNCChannelConfig(can_buses=[_make_can_bus("CAN0")], lin_buses=[_make_lin_bus("LIN0")])
    can_interface = CANInterface(name="CAN_IF_1", bus_ref="CAN0", sender_frames=[CANFrameRef(frame_ref=CAN_ID, id_format="standard_11bit")])
    lin_interface = LINMasterInterface(
        name="LIN_IF_1",
        bus_ref="LIN0",
        lin_protocol="2.0",
        p2_min=0.001,
        st_min=0.001,
        sender_frames=[LINFrameRef(frame_ref=LIN_ID)],
    )

    model = _make_model(channels, can_interfaces=[can_interface], lin_interfaces=[lin_interface])

    assert model.ecus[0].controllers[0].can_interfaces[0].bus_ref == "CAN0"
    assert model.ecus[0].controllers[0].lin_interfaces[0].bus_ref == "LIN0"
    assert isinstance(model, FLYNCModel)
    assert isinstance(model.ecus[0].controllers[0].can_interfaces[0], CANInterface)
    assert isinstance(model.ecus[0].controllers[0].lin_interfaces[0], LINMasterInterface)


def test_bus_interfaces_skipped_when_no_buses_declared():
    """A partial model without a bus catalog is accepted: there is nothing to resolve against."""
    can_interface = CANInterface(name="CAN_IF_1", bus_ref="CAN_NOT_MODELLED_YET")

    model = _make_model(FLYNCChannelConfig(), can_interfaces=[can_interface])

    assert model.ecus[0].controllers[0].can_interfaces[0].bus_ref == "CAN_NOT_MODELLED_YET"
    assert isinstance(model, FLYNCModel)
    assert isinstance(model.ecus[0].controllers[0].can_interfaces[0], CANInterface)
