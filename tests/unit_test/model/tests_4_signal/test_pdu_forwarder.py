"""Unit tests for the PDU forwarder model: parent-free, per-instance checks.

Workspace-level validation is exercised in ``tests/system_test/model/test_forwarders.py``.
"""

import pytest
from pydantic import ValidationError

from flync.model.flync_4_ecu.can_interface import CANFrameRef, CANInterface
from flync.model.flync_4_ecu.sockets import DeploymentUnion, SocketUDP
from flync.model.flync_4_signal.forwarder import CANFrameEgress, CANFrameForwarder, EthSocketEgress, ForwarderEgress, PDUForwarder
from tests.error_assertions import assert_single_error


def _can_egress(bus_ref: str, frame_ref: int, extract_pdu_ref: str | None = None) -> ForwarderEgress:
    return ForwarderEgress(root=CANFrameEgress(bus_ref=bus_ref, frame_ref=frame_ref, extract_pdu_ref=extract_pdu_ref))


def _eth_socket_egress(socket_ref: str, extract_pdu_ref: str | None = None) -> ForwarderEgress:
    return ForwarderEgress(root=EthSocketEgress(socket_ref=socket_ref, extract_pdu_ref=extract_pdu_ref))


def _assert_duplicate_egress(builder, message_fragment: str):
    with pytest.raises(ValidationError) as exc_info:
        builder()
    assert_single_error(exc_info, "FLYNC-SIG-MAJ-UNIQ-102", message_fragment)


def test_positive_pdu_forwarder_fields_exact():
    assert list(PDUForwarder.model_fields) == ["deployment_type", "pdu_ref", "egresses"]


def test_positive_can_frame_forwarder_fields_exact():
    assert list(CANFrameForwarder.model_fields) == ["frame_ref", "egresses"]


def test_positive_can_frame_sink_fields_exact():
    assert list(CANFrameEgress.model_fields) == ["egress_type", "bus_ref", "frame_ref", "extract_pdu_ref"]


def test_positive_eth_eth_socket_egress_fields_exact():
    assert list(EthSocketEgress.model_fields) == ["egress_type", "socket_ref", "extract_pdu_ref"]


def test_positive_can_interface_config_fields_exact():
    assert list(CANInterface.model_fields) == ["name", "bus_ref", "sender_frames", "receiver_frames", "forwarder_frames"]


def test_positive_pdu_forwarder_constructs_without_registry():
    """Per-model validator does no Registry lookups, so construction works standalone."""

    fwd = PDUForwarder(
        pdu_ref="PDU_Anything",
        egresses=[_can_egress(bus_ref="DiagCAN", frame_ref=0x100)],
    )
    assert fwd.pdu_ref == "PDU_Anything"
    assert len(fwd.egresses) == 1


def test_positive_pdu_forwarder_different_egress_targets_ok():
    fwd = PDUForwarder(
        pdu_ref="PDU_X",
        egresses=[
            _can_egress(bus_ref="A", frame_ref=0x100),
            _can_egress(bus_ref="B", frame_ref=0x100),
            _eth_socket_egress(socket_ref="sock_a"),
        ],
    )
    assert len(fwd.egresses) == 3


def test_positive_deployment_union_dispatches_pdu_forwarder():
    union = DeploymentUnion.model_validate(
        {
            "deployment_type": "pdu_forwarder",
            "pdu_ref": "PDU_X",
            "egresses": [{"egress_type": "eth_socket", "socket_ref": "egress"}],
        }
    )
    assert isinstance(union.root, PDUForwarder)
    assert union.root.pdu_ref == "PDU_X"


def test_positive_deployment_union_existing_variants_unaffected():
    """The three existing discriminators still dispatch correctly."""

    sender = DeploymentUnion.model_validate({"deployment_type": "pdu_sender", "pdu_ref": "X"})
    receiver = DeploymentUnion.model_validate({"deployment_type": "pdu_receiver", "pdu_ref": "Y"})
    assert sender.root.deployment_type == "pdu_sender"
    assert receiver.root.deployment_type == "pdu_receiver"


def test_positive_forwarder_egress_dispatches_both_kinds():
    can = ForwarderEgress.model_validate({"egress_type": "can_frame", "bus_ref": "DiagCAN", "frame_ref": 0x100})
    eth = ForwarderEgress.model_validate({"egress_type": "eth_socket", "socket_ref": "sock_a"})
    assert isinstance(can.root, CANFrameEgress)
    assert isinstance(eth.root, EthSocketEgress)


# negative — schema (plain Pydantic)


@pytest.mark.parametrize(
    "model,payload",
    [
        pytest.param(
            PDUForwarder,
            {"pdu_ref": "X", "egresses": [{"egress_type": "eth_socket", "socket_ref": "s"}], "unknown_field": 1},
            id="pdu forwarder",
        ),
        pytest.param(
            CANFrameEgress,
            {"bus_ref": "B", "frame_ref": 1, "unknown_field": 1},
            id="can frame sink",
        ),
        pytest.param(
            EthSocketEgress,
            {"socket_ref": "s", "unknown_field": 1},
            id="eth socket sink",
        ),
    ],
)
def test_negative_extra_field_rejected(model, payload):
    with pytest.raises(ValidationError) as exc_info:
        model.model_validate(payload)
    assert_single_error(exc_info, None, "Extra inputs are not permitted")


# negative — egress uniqueness


