"""Negative tests for the virtualization subtree: subtree-wide uniqueness, the PHY-less compute node interface, and the controller/ECU boundary.

The boundary cases are the ones worth pinning: the controller's own physical interface is the only
component that appears in both scopes, so an ECU connection must never resolve a compute node interface or a
virtual switch port, and a controller connection must never resolve an ECU hardware switch port.
"""

import pytest
from pydantic import ValidationError

from flync.model.flync_4_ecu import ECU, EthernetInterface, EthernetInterfaceConfig
from flync.model.flync_4_ecu.controller_topology import ControllerTopology
from flync.model.flync_4_ecu.internal_topology import ECUPortToControllerInterface, InternalTopology, SwitchPortToControllerInterface
from flync.model.flync_4_ecu.phy import BASET1, RGMII
from flync.model.flync_4_ecu.port import ECUPort
from tests.error_assertions import assert_single_error
from tests.model_builders import (
    make_compute_node,
    make_controller,
    make_ecu_metadata,
    make_eth_interface,
    make_switch,
    make_vci,
    make_virtual_switch,
)


def _duplicate_node_names():
    return {
        "compute_nodes": [
            make_compute_node(name="NODE0"),
            make_compute_node(name="NODE0", ethernet_interfaces=[make_eth_interface(name="other_eth0", mac="AA:BB:CC:DD:EE:02")]),
        ]
    }


def _duplicate_virtual_switch_names():
    return {"virtual_switches": [make_virtual_switch(name="br0"), make_virtual_switch(name="br0", port_names=["br1_p1", "br1_p2"])]}


def _nested_virtual_switch_shadowing_an_outer_one():
    inner_node = make_compute_node(
        name="NODE0",
        ethernet_interfaces=[make_eth_interface(name="NODE0_eth0", mac="AA:BB:CC:DD:EE:05")],
        virtual_switches=[make_virtual_switch(name="br0", port_names=["ibr0_p1", "ibr0_p2"])],
    )
    return {"compute_nodes": [inner_node], "virtual_switches": [make_virtual_switch(name="br0")]}


@pytest.mark.parametrize(
    ("controller_kwargs", "message_fragment"),
    [
        pytest.param(_duplicate_node_names(), "Compute Nodes (name):['NODE0']", id="compute_node_names"),
        pytest.param(_duplicate_virtual_switch_names(), "Virtual Switches (name):['br0']", id="virtual_switch_names"),
        pytest.param(_nested_virtual_switch_shadowing_an_outer_one(), "Virtual Switches (name):['br0']", id="virtual_switch_names_when_nested"),
    ],
)
def test_names_must_be_unique_across_the_whole_subtree(controller_kwargs, message_fragment):
    """A name reused anywhere in the subtree is rejected: the controller topology resolves bare names across the whole of it."""
    with pytest.raises(ValidationError) as exc_info:
        make_controller(**controller_kwargs)
    assert_single_error(exc_info, "FLYNC-CMN-MAJ-UNIQ-009", message_fragment)


def test_interface_names_may_repeat_across_compute_nodes():
    """Interface name uniqueness is checked per-owner, not across the subtree: sibling nodes may reuse a name."""
    make_controller(
        compute_nodes=[
            make_compute_node(name="NODE0", ethernet_interfaces=[make_eth_interface(name="eth0", mac="AA:BB:CC:DD:EE:03")]),
            make_compute_node(name="NODE1", ethernet_interfaces=[make_eth_interface(name="eth0", mac="AA:BB:CC:DD:EE:04")]),
        ]
    )


def test_node_interface_may_not_reuse_a_controller_interface_mac():
    """MAC uniqueness spans the subtree, so a compute node interface cannot repeat the MAC of the controller's physical interface."""
    node = make_compute_node(
        name="NODE0",
        ethernet_interfaces=[make_eth_interface(name="NODE0_eth0", mac="AA:BB:CC:DD:EE:FF")],
    )
    with pytest.raises(ValidationError) as exc_info:
        make_controller(compute_nodes=[node])
    assert_single_error(exc_info, "FLYNC-ECU-MAJ-UNIQ-249", "is used by more than one Ethernet interface on controller 'CTRL0'")


