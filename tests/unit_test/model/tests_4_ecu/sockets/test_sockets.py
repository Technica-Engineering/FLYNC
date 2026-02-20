import pytest
from pydantic import ValidationError

from flync.model.flync_4_ecu.sockets import *
from flync.model.flync_4_someip.deployment import (
    MulticastEndpoint,
    SOMEIPServiceConsumer,
    SOMEIPServiceProvider,
)
from flync.model.flync_4_someip.service_interface import SOMEIPServiceInterface


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

    print(udp_socket)
    with pytest.raises(ValidationError) as e:
        udp_example = SocketUDP.model_validate(udp_socket)


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
                "tcp_profile": 3,
                "protocol": "tcp",
            },
            id="Invalid TCP profile",
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
    print(tcp_socket)
    with pytest.raises(ValidationError) as e:
        tcp_example = SocketTCP.model_validate(tcp_socket)


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


@pytest.mark.parametrize(
    "tcp_options",
    [
        pytest.param(
            {
                "tcp_profile_id": 1,
                "no_delay": "Off",
            },
            id="Test No delay",
        ),
        pytest.param(
            {
                "tcp_profile_id": 1,
                "keepalive_enabled": "Off",
            },
            id="Test Keepalive enabled",
        ),
        pytest.param(
            {
                "tcp_profile_id": 1,
                "keepidle": "five",
            },
            id="Test Keep Idle",
        ),
        pytest.param(
            {
                "tcp_profile_id": 1,
                "keepcount": "five",
            },
            id="Test Keep count",
        ),
        pytest.param(
            {
                "tcp_profile_id": 1,
                "keepintvl": "one",
            },
            id="Test Keep Interval",
        ),
        pytest.param(
            {
                "tcp_profile_id": 1,
                "user_timeout": "fourteen",
            },
            id="Test User timeout",
        ),
        pytest.param(
            {
                "tcp_profile_id": 1,
                "congestion_avoidance": "cuboid",
            },
            id="Test Congestion avoidance",
        ),
        pytest.param(
            {
                "tcp_profile_id": 1,
                "tcp_maxseg": "2 thousand",
            },
            id="Test Max Segment",
        ),
        pytest.param(
            {
                "tcp_profile_id": 1,
                "tcp_quickack": "no",
            },
            id="Test Quickack",
        ),
        pytest.param(
            {
                "tcp_profile_id": 1,
                "tcp_syncnt": "four",
            },
            id="Test SYNC retries",
        ),
        pytest.param(
            {"tcp_syncnt": 4},
            id="No TCP profile",
        ),
        pytest.param(
            {
                "tcp_profile_id": 1,
                "tcp_ack_retries": 4,
            },
            id="Extra input",
        ),
    ],
)
def test_negative_tcp_options(tcp_options):

    with pytest.raises(ValidationError) as e:
        tcp_option_example = TCPOption.model_validate(tcp_options)


def test_tcp_socket_is_instance_of_socket(tcp_socket_entry_ipv4):
    assert isinstance(tcp_socket_entry_ipv4, Socket)


def test_udp_socket_is_instance_of_socket(udp_socket_entry_ipv4):
    assert isinstance(udp_socket_entry_ipv4, Socket)


def test_ipv4_address_endpoint_with_tcp_and_udp_sockets(
    tcp_socket_entry_ipv4, udp_socket_entry_ipv4
):
    ip_obj = {
        "address": "10.0.1.1",
        "ipv4netmask": "224.0.0.1",
        "sockets": [tcp_socket_entry_ipv4, udp_socket_entry_ipv4],
    }
    ip_obj = IPv4AddressEndpoint.model_validate(ip_obj)
    assert isinstance(ip_obj, IPv4AddressEndpoint)


def test_ipv6_address_endpoint_with_tcp_and_udp_sockets(
    tcp_socket_entry_ipv6, udp_socket_entry_ipv6
):
    ip_obj = {
        "address": "2001:0db8:85a3:0000:0000:8a2e:0370:7334",
        "ipv6prefix": 64,
        "sockets": [tcp_socket_entry_ipv6, udp_socket_entry_ipv6],
    }
    ip_obj = IPv6AddressEndpoint.model_validate(ip_obj)
    assert isinstance(ip_obj, IPv6AddressEndpoint)


def test_negative_ipv4_address_endpoint_with_tcp_and_udp_sockets(
    tcp_socket_entry_ipv6, udp_socket_entry_ipv6
):
    ip_obj = {
        "address": "10.0.1.1",
        "ipv4netmask": "224.0.0.1",
        "sockets": [tcp_socket_entry_ipv6, udp_socket_entry_ipv6],
    }
    with pytest.raises(ValidationError) as e:
        ip_obj = IPv4AddressEndpoint.model_validate(ip_obj)


def test_negative_ipv6_address_endpoint_with_tcp_and_udp_sockets(
    tcp_socket_entry_ipv4, udp_socket_entry_ipv4
):
    ip_obj = {
        "address": "2001:0db8:85a3:0000:0000:8a2e:0370:7334",
        "ipv6prefix": 64,
        "sockets": [tcp_socket_entry_ipv4, udp_socket_entry_ipv4],
    }
    with pytest.raises(ValidationError) as e:
        ip_obj = IPv6AddressEndpoint.model_validate(ip_obj)


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
    s = SOMEIPServiceInterface(meta=metadata_entry, name="s", id=1)
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


def test_tcp_socket_with_multicast_deployment():
    tcp_options = TCPOption(tcp_profile_id=1)

    with pytest.raises(ValidationError) as e:
        tcp_socket_entry_ipv6 = SocketTCP(
            endpoint_address="2001:0db8:85a3:0000:0000:8a2e:0370:7334",
            name="my_socket",
            port_no=4400,
            tcp_profile=1,
            protocol="tcp",
            deployments=[
                SOMEIPServiceConsumer(
                    service=1,
                    someip_sd_timings_profile="client_default",
                    instance_id=1,
                    find_service_multicast=MulticastEndpoint(
                        ip_address="224.0.0.1", port=4444
                    ),
                )
            ],
        )
