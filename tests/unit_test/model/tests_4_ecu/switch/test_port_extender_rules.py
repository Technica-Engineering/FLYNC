"""Rules of port extenders: what a switch rejects or warns about once extenders hang off it."""

import pytest
from pydantic import ValidationError

from flync.core.utils.exceptions_handling import validate_with_policy
from flync.model.flync_4_ecu.ecu import ECU
from flync.model.flync_4_ecu.internal_topology import ECUPortToSwitchPort, InternalTopology
from flync.model.flync_4_ecu.phy import BASET1
from flync.model.flync_4_ecu.port import ECUPort
from flync.model.flync_4_ecu.port_extender import PortExtender
from flync.model.flync_4_ecu.switch import Switch, SwitchConfig, SwitchPort
from flync.model.flync_4_ecu.vlan_entry import MulticastGroup, VLANEntry
from tests.error_assertions import assert_no_findings, assert_single_error, assert_single_warning
from tests.model_builders import make_controller_metadata, make_ecu_metadata, make_port_extender

XFI_MAC = {"type": "xfi", "mode": "mac"}
XFI_PHY = {"type": "xfi", "mode": "phy"}


def lane(variant: str, mode: str, speeds: tuple[int, ...] = (1000, 1000)) -> dict:
    return {"type": variant, "mode": mode, "channels": [{"subport_id": i, "speed": speed} for i, speed in enumerate(speeds)]}


def sgmii(mode: str, speed: int) -> dict:
    return {"type": "sgmii", "mode": mode, "speed": speed}


def tagged(mii: dict = XFI_PHY, switch_port: str = "UP0") -> dict:
    return {"type": "tagged", "switch_port": switch_port, "tag": {"format": "proprietary"}, "mii_config": mii}


def channelized(mii: dict | None = None) -> dict:
    return {"type": "channelized", "switch_port": "UP0", "mii_config": mii or lane("q_usgmii", "phy")}


def uplink_port(name: str = "UP0", **fields) -> SwitchPort:
    fields.setdefault("mii_config", XFI_MAC)
    return SwitchPort(name=name, silicon_port_no=0 if name == "UP0" else 1, default_vlan_id=1, **fields)


def ext_port(number: int, **fields) -> SwitchPort:
    return SwitchPort(name=f"PE0_P{number}", silicon_port_no=number + 10, default_vlan_id=20, **fields)


def channel_port(number: int, **fields) -> SwitchPort:
    """Extender port on channel ``number - 1`` of the lane on ``UP0``."""
    return ext_port(number, mii_subport_of="UP0", mii_subport_id=number - 1, **fields)


def switch_data(native=None, ext_ports=None, extenders=None, vlans=None, tcam_rules=None, uplink=None) -> dict:
    """A switch with a tagged XFI uplink on ``UP0`` and an extender ``PE0`` with two ports in one VLAN, unless overridden."""
    native = native if native is not None else [uplink_port()]
    ext_ports = ext_ports if ext_ports is not None else [ext_port(1), ext_port(2)]
    if extenders is None:
        extenders = [make_port_extender(uplink=uplink or tagged(), ports=[p.name for p in ext_ports])]
    if vlans is None:
        vlans = [VLANEntry(name="v20", id=20, default_priority=0, ports=["PE0_P1", "PE0_P2"])]
    config = SwitchConfig(
        meta=make_controller_metadata(), ports=[*native, *ext_ports], vlans=vlans, tcam_rules=tcam_rules or [], port_extenders=extenders
    )
    return {"name": "SW0", "switch_config": config}


def lane_data(extender_lane: dict | None = None) -> dict:
    """A channelized switch: ``UP0`` is the lane and ``PE0_P1`` / ``PE0_P2`` take its channels 0 and 1."""
    return switch_data(
        native=[uplink_port(mii_config=lane("q_usgmii", "mac"))],
        ext_ports=[channel_port(1), channel_port(2)],
        uplink=channelized(extender_lane),
    )


def tagged_data(switch_mii: dict, extender_mii: dict) -> dict:
    return switch_data(native=[uplink_port(mii_config=switch_mii)], ext_ports=[ext_port(1)], uplink=tagged(extender_mii), vlans=[])


def pe(ports: list[str], name: str = "PE0", uplink: dict | None = None) -> PortExtender:
    return make_port_extender(name=name, uplink=uplink or tagged(), ports=ports)


def test_a_tagged_and_a_channelized_switch_are_accepted():
    assert_no_findings(validate_with_policy(Switch, switch_data(), path=None))
    assert_no_findings(validate_with_policy(Switch, lane_data(), path=None))


