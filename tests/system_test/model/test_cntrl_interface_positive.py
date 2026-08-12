import json
import shutil
from pathlib import Path

import pytest

from flync.core.datatypes.ipaddress import IPv4AddressEntry
from flync.model.flync_4_ecu.can_interface import CANInterface
from flync.model.flync_4_ecu.controller import (
    ComputeNodes,
    Controller,
    EthernetInterface,
    EthernetInterfaceConfig,
    VirtualControllerInterface,
    VirtualSwitch,
    VirtualSwitchPort,
)
from flync.model.flync_4_ecu.controller_interface import ControllerInterface
from flync.model.flync_4_ecu.ecu import ECU
from flync.model.flync_4_ecu.internal_topology import ECUPortToControllerInterface, InternalTopology
from flync.model.flync_4_ecu.lin_interface import LINMasterInterface, LINSlaveInterface
from flync.model.flync_4_ecu.phy import BASET1
from flync.model.flync_4_ecu.port import ECUPort
from flync.model.flync_4_ecu.router import RouteEntry
from flync.model.flync_4_ecu.sockets import IPv4AddressEndpoint
from flync.model.flync_4_ecu.vlan_entry import VLANEntry


def _make_ethernet_ecu_ports_and_topology(controller_name: str, iface_name: str) -> tuple[list[ECUPort], InternalTopology]:
    """Build the minimal ECU ports and internal topology required for an ECU with an Ethernet interface."""

    port = ECUPort(name=f"{controller_name}_{iface_name}_port", mdi_config=BASET1())
    topology = InternalTopology(
        connections=[
            ECUPortToControllerInterface(
                id=f"conn_{controller_name}_{iface_name}",
                ecu_port=port.name,
                controller_interface=iface_name,
                controller=controller_name,
            )
        ]
    )
    return [port], topology


from flync.model.flync_4_metadata.metadata import BaseVersion, ECUMetadata, EmbeddedMetadata, SystemMetadata
from flync.model.flync_4_topology.ethernet_topology import EthernetTopology, FLYNCTopology
from flync.model.flync_model import FLYNCModel
from flync.sdk.workspace.flync_workspace import FLYNCWorkspace


# Verify that an ECU Controller can contain an EthernetInterface.
def test_controller_with_ethernet_interface():

    eth_iface = EthernetInterface(
        name="eth_iface", interface_config=EthernetInterfaceConfig(virtual_interfaces=[VirtualControllerInterface(name="vif0", addresses=[])])
    )

    controller = Controller(
        name="CTRL1",
        controller_metadata=EmbeddedMetadata(
            type="embedded", author="TestTeam", target_system="Device1", compatible_flync_version=BaseVersion(version="0.13.0")
        ),
        ethernet_interfaces=[eth_iface],
    )

    ports, topology = _make_ethernet_ecu_ports_and_topology("CTRL1", "eth_iface")
    ecu = ECU(
        name="ECU1",
        controllers=[controller],
        ports=ports,
        topology=topology,
        ecu_metadata=ECUMetadata(type="ecu", author="TestTeam", compatible_flync_version=BaseVersion(version="0.13.0")),
    )

    flync_model = FLYNCModel(
        ecus=[ecu],
        topology=FLYNCTopology(system_topology=EthernetTopology(connections=[])),
        metadata=SystemMetadata(
            type="system", release=BaseVersion(version="0.13.0"), author="TestTeam", compatible_flync_version=BaseVersion(version="0.13.0")
        ),
    )

    assert flync_model.ecus[0].controllers[0].ethernet_interfaces[0] == eth_iface


# Verify that a Controller can contain a CANInterface.
def test_controller_with_can_interface():

    can_iface = CANInterface(name="can_iface", bus_ref="can_bus")

    controller = Controller(
        name="CTRL1",
        controller_metadata=EmbeddedMetadata(
            type="embedded", author="TestTeam", target_system="Device1", compatible_flync_version=BaseVersion(version="0.13.0")
        ),
        can_interfaces=[can_iface],
    )

    ecu = ECU(
        name="ECU1",
        controllers=[controller],
        topology=InternalTopology(),
        ecu_metadata=ECUMetadata(type="ecu", author="TestTeam", compatible_flync_version=BaseVersion(version="0.13.0")),
    )

    flync_model = FLYNCModel(
        ecus=[ecu],
        topology=FLYNCTopology(system_topology=EthernetTopology(connections=[])),
        metadata=SystemMetadata(
            type="system", release=BaseVersion(version="0.13.0"), author="TestTeam", compatible_flync_version=BaseVersion(version="0.13.0")
        ),
    )

    assert flync_model.ecus[0].controllers[0].can_interfaces[0] == can_iface


