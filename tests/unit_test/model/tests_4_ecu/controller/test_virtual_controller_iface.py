from flync.core.utils.exceptions_handling import validate_with_policy
from flync.model.flync_4_ecu.controller import (
    EthernetInterface,
    VirtualControllerInterface,
)
from flync.model.flync_4_ecu.sockets import (
    IPv4AddressEndpoint,
    IPv6AddressEndpoint,
)
from tests.error_assertions import assert_single_warning


def test_positive_controller_viface_single_ipv4(
    ipv4_addressendpoint: IPv4AddressEndpoint,
):
    virtual_iface = {
        "name": "viface_test",
        "vlanid": 20,
        "addresses": [ipv4_addressendpoint],
        "multicast": ["224.0.0.1"],
    }
    eth_iface = EthernetInterface.model_validate(
        {
            "name": "iface1",
            "interface_config": {
                "mac_address": "00:11:22:33:44:55",
                "virtual_interfaces": [virtual_iface],
            },
        }
    )
    assert isinstance(eth_iface.interface_config.virtual_interfaces[0], VirtualControllerInterface)


def test_positive_controller_viface_single_ipv6(
    ipv6_address_endpoint: IPv6AddressEndpoint,
):
    virtual_iface = {
        "name": "viface_test",
        "vlanid": 20,
        "addresses": [ipv6_address_endpoint],
        "multicast": ["224.0.0.1"],
    }
    eth_iface = EthernetInterface.model_validate(
        {
            "name": "iface1",
            "interface_config": {
                "mac_address": "00:11:22:33:44:55",
                "virtual_interfaces": [virtual_iface],
            },
        }
    )
    assert isinstance(eth_iface.interface_config.virtual_interfaces[0], VirtualControllerInterface)


def test_positive_controller_viface_mixed_ipv4_ipv6(
    ipv4_addressendpoint: IPv4AddressEndpoint,
    ipv6_address_endpoint: IPv6AddressEndpoint,
):
    virtual_iface = {
        "name": "viface_test",
        "vlanid": 20,
        "addresses": [ipv6_address_endpoint, ipv4_addressendpoint],
        "multicast": ["224.0.0.1"],
    }
    eth_iface = EthernetInterface.model_validate(
        {
            "name": "iface1",
            "interface_config": {
                "mac_address": "00:11:22:33:44:55",
                "virtual_interfaces": [virtual_iface],
            },
        }
    )
    for viface in eth_iface.interface_config.virtual_interfaces:
        assert isinstance(viface, VirtualControllerInterface)


def test_negative_controller_viface_wrong_vlanid():
    """An out-of-range VLAN ID makes the virtual interface invalid, so it is dropped with a warning."""
    virtual_iface = {
        "name": "viface_test",
        "vlanid": 4096,
        "addresses": [],
        "multicast": ["224.0.0.1"],
    }
    result = validate_with_policy(
        EthernetInterface,
        {
            "name": "controller_iface",
            "interface_config": {
                "mac_address": "00:11:22:33:44:55",
                "virtual_interfaces": [virtual_iface],
            },
        },
        path=None,
    )
    assert_single_warning(result, None, "Removing virtual interface")
    assert "VLAN ID must be in the range 0-4094" in result[1][0]["ctx"]["sub_errors"]


def test_positive_controller_viface_empty_addresses():
    virtual_iface = {
        "name": "viface_test",
        "vlanid": 20,
        "addresses": [],
        "multicast": ["224.0.0.1"],
    }

    EthernetInterface.model_validate(
        {
            "name": "iface1",
            "interface_config": {
                "mac_address": "00:11:22:33:44:55",
                "virtual_interfaces": [virtual_iface],
            },
        }
    )


def test_negative_controller_viface_missing_addresses():
    """``addresses`` is a required field on the virtual interface, so a missing one is dropped with a warning."""
    virtual_iface = {
        "name": "viface_test",
        "vlanid": 20,
        "multicast": ["224.0.0.1"],
    }
    result = validate_with_policy(
        EthernetInterface,
        {
            "name": "controller_iface",
            "interface_config": {
                "mac_address": "00:11:22:33:44:55",
                "virtual_interfaces": [virtual_iface],
            },
        },
        path=None,
    )
    assert_single_warning(result, None, "Removing virtual interface")
    assert "addresses" in result[1][0]["ctx"]["sub_errors"]
    assert "Field required" in result[1][0]["ctx"]["sub_errors"]


def test_negative_controller_viface_unicast_as_multicast(
    ipv4_addressendpoint: IPv4AddressEndpoint,
):
    """A unicast address in ``multicast`` makes the virtual interface invalid, so it is dropped with a warning."""
    virtual_iface = {
        "name": "viface_test",
        "addresses": [ipv4_addressendpoint],
        "vlanid": 20,
        "multicast": ["10.0.0.1"],
    }
    result = validate_with_policy(
        EthernetInterface,
        {
            "name": "controller_iface",
            "interface_config": {
                "mac_address": "00:11:22:33:44:55",
                "virtual_interfaces": [virtual_iface],
            },
        },
        path=None,
    )
    assert_single_warning(result, None, "Removing virtual interface")
    assert "is not an IP Multicast" in result[1][0]["ctx"]["sub_errors"]
