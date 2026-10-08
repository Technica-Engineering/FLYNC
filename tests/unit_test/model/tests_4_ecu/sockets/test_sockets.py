import pytest
from pydantic import ValidationError

from flync.model.flync_4_ecu.sockets import (
    IPv4AddressEndpoint,
    IPv6AddressEndpoint,
    Socket,
    SocketTCP,
    SocketUDP,
    TCPOption,
)
from flync.model.flync_4_someip.deployment import (
    MulticastEndpoint,
    SOMEIPServiceConsumer,
    SOMEIPServiceProvider,
)
from flync.model.flync_4_someip.service_interface import SOMEIPServiceInterface
from tests.error_assertions import assert_single_error


def test_positive_udp_socket():
    udp_socket = {
        "endpoint_address": "10.0.0.1",
        "name": "my_socket",
        "port_no": 123,
        "udp_options": {"udp_cork": False},
        "protocol": "udp",
    }
    udp_example = SocketUDP.model_validate(udp_socket)
    assert isinstance(udp_example, SocketUDP)
    assert str(udp_example.endpoint_address) == "10.0.0.1"
    assert udp_example.name == "my_socket"
    assert udp_example.port_no == 123
    assert udp_example.protocol == "udp"
    assert udp_example.udp_options.udp_cork is False


@pytest.mark.parametrize(
    "udp_socket",
    [
        pytest.param(
            {
                "endpoint_address": "3a",
                "name": "my_socket",
                "port_no": 123,
                "udp_options": {"udp_cork": False},
                "protocol": "udp",
            },
            id="Invalid address endpoint",
        ),
        pytest.param(
            {
                "endpoint_address": "10.0.0.1",
                "name": 1,
                "port_no": 123,
                "udp_options": {"udp_cork": False},
                "protocol": "udp",
            },
            id="Invalid name",
        ),
        pytest.param(
            {
                "endpoint_address": "10.0.0.1",
                "name": "my_socket",
                "port_no": "abc",
                "udp_options": {"udp_cork": False},
                "protocol": "udp",
            },
            id="Invalid port number",
        ),
        pytest.param(
            {
                "endpoint_address": "10.0.0.1",
                "name": "my_socket",
                "port_no": 123,
                "udp_options": {"keepalive": False},
                "protocol": "udp",
            },
            id="Invalid udp options",
        ),
        pytest.param(
            {
                "endpoint_address": "10.0.0.1",
                "name": "my_socket",
                "port_no": 123,
                "udp_options": {"udp_cork": False},
                "protocol": "tcp",
            },
            id="Wrong protocol",
        ),
        pytest.param(
            {
                "endpoint_address": "10.0.0.1",
                "vlan_id": 1,
                "name": "my_socket",
                "port_no": 123,
                "udp_options": {"udp_cork": False},
                "protocol": "udp",
            },
            id="Extra input defined",
        ),
        pytest.param(
            {
                "endpoint_address": "10.0.0.1",
                "port_no": 123,
                "udp_options": {"udp_cork": False},
                "protocol": "udp",
            },
            id="Name not defined",
        ),
    ],
)
def test_negative_udp_socket_parameters(udp_socket):

    with pytest.raises(ValidationError) as e:
        SocketUDP.model_validate(udp_socket)


def test_positive_tcp_socket():
    tcp_options = TCPOption(tcp_profile_id=1)
    tcp_socket = {
        "endpoint_address": "10.0.0.1",
        "name": "my_socket",
        "port_no": 123,
        "tcp_profile": 1,
        "protocol": "tcp",
    }
    tcp_example = SocketTCP.model_validate(tcp_socket)
    assert isinstance(tcp_example, SocketTCP)
    assert str(tcp_example.endpoint_address) == "10.0.0.1"
    assert tcp_example.name == "my_socket"
    assert tcp_example.port_no == 123
    assert tcp_example.protocol == "tcp"
    assert tcp_example.tcp_profile == 1


