import pytest
from pydantic import ValidationError

from flync.core.base_models.base_model import FLYNCBaseModel
from flync.core.datatypes.ipaddress import IPv4AddressEntry, IPv6AddressEntry
from flync.model.flync_4_ecu.router import RouteEntry
from tests.error_assertions import assert_single_error


# Test if the class can be bound to parent class.
def test_class_inherits_from_base_model():
    assert issubclass(RouteEntry, FLYNCBaseModel)


_IPV4_DESTINATION = {"address": "10.0.0.0", "ipv4netmask": "255.255.255.0"}


# Test positive: Test the class with only required fields.
@pytest.mark.parametrize(
    "destination, gateway, egress_interface",
    [
        pytest.param(IPv4AddressEntry(address="10.0.0.0", ipv4netmask="255.255.255.0"), "10.0.0.1", "eth0", id="ipv4"),
        pytest.param(IPv6AddressEntry(address="2001:db8::", ipv6prefix="64"), "2001:db8::1", "eth1", id="ipv6"),
    ],
)
def test_route_entry_required_fields_only(destination, gateway, egress_interface):
    route = RouteEntry(destination=destination, default_gateway=gateway, egress_interface=egress_interface)

    assert route.egress_interface == egress_interface
    assert str(route.destination.address) == str(destination.address)
    assert str(route.default_gateway) == gateway
    assert isinstance(route, RouteEntry)


# Test Negative: a required field is missing, or a scalar field has the wrong format.
@pytest.mark.parametrize(
    "invalid_data, message",
    [
        pytest.param({"default_gateway": "10.0.0.1", "egress_interface": "eth0"}, "destination", id="missing_destination"),
        pytest.param({"destination": _IPV4_DESTINATION, "egress_interface": "eth0"}, "default_gateway", id="missing_gateway"),
        pytest.param({"destination": _IPV4_DESTINATION, "default_gateway": "10.0.0.1"}, "egress_interface", id="missing_egress_interface"),
        pytest.param(
            {"destination": _IPV4_DESTINATION, "default_gateway": "not-an-ip", "egress_interface": "eth0"},
            "not a valid IPv4 or IPv6 address",
            id="gateway_is_not_an_ip",
        ),
        pytest.param(
            {"destination": _IPV4_DESTINATION, "default_gateway": "10.0.0.1", "egress_interface": 123},
            "Input should be a valid string",
            id="egress_interface_is_not_a_string",
        ),
    ],
)
def test_route_entry_invalid_field(invalid_data, message):
    with pytest.raises(ValidationError) as exc_info:
        RouteEntry(**invalid_data)

    assert_single_error(exc_info, None, message)


def test_route_entry_missing_required_fields():
    with pytest.raises(ValidationError) as exc_info:
        RouteEntry()

    errors = exc_info.value.errors()
    assert len(errors) == 3
    assert {error["loc"][0] for error in errors} == {"destination", "default_gateway", "egress_interface"}


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
