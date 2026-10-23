"""Binding of a port extender to its switch, and multicast path walking through it; the rules are in ``test_port_extender_rules.py``."""

import pytest
from pydantic import ValidationError

from flync.core.utils.multicast.multicast_paths import check_vlan_conn_valid, get_switch_port_connected_component
from flync.model.flync_4_ecu.port_extender import ChannelizedUplink, TaggedUplink
from flync.model.flync_4_ecu.switch import SwitchPort
from tests.model_builders import make_port_extender, make_switch, make_vlan_entry

TAGGED = {"type": "tagged", "switch_port": "UP0", "tag": {"format": "ieee_802_1br"}, "mii_config": {"type": "xfi", "mode": "phy"}}
LANE = [{"subport_id": i, "speed": 1000} for i in range(2)]
CHANNELIZED = {"type": "channelized", "switch_port": "UP0", "mii_config": {"type": "usxgmii_10g_dxgmii", "mode": "phy", "channels": LANE}}


def _switch():
    ports = [
        SwitchPort(name="UP0", silicon_port_no=0, default_vlan_id=1, mii_config={"type": "xfi", "mode": "mac"}),
        SwitchPort(name="NATIVE", silicon_port_no=1, default_vlan_id=20),
        SwitchPort(name="PE0_P1", silicon_port_no=2, default_vlan_id=20),
        SwitchPort(name="PE0_P2", silicon_port_no=3, default_vlan_id=20),
    ]
    vlans = [make_vlan_entry(vlan_id=20, ports=("NATIVE", "PE0_P1", "PE0_P2"))]
    return make_switch(ports=ports, vlans=vlans, port_extenders=[make_port_extender(uplink=TAGGED, ports=["PE0_P1", "PE0_P2"])])


@pytest.mark.parametrize(
    ("uplink", "variant"), [pytest.param(TAGGED, TaggedUplink, id="tagged"), pytest.param(CHANNELIZED, ChannelizedUplink, id="channelized")]
)
def test_the_uplink_type_selects_the_variant(uplink, variant):
    assert isinstance(make_port_extender(uplink=uplink).uplink, variant)


@pytest.mark.parametrize("uplink", [{**TAGGED, "type": "bogus"}, {k: v for k, v in TAGGED.items() if k != "tag"}])
def test_an_incomplete_or_unknown_uplink_is_rejected(uplink):
    with pytest.raises(ValidationError):
        make_port_extender(uplink=uplink)


def test_the_switch_binds_extender_ports_and_the_uplink_port():
    switch = _switch()
    extender = switch.find_port_extender("PE0")
    assert extender.switch is switch
    assert [p.name for p in extender.get_ports()] == ["PE0_P1", "PE0_P2"]
    assert all(p.port_extender is extender for p in extender.get_ports())
    assert switch.find_switch_port("NATIVE").port_extender is None
    assert extender.uplink.switch_port is switch.find_switch_port("UP0")
    assert switch.find_switch_port("UP0").connected_component is extender


def test_a_native_port_reaches_the_extender_ports_through_the_vlan():
    native = _switch().find_switch_port("NATIVE")
    reached: list = []
    get_switch_port_connected_component(native, [native], [], reached, 20, {})
    assert [port.name for port in reached] == ["PE0_P1", "PE0_P2"]


def test_the_uplink_neighbor_is_the_extender_and_is_not_followed_any_further():
    switch = _switch()
    extender = switch.find_port_extender("PE0")
    assert check_vlan_conn_valid(extender, [], [], 20)
    uplink = switch.find_switch_port("UP0")
    reached: list = []
    get_switch_port_connected_component(uplink, [uplink], [], reached, 20, {})
    assert extender in reached
