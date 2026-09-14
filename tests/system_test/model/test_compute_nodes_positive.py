"""Positive tests for the virtualization subtree of a Controller: nested compute nodes, virtual switches and ``controller_topology``.

These pin the two guarantees the model is built on:

* the subtree is recursive - ``compute_nodes`` nest arbitrarily deep and the ``iter_subtree_*``
  accessors walk all of it, while ``get_interfaces()`` stays limited to the controller's own
  physical interfaces;
* ``controller_topology`` is a closed scope - every connection resolves against the controller's
  own virtual switches and subtree interfaces, and a software-to-hardware uplink is two hops in
  two files.
"""

import shutil
from pathlib import Path

import pytest

from flync.model.flync_4_ecu import ECU, EthernetInterface, EthernetInterfaceConfig
from flync.model.flync_4_ecu.controller_topology import (
    ControllerTopology,
    InterfaceToInterfaceLink,
    VirtualSwitchPortToInterface,
    VirtualSwitchPortToVirtualSwitchPort,
)
from flync.model.flync_4_ecu.internal_topology import ECUPortToSwitchPort, InternalTopology, SwitchPortToControllerInterface
from flync.model.flync_4_ecu.phy import BASET1, RGMII
from flync.model.flync_4_ecu.port import ECUPort
from flync.model.flync_4_ecu.switch import SwitchPort
from flync.sdk.workspace.flync_workspace import FLYNCWorkspace
from tests.model_builders import (
    make_compute_node,
    make_controller,
    make_ecu_metadata,
    make_eth_interface,
    make_ethernet_ecu,
    make_ipv4_address,
    make_model,
    make_switch,
    make_switch_port,
    make_vci,
    make_virtual_switch,
    make_vlan_entry,
)


def _node_interface(name: str, mac: str) -> EthernetInterface:
    """Return a PHY-less Ethernet interface for a compute node."""
    return make_eth_interface(name=name, mac=mac)


def _physical_interface(*, name: str = "ETH0", mac: str = "AA:BB:CC:DD:EE:FF") -> EthernetInterface:
    """Return a controller interface with the ``mii_config`` only a physical interface may carry."""
    return EthernetInterface(
        name=name,
        interface_config=EthernetInterfaceConfig(mac_address=mac, mii_config=RGMII(mode="mac"), virtual_interfaces=[make_vci()]),
    )


def _nested_controller(*, controller_topology=None):
    """Return a controller holding NODE_OUTER (own interface + inner bridge) with NODE_INNER nested inside it."""
    inner = make_compute_node(name="NODE_INNER", ethernet_interfaces=[_node_interface("NODE_INNER_eth0", "AA:BB:CC:DD:EE:03")])
    outer = make_compute_node(
        name="NODE_OUTER",
        ethernet_interfaces=[_node_interface("NODE_OUTER_eth0", "AA:BB:CC:DD:EE:04")],
        compute_nodes=[inner],
        virtual_switches=[make_virtual_switch(name="ibr0", port_names=["ibr0_p1", "ibr0_p2"])],
    )
    return make_controller(
        compute_nodes=[outer],
        virtual_switches=[make_virtual_switch(name="br0")],
        controller_topology=controller_topology,
    )


def test_node_interface_is_owned_by_its_compute_node():
    """A compute node interface reports the compute node as its owner, so ``get_other_interfaces`` returns node siblings, not controller ones."""
    node = make_compute_node(
        name="NODE0",
        ethernet_interfaces=[_node_interface("NODE0_eth0", "AA:BB:CC:DD:EE:0A"), _node_interface("NODE0_eth1", "AA:BB:CC:DD:EE:0B")],
    )
    controller = make_controller(compute_nodes=[node])

    iface = controller.compute_nodes[0].ethernet_interfaces[0]
    assert iface.get_controller().name == "NODE0"
    assert [sibling.name for sibling in iface.get_other_interfaces()] == ["NODE0_eth0", "NODE0_eth1"]


def test_subtree_accessors_walk_two_levels_of_nesting():
    """A compute node nested inside a compute node, and a virtual switch declared inside that node, are both reachable from the controller.

    ``get_interfaces()`` stays the ECU-visible view - the controller's own physical interfaces only.
    """
    controller = _nested_controller()

    assert [iface.name for iface in controller.get_interfaces()] == ["ETH0"]
    assert [node.name for node in controller.iter_subtree_compute_nodes()] == ["NODE_OUTER", "NODE_INNER"]
    assert [switch.name for switch in controller.iter_subtree_switches()] == ["br0", "ibr0"]
    assert [iface.name for iface in controller.iter_subtree_interfaces()] == ["ETH0", "NODE_OUTER_eth0", "NODE_INNER_eth0"]