@pytest.mark.parametrize(
    "tcp_socket",
    [
        pytest.param(
            {
                "endpoint_address": "3a",
                "name": "my_socket",
                "port_no": 123,
                "tcp_profile": 1,
                "protocol": "tcp",
            },
            id="Invalid address endpoint",
        ),
        pytest.param(
            {
                "endpoint_address": "10.0.0.1",
                "name": 1,
                "port_no": 123,
                "tcp_profile": 1,
                "protocol": "tcp",
            },
            id="Invalid name",
        ),
        pytest.param(
            {
                "endpoint_address": "10.0.0.1",
                "name": "My socket",
                "port_no": "abc",
                "tcp_profile": 1,
                "protocol": "tcp",
            },
            id="Invalid port no.",
        ),
        pytest.param(
            {
                "endpoint_address": "10.0.0.1",
                "name": "my_socket",
                "port_no": 123,
                "tcp_profile": 1,
                "protocol": "udp",
            },
            id="Wrong protocol",
        ),
        pytest.param(
            {
                "endpoint_address": "10.0.0.1",
                "vlan_id": 1,
                "name": "my_socket",
                "port_no": 123,
                "tcp_profile": 1,
                "protocol": "tcp",
            },
            id="Extra input defined",
        ),
        pytest.param(
            {
                "endpoint_address": "10.0.0.1",
                "port_no": 123,
                "tcp_profile": 1,
                "protocol": "tcp",
            },
            id="Name not defined",
        ),
    ],
)
def test_negative_tcp_socket_parameters(tcp_socket):
    tcp_options = TCPOption(tcp_profile_id=1)
    with pytest.raises(ValidationError) as e:
        SocketTCP.model_validate(tcp_socket)


@pytest.mark.parametrize(
    "tcp_options",
    [
        pytest.param(
            {
                "tcp_profile_id": 1,
                "nagle": True,
            },
            id="Test Nagle true",
        ),
        pytest.param(
            {
                "tcp_profile_id": 1,
                "keepalive_enabled": False,
            },
            id="Test Keepalive enabled",
        ),
        pytest.param(
            {
                "tcp_profile_id": 1,
                "keepidle": 5,
            },
            id="Test Keep Idle",
        ),
        pytest.param(
            {
                "tcp_profile_id": 1,
                "keepcount": 5,
            },
            id="Test Keep count",
        ),
        pytest.param(
            {
                "tcp_profile_id": 1,
                "keepintvl": 1,
            },
            id="Test Keep Interval",
        ),
        pytest.param(
            {
                "tcp_profile_id": 1,
                "user_timeout": 14,
            },
            id="Test User timeout",
        ),
        pytest.param(
            {
                "tcp_profile_id": 1,
                "congestion_avoidance": "cubic",
            },
            id="Test Congestion avoidance",
        ),
        pytest.param(
            {
                "tcp_profile_id": 1,
                "tcp_maxseg": 1200,
            },
            id="Test Max Segment",
        ),
        pytest.param(
            {
                "tcp_profile_id": 1,
                "tcp_quickack": True,
            },
            id="Test Quickack",
        ),
        pytest.param(
            {
                "tcp_profile_id": 1,
                "tcp_syncnt": 4,
            },
            id="Test SYNC retries",
        ),
    ],
)
def test_positive_tcp_options(tcp_options):

    tcp_options_example = TCPOption.model_validate(tcp_options)
    assert isinstance(tcp_options_example, TCPOption)
    assert tcp_options_example.tcp_profile_id == 1


def test_positive_tcp_profile_invalid():

    tcp_socket = {
        "endpoint_address": "10.0.0.1",
        "name": "my_socket",
        "port_no": 123,
        "tcp_profile": 3,
        "protocol": "tcp",
    }
    tcp_example = SocketTCP.model_validate(tcp_socket)
    assert isinstance(tcp_example, SocketTCP)
    assert str(tcp_example.endpoint_address) == "10.0.0.1"
    assert tcp_example.name == "my_socket"
    assert tcp_example.port_no == 123
    assert tcp_example.protocol == "tcp"
    assert tcp_example.tcp_profile == 3