@pytest.mark.parametrize(
    "egresses,message_fragment",
    [
        pytest.param(
            [_can_egress(bus_ref="DiagCAN", frame_ref=0x200), _can_egress(bus_ref="DiagCAN", frame_ref=0x200)],
            "'can_frame'",
            id="duplicate can egress",
        ),
        pytest.param(
            [_eth_socket_egress(socket_ref="sock_a"), _eth_socket_egress(socket_ref="sock_a")],
            "'eth_socket'",
            id="duplicate eth socket egress",
        ),
    ],
)
def test_negative_pdu_forwarder_duplicate_egresses(egresses, message_fragment):
    _assert_duplicate_egress(lambda: PDUForwarder(pdu_ref="PDU_X", egresses=egresses), message_fragment)


@pytest.mark.parametrize(
    "egresses,message_fragment",
    [
        pytest.param(
            [_can_egress(bus_ref="DiagCAN", frame_ref=0x101), _can_egress(bus_ref="DiagCAN", frame_ref=0x101)],
            "'can_frame'",
            id="duplicate can egress",
        ),
        pytest.param(
            [_eth_socket_egress(socket_ref="sock_a"), _eth_socket_egress(socket_ref="sock_a")],
            "'eth_socket'",
            id="duplicate eth socket egress",
        ),
    ],
)
def test_negative_can_frame_forwarder_duplicate_egresses(egresses, message_fragment):
    _assert_duplicate_egress(lambda: CANFrameForwarder(frame_ref="Frame_X", egresses=egresses), message_fragment)


# negative — empty sinks


def test_negative_pdu_forwarder_empty_sinks():
    with pytest.raises(ValidationError) as exc_info:
        PDUForwarder(pdu_ref="PDU_X", egresses=[])
    assert_single_error(exc_info, None, "at least 1 item")


def test_negative_can_frame_forwarder_empty_sinks():
    with pytest.raises(ValidationError) as exc_info:
        CANFrameForwarder(frame_ref="Frame_X", egresses=[])
    assert_single_error(exc_info, None, "at least 1 item")


# negative — egress member schema


@pytest.mark.parametrize(
    "payload,message_fragment",
    [
        pytest.param({"egress_type": "bogus", "socket_ref": "s"}, "does not match any of the expected tags", id="invalid egress type"),
        pytest.param({"egress_type": "eth_socket"}, "Field required", id="eth socket missing socket_ref"),
        pytest.param({"egress_type": "can_frame", "frame_ref": 1}, "Field required", id="can egress missing bus_ref"),
    ],
)
def test_negative_invalid_egress_member(payload, message_fragment):
    with pytest.raises(ValidationError) as exc_info:
        ForwarderEgress.model_validate(payload)
    assert_single_error(exc_info, None, message_fragment)


# negative — higher-level uniqueness


def test_negative_can_interface_duplicate_forwarder_frames():
    fwd_a = CANFrameForwarder(frame_ref="Frame_X", egresses=[_can_egress(bus_ref="DiagCAN", frame_ref=0x101)])
    fwd_b = CANFrameForwarder(frame_ref="Frame_X", egresses=[_can_egress(bus_ref="DiagCAN", frame_ref=0x102)])
    with pytest.raises(ValidationError) as exc_info:
        CANInterface(name="CAN1", bus_ref="PowertrainCAN", forwarder_frames=[fwd_a, fwd_b])
    assert_single_error(exc_info, "FLYNC-ECU-MAJ-UNIQ-058", "duplicate frame_ref(s) in forwarder_frames")


def test_negative_socket_duplicate_pdu_forwarder_for_same_pdu():
    fwd_a = {
        "deployment_type": "pdu_forwarder",
        "pdu_ref": "PDU_X",
        "egresses": [{"egress_type": "eth_socket", "socket_ref": "a"}],
    }
    fwd_b = {
        "deployment_type": "pdu_forwarder",
        "pdu_ref": "PDU_X",
        "egresses": [{"egress_type": "eth_socket", "socket_ref": "b"}],
    }
    with pytest.raises(ValidationError) as exc_info:
        _build_socket_with_deployments([fwd_a, fwd_b])
    assert_single_error(exc_info, "FLYNC-ECU-MAJ-UNIQ-083", "duplicate PDUForwarder deployment(s)")


# positive — coexistence


def test_positive_can_interface_receiver_and_forwarder_coexist():
    """A frame can legitimately appear in receiver_frames AND forwarder_frames (dual-consume)."""

    fwd = CANFrameForwarder(frame_ref="Frame_X", egresses=[_can_egress(bus_ref="DiagCAN", frame_ref=0x101)])
    iface = CANInterface(
        name="CAN1",
        bus_ref="PowertrainCAN",
        receiver_frames=[CANFrameRef(bus_ref="PowertrainCAN", frame_ref=0x101)],
        forwarder_frames=[fwd],
    )
    assert iface.receiver_frames[0].frame_ref == 0x101
    assert iface.forwarder_frames[0].frame_ref == "Frame_X"


def _build_socket_with_deployments(deployments: list) -> SocketUDP:
    return SocketUDP.model_validate(
        {
            "name": "sk",
            "endpoint_address": "10.0.0.5",
            "port_no": 30000,
            "protocol": "udp",
            "deployments": deployments,
        }
    )


def test_positive_socket_forwarder_and_receiver_for_same_pdu_coexist():
    """pdu_forwarder + pdu_receiver for the same PDU is the dual-consume pattern; valid."""

    deployments = [
        {"deployment_type": "pdu_receiver", "pdu_ref": "PDU_X"},
        {
            "deployment_type": "pdu_forwarder",
            "pdu_ref": "PDU_X",
            "egresses": [{"egress_type": "eth_socket", "socket_ref": "a"}],
        },
    ]
    sk = _build_socket_with_deployments(deployments)
    types = sorted(d.root.deployment_type for d in (sk.deployments or []))
    assert types == ["pdu_forwarder", "pdu_receiver"]