# Verify that a Controller can contain a LINInterface.
def test_controller_with_lin_interface():

    lin_slave = LINSlaveInterface(name="lin_slave_iface", bus_ref="lin_bus", lin_protocol="2.0", configured_nad=1, initial_nad=1)

    lin_master = LINMasterInterface(name="lin_master_iface", bus_ref="lin_bus", lin_protocol="2.0", p2_min=10, st_min=10)

    controller = Controller(
        name="CTRL1",
        controller_metadata=EmbeddedMetadata(
            type="embedded", author="TestTeam", target_system="Device1", compatible_flync_version=BaseVersion(version="0.13.0")
        ),
        lin_interfaces=[lin_master, lin_slave],
    )

    ecu = ECU(
        name="ECU1",
        controllers=[controller],
        topology=InternalTopology(),
        ecu_metadata=ECUMetadata(type="ecu", author="TestTeam", compatible_flync_version=BaseVersion(version="0.13.0")),
    )

    flync_model = FLYNCModel(
        ecus=[ecu],
        topology=FLYNCTopology(system_topology=EthernetTopology(connections=[])),
        metadata=SystemMetadata(
            type="system", release=BaseVersion(version="0.13.0"), author="TestTeam", compatible_flync_version=BaseVersion(version="0.13.0")
        ),
    )

    assert len(flync_model.ecus[0].controllers[0].lin_interfaces) == 2
    lin_names = {interface.name for interface in flync_model.ecus[0].controllers[0].lin_interfaces}

    assert "lin_master_iface" in lin_names
    assert "lin_slave_iface" in lin_names


# Verify that one ECU can contain multiple communication technologies simultaneously: Ethernet + CAN + LIN
def test_controller_with_mixed_communication_interfaces():

    can_iface = CANInterface(name="can_iface", bus_ref="can_bus")
    eth_iface = EthernetInterface(
        name="eth_iface", interface_config=EthernetInterfaceConfig(virtual_interfaces=[VirtualControllerInterface(name="vif0", addresses=[])])
    )
    lin_iface_slave = LINSlaveInterface(name="lin_slave_iface", bus_ref="lin_bus", lin_protocol="2.0", configured_nad=1, initial_nad=1)
    lin_iface_master = LINMasterInterface(name="lin_master_iface", bus_ref="lin_bus", lin_protocol="2.0", p2_min=10, st_min=10)
    controller = Controller(
        name="CTRL1",
        controller_metadata=EmbeddedMetadata(
            type="embedded", author="TestTeam", target_system="Device1", compatible_flync_version=BaseVersion(version="0.13.0")
        ),
        can_interfaces=[can_iface],
        ethernet_interfaces=[eth_iface],
        lin_interfaces=[lin_iface_master, lin_iface_slave],
    )

    ports, topology = _make_ethernet_ecu_ports_and_topology("CTRL1", "eth_iface")
    ecu = ECU(
        name="ECU1",
        controllers=[controller],
        ports=ports,
        topology=topology,
        ecu_metadata=ECUMetadata(type="ecu", author="TestTeam", compatible_flync_version=BaseVersion(version="0.13.0")),
    )

    flync_model = FLYNCModel(
        ecus=[ecu],
        topology=FLYNCTopology(system_topology=EthernetTopology(connections=[])),
        metadata=SystemMetadata(
            type="system", release=BaseVersion(version="0.13.0"), author="TestTeam", compatible_flync_version=BaseVersion(version="0.13.0")
        ),
    )

    assert len(controller.ethernet_interfaces) == 1
    assert isinstance(controller.ethernet_interfaces[0], EthernetInterface)
    assert controller.ethernet_interfaces[0].name == "eth_iface"

    assert len(controller.can_interfaces) == 1
    assert isinstance(controller.can_interfaces[0], CANInterface)
    assert controller.can_interfaces[0].name == "can_iface"
    assert controller.can_interfaces[0].bus_ref == "can_bus"

    assert len(controller.lin_interfaces) == 2

    lin_names = {iface.name for iface in controller.lin_interfaces}
    assert "lin_master_iface" in lin_names
    assert "lin_slave_iface" in lin_names