@pytest.mark.parametrize(
    "tcp_options, expected_fragment",
    [
        pytest.param(
            {
                "tcp_profile_id": 1,
                "no_delay": "Off",
            },
            "Extra inputs are not permitted",
            id="Test No delay",
        ),
        pytest.param(
            {
                "tcp_profile_id": 1,
                "keepalive_enabled": "Off",
            },
            "Input should be a valid boolean",
            id="Test Keepalive enabled",
        ),
        pytest.param(
            {
                "tcp_profile_id": 1,
                "keepidle": "five",
            },
            "Input should be a valid integer",
            id="Test Keep Idle",
        ),
        pytest.param(
            {
                "tcp_profile_id": 1,
                "keepcount": "five",
            },
            "Input should be a valid integer",
            id="Test Keep count",
        ),
        pytest.param(
            {
                "tcp_profile_id": 1,
                "keepintvl": "one",
            },
            "Input should be a valid integer",
            id="Test Keep Interval",
        ),
        pytest.param(
            {
                "tcp_profile_id": 1,
                "user_timeout": "fourteen",
            },
            "Input should be a valid integer",
            id="Test User timeout",
        ),
        pytest.param(
            {
                "tcp_profile_id": 1,
                "congestion_avoidance": "cuboid",
            },
            "Input should be 'reno', 'cubic' or 'bbr'",
            id="Test Congestion avoidance",
        ),
        pytest.param(
            {
                "tcp_profile_id": 1,
                "tcp_maxseg": "2 thousand",
            },
            "Input should be a valid integer",
            id="Test Max Segment",
        ),
        pytest.param(
            {
                "tcp_profile_id": 1,
                "tcp_quickack": "no",
            },
            "Input should be a valid boolean",
            id="Test Quickack",
        ),
        pytest.param(
            {
                "tcp_profile_id": 1,
                "tcp_syncnt": "four",
            },
            "Input should be a valid integer",
            id="Test SYNC retries",
        ),
        pytest.param(
            {"tcp_syncnt": 4},
            "Field required",
            id="No TCP profile",
        ),
        pytest.param(
            {
                "tcp_profile_id": 1,
                "tcp_ack_retries": 4,
            },
            "Extra inputs are not permitted",
            id="Extra input",
        ),
    ],
)
def test_negative_tcp_options(tcp_options, expected_fragment):

    with pytest.raises(ValidationError) as exc_info:
        TCPOption.model_validate(tcp_options)
    assert_single_error(exc_info, None, expected_fragment)


def test_tcp_socket_is_instance_of_socket(tcp_socket_entry_ipv4):
    assert isinstance(tcp_socket_entry_ipv4, Socket)
    assert str(tcp_socket_entry_ipv4.endpoint_address) == "10.0.1.1"
    assert tcp_socket_entry_ipv4.name == "my_socket"
    assert tcp_socket_entry_ipv4.port_no == 4400
    assert tcp_socket_entry_ipv4.protocol == "tcp"


def test_udp_socket_is_instance_of_socket(udp_socket_entry_ipv4):
    assert isinstance(udp_socket_entry_ipv4, Socket)
    assert str(udp_socket_entry_ipv4.endpoint_address) == "10.0.1.1"
    assert udp_socket_entry_ipv4.name == "my_socket"
    assert udp_socket_entry_ipv4.port_no == 4400
    assert udp_socket_entry_ipv4.protocol == "udp"


def test_ipv4_address_endpoint_with_tcp_and_udp_sockets(tcp_socket_entry_ipv4, udp_socket_entry_ipv4):
    ip_obj = {
        "address": "10.0.1.1",
        "ipv4netmask": "224.0.0.1",
        "sockets": [tcp_socket_entry_ipv4, udp_socket_entry_ipv4],
    }
    ip_obj = IPv4AddressEndpoint.model_validate(ip_obj)
    assert isinstance(ip_obj, IPv4AddressEndpoint)
    assert str(ip_obj.address) == "10.0.1.1"
    assert str(ip_obj.ipv4netmask) == "224.0.0.1"
    assert len(ip_obj.sockets) == 2
    assert {s.protocol for s in ip_obj.sockets} == {"tcp", "udp"}
    assert all(str(s.endpoint_address) == "10.0.1.1" for s in ip_obj.sockets)


