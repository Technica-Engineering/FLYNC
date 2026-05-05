import pytest
from pydantic import ValidationError

from flync.model.flync_4_ecu.controller import (
    ComputeNodes,
    Controller,
    ControllerInterface,
    EmbeddedMetadata,
    EthernetInterface,
    L2BridgePort,
    PTPConfig,
    VirtualControllerInterface,
    VirtualSwitch,
    VLANEntry,
)
from flync.model.flync_4_metadata.metadata import BaseVersion


@pytest.mark.xfail(reason="Known bug")
def test_compute_nodes_require_l2bridge():
    """
    Objective:
    Enforce that compute nodes cannot exist without a bridge.

    The architectural rule: all compute node traffic must traverse VirtualSwitch
    Prevents “orphaned” compute nodes with no data path

    Without this, model would allow impossible network topologies.
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
                mac_address="00:11:22:33:44:66",
                virtual_interfaces=[VirtualControllerInterface(name="vctrl", vlanid=10, addresses=[])],
            )
        ],
    )
    iface = EthernetInterface(interface_config=ctrl_iface)

    with pytest.raises(ValidationError):
        Controller(
            name="ctrl1",
            controller_metadata=embedded_metadata,
            ethernet_interfaces=[iface],
            virtual_switch=None,
        )


def test_bridge_port_invalid_reference():
    """
    Objective:
    Ensure referential integrity inside the controller.

    Every L2BridgePort.node_connected maps to:
    a ControllerInterface, OR a ComputeNodes
    Prevents typos / misconfigurations

    This avoids silent miswiring like "ethO" vs "eth0".
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
            L2BridgePort(name="p1", node_connected="unknown_node"),
        ],
        vlans=[],
    )
    iface = EthernetInterface(interface_config=ctrl_iface)

    with pytest.raises(ValidationError):
        Controller(
            name="ctrl1",
            controller_metadata=embedded_metadata,
            ethernet_interfaces=[iface],
            virtual_switch=bridge,
        )


def test_ptp_conflict_between_interface_and_compute_node():
    """
    Objective:
    Enforce mutual exclusivity of feature placement.

    Features like PTP/MACsec exist in only one layer
    either interface or compute node
    Prevents ambiguous ownership of functionality

    This protects against undefined runtime behavior (who actually handles PTP?).
    """
    with pytest.raises(ValidationError):
        ControllerInterface(
            name="eth0",
            mac_address="00:11:22:33:44:55",
            ptp_config=PTPConfig(),
            compute_nodes=[
                ComputeNodes(
                    name="vm1",
                    mac_address="00:11:22:33:44:66",
                    virtual_interfaces=[VirtualControllerInterface(name="vctrl", vlanid=10, addresses=[])],
                    ptp_config=PTPConfig(),
                )
            ],
        )


@pytest.mark.xfail(reason="Known bug")
def test_vlan_invalid_port_reference():
    """
    Objective:
    Ensure VLAN definitions are consistent with bridge topology.

    VLAN ports must exist in VirtualSwitch.ports
    Prevents dangling VLAN memberships

    Without this, VLAN configs would reference ghost ports, breaking connectivity logic.
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
        ports=[L2BridgePort(name="p1", node_connected="eth0")],
        vlans=[VLANEntry(name="test", id=10, default_priority=0, ports=["p2"])],
    )
    iface = EthernetInterface(interface_config=ctrl_iface)

    with pytest.raises(ValidationError):
        Controller(
            name="ctrl1",
            controller_metadata=embedded_metadata,
            ethernet_interfaces=[iface],
            virtual_switch=bridge,
        )


@pytest.mark.xfail(reason="Known bug")
def test_compute_node_not_in_bridge_ports():
    """
    Objective:
    Ensure every compute node is actually reachable.

    All compute nodes must appear in VirtualSwitch ports
    Prevents disconnected VMs

    Otherwise, you'd have compute nodes defined but no path to anything.
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
                mac_address="00:11:22:33:44:66",
                virtual_interfaces=[VirtualControllerInterface(name="vctrl", vlanid=10, addresses=[])],
            )
        ],
    )
    bridge = VirtualSwitch(
        name="br0",
        ports=[L2BridgePort(name="p1", node_connected="eth0")],
        vlans=[],
    )
    iface = EthernetInterface(interface_config=ctrl_iface)

    with pytest.raises(ValidationError):
        Controller(
            name="ctrl1",
            controller_metadata=embedded_metadata,
            ethernet_interfaces=[iface],
            virtual_switch=bridge,
        )


def test_feature_offload_to_compute_node_only():
    """
    Objective:
    Validate correct feature offloading behavior.

    Interface can delegate features (e.g., PTP) to compute nodes
    No conflict occurs when interface config is absent

    This ensures system supports flexible feature placement, not just centralized config.
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
        ptp_config=None,
        compute_nodes=[
            ComputeNodes(
                name="vm1",
                mac_address="00:11:22:33:44:66",
                virtual_interfaces=[VirtualControllerInterface(name="vctrl", vlanid=10, addresses=[])],
                ptp_config=PTPConfig(),
            )
        ],
    )
    bridge = VirtualSwitch(
        name="br0",
        ports=[
            L2BridgePort(name="p1", node_connected="eth0"),
            L2BridgePort(name="p2", node_connected="vm1"),
        ],
        vlans=[],
    )
    iface = EthernetInterface(interface_config=ctrl_iface)
    controller = Controller(
        name="ctrl1",
        controller_metadata=embedded_metadata,
        ethernet_interfaces=[iface],
        virtual_switch=bridge,
    )

    assert controller.ethernet_interfaces[0].interface_config.compute_nodes[0].ptp_config is not None


@pytest.mark.xfail(reason="Known bug")
def test_duplicate_name_between_interface_and_compute_node_should_fail():
    """
    Objective:
    Ensure that ControllerInterface and ComputeNode cannot share the same name.

    Having identical names creates ambiguity in node resolution (node_connected),
    since the system would not be able to distinguish whether a reference
    points to an interface or a compute node.

    This prevents undefined behavior in VirtualSwitch connectivity resolution.
    """
    ControllerInterface(
        name="eth0",
        mac_address="00:11:22:33:44:55",
        ptp_config=None,
        compute_nodes=[
            ComputeNodes(
                name="eth0",
                mac_address="00:11:22:33:44:66",
                virtual_interfaces=[VirtualControllerInterface(name="vctrl", vlanid=10, addresses=[])],
                ptp_config=PTPConfig(),
            )
        ],
    )
    with pytest.raises(ValidationError):
        VirtualSwitch(
            name="br0",
            ports=[
                L2BridgePort(name="p1", node_connected="eth0"),
                L2BridgePort(name="p2", node_connected="eth0"),
            ],
            vlans=[],
        )
