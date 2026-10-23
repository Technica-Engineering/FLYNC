import pytest
from pydantic import ValidationError

from flync.model.flync_4_ecu import (
    BASET1,
    ECU,
    MII,
    RGMII,
    ECUPort,
    Switch,
    VLANEntry,
)
from flync.model.flync_4_someip import (
    SOMEIPServiceInterface,
)
from tests.error_assertions import assert_single_error


def test_ecu_parsing_from_dicts(metadata_entry, embedded_metadata_entry, ecu_port: ECUPort, MII_entry):
    SOMEIPServiceInterface(meta=metadata_entry, name="s", id=1)
    kwargs = dict(
        name="test",
        topology={
            "connections": [
                {
                    "type": "ecu_port_to_switch_port",
                    "id": "1",
                    "ecu_port": "test_ecu_port",
                    "switch_port": "b",
                },
            ]
        },
        switches=[
            dict(
                name="a",
                switch_config=dict(
                    meta=embedded_metadata_entry,
                    ports=[
                        dict(
                            name="b",
                            silicon_port_no=1,
                            default_vlan_id=1,
                            mii_config=MII(mode="mac"),
                        ),
                        dict(name="c", silicon_port_no=2, default_vlan_id=1),
                    ],
                    vlans=[VLANEntry(name="vlan10", id=1, default_priority=1, ports=["b"])],
                ),
            )
        ],
        controllers=[],
        ports=[
            ECUPort(
                name="test_ecu_port",
                mdi_config=BASET1(speed=100, role="slave"),
                mii_config=MII(mode="phy"),
            )
        ],
        ecu_metadata=metadata_entry,
    )
    switch = dict(
        name="d",
        switch_config=dict(
            meta=embedded_metadata_entry,
            ports=[
                dict(
                    name="e",
                    silicon_port_no=1,
                    default_vlan_id=1,
                    mii_config=MII(mode="mac"),
                ),
                dict(name="f", silicon_port_no=2, default_vlan_id=1),
            ],
            vlans=[VLANEntry(name="vlan10", id=1, default_priority=1, ports=["f"])],
        ),
    )
    Switch.model_validate(switch)
    ecu = ECU.model_validate(kwargs)
    assert isinstance(ecu, ECU)


def test_ecu_internal_topology_ambiguous_switch_port_name_across_switches(metadata_entry, embedded_metadata_entry, ecu_port):
    """
    An ECU contains two switches that each define a port with the same name. A switch-to-switch
    connection inside the ECU references that name on one side — the reference is ambiguous
    (could resolve to either switch) and validation must reject it with an actionable error
    naming both switches.
    """

    kwargs = dict(
        name="ECU_B",
        ports=[ecu_port],
        controllers=[],
        switches=[
            dict(
                name="Switch_B",
                switch_config=dict(
                    meta=embedded_metadata_entry,
                    ports=[
                        dict(
                            name="couplingPort_ConnectTo_Switch_A",
                            silicon_port_no=1,
                            default_vlan_id=1,
                            mii_config=MII(mode="mac"),
                        ),
                        dict(
                            name="couplingPort_ConnectTo_Switch_C",
                            silicon_port_no=2,
                            default_vlan_id=1,
                            mii_config=MII(mode="mac"),
                        ),
                    ],
                    vlans=[VLANEntry(name="vlan10", id=1, default_priority=1, ports=[])],
                ),
            ),
            dict(
                name="Switch_C",
                switch_config=dict(
                    meta=embedded_metadata_entry,
                    ports=[
                        dict(
                            name="couplingPort_ConnectTo_Switch_A",
                            silicon_port_no=1,
                            default_vlan_id=1,
                            mii_config=MII(mode="phy"),
                        ),
                        dict(
                            name="couplingPort_ConnectTo_Switch_B",
                            silicon_port_no=2,
                            default_vlan_id=1,
                            mii_config=MII(mode="phy"),
                        ),
                    ],
                    vlans=[VLANEntry(name="vlan10", id=1, default_priority=1, ports=[])],
                ),
            ),
        ],
        topology={
            "connections": [
                {
                    "type": "switch_to_switch_same_ecu",
                    "id": "int_conn_4",
                    "switch_port": "couplingPort_ConnectTo_Switch_C",
                    "switch2_port": "couplingPort_ConnectTo_Switch_A",
                },
                {
                    "type": "switch_to_switch_same_ecu",
                    "id": "int_conn_5",
                    "switch_port": "couplingPort_ConnectTo_Switch_B",
                    "switch2_port": "couplingPort_ConnectTo_Switch_A",
                },
            ],
        },
        ecu_metadata=metadata_entry,
    )

    with pytest.raises(ValidationError) as exc_info:
        ECU.model_validate(kwargs)

    assert_single_error(
        exc_info,
        "FLYNC-ECU-MAJ-UNIQ-074",
        "Switch port 'couplingPort_ConnectTo_Switch_A' referenced in connection 'int_conn_4' is ambiguous",
    )


