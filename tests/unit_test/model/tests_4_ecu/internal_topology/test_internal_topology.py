import pytest
from pydantic import ValidationError

from flync.model.flync_4_ecu import (
    BASET1,
    ECU,
    MII,
    Controller,
    ECUPort,
    EthernetInterface,
    EthernetInterfaceConfig,
    Switch,
    SwitchPort,
)
from flync.model.flync_4_ecu.internal_topology import (
    ECUPortToSwitchPort,
    InternalTopology,
    SwitchPortToControllerInterface,
    SwitchPortToSwitchPort,
)
from flync.model.flync_4_metadata import BaseVersion, EmbeddedMetadata


def _embedded_metadata():
    return EmbeddedMetadata(
        type="embedded",
        author="t",
        compatible_flync_version=BaseVersion(version_schema="semver", version="0.11.0"),
        target_system="t",
    )


def _ecu_metadata():
    return {"author": "t", "compatible_flync_version": {"version_schema": "semver", "version": "0.11.0"}}


def _switch(name: str, ports):
    return Switch(name=name, ports=ports, vlans=[], meta=_embedded_metadata())


def _controller(name: str, iface_name: str, iface: EthernetInterfaceConfig):
    return Controller(
        name=name,
        controller_metadata=_embedded_metadata(),
        ethernet_interfaces=[EthernetInterface(name=iface_name, interface_config=iface)],
    )


def _dummy_port():
    return ECUPort(name="_dummy", mdi_config=BASET1(speed=100, role="slave"))


def _ecu(switches=None, controllers=None, ports=None, connections=None):
    """Construct a minimal ECU for resolution tests."""
    return ECU.model_validate(
        {
            "name": "test_ecu",
            "ports": ports or [_dummy_port()],
            "switches": switches or [],
            "controllers": controllers or [],
            "topology": {"connections": connections or []},
            "ecu_metadata": _ecu_metadata(),
        }
    )


def test_internal_topology_chooses_ecu_port_to_switch_port_if_type_expected():
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


def test_internal_topology_chooses_switch_port_to_controller_interface_if_type_expected():
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


def test_internal_topology_chooses_switch_to_switch_same_ecu_if_type_expected():
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


def test_internal_topology_ecu_port_not_defined():
    switch = _switch("sw", [SwitchPort(name="b", silicon_port_no=1, default_vlan_id=0)])
    with pytest.raises(ValidationError):
        _ecu(
            switches=[switch],
            connections=[{"type": "ecu_port_to_switch_port", "id": "1", "ecu_port": "c", "switch_port": "b"}],
        )


def test_internal_topology_switch_port_not_defined():
    ecu_port = ECUPort(name="a", mdi_config=BASET1(speed=100, role="slave"))
    with pytest.raises(ValidationError):
        _ecu(
            ports=[ecu_port],
            connections=[{"type": "ecu_port_to_switch_port", "id": "1", "ecu_port": "a", "switch_port": "d"}],
        )


def test_negative_internal_topology_switch_port_to_controller_interface_missing_switch_port(
    virtual_controller_interface,
):
    ctrl = _controller(
        "ctrl",
        "b",
        EthernetInterfaceConfig(
            mac_address="10:10:10:22:22:22",
            virtual_interfaces=[virtual_controller_interface],
            mii_config=MII(mode="phy"),
        ),
    )
    with pytest.raises(ValidationError):
        _ecu(
            controllers=[ctrl],
            connections=[{"type": "switch_port_to_controller_interface", "id": "1", "switch_port": "a", "controller_interface": "b"}],
        )


def test_negative_internal_topology_switch_port_to_controller_interface_missing_controller_interface(
    virtual_controller_interface,
):
    switch = _switch(
        "sw",
        [SwitchPort(name="a", silicon_port_no=1, default_vlan_id=0, mii_config=MII(mode="mac"))],
    )
    with pytest.raises(ValidationError):
        _ecu(
            switches=[switch],
            connections=[{"type": "switch_port_to_controller_interface", "id": "1", "switch_port": "a", "controller_interface": "e"}],
        )