def test_ipv6_address_endpoint_with_tcp_and_udp_sockets(tcp_socket_entry_ipv6, udp_socket_entry_ipv6):
    ip_obj = {
        "address": "2001:0db8:85a3:0000:0000:8a2e:0370:7334",
        "ipv6prefix": 64,
        "sockets": [tcp_socket_entry_ipv6, udp_socket_entry_ipv6],
    }
    ip_obj = IPv6AddressEndpoint.model_validate(ip_obj)
    assert isinstance(ip_obj, IPv6AddressEndpoint)
    assert str(ip_obj.address) == "2001:db8:85a3::8a2e:370:7334"
    assert ip_obj.ipv6prefix == 64
    assert len(ip_obj.sockets) == 2
    assert {s.protocol for s in ip_obj.sockets} == {"tcp", "udp"}
    assert all(str(s.endpoint_address) == "2001:db8:85a3::8a2e:370:7334" for s in ip_obj.sockets)


def test_negative_ipv4_address_endpoint_with_tcp_and_udp_sockets(tcp_socket_entry_ipv6, udp_socket_entry_ipv6):
    ip_obj = {
        "address": "10.0.1.1",
        "ipv4netmask": "224.0.0.1",
        "sockets": [tcp_socket_entry_ipv6, udp_socket_entry_ipv6],
    }
    with pytest.raises(ValidationError) as exc_info:
        IPv4AddressEndpoint.model_validate(ip_obj)
    assert_single_error(exc_info, "FLYNC-ECU-MIN-CONS-085", "Sockets must be tied to the same address as the IPv4 endpoint.")


def test_negative_ipv6_address_endpoint_with_tcp_and_udp_sockets(tcp_socket_entry_ipv4, udp_socket_entry_ipv4):
    ip_obj = {
        "address": "2001:0db8:85a3:0000:0000:8a2e:0370:7334",
        "ipv6prefix": 64,
        "sockets": [tcp_socket_entry_ipv4, udp_socket_entry_ipv4],
    }
    with pytest.raises(ValidationError) as exc_info:
        IPv6AddressEndpoint.model_validate(ip_obj)
    assert_single_error(exc_info, "FLYNC-ECU-MIN-CONS-086", "Sockets must be tied to the same address as the IPv6 endpoint.")


@pytest.mark.parametrize(
    "deployments",
    [
        pytest.param(
            lambda: [
                SOMEIPServiceConsumer(
                    service=1,
                    someip_sd_timings_profile="client_default",
                    instance_id=1,
                )
            ],
            id="SOME/IP consumer deployment on socket",
        ),
        pytest.param(
            lambda: [
                SOMEIPServiceProvider(
                    service=1,
                    someip_sd_timings_profile="server_default",
                    instance_id=1,
                    major_version=1,
                )
            ],
            id="SOME/IP provider deployment on socket",
        ),
    ],
)
def test_sockets_deployments(
    metadata_entry,
    deployments,
    someip_sd_server_timings_profile_entry,
    someip_sd_client_timings_profile_entry,
):
    s = SOMEIPServiceInterface(meta=metadata_entry, name="s", id=1, major_version=1)
    deploy = deployments()
    udp_socket = {
        "endpoint_address": "10.0.0.1",
        "name": "my_socket",
        "port_no": 123,
        "udp_options": {"udp_cork": False},
        "protocol": "udp",
        "deployments": deploy,
    }
    udp_example = SocketUDP.model_validate(udp_socket)
    assert isinstance(udp_example, Socket)
    assert str(udp_example.endpoint_address) == "10.0.0.1"
    assert udp_example.name == "my_socket"
    assert udp_example.port_no == 123
    assert udp_example.protocol == "udp"
    assert udp_example.udp_options.udp_cork is False
    assert len(udp_example.deployments) == 1


def test_someip_consumer_rejects_unknown_multicast_field():
    """SOMEIPServiceConsumer carries no multicast field - eventgroup multicast lives on the provider."""

    find_service_multicast = MulticastEndpoint(ip_address="224.0.0.1", port=4444)

    with pytest.raises(ValidationError) as exc_info:
        SOMEIPServiceConsumer(
            service=1,
            someip_sd_timings_profile="client_default",
            instance_id=1,
            find_service_multicast=find_service_multicast,
        )
    # No error id: the unknown field is rejected by Pydantic's extra='forbid', not by a FLYNC validator, and the
    # field name shows up in the error location rather than in the message.
    assert_single_error(exc_info, None, "find_service_multicast")