def test_ecu_internal_topology_ambiguous_controller_interface_name_across_controllers(
    metadata_entry, embedded_metadata_entry, ecu_port, virtual_controller_interface
):
    """
    An ECU contains two controllers that each define an interface with the same name. An
    ecu-port-to-controller-interface connection references that name without a ``controller:``
    reference — the lookup is ambiguous (could resolve to either controller) and validation must
    reject it with an actionable error naming both controllers.
    """

    kwargs = dict(
        name="ECU_D",
        ports=[ecu_port],
        switches=[],
        controllers=[
            dict(
                name="Controller_A",
                controller_metadata=embedded_metadata_entry,
                ethernet_interfaces=[
                    dict(
                        name="shared_iface",
                        interface_config=dict(
                            mac_address="10:10:10:11:11:11",
                            mii_config=MII(mode="mac"),
                            virtual_interfaces=[virtual_controller_interface],
                        ),
                    )
                ],
            ),
            dict(
                name="Controller_B",
                controller_metadata=embedded_metadata_entry,
                ethernet_interfaces=[
                    dict(
                        name="shared_iface",
                        interface_config=dict(
                            mac_address="20:20:20:22:22:22",
                            mii_config=MII(mode="mac"),
                            virtual_interfaces=[virtual_controller_interface],
                        ),
                    )
                ],
            ),
        ],
        topology={
            "connections": [
                {
                    "type": "ecu_port_to_controller_interface",
                    "id": "int_conn_ambiguous_ctrl_iface",
                    "ecu_port": ecu_port.name,
                    "controller_interface": "shared_iface",
                },
            ],
        },
        ecu_metadata=metadata_entry,
    )

    with pytest.raises(ValidationError) as exc_info:
        ECU.model_validate(kwargs)

    error_messages = "\n".join(e.get("msg", "") for e in exc_info.value.errors())
    assert "shared_iface" in error_messages
    assert "ambiguous" in error_messages.lower()
    assert "Controller_A" in error_messages
    assert "Controller_B" in error_messages


def test_ecu_port_mdi_mii_speed_mismatch_invalid():
    """An ECU port must reject MDI and MII configurations with different speeds."""
    mdi_config = BASET1(
        speed=1000,
        role="slave",
    )
    mii_config = RGMII(
        speed=100,
        mode="mac",
    )
    with pytest.raises(ValidationError) as exc_info:
        ECUPort.model_validate(
            {
                "name": "p0",
                "mdi_config": mdi_config,
                "mii_config": mii_config,
            }
        )

    assert_single_error(
        exc_info,
        "FLYNC-ECU-MAJ-CONS-081",
        "MII and MDI config should have a compatible speed in ECU Ports. Port p0",
    )


def test_positive_ecu_port_mii_subports(metadata_entry):
    """The port carrying the link occupies channel 0 (the default); the subport takes channel 1."""

    uplink = ECUPort(
        name="uplink",
        mii_config={
            "type": "usxgmii_10g_qxgmii",
            "mode": "mac",
            "channels": [{"subport_id": 0, "speed": 1000}, {"subport_id": 1, "speed": 1000}],
        },
    )
    p1 = ECUPort(name="p1", mii_subport_of="uplink", mii_subport_id=1)

    ecu = ECU.model_validate(
        {
            "name": "ecu1",
            "controllers": [],
            "ports": [uplink, p1],
            "ecu_metadata": metadata_entry,
        }
    )

    assert ecu.ports[1].mii_subport_id == 1


def test_ecu_port_mii_subport_id_not_a_channel_is_rejected(metadata_entry):
    uplink = ECUPort(
        name="uplink",
        mii_config={
            "type": "usxgmii_10g_qxgmii",
            "mode": "mac",
            "channels": [{"subport_id": 0, "speed": 1000}],
        },
    )
    p0 = ECUPort(name="p0", mii_subport_of="uplink", mii_subport_id=5)

    with pytest.raises(ValidationError) as exc_info:
        ECU.model_validate(
            {
                "name": "ecu1",
                "controllers": [],
                "ports": [uplink, p0],
                "ecu_metadata": metadata_entry,
            }
        )

    assert_single_error(exc_info, "FLYNC-CMN-MAJ-REF-386", "not a channel of")