# Verify that ControllerTopology can work with the ControllerInterface base class and accept EthernetInterface, CANInterface, and LINInterface derived classes.
def test_controller_interface_polymorphism_support():

    interfaces = [
        EthernetInterface(
            name="eth_iface", interface_config=EthernetInterfaceConfig(virtual_interfaces=[VirtualControllerInterface(name="vif0", addresses=[])])
        ),
        CANInterface(name="can_iface", bus_ref="can_bus"),
        LINMasterInterface(name="lin_master_iface", bus_ref="lin_bus", lin_protocol="2.0", p2_min=10, st_min=10),
    ]

    assert all(isinstance(iface, ControllerInterface) for iface in interfaces)

    assert isinstance(interfaces[0], EthernetInterface)
    assert isinstance(interfaces[1], CANInterface)
    assert isinstance(interfaces[2], LINMasterInterface)


# Verify that a Controller can contain multiple CAN interfaces while keeping each CAN bus independent (CAN0 Powertrain, CAN1 Body, CAN2 Diagnostic).
def test_multi_can_controller_support():

    can_powertrain = CANInterface(name="CAN0", bus_ref="powertrain_can_bus")

    can_body = CANInterface(name="CAN1", bus_ref="body_can_bus")

    can_diagnostic = CANInterface(name="CAN2", bus_ref="diagnostic_can_bus")

    controller = Controller(
        name="CTRL_GATEWAY",
        controller_metadata=EmbeddedMetadata(
            type="embedded", author="TestTeam", target_system="VehicleGateway", compatible_flync_version=BaseVersion(version="0.13.0")
        ),
        can_interfaces=[can_powertrain, can_body, can_diagnostic],
    )

    ecu = ECU(
        name="Gateway_ECU",
        controllers=[controller],
        topology=InternalTopology(),
        ecu_metadata=ECUMetadata(type="ecu", author="TestTeam", compatible_flync_version=BaseVersion(version="0.13.0")),
    )

    flync_model = FLYNCModel(
        ecus=[ecu],
        topology=FLYNCTopology(system_topology=EthernetTopology(connections=[])),
        metadata=SystemMetadata(
            type="system", release=BaseVersion(version="0.13.0"), author="TestTeam", compatible_flync_version=BaseVersion(version="0.13.0")
        ),
    )

    assert len(flync_model.ecus) == 1
    assert len(flync_model.ecus[0].controllers) == 1

    controller = flync_model.ecus[0].controllers[0]

    assert len(controller.can_interfaces) == 3

    assert controller.can_interfaces[0].name == "CAN0"
    assert controller.can_interfaces[0].bus_ref == "powertrain_can_bus"

    assert controller.can_interfaces[1].name == "CAN1"
    assert controller.can_interfaces[1].bus_ref == "body_can_bus"

    assert controller.can_interfaces[2].name == "CAN2"
    assert controller.can_interfaces[2].bus_ref == "diagnostic_can_bus"

    assert all(isinstance(interface, CANInterface) for interface in controller.can_interfaces)

    bus_refs = {interface.bus_ref for interface in controller.can_interfaces}

    assert bus_refs == {"powertrain_can_bus", "body_can_bus", "diagnostic_can_bus"}


# Verify that two different Controllers/ECUs can use the same interface name because interface naming scope is limited to the Controller.
def test_interface_name_scope_validation():

    eth_iface_ecu1 = EthernetInterface(
        name="eth0", interface_config=EthernetInterfaceConfig(virtual_interfaces=[VirtualControllerInterface(name="vif0", addresses=[])])
    )

    eth_iface_ecu2 = EthernetInterface(
        name="eth0", interface_config=EthernetInterfaceConfig(virtual_interfaces=[VirtualControllerInterface(name="vif0", addresses=[])])
    )

    controller_1 = Controller(
        name="CTRL_CAMERA",
        controller_metadata=EmbeddedMetadata(
            type="embedded", author="TestTeam", target_system="CameraSystem", compatible_flync_version=BaseVersion(version="0.13.0")
        ),
        ethernet_interfaces=[eth_iface_ecu1],
    )

    controller_2 = Controller(
        name="CTRL_RADAR",
        controller_metadata=EmbeddedMetadata(
            type="embedded", author="TestTeam", target_system="RadarSystem", compatible_flync_version=BaseVersion(version="0.13.0")
        ),
        ethernet_interfaces=[eth_iface_ecu2],
    )

    ports_1, topology_1 = _make_ethernet_ecu_ports_and_topology("CTRL_CAMERA", "eth0")
    ecu_1 = ECU(
        name="CAMERA_ECU",
        controllers=[controller_1],
        ports=ports_1,
        topology=topology_1,
        ecu_metadata=ECUMetadata(type="ecu", author="TestTeam", compatible_flync_version=BaseVersion(version="0.13.0")),
    )

    ports_2, topology_2 = _make_ethernet_ecu_ports_and_topology("CTRL_RADAR", "eth0")
    ecu_2 = ECU(
        name="RADAR_ECU",
        controllers=[controller_2],
        ports=ports_2,
        topology=topology_2,
        ecu_metadata=ECUMetadata(type="ecu", author="TestTeam", compatible_flync_version=BaseVersion(version="0.13.0")),
    )

    flync_model = FLYNCModel(
        ecus=[ecu_1, ecu_2],
        topology=FLYNCTopology(system_topology=EthernetTopology(connections=[])),
        metadata=SystemMetadata(
            type="system", release=BaseVersion(version="0.13.0"), author="TestTeam", compatible_flync_version=BaseVersion(version="0.13.0")
        ),
    )

    assert len(flync_model.ecus) == 2

    camera_controller = flync_model.ecus[0].controllers[0]
    radar_controller = flync_model.ecus[1].controllers[0]

    assert camera_controller.ethernet_interfaces[0].name == "eth0"
    assert radar_controller.ethernet_interfaces[0].name == "eth0"

    assert camera_controller.name != radar_controller.name

    assert camera_controller.ethernet_interfaces[0] is not radar_controller.ethernet_interfaces[0]

    assert isinstance(camera_controller.ethernet_interfaces[0], ControllerInterface)
    assert isinstance(radar_controller.ethernet_interfaces[0], ControllerInterface)