@pytest.mark.parametrize(
    ("data", "error_id", "fragment"),
    [
        pytest.param(
            switch_data(
                native=[uplink_port(), uplink_port("UP1")],
                ext_ports=[ext_port(1)],
                extenders=[pe(["PE0_P1"]), pe([], uplink=tagged(switch_port="UP1"))],
            ),
            "FLYNC-CMN-MAJ-UNIQ-009",
            "Port Extenders (name)",
            id="duplicate_extender_name",
        ),
        pytest.param(switch_data(uplink=tagged(switch_port="NOPE")), "FLYNC-ECU-MAJ-REF-392", "'NOPE' of extender 'PE0'", id="uplink_port_unknown"),
        pytest.param(
            switch_data(
                ext_ports=[ext_port(1), SwitchPort(name="PE1_P2", silicon_port_no=2, default_vlan_id=20)],
                extenders=[pe(["PE0_P1"]), pe(["PE1_P2"], name="PE1", uplink=tagged(switch_port="PE0_P1"))],
            ),
            "FLYNC-ECU-MAJ-COMP-393",
            "Cascading extenders are not supported",
            id="cascading",
        ),
        pytest.param(
            switch_data(native=[uplink_port(), uplink_port("UP1")], ext_ports=[ext_port(1)], extenders=[pe(["PE0_P1"]), pe([], name="PE1")]),
            "FLYNC-CMN-MAJ-UNIQ-009",
            "Port Extenders (uplink switch_port)",
            id="shared_uplink_port",
        ),
        pytest.param(
            switch_data(extenders=[pe(["PE0_P1", "GHOST"])], vlans=[]),
            "FLYNC-ECU-MAJ-REF-391",
            "lists port 'GHOST', which is not a port of this switch",
            id="unknown_port",
        ),
        pytest.param(
            switch_data(extenders=[pe(["PE0_P1", "PE0_P1"])], vlans=[]), "FLYNC-CMN-MAJ-UNIQ-009", "Port Extenders (ports)", id="port_listed_twice"
        ),
        pytest.param(
            switch_data(
                native=[uplink_port(), uplink_port("UP1")], extenders=[pe(["PE0_P1"]), pe(["PE0_P1"], name="PE1", uplink=tagged(switch_port="UP1"))]
            ),
            "FLYNC-CMN-MAJ-UNIQ-009",
            "Port Extenders (ports)",
            id="port_listed_by_two_extenders",
        ),
        pytest.param(
            switch_data(native=[uplink_port(mii_config=lane("q_usgmii", "mac"))], ext_ports=[channel_port(1), ext_port(2)], uplink=channelized()),
            "FLYNC-ECU-MAJ-CONS-394",
            "needs mii_subport_of 'UP0'",
            id="channelized_port_without_channel",
        ),
        pytest.param(
            switch_data(ext_ports=[ext_port(1), ext_port(2, mii_config=XFI_MAC)]),
            "FLYNC-ECU-MAJ-CONS-395",
            "whose uplink is tagged",
            id="tagged_port_with_xmii",
        ),
        pytest.param(
            switch_data(ext_ports=[ext_port(1), ext_port(2, mii_subport_of="UP0", mii_subport_id=0)]),
            "FLYNC-ECU-MAJ-CONS-395",
            "whose uplink is tagged",
            id="tagged_port_with_channel",
        ),
    ],
)
def test_extender_references_and_ports_are_checked(data, error_id, fragment):
    with pytest.raises(ValidationError) as exc_info:
        Switch(**data)
    assert_single_error(exc_info, error_id, fragment)


@pytest.mark.parametrize(
    ("data", "error_id", "fragment"),
    [
        pytest.param(tagged_data(XFI_PHY, XFI_PHY), "FLYNC-CMN-MAJ-COMP-013", "Incompatible MII Mode", id="same_mode"),
        pytest.param(
            tagged_data({"type": "rgmii", "mode": "mac", "speed": 1000}, sgmii("phy", 1000)),
            "FLYNC-CMN-MAJ-COMP-015",
            "Incompatible MII Type",
            id="type_differs",
        ),
        pytest.param(tagged_data(sgmii("mac", 1000), sgmii("phy", 2500)), "FLYNC-CMN-MAJ-COMP-014", "Incompatible MII Speed", id="speed_differs"),
        pytest.param(tagged_data(None, XFI_PHY), "FLYNC-CMN-MAJ-COMP-016", "MII configuration missing", id="switch_end_has_no_xmii"),
        pytest.param(
            switch_data(
                native=[uplink_port(mii_config=lane("usxgmii_10g_sxgmii", "mac", (1000,)))],
                ext_ports=[channel_port(1)],
                uplink=channelized(lane("usxgmii_10g_sxgmii", "phy", (1000,))),
                vlans=[],
            ),
            "FLYNC-ECU-MAJ-COMP-396",
            "channelized uplink, which needs a multi-port",
            id="channelized_over_a_single_port_lane",
        ),
        pytest.param(
            tagged_data(lane("q_usgmii", "mac"), lane("q_usgmii", "phy")),
            "FLYNC-ECU-MAJ-COMP-397",
            "tagged uplink, which needs a single-port",
            id="tagged_over_a_multi_port_lane",
        ),
        pytest.param(
            lane_data(lane("q_usgmii", "phy", (1000, 100))),
            "FLYNC-ECU-MAJ-COMP-398",
            "differs between the switch and extender 'PE0'",
            id="lane_channels_differ",
        ),
    ],
)
def test_the_two_ends_of_the_uplink_must_agree(data, error_id, fragment):
    with pytest.raises(ValidationError) as exc_info:
        Switch(**data)
    assert_single_error(exc_info, error_id, fragment)


