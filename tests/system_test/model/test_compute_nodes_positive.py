from flync.model.flync_4_ecu.controller import *
from flync.model.flync_4_metadata.metadata import *


def test_controller_with_bridge_and_compute_nodes_valid():
    """
    Ensure that a complete, correctly wired topology is accepted.

    - Controller ↔ Interface ↔ ComputeNode linkage works
    - VirtualSwitch connects both interface and compute node
    - VLAN enables communication between them
    - No invalid constraints are triggered

    This is baseline sanity check.
    """

    system_version = BaseVersion(version_schema="semver", version="0.9.0")
    embedded_metadata = EmbeddedMetadata(
        type="embedded",
        author="test_team",
        compatible_flync_version=system_version,
        target_system="my_system",
    )
    ctrl_iface = ControllerInterface(
        name="eth0",
        mac_address="00:11:22:33:44:55",
        compute_nodes=[
            ComputeNodes(
                name="vm1",
                mac_address="00:11:22:33:44:55",
                virtual_interfaces=[VirtualControllerInterface(name="vctrl", vlanid=10, addresses=[])],
            )
        ],
    )
    bridge = VirtualSwitch(
        name="br0",
        ports=[
            L2BridgePort(name="p1", node_connected="eth0"),
            L2BridgePort(name="p2", node_connected="vm1"),
        ],
        vlans=[VLANEntry(name="test", id=10, default_priority=0, ports=["p1", "p2"])],
    )
    iface = EthernetInterface(interface_config=ctrl_iface)
    controller = Controller(
        name="ctrl1",
        controller_metadata=embedded_metadata,
        ethernet_interfaces=[iface],
        virtual_switch=bridge,
    )

    assert controller.virtual_switch is not None


def test_multiple_interfaces_layer2_connectivity():
    """
    Objective:
    Validate Layer 2 connectivity across interfaces.

    Multiple interfaces can coexist in one bridge
    VLAN allows them to communicate
    Bridge behaves like a switch fabric

    This confirms model supports multi-port switching behavior.
    """
    system_version = BaseVersion(version_schema="semver", version="0.9.0")
    embedded_metadata = EmbeddedMetadata(
        type="embedded",
        author="test_team",
        compatible_flync_version=system_version,
        target_system="my_system",
    )
    ctrl_iface1 = ControllerInterface(
        name="eth0",
        mac_address="00:11:22:33:44:55",
        compute_nodes=[
            ComputeNodes(
                name="vm1",
                mac_address="00:11:22:33:44:55",
                virtual_interfaces=[VirtualControllerInterface(name="vctrl", vlanid=10, addresses=[])],
            )
        ],
    )
    ctrl_iface2 = ControllerInterface(
        name="eth1",
        mac_address="00:11:22:33:44:56",
        compute_nodes=[
            ComputeNodes(
                name="vm1",
                mac_address="00:11:22:33:44:55",
                virtual_interfaces=[VirtualControllerInterface(name="vctrl", vlanid=10, addresses=[])],
            )
        ],
    )
    bridge = VirtualSwitch(
        name="br0",
        ports=[
            L2BridgePort(name="p1", node_connected="eth0"),
            L2BridgePort(name="p2", node_connected="eth1"),
        ],
        vlans=[VLANEntry(name="test", id=1, default_priority=0, ports=["p1", "p2"])],
    )
    iface1 = EthernetInterface(interface_config=ctrl_iface1)
    iface2 = EthernetInterface(interface_config=ctrl_iface2)
    controller = Controller(
        name="ctrl1",
        controller_metadata=embedded_metadata,
        ethernet_interfaces=[iface1, iface2],
        virtual_switch=bridge,
    )

    assert len(controller.ethernet_interfaces) == 2