def test_compute_node_may_declare_only_virtual_switches():
    """A compute node that only bridges its guests' traffic needs no interfaces of its own."""
    node = make_compute_node(name="NODE0", ethernet_interfaces=[], virtual_switches=[make_virtual_switch(name="ibr0")])

    assert node.get_interfaces() == []
    assert [switch.name for switch in node.virtual_switches] == ["ibr0"]


@pytest.mark.parametrize(
    ("connection", "expected_class", "expected_endpoints"),
    [
        pytest.param(
            {"id": "c1", "type": "switch_port_to_controller_interface", "switch_port": "br0_p1", "controller_interface": "NODE0_eth0"},
            VirtualSwitchPortToInterface,
            ("br0", "br0_p1", "NODE0", "NODE0_eth0"),
            id="virtual_switch_port_to_node_interface",
        ),
        pytest.param(
            {
                "id": "c2",
                "type": "controller_interface_to_controller_interface",
                "controller_interface": "NODE0_eth0",
                "controller_interface2": "ETH0",
            },
            InterfaceToInterfaceLink,
            ("NODE0", "NODE0_eth0", "CTRL0", "ETH0"),
            id="point_to_point_no_switch",
        ),
        pytest.param(
            {"id": "c3", "type": "switch_to_switch_same_ecu", "switch_port": "br0_p1", "switch2_port": "br1_p1"},
            VirtualSwitchPortToVirtualSwitchPort,
            ("br0", "br0_p1", "br1", "br1_p1"),
            id="virtual_switch_to_virtual_switch",
        ),
    ],
)
def test_controller_topology_connection_resolves_inside_the_subtree(connection, expected_class, expected_endpoints):
    """Each of the three connection types binds both endpoints from bare names within the controller subtree."""
    controller = make_controller(
        compute_nodes=[make_compute_node(name="NODE0")],
        virtual_switches=[make_virtual_switch(name="br0"), make_virtual_switch(name="br1", port_names=["br1_p1", "br1_p2"])],
        controller_topology=ControllerTopology(connections=[connection]),
    )

    conn = controller.controller_topology.connections[0].root
    assert isinstance(conn, expected_class)
    if isinstance(conn, VirtualSwitchPortToVirtualSwitchPort):
        resolved = (conn.switch.name, conn.switch_port.name, conn.switch2.name, conn.switch2_port.name)
    elif isinstance(conn, VirtualSwitchPortToInterface):
        resolved = (conn.switch.name, conn.switch_port.name, conn.controller.name, conn.iface.name)
    else:
        resolved = (conn.controller.name, conn.iface.name, conn.controller2.name, conn.iface2.name)
    assert resolved == expected_endpoints


def test_nested_node_interface_binds_to_a_virtual_switch_two_levels_up():
    """A nested compute node may bypass its parent and land on a virtual switch declared on the controller itself."""
    controller = _nested_controller(
        controller_topology=ControllerTopology(
            connections=[
                {"id": "bypass", "type": "switch_port_to_controller_interface", "switch_port": "br0_p1", "controller_interface": "NODE_INNER_eth0"},
                {"id": "inner", "type": "switch_port_to_controller_interface", "switch_port": "ibr0_p1", "controller_interface": "NODE_OUTER_eth0"},
            ]
        ),
    )

    bypass, inner = (conn.root for conn in controller.controller_topology.connections)
    assert (bypass.switch.name, bypass.iface.name) == ("br0", "NODE_INNER_eth0")
    assert (inner.switch.name, inner.iface.name) == ("ibr0", "NODE_OUTER_eth0")


