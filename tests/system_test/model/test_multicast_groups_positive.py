import pytest
from ipaddress import IPv4Address
from flync.model.flync_4_ecu.multicast_groups import MulticastGroupMembership

def test_minimal_creation():
    """Test default creation of a MulticastGroupMembership and verify default attributes."""
    m = MulticastGroupMembership(group="239.1.1.1")
    assert str(m.group) == "239.1.1.1"
    assert m.description == ""
    assert m.vlan == 0
    assert m.src_ip is None
    assert m.solicited_node_multicast is False

@pytest.mark.parametrize("group", ["239.1.1.1","ff02::1",])
def test_valid_multicast_addresses(group):
    """Test that valid IPv4 and IPv6 multicast addresses are accepted."""
    m = MulticastGroupMembership(group=group)
    assert m.group is not None


@pytest.mark.parametrize("vlanid", ["100", 101, None])
def test_valid_vlan_assignment(vlanid):
    """Test that a VLAN ID can be assigned correctly."""
    m = MulticastGroupMembership(group="239.1.1.1", vlan=vlanid)
    if vlanid:
        assert m.vlan == int(vlanid)
    else:
        assert m.vlan == None


def test_valid_tx_group(ci):
    """TX group with correct VLAN and src_ip."""
    tx_group = MulticastGroupMembership(group="239.1.1.3",mode="tx",src_ip="192.168.1.20",vlan=10)
    tx_group._interface = ci

    assert tx_group.mode == "tx"
    assert str(tx_group.src_ip) == "192.168.1.20"
    assert tx_group.vlan == 10
    assert tx_group.interface == ci

def test_valid_rx_group(ci):
    """RX group must not define src_ip."""
    rx_group = MulticastGroupMembership(group="239.1.1.2",mode="rx",vlan=10)
    rx_group._interface = ci

    assert rx_group.mode == "rx"
    assert rx_group.src_ip is None
    assert rx_group.vlan == 10
    assert rx_group.interface == ci

def test_valid_tx_rx_communication(ci):
    """Test basic TX-RX communication on the same VLAN and multicast group."""
    tx_group = MulticastGroupMembership(group="239.1.1.1",mode="tx",src_ip="192.168.1.10",vlan=10)
    tx_group._interface = ci
    rx_group = MulticastGroupMembership(group="239.1.1.1",mode="rx",vlan=10)
    rx_group._interface = ci

    assert tx_group.group == rx_group.group
    assert tx_group.mode == "tx"
    assert rx_group.mode == "rx"
    assert str(tx_group.src_ip) == "192.168.1.10"
    assert tx_group.interface == ci
    assert rx_group.interface == ci


@pytest.mark.parametrize(
    "mode,src_ip",
    [("tx", "192.168.1.1"), ("rx", None)],
)
def test_valid_src_ip_mode(mode, src_ip, ci):
    """Test the interaction between src_ip and mode"""
    src_ip_obj = IPv4Address(src_ip) if src_ip else None
    mode_group = MulticastGroupMembership(group="239.1.1.6",mode=mode,src_ip=src_ip_obj,vlan=10)
    mode_group._interface = ci

    if src_ip_obj:
        assert mode_group.src_ip == src_ip_obj
    else:
        assert mode_group.src_ip is None

    assert mode_group.mode == mode
    assert mode_group.interface == ci