# Verify that an Ethernet interface supports multiple VLAN virtual interfaces (example: Safety, Infotainment, Management VLANs).
def test_ethernet_vlan_configuration_support():

    safety_vlan = VirtualControllerInterface(name="safety_vlan", vlanid=10, addresses=[])

    infotainment_vlan = VirtualControllerInterface(name="infotainment_vlan", vlanid=20, addresses=[])

    management_vlan = VirtualControllerInterface(name="management_vlan", vlanid=30, addresses=[])

    eth_iface = EthernetInterface(
        name="eth0",
        interface_config=EthernetInterfaceConfig(
            virtual_interfaces=[
                safety_vlan,
                infotainment_vlan,
                management_vlan,
            ]
        ),
    )

    controller = Controller(
        name="CTRL1",
        controller_metadata=EmbeddedMetadata(
            type="embedded",
            author="TestTeam",
            target_system="Vehicle",
            compatible_flync_version=BaseVersion(version="0.13.0"),
        ),
        ethernet_interfaces=[eth_iface],
    )

    ports, topology = _make_ethernet_ecu_ports_and_topology("CTRL1", "eth0")
    ecu = ECU(
        name="ECU1",
        controllers=[controller],
        ports=ports,
        topology=topology,
        ecu_metadata=ECUMetadata(
            type="ecu",
            author="TestTeam",
            compatible_flync_version=BaseVersion(version="0.13.0"),
        ),
    )

    flync_model = FLYNCModel(
        ecus=[ecu],
        topology=FLYNCTopology(system_topology=EthernetTopology(connections=[])),
        metadata=SystemMetadata(
            type="system",
            release=BaseVersion(version="0.13.0"),
            author="TestTeam",
            compatible_flync_version=BaseVersion(version="0.13.0"),
        ),
    )

    controller = flync_model.ecus[0].controllers[0]
    eth_iface = controller.ethernet_interfaces[0]

    assert len(controller.ethernet_interfaces) == 1

    assert len(eth_iface.interface_config.virtual_interfaces) == 3

    vlan_names = {vif.name for vif in eth_iface.interface_config.virtual_interfaces}

    assert vlan_names == {
        "safety_vlan",
        "infotainment_vlan",
        "management_vlan",
    }

    assert all(isinstance(vif, VirtualControllerInterface) for vif in eth_iface.interface_config.virtual_interfaces)