def test_virtual_switch_uplink_reaches_the_ecu_in_two_hops():
    """The software-to-hardware uplink is two connections in two scopes: vSwitch to physical interface, then that interface to a hardware port."""
    physical = _physical_interface()
    controller = make_controller(
        ethernet_interfaces=[physical],
        compute_nodes=[make_compute_node(name="NODE0")],
        virtual_switches=[make_virtual_switch(name="br0", port_names=["UPLINK", "br0_node"])],
        controller_topology=ControllerTopology(
            connections=[
                {"id": "uplink", "type": "switch_port_to_controller_interface", "switch_port": "UPLINK", "controller_interface": "ETH0"},
                {"id": "guest", "type": "switch_port_to_controller_interface", "switch_port": "br0_node", "controller_interface": "NODE0_eth0"},
            ]
        ),
    )
    hardware_switch = make_switch(
        name="SW0",
        ports=[
            SwitchPort(name="SP0", silicon_port_no=0, default_vlan_id=10, mii_config=RGMII(mode="phy")),
            make_switch_port(name="SP1", silicon_port_no=1),
        ],
        vlans=[make_vlan_entry(ports=("SP0", "SP1"))],
    )
    ecu = ECU(
        name="ECU1",
        controllers=[controller],
        switches=[hardware_switch],
        ports=[ECUPort(name="SP1_port", mdi_config=BASET1())],
        topology=InternalTopology(
            connections=[
                SwitchPortToControllerInterface(id="hw_hop", switch_port="SP0", switch="SW0", controller_interface="ETH0", controller="CTRL0"),
                ECUPortToSwitchPort(id="ext", ecu_port="SP1_port", switch_port="SP1", switch="SW0"),
            ]
        ),
        ecu_metadata=make_ecu_metadata(),
    )
    make_model(ecus=[ecu])

    uplink = controller.controller_topology.connections[0].root
    assert (uplink.switch_port.name, uplink.iface.name) == ("UPLINK", "ETH0")
    # The one interface that crosses the controller boundary carries both hops.
    assert {component.name for component in physical._connected_component} == {"UPLINK", "SP0"}


def test_controller_addresses_include_compute_node_interfaces():
    """A compute node's IPs and MACs belong to the controller hosting it, so the aggregate accessors walk the subtree."""
    node = make_compute_node(
        name="NODE0",
        ethernet_interfaces=[
            make_eth_interface(
                name="NODE0_eth0",
                mac="AA:BB:CC:DD:EE:01",
                vcis=[make_vci(name="vi20", vlanid=20, addresses=[make_ipv4_address(address="10.0.20.6")])],
            ),
        ],
    )
    controller = make_controller(compute_nodes=[node])

    assert controller.get_all_ips() == ["10.0.20.5", "10.0.20.6"]
    assert [str(mac) for mac in controller.get_all_macs()] == ["aa:bb:cc:dd:ee:ff", "aa:bb:cc:dd:ee:01"]


def test_virtual_switch_name_may_match_a_hardware_switch_name():
    """Virtual and hardware switches live in namespaces that never meet, since no connection can span both."""
    controller = make_controller(virtual_switches=[make_virtual_switch(name="SW0")])
    wiring = make_ethernet_ecu(controllers=[controller])

    ecu = ECU(
        name="ECU1",
        controllers=[controller],
        switches=[make_switch(name="SW0")],
        ports=wiring.ports,
        topology=wiring.topology,
        ecu_metadata=make_ecu_metadata(),
    )

    assert [switch.name for switch in ecu.switches] == ["SW0"]
    assert [switch.name for switch in controller.iter_subtree_switches()] == ["SW0"]


def test_example_variant_loads_the_virtualization_subtree_from_disk(tmpdir):
    """The ``compute_nodes/``, ``switches/`` and ``controller_topology.flync.yaml`` layout loads and resolves end to end."""
    variant = "ecu_variant_5_single_controller_single_iface_multiple_vms"
    workspace_path = Path(tmpdir)
    (workspace_path / "ecus").mkdir()
    shutil.copytree(Path("examples/ecu_variants") / variant, workspace_path / "ecus" / variant, dirs_exist_ok=True)
    shutil.copy2(Path("examples/flync_example/system_metadata.flync.yaml"), workspace_path / "system_metadata.flync.yaml")

    workspace = FLYNCWorkspace.load_workspace(workspace_name=variant, workspace_path=workspace_path)

    assert [error for error in workspace.load_errors or [] if error.get("type") != "warning"] == []
    controller = workspace.flync_model.ecus[0].controllers[0]
    assert [node.name for node in controller.compute_nodes] == ["ecu1_c1_node1", "ecu1_c1_node2"]
    assert [switch.name for switch in controller.switches] == ["br0"]
    assert [conn.root.iface.name for conn in controller.controller_topology.connections] == [
        "ecu1_controller1_iface1",
        "ecu1_c1_node1_eth0",
        "ecu1_c1_node2_eth0",
    ]
