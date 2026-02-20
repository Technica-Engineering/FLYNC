import pytest
from pydantic import ValidationError

from flync.model.flync_4_ecu.controller import VirtualControllerInterface
from flync.model.flync_4_ecu.sockets import (
    IPv4AddressEndpoint,
    IPv6AddressEndpoint,
)


def test_positive_ipv4address():
    ip_address_entry = {
        "address": "10.0.0.100",
        "ipv4netmask": "255.255.255.0",
    }
    viface = VirtualControllerInterface.model_validate(
        {"name": "valid_iface", "vlanid": 10, "addresses": [ip_address_entry]}
    )
    assert isinstance(viface.addresses[0], IPv4AddressEndpoint)


def test_positive_ipv6address():
    ip_address_entry = {
        "address": "2001:0db8:85a3:0000:0000:8a2e:0370:7334",
        "ipv6prefix": 128,
    }
    viface = VirtualControllerInterface.model_validate(
        {"name": "valid_iface", "vlanid": 10, "addresses": [ip_address_entry]}
    )
    assert isinstance(viface.addresses[0], IPv6AddressEndpoint)


def test_negative_ipv4_address_wrong_range():
    ip_address_entry = {
        "address": "10.0.0.256",
        "ipv4netmask": "255.255.255.0",
    }
    with pytest.raises(ValidationError) as err:
        viface = VirtualControllerInterface.model_validate(
            {
                "name": "valid_iface",
                "vlanid": 10,
                "addresses": [ip_address_entry],
            }
        )


def test_negative_ipv6_address_wrong_range():
    ip_address_entry = {
        "address": "2001:0db8:85a3:0000:0000:8a2e:0370:73345",
        "ipv6prefix": 128,
    }
    with pytest.raises(ValidationError) as err:
        viface = VirtualControllerInterface.model_validate(
            {
                "name": "valid_iface",
                "vlanid": 10,
                "addresses": [ip_address_entry],
            }
        )


def test_negative_ipv4_netmask_wrong_range():
    ip_address_entry = {
        "address": "10.0.0.100",
        "ipv4netmask": "255.255.256.0",
    }
    with pytest.raises(ValidationError) as err:
        viface = VirtualControllerInterface.model_validate(
            {
                "name": "valid_iface",
                "vlanid": 10,
                "addresses": [ip_address_entry],
            }
        )


def test_negative_ipv6_prefix_wrong_range():
    ip_address_entry = {
        "address": "2001:0db8:85a3:0000:0000:8a2e:0370:7334",
        "ipv6prefix": 129,
    }
    with pytest.raises(ValidationError) as err:
        viface = VirtualControllerInterface.model_validate(
            {
                "name": "valid_iface",
                "vlanid": 10,
                "addresses": [ip_address_entry],
            }
        )


def test_negative_ipv4_address_with_ipv6prefix():
    ip_address_entry = {"address": "10.0.0.100", "ipv6prefix": "255.255.255.0"}
    with pytest.raises(ValidationError) as err:
        viface = VirtualControllerInterface.model_validate(
            {
                "name": "valid_iface",
                "vlanid": 10,
                "addresses": [ip_address_entry],
            }
        )


def test_negative_ipv6_address_with_ipv4netmask():
    ip_address_entry = {
        "address": "2001:0db8:85a3:0000:0000:8a2e:0370:7334",
        "ipv4netmask": 128,
    }
    with pytest.raises(ValidationError) as err:
        viface = VirtualControllerInterface.model_validate(
            {
                "name": "valid_iface",
                "vlanid": 10,
                "addresses": [ip_address_entry],
            }
        )
