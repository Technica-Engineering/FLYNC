import pytest
from pydantic import ValidationError

from flync.model.flync_4_ecu import (
    BASET1,
    ECU,
    MII,
    Controller,
    ControllerInterface,
    ECUPort,
    EthernetInterface,
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


def _controller(name: str, iface: ControllerInterface):
    return Controller(
        name=name,
        controller_metadata=_embedded_metadata(),
        ethernet_interfaces=[EthernetInterface(name=iface.name, interface_config=iface)],
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


# ---------------------------------------------------------------------------
# Type-discrimination tests (no ECU context needed — parsing only)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Resolution tests (validated through ECU — resolution happens there)
# ---------------------------------------------------------------------------


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
        ControllerInterface(
            name="b",
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
