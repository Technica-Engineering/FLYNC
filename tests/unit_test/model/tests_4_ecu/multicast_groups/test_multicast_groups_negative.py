import pytest
from pydantic import ValidationError

from flync.core.utils.exceptions_handling import validate_with_policy
from flync.model.flync_4_ecu.multicast_groups import MulticastGroupMembership
from tests.error_assertions import assert_single_error, assert_single_warning


@pytest.mark.parametrize(
    "invalid_group",
    [
        # IPv4 unicast (private)
        "192.168.1.1",
        "10.0.0.1",
        "172.16.0.1",
        # IPv4 special
        "127.0.0.1",  # loopback
        "169.254.1.1",  # link-local
        "255.255.255.255",  # broadcast
        "8.8.8.8",  # public unicast
        # IPv6 unicast
        "2001:db8::1",  # documentation/global
        "::1",  # loopback
        "fe80::1",  # link-local
        "::",  # unspecified
    ],
)
def test_invalid_group(invalid_group):
    """Test that non-multicast addresses raise ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        MulticastGroupMembership(group=invalid_group)

    assert_single_error(exc_info, "FLYNC-CMN-MIN-FMT-006", "is not an IP Multicast")


@pytest.mark.parametrize(
    "invalid_mac_group",
    [
        "00:11:22:33:44:55",  # unicast (first byte LSB = 0)
        "02:00:00:00:00:01",  # unicast (first byte LSB = 0)
    ],
)
def test_invalid_group_mac_not_multicast(invalid_mac_group):
    """Test that a well-formed unicast MAC group is rejected as a non-multicast address."""
    with pytest.raises(ValidationError) as exc_info:
        MulticastGroupMembership(group=invalid_mac_group)

    assert_single_error(
        exc_info,
        "FLYNC-CMN-MIN-FMT-005",
        "is not a MAC Multicast. The first byte's least significant bit should be 1",
    )


@pytest.mark.parametrize(
    "invalid_vlan",
    [
        -1,  # negative
        5000,  # above max range
    ],
)
def test_invalid_vlan(invalid_vlan):
    """Test that invalid VLAN values raise ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        MulticastGroupMembership(group="239.1.1.1", vlan=invalid_vlan)

    assert_single_error(exc_info, "FLYNC-CMN-MIN-VAL-002", "VLAN ID must be in the range 0-4094")


def test_invalid_vlan_float():
    """Test that a float VLAN value raises ValidationError with a type error."""
    with pytest.raises(ValidationError) as exc_info:
        MulticastGroupMembership(group="239.1.1.1", vlan=3.14)

    assert_single_error(exc_info, None, "vlan: Input should be a valid integer")


def test_reserved_vlan_emits_warning():
    """VLAN 4095 is reserved by IEEE 802.1Q — model loads but a warning is recorded."""
    result = validate_with_policy(
        MulticastGroupMembership,
        {"group": "239.1.1.1", "vlan": 4095},
        path=None,
    )

    assert_single_warning(result, "FLYNC-CMN-WARN-VAL-003", "reserved")


def test_invalid_mode():
    """Test that an invalid mode raises a ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        MulticastGroupMembership(group="239.1.1.1", mode="invalid")

    errors = exc_info.value.errors()
    assert len(errors) >= 2
    # The error locations are nested: ('mode', "literal['tx']") and ('mode', "literal['rx']")
    # Check that at least one error is for the 'mode' field with literal_error type
    mode_errors = [e for e in errors if "mode" in str(e["loc"]) and e["type"] == "literal_error"]
    assert len(mode_errors) >= 2
    # Verify specific error details
    err_types = {e["type"] for e in mode_errors}
    assert err_types == {"literal_error"}


def test_invalid_src_ip():
    """Test that an invalid source IP in TX mode raises a ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        MulticastGroupMembership(group="239.1.1.1", mode="tx", src_ip="invalid_ip")

    assert_single_error(exc_info, None, "src_ip: value is not a valid IPv4 or IPv6 address")


def test_interface_property():
    """Test that accessing the interface property without assignment raises AttributeError."""
    m = MulticastGroupMembership(group="239.1.1.1")
    with pytest.raises(AttributeError) as exc_info:
        _ = m.interface
    assert "interface" in str(exc_info.value).lower()


def test_tx_without_src_ip():
    """TX mode must define a source IP."""
    with pytest.raises(ValidationError) as exc_info:
        MulticastGroupMembership(group="239.1.1.11", mode="tx", src_ip=None, vlan=20)

    assert_single_error(exc_info, "FLYNC-ECU-MIN-REQ-080", "The field 'src_ip' must be defined for IP multicast senders!")