# Verify that a Gateway ECU can connect Ethernet networks with CAN/LIN networks through valid gateway configuration and topology resolution.
def test_gateway_communication_topology():

    ethernet_to_can_route = RouteEntry(
        destination=IPv4AddressEntry(address="10.0.0.0", ipv4netmask="255.255.255.0"), default_gateway="192.168.1.10", egress_interface="can_gateway"
    )

    ethernet_to_lin_route = RouteEntry(
        destination=IPv4AddressEntry(address="172.16.0.0", ipv4netmask="255.255.255.0"),
        default_gateway="192.168.1.20",
        egress_interface="lin_gateway_master",
    )

    eth_iface = EthernetInterface(
        name="eth_gateway",
        interface_config=EthernetInterfaceConfig(
            virtual_interfaces=[
                VirtualControllerInterface(
                    name="can_gateway", vlanid=10, addresses=[IPv4AddressEndpoint(address="192.168.1.10", ipv4netmask="255.255.255.0")]
                ),
                VirtualControllerInterface(
                    name="lin_gateway_master", vlanid=20, addresses=[IPv4AddressEndpoint(address="192.168.1.20", ipv4netmask="255.255.255.0")]
                ),
            ],
            routing_table=[ethernet_to_can_route, ethernet_to_lin_route],
        ),
    )

    can_iface = CANInterface(name="can_gateway", bus_ref="vehicle_can_bus")

    lin_master = LINMasterInterface(name="lin_gateway_master", bus_ref="body_lin_bus", lin_protocol="2.0", p2_min=10, st_min=10)


# Verify that a Controller can contain a physical Ethernet interface with multiple virtual Ethernet interfaces.
def test_physical_and_virtual_ethernet_interface_support():

    physical_eth_iface = EthernetInterface(
        name="eth0",
        interface_config=EthernetInterfaceConfig(
            virtual_interfaces=[
                VirtualControllerInterface(name="eth_vif_safety", vlanid=10, addresses=[]),
                VirtualControllerInterface(name="eth_vif_infotainment", vlanid=20, addresses=[]),
            ]
        ),
    )

    controller = Controller(
        name="CTRL_ETH",
        controller_metadata=EmbeddedMetadata(
            type="embedded", author="TestTeam", target_system="VehicleEthernetController", compatible_flync_version=BaseVersion(version="0.13.0")
        ),
        ethernet_interfaces=[physical_eth_iface],
    )

    ports, topology = _make_ethernet_ecu_ports_and_topology("CTRL_ETH", "eth0")
    ecu = ECU(
        name="ETH_ECU",
        controllers=[controller],
        ports=ports,
        topology=topology,
        ecu_metadata=ECUMetadata(type="ecu", author="TestTeam", compatible_flync_version=BaseVersion(version="0.13.0")),
    )

    flync_model = FLYNCModel(
        ecus=[ecu],
        topology=FLYNCTopology(system_topology=EthernetTopology(connections=[])),
        metadata=SystemMetadata(
            type="system", release=BaseVersion(version="0.13.0"), author="TestTeam", compatible_flync_version=BaseVersion(version="0.13.0")
        ),
    )

    controller = flync_model.ecus[0].controllers[0]

    assert len(controller.ethernet_interfaces) == 1

    eth_iface = controller.ethernet_interfaces[0]

    assert isinstance(eth_iface, EthernetInterface)

    assert eth_iface.name == "eth0"

    virtual_interfaces = eth_iface.interface_config.virtual_interfaces

    assert len(virtual_interfaces) == 2

    assert all(isinstance(vif, VirtualControllerInterface) for vif in virtual_interfaces)

    virtual_names = {vif.name for vif in virtual_interfaces}

    assert virtual_names == {"eth_vif_safety", "eth_vif_infotainment"}

    vlan_ids = {vif.vlanid for vif in virtual_interfaces}

    assert vlan_ids == {10, 20}