def _ecu_with_subports(metadata_entry, channel_speeds, host_mdi, subports):
    """Build an ECU whose ``uplink`` port carries one channel per entry of ``channel_speeds``.

    ``uplink`` occupies channel 0 with ``host_mdi``; ``subports`` maps a subport's name to ``(subport_id, mdi_config)``.
    """

    uplink = ECUPort(
        name="uplink",
        mdi_config=host_mdi,
        mii_config={
            "type": "usxgmii_20g_oxgmii",
            "mode": "mac",
            "channels": [{"subport_id": idx, "speed": speed} for idx, speed in enumerate(channel_speeds)],
        },
    )
    ports = [ECUPort(name=name, mdi_config=mdi, mii_subport_of="uplink", mii_subport_id=subport_id) for name, (subport_id, mdi) in subports.items()]
    return ECU.model_validate({"name": "ecu1", "controllers": [], "ports": [uplink, *ports], "ecu_metadata": metadata_entry})


def _t1(speed):
    return {"mode": "base_t1", "speed": speed}


def test_mdi_speed_matching_channel_is_accepted(metadata_entry):
    ecu = _ecu_with_subports(metadata_entry, (1000, 1000), _t1(1000), {"p1": (1, _t1(1000))})

    assert len(ecu.ports) == 2


def test_subport_mdi_faster_than_its_channel_is_rejected(metadata_entry):
    host_mdi = _t1(100)
    subports = {"p1": (1, _t1(1000))}

    with pytest.raises(ValidationError) as exc_info:
        _ecu_with_subports(metadata_entry, (100, 100), host_mdi, subports)

    assert_single_error(exc_info, "FLYNC-CMN-MAJ-CONS-388", "'p1' has an MDI speed of 1000 Mbps")


def test_channel_without_a_port_is_rejected(metadata_entry):
    host_mdi = _t1(100)
    subports = {"p1": (1, _t1(100))}

    with pytest.raises(ValidationError) as exc_info:
        _ecu_with_subports(metadata_entry, (1000, 1000, 1000), host_mdi, subports)

    assert_single_error(exc_info, "FLYNC-CMN-MAJ-CONS-387", "channel(s) [2] are not claimed")


def _ecu_with_switch(metadata_entry, embedded_metadata_entry, channel_speeds, uplink_mdi, p1_mdi):
    """An ECU whose ``uplink`` port feeds a switch ``uplink`` port over a two-channel link; ``p1`` feeds a switch subport."""

    def link(mode):
        return {
            "type": "usxgmii_10g_qxgmii",
            "mode": mode,
            "channels": [{"subport_id": idx, "speed": speed} for idx, speed in enumerate(channel_speeds)],
        }

    ecu_ports = [
        ECUPort(name="uplink", mdi_config=uplink_mdi, mii_config=link("phy")),
        ECUPort(name="p1", mdi_config=p1_mdi, mii_subport_of="uplink", mii_subport_id=1),
    ]
    switch_ports = [
        dict(name="s_uplink", silicon_port_no=1, default_vlan_id=1, mii_config=link("mac")),
        dict(name="s_p1", silicon_port_no=2, default_vlan_id=1, mii_subport_of="s_uplink", mii_subport_id=1),
    ]
    return ECU.model_validate(
        {
            "name": "ecu1",
            "controllers": [],
            "ports": ecu_ports,
            "switches": [
                {
                    "name": "sw",
                    "switch_config": {
                        "meta": embedded_metadata_entry,
                        "ports": switch_ports,
                        "vlans": [VLANEntry(name="vlan10", id=1, default_priority=1, ports=["s_uplink", "s_p1"])],
                    },
                }
            ],
            "topology": {
                "connections": [
                    {"type": "ecu_port_to_switch_port", "id": "1", "ecu_port": "uplink", "switch_port": "s_uplink"},
                    {"type": "ecu_port_to_switch_port", "id": "2", "ecu_port": "p1", "switch_port": "s_p1"},
                ]
            },
            "ecu_metadata": metadata_entry,
        }
    )


def test_switch_subport_mdi_faster_than_its_channel_is_rejected(metadata_entry, embedded_metadata_entry):
    """The subport's channel is 100M, so a 1G MDI behind it is rejected on the switch side."""

    with pytest.raises(ValidationError) as exc_info:
        _ecu_with_switch(
            metadata_entry, embedded_metadata_entry, (1000, 100), {"mode": "base_t1", "speed": 1000}, {"mode": "base_t1", "speed": 1000}
        )

    assert_single_error(exc_info, "FLYNC-CMN-MAJ-CONS-388", "Switch Ports 's_p1' has an MDI speed of 1000 Mbps")
