import pytest
from pydantic import ValidationError

from flync.model.flync_4_ecu import (
    BASET1,
    ECU,
    MII,
    ECUPort,
    Switch,
    VLANEntry,
)
from flync.model.flync_4_someip import (
    SOMEIPServiceInterface,
)


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
                meta=embedded_metadata_entry,
                name="a",
                ports=[
                    dict(
                        name="b",
                        silicon_port_no=1,
                        default_vlan_id=1,
                        mii_config=MII(mode="mac"),
                    ),
                    dict(name="c", silicon_port_no=2, default_vlan_id=1),
                ],
                vlans=[VLANEntry(name="vlan10", id=1, default_priority=1, ports=["a"])],
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
        meta=embedded_metadata_entry,
        name="d",
        ports=[
            dict(
                name="e",
                silicon_port_no=1,
                default_vlan_id=1,
                mii_config=MII(mode="mac"),
            ),
            dict(name="f", silicon_port_no=2, default_vlan_id=1),
        ],
        vlans=[VLANEntry(name="vlan10", id=1, default_priority=1, ports=["a"])],
    )
    Switch.model_validate(switch)
    ECU.model_validate(kwargs)


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
                meta=embedded_metadata_entry,
                name="Switch_B",
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
            dict(
                meta=embedded_metadata_entry,
                name="Switch_C",
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

    error_messages = "\n".join(e.get("msg", "") for e in exc_info.value.errors())
    assert "couplingPort_ConnectTo_Switch_A" in error_messages
    assert "ambiguous" in error_messages.lower()
    assert "Switch_B" in error_messages
    assert "Switch_C" in error_messages


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
                            name="shared_iface",
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
                            name="shared_iface",
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
