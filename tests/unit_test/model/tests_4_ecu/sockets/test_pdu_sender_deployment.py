import pytest
from pydantic import ValidationError

from flync.model.flync_4_ecu.sockets import (
    DeploymentUnion,
    Socket,
    SocketTCP,
    SocketUDP,
    TCPOption,
)
from flync.model.flync_4_signal.frame import PDUSender

# ---------------------------------------------------------------------------
# PDUSender via DeploymentUnion
# ---------------------------------------------------------------------------


def test_positive_deployment_union_pdu_sender():
    dep = DeploymentUnion.model_validate({"deployment_type": "pdu_sender", "pdu_ref": "my_container_pdu"})
    assert isinstance(dep.root, PDUSender)
    assert dep.root.pdu_ref == "my_container_pdu"


def test_positive_deployment_union_pdu_sender_default_type():
    dep = DeploymentUnion.model_validate({"deployment_type": "pdu_sender", "pdu_ref": "pdu_A"})
    assert dep.root.deployment_type == "pdu_sender"


# ---------------------------------------------------------------------------
# SocketUDP with PDUSender deployment
# ---------------------------------------------------------------------------


def test_positive_udp_socket_with_pdu_sender_deployment():
    socket = SocketUDP(
        name="udp_pdu_sock",
        endpoint_address="10.0.0.1",
        port_no=5000,
        deployments=[{"deployment_type": "pdu_sender", "pdu_ref": "container_pdu_1"}],
    )
    assert isinstance(socket, Socket)
    assert len(socket.deployments) == 1
    assert isinstance(socket.deployments[0].root, PDUSender)


def test_positive_udp_socket_with_multiple_pdu_sender_deployments():
    socket = SocketUDP(
        name="udp_multi_pdu",
        endpoint_address="10.0.0.2",
        port_no=5001,
        deployments=[
            {"deployment_type": "pdu_sender", "pdu_ref": "container_pdu_2"},
            {"deployment_type": "pdu_sender", "pdu_ref": "container_pdu_3"},
        ],
    )
    assert len(socket.deployments) == 2


def test_positive_udp_socket_multicast_with_pdu_sender():
    socket = SocketUDP(
        name="udp_mcast_pdu",
        endpoint_address="224.0.0.5",
        port_no=5002,
        deployments=[{"deployment_type": "pdu_sender", "pdu_ref": "mcast_container_pdu"}],
    )
    assert socket.endpoint_type == "multicast"
    assert isinstance(socket.deployments[0].root, PDUSender)


def test_positive_udp_socket_ipv6_with_pdu_sender():
    socket = SocketUDP(
        name="udp_ipv6_pdu",
        endpoint_address="2001:db8::1",
        port_no=5003,
        deployments=[{"deployment_type": "pdu_sender", "pdu_ref": "ipv6_container_pdu"}],
    )
    assert isinstance(socket.deployments[0].root, PDUSender)


def test_positive_udp_socket_no_deployments():
    socket = SocketUDP(
        name="udp_no_dep",
        endpoint_address="10.0.0.3",
        port_no=5004,
        deployments=[],
    )
    assert socket.deployments == []


# ---------------------------------------------------------------------------
# SocketTCP with PDUSender deployment
# ---------------------------------------------------------------------------


def test_positive_tcp_socket_with_pdu_sender_deployment():
    TCPOption(tcp_profile_id=10)
    socket = SocketTCP(
        name="tcp_pdu_sock",
        endpoint_address="10.0.0.10",
        port_no=6000,
        tcp_profile=10,
        deployments=[{"deployment_type": "pdu_sender", "pdu_ref": "tcp_container_pdu"}],
    )
    assert isinstance(socket, Socket)
    assert isinstance(socket.deployments[0].root, PDUSender)


# ---------------------------------------------------------------------------
# Negative tests
# ---------------------------------------------------------------------------


def test_negative_pdu_sender_missing_pdu_ref_on_socket():
    with pytest.raises(ValidationError):
        SocketUDP(
            name="udp_bad_dep",
            endpoint_address="10.0.0.4",
            port_no=5010,
            deployments=[{"deployment_type": "pdu_sender"}],
        )


def test_negative_deployment_union_unknown_type():
    with pytest.raises(ValidationError):
        DeploymentUnion.model_validate({"deployment_type": "unknown_type", "pdu_ref": "pdu_X"})


def test_negative_pdu_sender_extra_fields():
    with pytest.raises(ValidationError):
        SocketUDP(
            name="udp_extra_dep",
            endpoint_address="10.0.0.5",
            port_no=5011,
            deployments=[
                {
                    "deployment_type": "pdu_sender",
                    "pdu_ref": "container_pdu_extra",
                    "invalid_field": "bad_value",
                }
            ],
        )
