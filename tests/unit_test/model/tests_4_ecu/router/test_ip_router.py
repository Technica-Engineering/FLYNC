import pytest
from pydantic import ValidationError

from flync.core.base_models.base_model import FLYNCBaseModel
from flync.core.datatypes.ipaddress import IPv4AddressEntry, IPv6AddressEntry
from flync.model.flync_4_ecu.router import RouteEntry


# Test if the class can be bound to parent class.
def test_class_inherits_from_base_model():
    assert issubclass(RouteEntry, FLYNCBaseModel)


# Test positive: Test the class with only required fields.
def test_route_entry_required_fields_only_ipv4():
    route = RouteEntry(
        destination=IPv4AddressEntry(address="10.0.0.0", ipv4netmask="255.255.255.0"), default_gateway="10.0.0.1", egress_interface="eth0"
    )

    assert route.egress_interface == "eth0"
    assert str(route.destination.address) == "10.0.0.0"
    assert str(route.default_gateway) == "10.0.0.1"


def test_route_entry_required_fields_only_ipv6():
    route = RouteEntry(destination=IPv6AddressEntry(address="2001:db8::", ipv6prefix="64"), default_gateway="2001:db8::1", egress_interface="eth1")

    assert route.egress_interface == "eth1"
    assert str(route.destination.address) == "2001:db8::"
    assert str(route.default_gateway) == "2001:db8::1"


# Test Negative: Test the class with missing required fields.
def test_route_entry_missing_destination_field():
    invalid_data = {
        # destination missing
        "default_gateway": "10.0.0.1",
        "egress_interface": "eth0",
    }

    with pytest.raises(ValidationError) as exc_info:
        RouteEntry(**invalid_data)

    assert "destination" in str(exc_info.value)


def test_route_entry_missing_gateway_field():
    invalid_data = {
        "destination": {"address": "10.0.0.0", "ipv4netmask": "255.255.255.0"},
        # default_gateway missing
        "egress_interface": "eth0",
    }

    with pytest.raises(ValidationError) as exc_info:
        RouteEntry(**invalid_data)

    assert "default_gateway" in str(exc_info.value)


def test_route_entry_missing_interface_field():
    invalid_data = {
        "destination": {"address": "10.0.0.0", "ipv4netmask": "255.255.255.0"},
        "default_gateway": "10.0.0.1",
        # egress_interface missing
    }

    with pytest.raises(ValidationError) as exc_info:
        RouteEntry(**invalid_data)

    assert "egress_interface" in str(exc_info.value)


def test_route_entry_missing_required_fields():
    invalid_data = {
        # destination missing
        # default_gateway missing
        # egress_interface missing
    }

    with pytest.raises(ValidationError) as exc_info:
        RouteEntry(**invalid_data)

    error_msg = str(exc_info.value)

    assert "destination" in error_msg
    assert "default_gateway" in error_msg
    assert "egress_interface" in error_msg


# Test negative: Test the class with wrong input format for all the fields.
def test_route_entry_invalid_destination_ip():
    invalid_data = {
        "destination": {"address": "999.999.999.999", "ipv4netmask": "255.255.255.0"},  # invalid IP
        "default_gateway": "10.0.0.1",
        "egress_interface": "eth0",
    }

    with pytest.raises(ValidationError):
        RouteEntry(**invalid_data)


def test_route_entry_invalid_netmask():
    invalid_data = {
        "destination": {"address": "10.0.0.0", "ipv4netmask": "255.255.0"},  # invalid format
        "default_gateway": "10.0.0.1",
        "egress_interface": "eth0",
    }

    with pytest.raises(ValidationError):
        RouteEntry(**invalid_data)


def test_route_entry_invalid_gateway():
    invalid_data = {
        "destination": {"address": "10.0.0.0", "ipv4netmask": "255.255.255.0"},
        "default_gateway": "not-an-ip",  # invalid
        "egress_interface": "eth0",
    }

    with pytest.raises(ValidationError):
        RouteEntry(**invalid_data)


def test_route_entry_invalid_egress_interface():
    invalid_data = {
        "destination": {"address": "10.0.0.0", "ipv4netmask": "255.255.255.0"},
        "default_gateway": "10.0.0.1",
        "egress_interface": 123,  # should be str
    }

    with pytest.raises(ValidationError):
        RouteEntry(**invalid_data)


def test_route_entry_ipv6_in_ipv4_destination():
    invalid_data = {
        "destination": {"address": "2001:db8::1", "ipv4netmask": "255.255.255.0"},  # IPv6 in IPv4 field
        "default_gateway": "10.0.0.1",
        "egress_interface": "eth0",
    }

    with pytest.raises(ValidationError):
        RouteEntry(**invalid_data)


@pytest.mark.xfail(reason="FLYNC-1112")
def test_route_entry_ipv4_ipv6_mismatch():
    invalid_data = {
        "destination": {"address": "10.0.0.0", "ipv4netmask": "255.255.255.0"},
        "default_gateway": "2001:db8::1",  # IPv6 gateway mismatch
        "egress_interface": "eth0",
    }

    with pytest.raises(ValidationError):
        RouteEntry(**invalid_data)


def test_route_entry_multiple_invalid_fields():
    invalid_data = {
        "destination": {"address": "999.999.999.999", "ipv4netmask": "bad-mask"},
        "default_gateway": "not-an-ip",
        "egress_interface": 999,
    }

    with pytest.raises(ValidationError):
        RouteEntry(**invalid_data)
