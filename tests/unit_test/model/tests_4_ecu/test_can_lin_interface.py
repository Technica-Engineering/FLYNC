"""Unit tests for the CAN and LIN controller interface models."""

import pytest
from pydantic import TypeAdapter, ValidationError

from flync.model.flync_4_ecu.can_interface import CANFrameRef, CANInterface
from flync.model.flync_4_ecu.lin_interface import (
    AnyLINInterface,
    LINFrameRef,
    LINMasterInterface,
    LINSlaveInterface,
)
from tests.error_assertions import assert_single_error


def _can_forwarder(frame_ref="0x100", bus_ref="DiagCAN", egress_frame=0x200):
    """Build a CANFrameForwarder payload (validated from a dict) with a single CAN-frame egress."""
    return {
        "frame_ref": frame_ref,
        "egresses": [{"egress_type": "can_frame", "bus_ref": bus_ref, "frame_ref": egress_frame}],
    }


def test_positive_can_interface_minimal():
    iface = CANInterface(name="diag_can_iface", bus_ref="DiagCAN")
    assert iface.bus_ref == "DiagCAN"
    assert iface.sender_frames == []
    assert iface.receiver_frames == []
    assert iface.forwarder_frames == []


def test_positive_can_frame_ref_fields():
    ref = CANFrameRef(bus_ref="DiagCAN", frame_ref=0x123)
    assert ref.bus_ref == "DiagCAN"
    assert ref.frame_ref == 0x123


def test_positive_can_interface_with_sender_and_receiver_frames():
    iface = CANInterface(
        name="pt_can_iface",
        bus_ref="PowertrainCAN",
        sender_frames=[CANFrameRef(bus_ref="PowertrainCAN", frame_ref=0x100)],
        receiver_frames=[CANFrameRef(bus_ref="PowertrainCAN", frame_ref=0x200)],
    )
    assert len(iface.sender_frames) == 1
    assert len(iface.receiver_frames) == 1


def test_positive_can_interface_unique_forwarder_frames():
    iface = CANInterface(
        name="fwd_can_iface",
        bus_ref="DiagCAN",
        forwarder_frames=[_can_forwarder(frame_ref="0x100"), _can_forwarder(frame_ref="0x101")],
    )
    assert len(iface.forwarder_frames) == 2


def test_positive_can_interface_model_validate():
    iface = CANInterface.model_validate({"name": "mv_can_iface", "bus_ref": "DiagCAN"})
    assert isinstance(iface, CANInterface)


def test_negative_can_interface_missing_bus_ref():
    with pytest.raises(ValidationError) as exc_info:
        CANInterface(name="no_bus_iface")

    assert_single_error(exc_info, None, "bus_ref")


def test_negative_can_interface_duplicate_forwarder_frame_ref():
    forwarder_1 = _can_forwarder(frame_ref="0x100")
    forwarder_2 = _can_forwarder(frame_ref="0x100")
    with pytest.raises(ValidationError) as exc_info:
        CANInterface(
            name="dup_fwd_iface",
            bus_ref="DiagCAN",
            forwarder_frames=[forwarder_1, forwarder_2],
        )

    assert_single_error(exc_info, "FLYNC-ECU-MAJ-UNIQ-058", "duplicate frame_ref(s) in forwarder_frames")


def test_positive_lin_master_minimal():
    master = LINMasterInterface(
        name="body_lin_master",
        bus_ref="BodyLIN",
        lin_protocol="2.1",
        p2_min=50.0,
        st_min=10.0,
    )
    assert master.node_type == "master"
    assert master.bus_ref == "BodyLIN"
    assert master.sender_frames == []


def test_positive_lin_slave_minimal():
    slave = LINSlaveInterface(
        name="body_lin_slave",
        bus_ref="BodyLIN",
        lin_protocol="2.1",
        configured_nad=0x20,
        initial_nad=0x20,
    )
    assert slave.node_type == "slave"
    assert slave.product_id is None
    assert slave.receiver_frames == []


def test_positive_lin_frame_ref_fields():
    ref = LINFrameRef(bus_ref="BodyLIN", frame_ref=0x1A)
    assert ref.bus_ref == "BodyLIN"
    assert ref.frame_ref == 0x1A


@pytest.mark.parametrize("protocol", ["1.3", "2.0", "2.1", "2.2A"])
def test_positive_lin_master_all_protocols(protocol):
    master = LINMasterInterface(
        name=f"lin_master_{protocol}",
        bus_ref="BodyLIN",
        lin_protocol=protocol,
        p2_min=50.0,
        st_min=10.0,
    )
    assert master.lin_protocol == protocol


@pytest.mark.parametrize("nad", [0x00, 0x7F, 0xFF])
def test_positive_lin_slave_valid_nad_bounds(nad):
    slave = LINSlaveInterface(
        name=f"lin_slave_{nad}",
        bus_ref="BodyLIN",
        lin_protocol="2.1",
        configured_nad=nad,
        initial_nad=nad,
    )
    assert slave.configured_nad == nad


def test_negative_lin_master_missing_timing():
    with pytest.raises(ValidationError) as exc_info:
        LINMasterInterface(name="no_timing", bus_ref="BodyLIN", lin_protocol="2.1", p2_min=50.0)

    assert_single_error(exc_info, None, "st_min")


def test_negative_lin_invalid_protocol():
    with pytest.raises(ValidationError) as exc_info:
        LINMasterInterface(name="bad_proto", bus_ref="BodyLIN", lin_protocol="9.9", p2_min=50.0, st_min=10.0)

    assert_single_error(exc_info, None, "Input should be")


@pytest.mark.parametrize(
    "bad_nad,expected_fragment",
    [
        pytest.param(-1, "greater than or equal to 0", id="too_low"),
        pytest.param(0x100, "less than or equal to 255", id="too_high"),
        pytest.param(999, "less than or equal to 255", id="way_high"),
    ],
)
def test_negative_lin_slave_nad_out_of_range(bad_nad, expected_fragment):
    with pytest.raises(ValidationError) as exc_info:
        LINSlaveInterface(
            name="bad_nad",
            bus_ref="BodyLIN",
            lin_protocol="2.1",
            configured_nad=bad_nad,
            initial_nad=0x20,
        )

    assert_single_error(exc_info, None, expected_fragment)


def test_positive_any_lin_interface_discriminates_master():
    iface = TypeAdapter(AnyLINInterface).validate_python(
        {"name": "m", "node_type": "master", "bus_ref": "BodyLIN", "lin_protocol": "2.1", "p2_min": 50.0, "st_min": 10.0}
    )
    assert isinstance(iface, LINMasterInterface)


def test_positive_any_lin_interface_discriminates_slave():
    iface = TypeAdapter(AnyLINInterface).validate_python(
        {"name": "s", "node_type": "slave", "bus_ref": "BodyLIN", "lin_protocol": "2.1", "configured_nad": 1, "initial_nad": 1}
    )
    assert isinstance(iface, LINSlaveInterface)


def test_negative_any_lin_interface_unknown_node_type():
    adapter = TypeAdapter(AnyLINInterface)
    with pytest.raises(ValidationError) as exc_info:
        adapter.validate_python({"name": "x", "node_type": "gateway", "bus_ref": "BodyLIN", "lin_protocol": "2.1"})

    assert_single_error(exc_info, None, "does not match any of the expected tags")