# Verify that an HPC controller supports Ethernet physical interfaces, virtual Ethernet interfaces, CAN/LIN interfaces, Virtual Switches, and multiple compute nodes/VMs.
def test_hpc_network_architecture_support():

    eth_iface = EthernetInterface(
        name="eth_hpc0",
        interface_config=EthernetInterfaceConfig(
            mac_address="00:11:22:33:44:55",
            compute_nodes=[
                ComputeNodes(
                    name="VM_CAMERA",
                    mac_address="02:00:00:00:00:10",
                    virtual_interfaces=[VirtualControllerInterface(name="camera_vif", vlanid=10, addresses=[])],
                ),
                ComputeNodes(
                    name="VM_AI",
                    mac_address="02:00:00:00:00:20",
                    virtual_interfaces=[VirtualControllerInterface(name="ai_vif", vlanid=20, addresses=[])],
                ),
            ],
            virtual_interfaces=[
                VirtualControllerInterface(name="safety_vlan", vlanid=30, addresses=[]),
                VirtualControllerInterface(name="service_vlan", vlanid=40, addresses=[]),
            ],
        ),
    )

    can_iface = CANInterface(name="can_hpc", bus_ref="powertrain_can_bus")

    lin_master = LINMasterInterface(name="lin_hpc_master", bus_ref="body_lin_bus", lin_protocol="2.0", p2_min=10, st_min=10)

    virtual_switch = VirtualSwitch(
        name="hpc_virtual_switch",
        ports=[
            VirtualSwitchPort(name="eth_hpc0_port", node_connected="eth_hpc0"),
            VirtualSwitchPort(name="VM_CAMERA_port", node_connected="VM_CAMERA"),
            VirtualSwitchPort(name="VM_AI_port", node_connected="VM_AI"),
        ],
        vlans=[
            VLANEntry(name="camera_vlan", id=10, default_priority=0, ports=["VM_CAMERA_port"]),
            VLANEntry(name="ai_vlan", id=20, default_priority=0, ports=["VM_AI_port"]),
        ],
    )

    controller = Controller(
        name="HPC_CONTROLLER",
        controller_metadata=EmbeddedMetadata(
            type="embedded", author="TestTeam", target_system="HPC_Domain_Controller", compatible_flync_version=BaseVersion(version="0.13.0")
        ),
        ethernet_interfaces=[eth_iface],
        can_interfaces=[can_iface],
        lin_interfaces=[lin_master],
        virtual_switch=virtual_switch,
    )

    ports, topology = _make_ethernet_ecu_ports_and_topology("HPC_CONTROLLER", "eth_hpc0")
    ecu = ECU(
        name="HPC_ECU",
        controllers=[controller],
        ports=ports,
        topology=topology,
        ecu_metadata=ECUMetadata(type="ecu", author="TestTeam", compatible_flync_version=BaseVersion(version="0.13.0")),
    )

    flync_model = FLYNCModel(
        ecus=[ecu],
        topology=FLYNCTopology(system_topology=EthernetTopology(connections=[])),
        metadata=SystemMetadata(
            type="system", release=BaseVersion(version="0.13.0"), author="TestTeam", compatible_flync_version=BaseVersion(version="0.13.0")
        ),
    )

    controller = flync_model.ecus[0].controllers[0]

    assert len(controller.ethernet_interfaces) == 1

    eth_iface = controller.ethernet_interfaces[0]

    assert isinstance(eth_iface, EthernetInterface)

    assert eth_iface.name == "eth_hpc0"

    virtual_interfaces = eth_iface.interface_config.virtual_interfaces

    assert len(virtual_interfaces) == 2

    assert {vif.name for vif in virtual_interfaces} == {"safety_vlan", "service_vlan"}

    compute_nodes = eth_iface.interface_config.compute_nodes

    assert len(compute_nodes) == 2

    assert {node.name for node in compute_nodes} == {"VM_CAMERA", "VM_AI"}

    assert len(controller.can_interfaces) == 1

    assert isinstance(controller.can_interfaces[0], CANInterface)

    assert controller.can_interfaces[0].bus_ref == "powertrain_can_bus"

    assert len(controller.lin_interfaces) == 1

    assert isinstance(controller.lin_interfaces[0], LINMasterInterface)

    assert controller.lin_interfaces[0].bus_ref == "body_lin_bus"

    assert controller.virtual_switch.name == "hpc_virtual_switch"


ECU_VARIANTS_DIR = Path("examples/ecu_variants")

ecu_folders = [ecu.name for ecu in ECU_VARIANTS_DIR.iterdir() if ecu.is_dir()]


# Verify that ECU variants with single communication interface configurations are correctly loaded from the workspace structure.
@pytest.mark.xfail(reason="FLYNC-1333,FLYNC-1334")
@pytest.mark.parametrize("ecu_folder", ecu_folders)
def test_load_single_interface_configuration(tmpdir, ecu_folder):

    tmp_path = Path(tmpdir)
    examples = Path("examples")

    ecus_dir = tmp_path / "ecus"
    ecus_dir.mkdir()

    shutil.copytree(examples / "ecu_variants" / ecu_folder, ecus_dir / ecu_folder, dirs_exist_ok=True)

    shutil.copy2(examples / "flync_example" / "system_metadata.flync.yaml", tmp_path / "system_metadata.flync.yaml")

    workspace = FLYNCWorkspace.load_workspace(workspace_name=ecu_folder, workspace_path=tmp_path)
    assert workspace is not None

    model = workspace.flync_model
    assert model is not None

    assert model.ecus, f"No ECUs loaded for {ecu_folder}"

    for ecu in model.ecus:
        assert ecu.controllers, f"No controllers loaded for ECU {ecu.name}"

        for controller in ecu.controllers:
            assert (
                controller.ethernet_interfaces or controller.can_interfaces or controller.lin_interfaces
            ), f"{controller.name} has no communication interface"