def test_negative_switch_to_switch_missing_port_2():
    switch = _switch(
        "sw",
        [SwitchPort(name="a", silicon_port_no=1, default_vlan_id=0, mii_config=MII(mode="mac"))],
    )
    with pytest.raises(ValidationError):
        _ecu(
            switches=[switch],
            connections=[{"type": "switch_to_switch_same_ecu", "id": "1", "switch_port": "a", "switch2_port": "f"}],
        )


def test_switch_port_reused_across_two_connections(virtual_controller_interface):
    switch_port = SwitchPort(name="a", silicon_port_no=1, default_vlan_id=0, mii_config=MII(mode="mac"))
    switch = _switch("sw", [switch_port])
    ecu_port = ECUPort(name="e", mii_config=MII(mode="phy"))
    ctrl = _controller(
        "ctrl",
        "b",
        EthernetInterfaceConfig(
            mac_address="10:10:10:22:22:22",
            virtual_interfaces=[virtual_controller_interface],
            mii_config=MII(mode="phy"),
        ),
    )
    with pytest.raises(ValidationError, match="switch port 'a'"):
        _ecu(
            switches=[switch],
            controllers=[ctrl],
            ports=[ecu_port],
            connections=[
                {"type": "ecu_port_to_switch_port", "id": "1", "ecu_port": "e", "switch_port": "a"},
                {"type": "switch_port_to_controller_interface", "id": "2", "switch_port": "a", "controller_interface": "b"},
            ],
        )


def test_switch_port_connected_to_itself():
    switch = _switch(
        "sw",
        [SwitchPort(name="a", silicon_port_no=1, default_vlan_id=0, mii_config=MII(mode="mac"))],
    )
    with pytest.raises(ValidationError, match="connected to itself"):
        _ecu(
            switches=[switch],
            connections=[{"type": "switch_to_switch_same_ecu", "id": "1", "switch_port": "a", "switch2_port": "a"}],
        )


def test_switch_ports_each_used_once_is_valid(virtual_controller_interface):
    switch_port_a = SwitchPort(name="a", silicon_port_no=1, default_vlan_id=0, mii_config=MII(mode="mac"))
    switch_port_c = SwitchPort(name="c", silicon_port_no=2, default_vlan_id=0, mii_config=MII(mode="mac"))
    switch = _switch("sw", [switch_port_a, switch_port_c])
    ecu_port = ECUPort(name="e", mii_config=MII(mode="phy"))
    ctrl = _controller(
        "ctrl",
        "b",
        EthernetInterfaceConfig(
            mac_address="10:10:10:22:22:22",
            virtual_interfaces=[virtual_controller_interface],
            mii_config=MII(mode="phy"),
        ),
    )
    ecu = _ecu(
        switches=[switch],
        controllers=[ctrl],
        ports=[ecu_port],
        connections=[
            {"type": "ecu_port_to_switch_port", "id": "1", "ecu_port": "e", "switch_port": "a"},
            {"type": "switch_port_to_controller_interface", "id": "2", "switch_port": "c", "controller_interface": "b"},
        ],
    )
    assert len(ecu.topology.connections) == 2


def test_same_switch_port_name_in_different_switches_is_valid():
    """Two switches in one ECU may each define a port with the same name; using each in its own
    connection is valid because the dedup compares port objects by identity, not by name."""
    switch_a = _switch("switch_a", [SwitchPort(name="a", silicon_port_no=1, default_vlan_id=0, mii_config=MII(mode="mac"))])
    switch_b = _switch("switch_b", [SwitchPort(name="a", silicon_port_no=1, default_vlan_id=0, mii_config=MII(mode="mac"))])
    ecu_port_1 = ECUPort(name="e1", mii_config=MII(mode="phy"))
    ecu_port_2 = ECUPort(name="e2", mii_config=MII(mode="phy"))
    ecu = _ecu(
        switches=[switch_a, switch_b],
        ports=[ecu_port_1, ecu_port_2],
        connections=[
            {"type": "ecu_port_to_switch_port", "id": "1", "ecu_port": "e1", "switch_port": "a", "switch": "switch_a"},
            {"type": "ecu_port_to_switch_port", "id": "2", "ecu_port": "e2", "switch_port": "a", "switch": "switch_b"},
        ],
    )

    assert len(ecu.topology.connections) == 2