def test_vlan_multicast_and_tcam_refer_to_extender_ports_by_name():
    tcam = [{"name": "r1", "id": 1, "match_ports": ["PE0_P1"], "action": [{"type": "mirror", "ports": ["PE0_P2"]}]}]
    multicast = [MulticastGroup(address="224.1.1.1", ports=["PE0_P1"])]
    vlan = VLANEntry(name="v20", id=20, default_priority=0, ports=["PE0_P1", "PE0_P2"], multicast=multicast)
    assert_no_findings(validate_with_policy(Switch, switch_data(vlans=[vlan], tcam_rules=tcam), path=None))


def test_a_tcam_rule_without_ports_applies_to_every_port_but_the_uplink():
    switch = Switch(**switch_data(tcam_rules=[{"name": "r1", "id": 1, "action": [{"type": "drop"}]}]))
    assert switch.tcam_rules[0].match_ports == switch.tcam_rules[0].action[0].ports == ["PE0_P1", "PE0_P2"]


@pytest.mark.parametrize(
    ("kwargs", "fragment"),
    [
        pytest.param({"vlans": [VLANEntry(name="v20", id=20, default_priority=0, ports=["PE0_P1", "UP0"])]}, "VLAN 'v20'", id="vlan"),
        pytest.param({"tcam_rules": [{"name": "r1", "id": 1, "match_ports": ["UP0"]}]}, "TCAM rule 'r1' (match_ports)", id="tcam"),
        pytest.param(
            {"native": [uplink_port(traffic_classes=[{"name": "tc", "priority": 1, "frame_priority_values": [0]}])]},
            "carries traffic_classes",
            id="tc",
        ),
    ],
)
def test_using_the_uplink_port_for_forwarding_is_an_error(kwargs, fragment):
    code = "402" if "carries" in fragment else "401"
    data = switch_data(**kwargs)
    with pytest.raises(ValidationError) as exc_info:
        Switch(**data)
    assert_single_error(exc_info, f"FLYNC-ECU-MIN-CONS-{code}", fragment)


def test_an_extender_without_ports_warns():
    result = validate_with_policy(Switch, switch_data(ext_ports=[], vlans=[]), path=None)
    assert_single_warning(result, "FLYNC-ECU-WARN-STRUCT-403", "Port extender 'PE0' has no ports")


def ecu_data(uplink_mii: dict, *, wire_uplink: bool = False) -> dict:
    """An ECU whose switch has a tagged extender with four 1000 Mb/s ports, each wired to an ECU port."""
    ext_ports = [ext_port(n) for n in range(1, 5)]
    vlans = [VLANEntry(name="v20", id=20, default_priority=0, ports=[p.name for p in ext_ports])]
    mac = {**uplink_mii, "mode": "mac"}
    switch = Switch(
        **switch_data(native=[uplink_port(mii_config=mac)], ext_ports=ext_ports, vlans=vlans, uplink=tagged({**uplink_mii, "mode": "phy"}))
    )
    ecu_ports = [ECUPort(name=f"E{n}", mdi_config=BASET1(speed=1000)) for n in range(1, 5)]
    connections = [ECUPortToSwitchPort(id=f"c{n}", ecu_port=f"E{n}", switch_port=f"PE0_P{n}", switch="SW0") for n in range(1, 5)]
    if wire_uplink:
        ecu_ports.append(ECUPort(name="EU", mdi_config=BASET1()))
        connections.append(ECUPortToSwitchPort(id="cu", ecu_port="EU", switch_port="UP0", switch="SW0"))
    return {
        "name": "ECU1",
        "controllers": [],
        "switches": [switch],
        "ports": ecu_ports,
        "topology": InternalTopology(connections=connections),
        "ecu_metadata": make_ecu_metadata(),
    }


def test_oversubscribing_a_tagged_uplink_is_an_error():
    data = ecu_data({"type": "sgmii", "speed": 2500})
    with pytest.raises(ValidationError) as exc_info:
        ECU(**data)
    assert_single_error(exc_info, "FLYNC-ECU-MIN-CONS-400", "4 ports add up to 4000 Mb/s (1000 + 1000 + 1000 + 1000)")


def test_a_tagged_uplink_as_fast_as_its_ports_is_accepted():
    assert_no_findings(validate_with_policy(ECU, ecu_data({"type": "usxgmii_5g_sxgmii", "channels": [{"subport_id": 0, "speed": 5000}]}), path=None))


def test_the_uplink_port_cannot_also_be_wired_in_the_internal_topology():
    data = ecu_data({"type": "xfi"}, wire_uplink=True)
    with pytest.raises(ValidationError) as exc_info:
        ECU(**data)
    assert_single_error(exc_info, "FLYNC-ECU-MAJ-COMP-399", "'UP0' on switch 'SW0' is the uplink of a port extender")
