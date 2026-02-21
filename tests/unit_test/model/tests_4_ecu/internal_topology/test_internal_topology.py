import pytest
from pydantic import ValidationError

from flync.model.flync_4_ecu.internal_topology import (
    ECUPortToSwitchPort,
    InternalTopology,
    SwitchPortToControllerInterface,
    SwitchPortToSwitchPort,
)
from flync.model.flync_4_ecu import (
    ECUPort,
    SwitchPort,
    ControllerInterface,
    BASET1,
    MII,
)


def test_internal_topology_chooses_ecu_port_to_switch_port_if_type_expected():
    ecu_port = ECUPort(name="a", mdi_config=BASET1(speed=100, role="slave"))
    switch_port = SwitchPort(name="b", silicon_port_no=1, default_vlan_id=0)
    kwargs = {
        "connections": [
            {
                "type": "ecu_port_to_switch_port",
                "id": "1",
                "ecu_port": "a",
                "switch_port": "b",
            }
        ]
    }
    st = InternalTopology.model_validate(kwargs)
    assert isinstance(st.connections[0].root, ECUPortToSwitchPort)


def test_internal_topology_ecu_port_not_defined():

    switch_port = SwitchPort(name="b", silicon_port_no=1, default_vlan_id=0)
    kwargs = {
        "connections": [
            {
                "type": "ecu_port_to_switch_port",
                "id": "1",
                "ecu_port": "c",
                "switch_port": "b",
            }
        ]
    }
    with pytest.raises(ValidationError):
        st = InternalTopology.model_validate(kwargs)


def test_internal_topology_switch_port_not_defined():
    ecu_port = ECUPort(name="a", mdi_config=BASET1(speed=100, role="slave"))
    kwargs = {
        "connections": [
            {
                "type": "ecu_port_to_switch_port",
                "id": "1",
                "ecu_port": "a",
                "switch_port": "d",
            }
        ]
    }
    with pytest.raises(ValidationError):
        st = InternalTopology.model_validate(kwargs)


def test_negative_internal_topology_switch_port_to_controller_interface_missing_switch_port(
    virtual_controller_interface,
):
    ctrl_iface = ControllerInterface(
        name="b",
        mac_address="10:10:10:22:22:22",
        virtual_interfaces=[virtual_controller_interface],
        mii_config=MII(mode="phy"),
    )
    kwargs = {
        "connections": [
            {
                "type": "switch_port_to_controller_interface",
                "id": "1",
                "switch_port": "a",
                "controller_interface": "b",
            }
        ]
    }
    with pytest.raises(ValidationError):
        st = InternalTopology.model_validate(kwargs)


def test_negative_internal_topology_switch_port_to_controller_interface_missing_controller_interface(
    virtual_controller_interface,
):
    switch_port = SwitchPort(
        name="a",
        silicon_port_no=1,
        default_vlan_id=0,
        mii_config=MII(mode="mac"),
    )
    kwargs = {
        "connections": [
            {
                "type": "switch_port_to_controller_interface",
                "id": "1",
                "switch_port": "a",
                "controller_interface": "e",
            }
        ]
    }
    with pytest.raises(ValidationError):
        st = InternalTopology.model_validate(kwargs)


def test_internal_topology_chooses_switch_port_to_controller_interface_if_type_expected(
    virtual_controller_interface,
):
    switch_port = SwitchPort(
        name="a",
        silicon_port_no=1,
        default_vlan_id=0,
        mii_config=MII(mode="mac"),
    )
    ctrl_iface = ControllerInterface(
        name="b",
        mac_address="10:10:10:22:22:22",
        virtual_interfaces=[virtual_controller_interface],
        mii_config=MII(mode="phy"),
    )
    kwargs = {
        "connections": [
            {
                "type": "switch_port_to_controller_interface",
                "id": "1",
                "switch_port": "a",
                "controller_interface": "b",
            }
        ]
    }
    st = InternalTopology.model_validate(kwargs)
    assert isinstance(st.connections[0].root, SwitchPortToControllerInterface)


def test_negative_switch_to_switch_missing_port_2():
    switch_port = SwitchPort(
        name="a",
        silicon_port_no=1,
        default_vlan_id=0,
        mii_config=MII(mode="mac"),
    )
    kwargs = {
        "connections": [
            {
                "type": "switch_to_switch_same_ecu",
                "id": "1",
                "switch_port": "a",
                "switch2_port": "f",
            }
        ]
    }
    with pytest.raises(ValidationError):
        st = InternalTopology.model_validate(kwargs)


def test_internal_topology_chooses_switch_to_switch_same_ecu_if_type_expected():
    switch_port = SwitchPort(
        name="a",
        silicon_port_no=1,
        default_vlan_id=0,
        mii_config=MII(mode="mac"),
    )
    switch_port2 = SwitchPort(
        name="b",
        silicon_port_no=2,
        default_vlan_id=0,
        mii_config=MII(mode="phy"),
    )
    kwargs = {
        "connections": [
            {
                "type": "switch_to_switch_same_ecu",
                "id": "1",
                "switch_port": "a",
                "switch2_port": "b",
            }
        ]
    }
    st = InternalTopology.model_validate(kwargs)
    assert isinstance(st.connections[0].root, SwitchPortToSwitchPort)


# def test_internal_topology_ecu_port_to_switch_connection_ecu_port_resolved_correctly():
#     kwargs = {
#         "connections": [
#             {
#                 "type": "ecu_port_to_switch_port",
#                 "id": "1",
#                 "ecu_port": 'valid_ecu_port',
#                 "switch_port": 'valid_switch_port'
#             }
#         ]
#     }
#     st = InternalTopology.model_validate(kwargs)
#     assert isinstance(st.connections[0].root, ECUPortToSwitchPort)
#     assert isinstance(st.connections[0].root.ecu_port, ECUPort)
#     assert isinstance(st.connections[0].root.switch_port, SwitchPort)
