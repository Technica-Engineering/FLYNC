import pytest
from pydantic import ValidationError

from flync.model.flync_4_ecu.controller import (
    ComputeNodes,
    Controller,
    ControllerInterface,
    EmbeddedMetadata,
    EthernetInterface,
    PTPConfig,
    VirtualControllerInterface,
    VirtualSwitch,
    VirtualSwitchPort,
)
from flync.model.flync_4_metadata.metadata import BaseVersion

def test_bridge_port_invalid_reference():
    """
    Objective:
    Ensure referential integrity inside the controller.

    Every VirtualSwitchPort.node_connected maps to:
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
            VirtualSwitchPort(name="p1", node_connected="unknown_node"),
        ],
        vlans=[],
    )
    iface = EthernetInterface(name="eth0", interface_config=ctrl_iface)

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
            VirtualSwitchPort(name="p1", node_connected="eth0"),
            VirtualSwitchPort(name="p2", node_connected="vm1"),
        ],
        vlans=[],
    )
    iface = EthernetInterface(name="eth0", interface_config=ctrl_iface)
    controller = Controller(
        name="ctrl1",
        controller_metadata=embedded_metadata,
        ethernet_interfaces=[iface],
        virtual_switch=bridge,
    )

    assert controller.ethernet_interfaces[0].interface_config.compute_nodes[0].ptp_config is not None