# Verify that multiple communication interfaces (Ethernet, CAN, LIN) are correctly loaded and mapped to the FLYNC model.
def test_load_multiple_communication_interfaces(tmpdir):
    tmp_path = Path(tmpdir)

    examples = Path("examples")
    flync_example = examples / "flync_example"

    shutil.copytree(flync_example, tmp_path, dirs_exist_ok=True)

    workspace = FLYNCWorkspace.load_workspace(
        workspace_name="flync_example",
        workspace_path=tmp_path,
    )

    assert workspace is not None

    model = workspace.flync_model
    assert model is not None

    assert model.ecus

    has_ethernet_interface = False
    has_can_interface = False
    has_lin_interface = False

    for ecu in model.ecus:
        for controller in ecu.controllers:
            if controller.ethernet_interfaces:
                has_ethernet_interface = True

            if controller.can_interfaces:
                has_can_interface = True

            if controller.lin_interfaces:
                has_lin_interface = True

    assert has_ethernet_interface, "Ethernet interface was not loaded"
    assert has_can_interface, "CAN interface was not loaded"
    assert has_lin_interface, "LIN interface was not loaded"


# Verify Serialization and Deserialization Consistency for EthernetInterface configuration.
@pytest.mark.xfail(reason="FLYNC-1337")
def test_ethernet_interface_serialization_deserialization(tmp_path):

    eth_iface = EthernetInterface(
        name="eth_iface", interface_config=EthernetInterfaceConfig(virtual_interfaces=[VirtualControllerInterface(name="vif0", addresses=[])])
    )

    controller = Controller(
        name="CTRL1",
        controller_metadata=EmbeddedMetadata(
            type="embedded", author="TestTeam", target_system="Device1", compatible_flync_version=BaseVersion(version="0.13.0")
        ),
        ethernet_interfaces=[eth_iface],
    )

    ecu = ECU(
        name="ECU1",
        controllers=[controller],
        topology=InternalTopology(),
        ecu_metadata=ECUMetadata(type="ecu", author="TestTeam", compatible_flync_version=BaseVersion(version="0.13.0")),
    )

    initial_model = FLYNCModel(
        ecus=[ecu],
        topology=FLYNCTopology(system_topology=EthernetTopology(connections=[])),
        metadata=SystemMetadata(
            type="system", release=BaseVersion(version="0.13.0"), author="TestTeam", compatible_flync_version=BaseVersion(version="0.13.0")
        ),
    )

    workspace_path = tmp_path / "workspace"
    workspace = FLYNCWorkspace.load_model(
        flync_model=initial_model,
        workspace_name="TestWorkspace",
        file_path=workspace_path,
    )
    workspace.generate_configs()
    loaded_workspace = FLYNCWorkspace.load_workspace(
        workspace_name="TestWorkspace",
        workspace_path=workspace_path,
    )
    final_model = loaded_workspace.flync_model

    assert final_model is not None

    assert json.dumps(initial_model.model_dump(by_alias=False), sort_keys=True) == json.dumps(final_model.model_dump(by_alias=False), sort_keys=True)


# Verify Serialization and Deserialization Consistency for CANInterface configuration.
@pytest.mark.xfail(reason="FLYNC-1337")
def test_can_interface_serialization_deserialization(tmp_path):

    can_iface = CANInterface(name="can_iface", bus_ref="can_bus")

    controller = Controller(
        name="CTRL1",
        controller_metadata=EmbeddedMetadata(
            type="embedded", author="TestTeam", target_system="Device1", compatible_flync_version=BaseVersion(version="0.13.0")
        ),
        can_interfaces=[can_iface],
    )

    ecu = ECU(
        name="ECU1",
        controllers=[controller],
        topology=InternalTopology(),
        ecu_metadata=ECUMetadata(type="ecu", author="TestTeam", compatible_flync_version=BaseVersion(version="0.13.0")),
    )

    initial_model = FLYNCModel(
        ecus=[ecu],
        topology=FLYNCTopology(system_topology=EthernetTopology(connections=[])),
        metadata=SystemMetadata(
            type="system", release=BaseVersion(version="0.13.0"), author="TestTeam", compatible_flync_version=BaseVersion(version="0.13.0")
        ),
    )

    workspace_path = tmp_path / "workspace"
    workspace = FLYNCWorkspace.load_model(
        flync_model=initial_model,
        workspace_name="TestWorkspace",
        file_path=workspace_path,
    )
    workspace.generate_configs()
    loaded_workspace = FLYNCWorkspace.load_workspace(
        workspace_name="TestWorkspace",
        workspace_path=workspace_path,
    )
    final_model = loaded_workspace.flync_model

    assert final_model is not None

    assert json.dumps(initial_model.model_dump(by_alias=False), sort_keys=True) == json.dumps(final_model.model_dump(by_alias=False), sort_keys=True)


