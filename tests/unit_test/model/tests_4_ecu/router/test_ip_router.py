import pytest
from pydantic import ValidationError

from flync.core.base_models.base_model import FLYNCBaseModel
from flync.core.datatypes.ipaddress import IPv4AddressEntry, IPv6AddressEntry
from flync.model.flync_4_ecu.router import RouteEntry
from tests.error_assertions import assert_single_error


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

    assert_single_error(exc_info, None, "destination")


def test_route_entry_missing_gateway_field():
    invalid_data = {
        "destination": {"address": "10.0.0.0", "ipv4netmask": "255.255.255.0"},
        # default_gateway missing
        "egress_interface": "eth0",
    }

    with pytest.raises(ValidationError) as exc_info:
        RouteEntry(**invalid_data)

    assert_single_error(exc_info, None, "default_gateway")


def test_route_entry_missing_interface_field():
    invalid_data = {
        "destination": {"address": "10.0.0.0", "ipv4netmask": "255.255.255.0"},
        "default_gateway": "10.0.0.1",
        # egress_interface missing
    }

    with pytest.raises(ValidationError) as exc_info:
        RouteEntry(**invalid_data)

    assert_single_error(exc_info, None, "egress_interface")


def test_route_entry_missing_required_fields():
    with pytest.raises(ValidationError) as exc_info:
        RouteEntry()

    errors = exc_info.value.errors()
    assert len(errors) == 3
    assert {error["loc"][0] for error in errors} == {"destination", "default_gateway", "egress_interface"}


# Test negative: Test the class with wrong input format for the scalar fields.
def test_route_entry_invalid_gateway():
    invalid_data = {
        "destination": {"address": "10.0.0.0", "ipv4netmask": "255.255.255.0"},
        "default_gateway": "not-an-ip",  # invalid
        "egress_interface": "eth0",
    }

    with pytest.raises(ValidationError) as exc_info:
        RouteEntry(**invalid_data)

    assert_single_error(exc_info, None, "not a valid IPv4 or IPv6 address")


def test_route_entry_invalid_egress_interface():
    invalid_data = {
        "destination": {"address": "10.0.0.0", "ipv4netmask": "255.255.255.0"},
        "default_gateway": "10.0.0.1",
        "egress_interface": 123,  # should be str
    }

    with pytest.raises(ValidationError) as exc_info:
        RouteEntry(**invalid_data)

    assert_single_error(exc_info, None, "Input should be a valid string")


# Test negative: the destination and the gateway must share the same address family.
@pytest.mark.parametrize(
    "destination,gateway",
    [
        pytest.param(
            {"address": "10.0.0.0", "ipv4netmask": "255.255.255.0"},
            "2001:db8::1",
            id="ipv4_destination_ipv6_gateway",
        ),
        pytest.param(
            {"address": "2001:db8::", "ipv6prefix": "64"},
            "10.0.0.1",
            id="ipv6_destination_ipv4_gateway",
        ),
    ],
)
def test_route_entry_gateway_family_mismatch(destination, gateway):
    invalid_data = {
        "destination": destination,
        "default_gateway": gateway,
        "egress_interface": "eth0",
    }

    with pytest.raises(ValidationError) as exc_info:
        RouteEntry(**invalid_data)

    assert_single_error(exc_info, "FLYNC-ECU-MAJ-CONS-247", "does not belong to the same address family")
