import pytest
from pydantic import ValidationError

from flync.model.flync_4_ecu.controller import (
    ControllerInterface,
    VirtualControllerInterface,
)
from flync.model.flync_4_ecu.sockets import (
    IPv4AddressEndpoint,
    IPv6AddressEndpoint,
)


def test_positive_controller_viface_single_ipv4(
    ipv4_addressendpoint: IPv4AddressEndpoint,
):
    virtual_iface = {
        "name": "viface_test",
        "vlanid": 20,
        "addresses": [ipv4_addressendpoint],
        "multicast": ["224.0.0.1"],
    }
    controller_iface = ControllerInterface.model_validate(
        {
            "name": "controller_iface",
            "mac_address": "00:11:22:33:44:55",
            "virtual_interfaces": [virtual_iface],
        }
    )
    assert isinstance(
        controller_iface.virtual_interfaces[0], VirtualControllerInterface
    )


def test_positive_controller_viface_single_ipv6(
    ipv6_address_endpoint: IPv6AddressEndpoint,
):
    virtual_iface = {
        "name": "viface_test",
        "vlanid": 20,
        "addresses": [ipv6_address_endpoint],
        "multicast": ["224.0.0.1"],
    }
    controller_iface = ControllerInterface.model_validate(
        {
            "name": "controller_iface",
            "mac_address": "00:11:22:33:44:55",
            "virtual_interfaces": [virtual_iface],
        }
    )
    assert isinstance(
        controller_iface.virtual_interfaces[0], VirtualControllerInterface
    )


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
    controller_iface = ControllerInterface.model_validate(
        {
            "name": "controller_iface",
            "mac_address": "00:11:22:33:44:55",
            "virtual_interfaces": [virtual_iface],
        }
    )
    for viface in controller_iface.virtual_interfaces:
        assert isinstance(viface, VirtualControllerInterface)


def test_negative_controller_viface_wrong_vlanid(
    ipv4_entry: IPv4AddressEndpoint,
):
    virtual_iface = {
        "name": "viface_test",
        "vlanid": 4096,
        "addresses": [IPv4AddressEndpoint],
        "multicast": ["224.0.0.1"],
    }
    with pytest.raises(ValidationError) as e:
        controller_iface = ControllerInterface.model_validate(
            {
                "name": "controller_iface",
                "mac_address": "00:11:22:33:44:55",
                "virtual_interfaces": [virtual_iface],
            }
        )


def test_positive_controller_viface_empty_addresses():
    virtual_iface = {
        "name": "viface_test",
        "vlanid": 20,
        "addresses": [],
        "multicast": ["224.0.0.1"],
    }

    controller_iface = ControllerInterface.model_validate(
        {
            "name": "controller_iface",
            "mac_address": "00:11:22:33:44:55",
            "virtual_interfaces": [virtual_iface],
        }
    )


def test_negative_controller_viface_missing_addresses():
    virtual_iface = {
        "name": "viface_test",
        "vlanid": 20,
        "multicast": ["224.0.0.1"],
    }
    with pytest.raises(ValidationError) as e:
        controller_iface = ControllerInterface.model_validate(
            {
                "name": "controller_iface",
                "mac_address": "00:11:22:33:44:55",
                "virtual_interfaces": [virtual_iface],
            }
        )


def test_negative_controller_viface_unicast_as_multicast(
    ipv4_addressendpoint: IPv4AddressEndpoint,
):
    virtual_iface = {
        "name": "viface_test",
        "addresses": [ipv4_addressendpoint],
        "vlanid": 20,
        "multicast": ["10.0.0.1"],
    }
    with pytest.raises(ValidationError) as e:
        controller_iface = ControllerInterface.model_validate(
            {
                "name": "controller_iface",
                "mac_address": "00:11:22:33:44:55",
                "virtual_interfaces": [virtual_iface],
            }
        )