def test_mii_config_on_a_node_interface_is_rejected():
    """A virtual NIC has no PHY: a ``mii_config`` on a compute node interface means a physical interface was misplaced."""
    iface = EthernetInterface(
        name="NODE0_eth0",
        interface_config=EthernetInterfaceConfig(mac_address="AA:BB:CC:DD:EE:06", mii_config=RGMII(mode="mac"), virtual_interfaces=[make_vci()]),
    )
    with pytest.raises(ValidationError) as exc_info:
        make_compute_node(name="NODE0", ethernet_interfaces=[iface])
    assert_single_error(exc_info, "FLYNC-ECU-MAJ-CONS-339", "declares a mii_config")


def _ecu_naming_a_node_interface():
    """An ECU connection that tries to reach a compute node interface - resolvable only through ``get_interfaces()``, which excludes compute nodes."""
    controller = make_controller(compute_nodes=[make_compute_node(name="NODE0")])
    return {
        "controllers": [controller],
        "ports": [ECUPort(name="p_node", mdi_config=BASET1())],
        "topology": InternalTopology(
            connections=[ECUPortToControllerInterface(id="bad", ecu_port="p_node", controller_interface="NODE0_eth0", controller="CTRL0")]
        ),
    }


def _ecu_naming_a_virtual_switch_port():
    """An ECU connection that tries to reach a virtual switch: virtual switches are not in ``ecu.switches``."""
    controller = make_controller(virtual_switches=[make_virtual_switch(name="br0")])
    return {
        "controllers": [controller],
        "switches": [make_switch(name="SW0")],
        "ports": [ECUPort(name="p0", mdi_config=BASET1())],
        "topology": InternalTopology(
            connections=[SwitchPortToControllerInterface(id="bad", switch_port="br0_p1", switch="br0", controller_interface="ETH0")]
        ),
    }


@pytest.mark.parametrize(
    ("ecu_kwargs", "expected_error_id", "message_fragment"),
    [
        pytest.param(
            _ecu_naming_a_node_interface(),
            "FLYNC-ECU-MAJ-REF-078",
            "Controller interface 'NODE0_eth0' referenced in connection 'bad' was not found",
            id="ecu_topology_names_a_node_interface",
        ),
        pytest.param(
            _ecu_naming_a_virtual_switch_port(),
            "FLYNC-ECU-MAJ-REF-073",
            "Switch 'br0' referenced in connection 'bad' was not found in the current ECU",
            id="ecu_topology_names_a_virtual_switch",
        ),
    ],
)
def test_ecu_topology_cannot_reach_into_a_controller(ecu_kwargs, expected_error_id, message_fragment):
    """The ECU scope stops at the controller's physical interfaces - nothing inside a controller is visible to it."""
    with pytest.raises(ValidationError) as exc_info:
        ECU(name="ECU1", ecu_metadata=make_ecu_metadata(), **ecu_kwargs)
    assert_single_error(exc_info, expected_error_id, message_fragment)


def test_controller_topology_cannot_reach_an_ecu_hardware_switch_port():
    """The boundary holds in the other direction too: a controller connection resolves only against its own virtual switches."""
    with pytest.raises(ValidationError) as exc_info:
        make_controller(
            virtual_switches=[make_virtual_switch(name="br0")],
            controller_topology=ControllerTopology(
                connections=[
                    {
                        "id": "bad",
                        "type": "switch_port_to_controller_interface",
                        "switch": "SW0",
                        "switch_port": "SP0",
                        "controller_interface": "ETH0",
                    }
                ]
            ),
        )
    assert_single_error(exc_info, "FLYNC-ECU-MAJ-REF-073", "Switch 'SW0' referenced in connection 'bad' was not found")