# Verify Serialization and Deserialization Consistency for LINInterface configuration.
@pytest.mark.xfail(reason="FLYNC-1337")
def test_lin_interface_serialization_deserialization(tmp_path):

    lin_slave = LINSlaveInterface(name="lin_slave_iface", bus_ref="lin_bus", lin_protocol="2.0", configured_nad=1, initial_nad=1)

    lin_master = LINMasterInterface(name="lin_master_iface", bus_ref="lin_bus", lin_protocol="2.0", p2_min=10, st_min=10)

    controller = Controller(
        name="CTRL1",
        controller_metadata=EmbeddedMetadata(
            type="embedded", author="TestTeam", target_system="Device1", compatible_flync_version=BaseVersion(version="0.13.0")
        ),
        lin_interfaces=[lin_master, lin_slave],
    )

    ecu = ECU(
        name="ECU1",
        controllers=[controller],
        topology=InternalTopology(),
        ecu_metadata=ECUMetadata(type="ecu", author="TestTeam", compatible_flync_version=BaseVersion(version="0.13.0")),
    )

    initial_model = FLYNCModel(
        ecus=[ecu],
        topology=FLYNCTopology(system_topology=EthernetTopology(connections=[])),
        metadata=SystemMetadata(
            type="system", release=BaseVersion(version="0.13.0"), author="TestTeam", compatible_flync_version=BaseVersion(version="0.13.0")
        ),
    )

    workspace_path = tmp_path / "workspace"
    workspace = FLYNCWorkspace.load_model(
        flync_model=initial_model,
        workspace_name="TestWorkspace",
        file_path=workspace_path,
    )
    workspace.generate_configs()
    loaded_workspace = FLYNCWorkspace.load_workspace(
        workspace_name="TestWorkspace",
        workspace_path=workspace_path,
    )
    final_model = loaded_workspace.flync_model

    assert final_model is not None

    assert json.dumps(initial_model.model_dump(by_alias=False), sort_keys=True) == json.dumps(final_model.model_dump(by_alias=False), sort_keys=True)


# Verify Serialization and Deserialization Consistency for LINInterface configuration.
@pytest.mark.xfail(reason="FLYNC-1337")
def test_lin_interface_serialization_deserialization(tmp_path):

    lin_slave = LINSlaveInterface(name="lin_slave_iface", bus_ref="lin_bus", lin_protocol="2.0", configured_nad=1, initial_nad=1)

    lin_master = LINMasterInterface(name="lin_master_iface", bus_ref="lin_bus", lin_protocol="2.0", p2_min=10, st_min=10)

    controller = Controller(
        name="CTRL1",
        controller_metadata=EmbeddedMetadata(
            type="embedded", author="TestTeam", target_system="Device1", compatible_flync_version=BaseVersion(version="0.13.0")
        ),
        lin_interfaces=[lin_master, lin_slave],
    )

    ecu = ECU(
        name="ECU1",
        controllers=[controller],
        topology=InternalTopology(),
        ecu_metadata=ECUMetadata(type="ecu", author="TestTeam", compatible_flync_version=BaseVersion(version="0.13.0")),
    )

    initial_model = FLYNCModel(
        ecus=[ecu],
        topology=FLYNCTopology(system_topology=EthernetTopology(connections=[])),
        metadata=SystemMetadata(
            type="system", release=BaseVersion(version="0.13.0"), author="TestTeam", compatible_flync_version=BaseVersion(version="0.13.0")
        ),
    )

    workspace_path = tmp_path / "workspace"
    workspace = FLYNCWorkspace.load_model(
        flync_model=initial_model,
        workspace_name="TestWorkspace",
        file_path=workspace_path,
    )
    workspace.generate_configs()
    loaded_workspace = FLYNCWorkspace.load_workspace(
        workspace_name="TestWorkspace",
        workspace_path=workspace_path,
    )
    final_model = loaded_workspace.flync_model

    assert final_model is not None

    assert json.dumps(initial_model.model_dump(by_alias=False), sort_keys=True) == json.dumps(final_model.model_dump(by_alias=False), sort_keys=True)
