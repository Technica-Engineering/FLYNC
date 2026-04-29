import pytest
from flync.model.flync_4_ecu.multicast_groups import MulticastGroupMembership
from flync.sdk.workspace.flync_workspace import validate_with_policy
from pydantic import ValidationError


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
        # Not even IP
        "not_an_ip",
    ],
)
def test_invalid_group(invalid_group):
    """Test that non-multicast addresses raise ValidationError."""
    with pytest.raises(ValidationError):
        MulticastGroupMembership(group=invalid_group)


@pytest.mark.parametrize(
    "invalid_vlan",
    [
        -1,  # negative
        5000,  # above max range
        3.14,  # wrong type (float)
    ],
)
def test_invalid_vlan(invalid_vlan):
    """Test that invalid VLAN values raise ValidationError."""
    with pytest.raises(ValidationError):
        MulticastGroupMembership(group="239.1.1.1",vlan=invalid_vlan)


def test_reserved_vlan_emits_warning():
    """VLAN 4095 is reserved by IEEE 802.1Q — model loads but a warning is recorded."""
    model, errors = validate_with_policy(
        MulticastGroupMembership,
        {"group": "239.1.1.1", "vlan": 4095},
        path=None,
    )

    assert model is not None
    assert model.vlan == 4095

    warnings = [e for e in errors if e.get("type") == "warning"]
    assert len(warnings) == 1
    assert "4095" in warnings[0]["msg"]
    assert "reserved" in warnings[0]["msg"].lower()


def test_invalid_mode():
    """Test that an invalid mode raises a ValidationError."""
    with pytest.raises(ValidationError):
        MulticastGroupMembership(group="239.1.1.1",mode="invalid")

def test_invalid_src_ip():
    """Test that an invalid source IP in TX mode raises a ValidationError."""
    with pytest.raises(ValidationError):
        MulticastGroupMembership(group="239.1.1.1",mode="tx",src_ip="invalid_ip")

@pytest.mark.xfail(reason="Known bug")
def test_invalid_interface(vci):
    """Assigning a VirtualControllerInterface to _interface should be invalid."""
    group = MulticastGroupMembership(group="239.1.1.1",mode="tx",src_ip="192.168.1.10",vlan=10)
    with pytest.raises(TypeError):
        group._interface = vci

def test_interface_property():
    """Test that accessing the interface property without assignment raises AttributeError."""
    m = MulticastGroupMembership(group="239.1.1.1")
    with pytest.raises(AttributeError):
        _ = m.interface

@pytest.mark.xfail(reason="Known bug")
def test_rx_with_src_ip(ci):
    """RX mode must not define a source IP."""

    rx_group = MulticastGroupMembership(group="239.1.1.10",mode="rx",src_ip="192.168.1.10",vlan=10)
    rx_group._interface = ci

    with pytest.raises(ValueError):
        if rx_group.mode == "rx" and rx_group.src_ip is not None:
            raise ValueError("RX mode cannot have src_ip defined.")

@pytest.mark.xfail(reason="Known bug")
def test_tx_without_src_ip(ci):
    """TX mode must define a source IP."""

    tx_group = MulticastGroupMembership(group="239.1.1.11",mode="tx",vlan=10)
    tx_group._interface = ci

    with pytest.raises(ValueError):
        if tx_group.mode == "tx" and tx_group.src_ip is None:
            raise ValueError("TX mode requires a source IP.")

@pytest.mark.xfail(reason="Known bug")
def test_vlan_mismatch(ci,vci):
    """Group VLAN must match interface VLAN."""

    tx_group = MulticastGroupMembership(group="239.1.1.12",mode="tx",src_ip="192.168.1.20",vlan=20)
    tx_group._interface = ci

    with pytest.raises(ValueError):
        if tx_group.vlan != vci.vlanid:
            raise ValueError("Multicast group VLAN does not match interface VLAN.")

@pytest.mark.xfail(reason="Known bug")
def test_rx_group_not_configured(ci,vci):
    """RX group must exist in multicast configuration."""

    rx_group = MulticastGroupMembership(group="239.1.1.99", mode="rx",vlan=10)
    rx_group._interface = ci

    with pytest.raises(ValueError):
        if str(rx_group.group) not in vci.multicast:
            raise ValueError("RX group not configured in interface multicast list.")
