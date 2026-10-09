import pytest
from pydantic import ValidationError

from flync.model.flync_4_ecu.controller import VirtualControllerInterface
from flync.model.flync_4_ecu.sockets import (
    IPv4AddressEndpoint,
    IPv6AddressEndpoint,
)


def _viface_with(address_entry):
    """Build a virtual controller interface carrying one address entry."""
    return VirtualControllerInterface.model_validate({"name": "valid_iface", "vlanid": 10, "addresses": [address_entry]})


def _assert_union_error(exc_info, field, error_type):
    """Assert the address union reports ``error_type`` on ``field``.

    ``addresses`` is a union of the IPv4 and IPv6 endpoints, so a bad entry is reported once per branch and
    ``assert_single_error`` does not apply here. This pins the branch that describes the actual defect.
    """
    errors = exc_info.value.errors()
    matches = [error for error in errors if error["loc"][-1] == field and error["type"] == error_type]
    assert matches, f"expected a {error_type!r} error on {field!r}, got {[(error['loc'][-1], error['type']) for error in errors]}"


@pytest.mark.parametrize(
    "address_entry, expected_class",
    [
        pytest.param({"address": "10.0.0.100", "ipv4netmask": "255.255.255.0"}, IPv4AddressEndpoint, id="ipv4"),
        pytest.param({"address": "2001:0db8:85a3:0000:0000:8a2e:0370:7334", "ipv6prefix": 128}, IPv6AddressEndpoint, id="ipv6"),
    ],
)
def test_positive_address_entry(address_entry, expected_class):
    """An address entry resolves to the endpoint class of its own address family."""

    viface = _viface_with(address_entry)

    assert isinstance(viface.addresses[0], expected_class)


@pytest.mark.parametrize(
    "address_entry, field, error_type",
    [
        pytest.param({"address": "10.0.0.256", "ipv4netmask": "255.255.255.0"}, "address", "ip_v4_address", id="ipv4_address_wrong_range"),
        pytest.param(
            {"address": "2001:0db8:85a3:0000:0000:8a2e:0370:73345", "ipv6prefix": 128},
            "address",
            "ip_v6_address",
            id="ipv6_address_wrong_range",
        ),
        pytest.param({"address": "10.0.0.100", "ipv4netmask": "255.255.256.0"}, "ipv4netmask", "ip_v4_address", id="ipv4_netmask_wrong_range"),
        pytest.param(
            {"address": "2001:0db8:85a3:0000:0000:8a2e:0370:7334", "ipv6prefix": 129},
            "ipv6prefix",
            "less_than_equal",
            id="ipv6_prefix_above_128",
        ),
        # An IPv4 address may not carry an IPv6 prefix, and vice versa: the field is rejected as extra on its own family's branch.
        pytest.param({"address": "10.0.0.100", "ipv6prefix": "255.255.255.0"}, "ipv6prefix", "extra_forbidden", id="ipv4_address_with_ipv6prefix"),
        pytest.param(
            {"address": "2001:0db8:85a3:0000:0000:8a2e:0370:7334", "ipv4netmask": 128},
            "ipv4netmask",
            "extra_forbidden",
            id="ipv6_address_with_ipv4netmask",
        ),
    ],
)
def test_negative_address_entry(address_entry, field, error_type):
    """An address outside its range, or paired with the other family's netmask/prefix, is rejected."""

    with pytest.raises(ValidationError) as exc_info:
        _viface_with(address_entry)

    _assert_union_error(exc_info, field, error_type)
