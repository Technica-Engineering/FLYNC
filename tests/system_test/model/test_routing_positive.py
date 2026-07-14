import json
from ipaddress import IPv4Address
from pathlib import Path

from flync.model.flync_4_bus.can_bus import CANBus
from flync.model.flync_4_communication.flync_channels import FLYNCChannelConfig
from flync.model.flync_4_communication.flync_communication import FLYNCCommunicationConfig
from flync.model.flync_4_ecu import Controller, EthernetInterfaceConfig, SocketTCP, VirtualControllerInterface
from flync.model.flync_4_ecu.can_interface import CANFrameRef, CANInterface
from flync.model.flync_4_ecu.controller import Controller, EthernetInterface
from flync.model.flync_4_ecu.ecu import ECU
from flync.model.flync_4_ecu.internal_topology import InternalTopology
from flync.model.flync_4_ecu.socket_container import SocketContainer
from flync.model.flync_4_ecu.sockets import IPv4AddressEndpoint
from flync.model.flync_4_metadata.metadata import BaseVersion, ECUMetadata, EmbeddedMetadata, SystemMetadata
from flync.model.flync_4_signal import CANFrame, CANFrameEgress, CANFrameForwarder, ContainerPDUHeader, PDUReceiver, PDUSender
from flync.model.flync_4_signal.forwarder import EthSocketEgress, ForwarderEgress, PDUForwarder
from flync.model.flync_4_signal.pdu import ContainedPDURef, ContainerPDU, PDUInstance, SignalInstance, StandardPDU
from flync.model.flync_4_signal.signal import Signal
from flync.model.flync_4_topology.system_topology import FLYNCTopology, SystemTopology
from flync.model.flync_model import FLYNCModel
from flync.sdk.workspace.flync_workspace import FLYNCWorkspace


def test_can_frame_routed_across_buses_successfully():
    """
    Verifies that a CAN frame is correctly forwarded from one CAN bus to another. Checks that the forwarder maps ingress to egress with the correct bus.
    """
    can_interface_1 = CANInterface(name="CAN_IF_1", bus_ref="CAN_BUS_1")
    can_interface_2 = CANInterface(name="CAN_IF_2", bus_ref="CAN_BUS_2")
    sample_frame = CANFrame(name="EngineStatus", length=8, can_id=0x100, id_format="standard_11bit", is_remote_frame=False)
    forwarder = CANFrameForwarder(
        frame_ref=sample_frame.name, egresses=[ForwarderEgress(CANFrameEgress(frame_ref=sample_frame.can_id, bus_ref=can_interface_2.bus_ref))]
    )
    can_interface_1.forwarder_frames.append(forwarder)

    assert can_interface_1.forwarder_frames[0].frame_ref == "EngineStatus"
    assert can_interface_1.forwarder_frames[0].egresses[0].root.frame_ref == sample_frame.can_id
    assert can_interface_1.forwarder_frames[0].egresses[0].root.bus_ref == "CAN_BUS_2"


def test_multiple_can_frames_routed_same_interface():
    """
    Ensures multiple CANFrameForwarders on the same interface forward each frame to the correct egress without conflicts.
    """
    can_interface_1 = CANInterface(name="CAN_IF_1", bus_ref="CAN_BUS_1")
    frame1 = CANFrame(name="Frame1", length=4, can_id=0x101, id_format="standard_11bit")
    frame2 = CANFrame(name="Frame2", length=4, can_id=0x102, id_format="standard_11bit")
    forwarder1 = CANFrameForwarder(frame_ref="Frame1", egresses=[ForwarderEgress(CANFrameEgress(frame_ref=0x101, bus_ref=can_interface_1.bus_ref))])
    forwarder2 = CANFrameForwarder(frame_ref="Frame2", egresses=[ForwarderEgress(CANFrameEgress(frame_ref=0x102, bus_ref=can_interface_1.bus_ref))])
    can_interface_1.forwarder_frames.extend([forwarder1, forwarder2])

    assert forwarder1.egresses[0].root.frame_ref == 0x101
    assert forwarder2.egresses[0].root.frame_ref == 0x102


def test_forwarding_with_valid_can_sender_receiver_context(tmpdir):
    """
    Confirms that a CAN frame is forwarded correctly between interfaces within a FLYNC model. Validates forwarder configuration and model integrity.
    """
    engine_status = CANFrame(name="EngineStatus", length=8, can_id=0x100, id_format="standard_11bit", is_remote_frame=False)
    can_bus = CANBus(name="CAN2", baud_rate=10000, frames=[engine_status])
    forwarder = CANFrameForwarder(
        frame_ref="EngineStatus", egresses=[ForwarderEgress(root=CANFrameEgress(egress_type="can_frame", bus_ref="CAN2", frame_ref=0x100))]
    )
    can_interface_1 = CANInterface(
        name="IF1", bus_ref="CAN1", receiver_frames=[], sender_frames=[CANFrameRef(bus_ref="CAN1", frame_ref=0x100)], forwarder_frames=[forwarder]
    )
    can_interface_2 = CANInterface(
        name="IF2",
        bus_ref="CAN2",
        receiver_frames=[CANFrameRef(bus_ref="CAN2", frame_ref=0x100)],
        sender_frames=[CANFrameRef(bus_ref="CAN2", frame_ref=0x100)],
        forwarder_frames=[],
    )
    controller = Controller(
        name="CTRL1",
        controller_metadata=EmbeddedMetadata(
            type="embedded", author="TestTeam", target_system="Device1", compatible_flync_version=BaseVersion(version="0.12.0")
        ),
        can_interfaces=[can_interface_1, can_interface_2],
        ethernet_interfaces=[],
    )
    ecu = ECU(
        name="ECU1",
        controllers=[controller],
        topology=InternalTopology(),
        ecu_metadata=ECUMetadata(type="ecu", author="TestTeam", compatible_flync_version=BaseVersion(version="0.12.0")),
    )

    flync_model = FLYNCModel(
        ecus=[ecu],
        topology=FLYNCTopology(system_topology=SystemTopology(connections=[])),
        metadata=SystemMetadata(
            type="system", release=BaseVersion(version="0.12.0"), author="TestTeam", compatible_flync_version=BaseVersion(version="0.12.0")
        ),
        communication=FLYNCCommunicationConfig(channels=FLYNCChannelConfig(can_buses=[can_bus])),
    )
    workspace_path = Path(tmpdir) / "temp_workspace"
    ws = FLYNCWorkspace.load_model(flync_model=flync_model, workspace_name="generated_workspace", file_path=workspace_path)
    final_model = ws.flync_model
    assert json.dumps(flync_model.model_dump(), sort_keys=True) == json.dumps(final_model.model_dump(), sort_keys=True)


def test_forwarding_can_to_ethernet_simple(tmpdir):
    """
    Validates CAN-to-Ethernet model configuration where a full StandardPDU is forwarded from a CAN frame to an Ethernet socket without extraction.
    """
    engine_speed_signal = Signal(name="EngineSpeed", bit_length=16, data_type="uint16", factor=0.125, offset=0)
    eth_iface = EthernetInterface(
        name="ETH_IF_1",
        interface_config=EthernetInterfaceConfig(
            virtual_interfaces=[
                VirtualControllerInterface(
                    name="VLAN_1",
                    vlanid=0,
                    addresses=[IPv4AddressEndpoint(address="192.168.1.10", ipv4netmask=IPv4Address("255.255.255.0"), sockets=[])],
                    multicast=[],
                )
            ],
        ),
        sockets=[
            SocketContainer(
                name="ETH_CONTAINER_1",
                vlan_id=0,
                sockets=[
                    SocketTCP(
                        name="ETH_SOCKET_1",
                        endpoint_address="192.168.1.10",
                        port_no=2000,
                        tcp_profile=0,
                        deployments=[PDUSender(pdu_ref="EngineStatusPDU")],
                    )
                ],
            )
        ],
    )
    engine_status_pdu = StandardPDU(name="EngineStatusPDU", length=8, signals=[SignalInstance(signal=engine_speed_signal, bit_position=0)])
    engine_status_frame = CANFrame(
        name="EngineStatus", length=8, can_id=0x100, id_format="standard_11bit", packed_pdus=[PDUInstance(pdu_ref="EngineStatusPDU", bit_position=0)]
    )
    can_bus = CANBus(name="CAN1_BUS", baud_rate=10000, frames=[engine_status_frame])
    forwarder = CANFrameForwarder(
        frame_ref="EngineStatus", egresses=[ForwarderEgress(root=EthSocketEgress(egress_type="eth_socket", socket_ref="ETH_SOCKET_1"))]
    )
    can_interface = CANInterface(
        name="CAN_IF_1",
        bus_ref="CAN1_BUS",
        receiver_frames=[],
        sender_frames=[CANFrameRef(bus_ref="CAN1_BUS", frame_ref=0x100)],
        forwarder_frames=[],
    )
    controller = Controller(
        name="CTRL1",
        controller_metadata=EmbeddedMetadata(
            type="embedded", author="TestTeam", target_system="Device1", compatible_flync_version=BaseVersion(version="0.12.0")
        ),
        can_interfaces=[can_interface],
        ethernet_interfaces=[eth_iface],
    )
    ecu = ECU(
        name="ECU1",
        controllers=[controller],
        topology=InternalTopology(),
        ecu_metadata=ECUMetadata(type="ecu", author="TestTeam", compatible_flync_version=BaseVersion(version="0.12.0")),
    )

    flync_model = FLYNCModel(
        ecus=[ecu],
        topology=FLYNCTopology(system_topology=SystemTopology(connections=[])),
        metadata=SystemMetadata(
            type="system", release=BaseVersion(version="0.12.0"), author="TestTeam", compatible_flync_version=BaseVersion(version="0.12.0")
        ),
        communication=FLYNCCommunicationConfig(channels=FLYNCChannelConfig(can_buses=[can_bus], pdus=[engine_status_pdu])),
    )
    workspace_path = Path(tmpdir) / "temp_workspace"
    ws = FLYNCWorkspace.load_model(flync_model=flync_model, workspace_name="generated_workspace", file_path=workspace_path)
    final_model = ws.flync_model
    assert json.dumps(flync_model.model_dump(), sort_keys=True) == json.dumps(final_model.model_dump(), sort_keys=True)


def test_multi_egress_forwarding_can_to_eth_and_can(tmpdir):
    """
    Validates that a CAN frame can be forwarded simultaneously to an Ethernet socket and to another CAN frame.
    """

    engine_speed_signal = Signal(name="EngineSpeed", bit_length=16, data_type="uint16", factor=0.125, offset=0)
    engine_status_pdu = StandardPDU(name="EngineStatusPDU", length=8, signals=[SignalInstance(signal=engine_speed_signal, bit_position=0)])
    source_frame = CANFrame(
        name="EngineStatusFrame",
        length=8,
        can_id=0x100,
        id_format="standard_11bit",
        packed_pdus=[PDUInstance(pdu_ref="EngineStatusPDU", bit_position=0)],
    )
    mirror_frame = CANFrame(
        name="EngineStatusMirrorFrame",
        length=8,
        can_id=0x200,
        id_format="standard_11bit",
        packed_pdus=[PDUInstance(pdu_ref="EngineStatusPDU", bit_position=0)],
    )
    can_bus = CANBus(name="CAN1_BUS", baud_rate=500000, frames=[source_frame, mirror_frame])
    eth_socket = SocketTCP(
        name="ETH_SOCKET_1", endpoint_address="192.168.1.10", port_no=2000, tcp_profile=0, deployments=[PDUSender(pdu_ref="EngineStatusPDU")]
    )
    eth_interface = EthernetInterface(
        name="ETH_IF_1",
        interface_config=EthernetInterfaceConfig(
            virtual_interfaces=[
                VirtualControllerInterface(
                    name="VLAN_1",
                    vlanid=0,
                    addresses=[IPv4AddressEndpoint(address="192.168.1.10", ipv4netmask=IPv4Address("255.255.255.0"), sockets=[])],
                )
            ],
        ),
        sockets=[SocketContainer(name="ETH_CONTAINER_1", vlan_id=0, sockets=[eth_socket])],
    )
    forwarder = CANFrameForwarder(
        frame_ref="EngineStatusFrame",
        egresses=[
            ForwarderEgress(root=EthSocketEgress(egress_type="eth_socket", socket_ref="ETH_SOCKET_1")),
            ForwarderEgress(root=CANFrameEgress(egress_type="can_frame", bus_ref="CAN1_BUS", frame_ref=0x200)),
        ],
    )
    can_interface = CANInterface(
        name="CAN_IF_1",
        bus_ref="CAN1_BUS",
        receiver_frames=[],
        sender_frames=[CANFrameRef(bus_ref="CAN1_BUS", frame_ref=0x100), CANFrameRef(bus_ref="CAN1_BUS", frame_ref=0x200)],
        forwarder_frames=[forwarder],
    )
    controller = Controller(
        name="CTRL1",
        controller_metadata=EmbeddedMetadata(
            type="embedded", author="TestTeam", target_system="Device1", compatible_flync_version=BaseVersion(version="0.12.0")
        ),
        can_interfaces=[can_interface],
        ethernet_interfaces=[eth_interface],
    )
    ecu = ECU(
        name="ECU1",
        controllers=[controller],
        topology=InternalTopology(),
        ecu_metadata=ECUMetadata(type="ecu", author="TestTeam", compatible_flync_version=BaseVersion(version="0.12.0")),
    )
    flync_model = FLYNCModel(
        ecus=[ecu],
        topology=FLYNCTopology(system_topology=SystemTopology(connections=[])),
        metadata=SystemMetadata(
            type="system", release=BaseVersion(version="0.12.0"), author="TestTeam", compatible_flync_version=BaseVersion(version="0.12.0")
        ),
        communication=FLYNCCommunicationConfig(channels=FLYNCChannelConfig(can_buses=[can_bus], pdus=[engine_status_pdu])),
    )

    workspace_path = Path(tmpdir) / "temp_workspace"
    ws = FLYNCWorkspace.load_model(flync_model=flync_model, workspace_name="generated_workspace", file_path=workspace_path)
    final_model = ws.flync_model
    assert json.dumps(flync_model.model_dump(), sort_keys=True) == json.dumps(final_model.model_dump(), sort_keys=True)


def test_forwarding_ethernet_to_can_simple(tmpdir):
    """
    Validates Ethernet-to-CAN model configuration where a StandardPDU received on an Ethernet socket is forwarded to a CAN frame.
    """

    engine_speed_signal = Signal(name="EngineSpeed", bit_length=16, data_type="uint16", factor=0.125, offset=0)
    engine_status_pdu = StandardPDU(name="EngineStatusPDU", length=8, signals=[SignalInstance(signal=engine_speed_signal, bit_position=0)])
    engine_status_frame = CANFrame(
        name="EngineStatus", length=8, can_id=0x100, id_format="standard_11bit", packed_pdus=[PDUInstance(pdu_ref="EngineStatusPDU", bit_position=0)]
    )
    can_bus = CANBus(name="CAN1_BUS", baud_rate=500000, frames=[engine_status_frame])
    eth_socket = SocketTCP(
        name="ETH_SOCKET_1",
        endpoint_address="192.168.1.10",
        port_no=2000,
        tcp_profile=0,
        deployments=[
            PDUReceiver(pdu_ref="EngineStatusPDU"),
            PDUForwarder(pdu_ref="EngineStatusPDU", egresses=[ForwarderEgress(root=CANFrameEgress(bus_ref="CAN1_BUS", frame_ref=0x100))]),
        ],
    )
    eth_interface = EthernetInterface(
        name="ETH_IF_1",
        interface_config=EthernetInterfaceConfig(
            virtual_interfaces=[
                VirtualControllerInterface(
                    name="VLAN_1",
                    vlanid=0,
                    addresses=[IPv4AddressEndpoint(address="192.168.1.10", ipv4netmask=IPv4Address("255.255.255.0"), sockets=[])],
                    multicast=[],
                )
            ],
        ),
        sockets=[SocketContainer(name="ETH_CONTAINER_1", vlan_id=0, sockets=[eth_socket])],
    )
    can_interface = CANInterface(
        name="CAN_IF_1",
        bus_ref="CAN1_BUS",
        receiver_frames=[],
        sender_frames=[CANFrameRef(bus_ref="CAN1_BUS", frame_ref=0x100)],
        forwarder_frames=[],
    )
    controller = Controller(
        name="CTRL1",
        controller_metadata=EmbeddedMetadata(
            type="embedded", author="TestTeam", target_system="Device1", compatible_flync_version=BaseVersion(version="0.12.0")
        ),
        can_interfaces=[can_interface],
        ethernet_interfaces=[eth_interface],
    )
    ecu = ECU(
        name="ECU1",
        controllers=[controller],
        topology=InternalTopology(),
        ecu_metadata=ECUMetadata(type="ecu", author="TestTeam", compatible_flync_version=BaseVersion(version="0.12.0")),
    )

    flync_model = FLYNCModel(
        ecus=[ecu],
        topology=FLYNCTopology(system_topology=SystemTopology(connections=[])),
        metadata=SystemMetadata(
            type="system", release=BaseVersion(version="0.12.0"), author="TestTeam", compatible_flync_version=BaseVersion(version="0.12.0")
        ),
        communication=FLYNCCommunicationConfig(channels=FLYNCChannelConfig(can_buses=[can_bus], pdus=[engine_status_pdu])),
    )
    workspace_path = Path(tmpdir) / "temp_workspace"
    ws = FLYNCWorkspace.load_model(flync_model=flync_model, workspace_name="generated_workspace", file_path=workspace_path)
    final_model = ws.flync_model
    assert json.dumps(flync_model.model_dump(), sort_keys=True) == json.dumps(final_model.model_dump(), sort_keys=True)


def test_multi_hop_forwarding_ethernet_to_can(tmpdir):
    """
    Validates end-to-end forwarding where a PDU received on an Ethernet socket is forwarded through a PDUForwarder and emitted on a CAN frame.
    """

    engine_speed_signal = Signal(name="EngineSpeed", bit_length=16, data_type="uint16", factor=0.125, offset=0)
    engine_status_pdu = StandardPDU(name="EngineStatusPDU", length=8, signals=[SignalInstance(signal=engine_speed_signal, bit_position=0)])
    engine_status_frame = CANFrame(
        name="EngineStatusFrame",
        length=8,
        can_id=0x100,
        id_format="standard_11bit",
        packed_pdus=[PDUInstance(pdu_ref="EngineStatusPDU", bit_position=0)],
    )
    can_bus = CANBus(name="CAN1_BUS", baud_rate=500000, frames=[engine_status_frame])
    eth_socket = SocketTCP(
        name="ETH_SOCKET_RX",
        endpoint_address="192.168.1.10",
        port_no=2000,
        tcp_profile=0,
        deployments=[
            PDUReceiver(pdu_ref="EngineStatusPDU"),
            PDUForwarder(
                pdu_ref="EngineStatusPDU",
                egresses=[ForwarderEgress(root=CANFrameEgress(egress_type="can_frame", bus_ref="CAN1_BUS", frame_ref=0x100))],
            ),
        ],
    )
    eth_iface = EthernetInterface(
        name="ETH_IF_1",
        interface_config=EthernetInterfaceConfig(
            virtual_interfaces=[
                VirtualControllerInterface(
                    name="VLAN_1",
                    vlanid=0,
                    addresses=[IPv4AddressEndpoint(address="192.168.1.10", ipv4netmask=IPv4Address("255.255.255.0"), sockets=[])],
                    multicast=[],
                )
            ],
        ),
        sockets=[SocketContainer(name="ETH_CONTAINER_1", vlan_id=0, sockets=[eth_socket])],
    )
    can_interface = CANInterface(
        name="CAN_IF_1",
        bus_ref="CAN1_BUS",
        receiver_frames=[],
        sender_frames=[CANFrameRef(bus_ref="CAN1_BUS", frame_ref=0x100)],
        forwarder_frames=[],
    )
    controller = Controller(
        name="CTRL1",
        controller_metadata=EmbeddedMetadata(
            type="embedded", author="TestTeam", target_system="Device1", compatible_flync_version=BaseVersion(version="0.12.0")
        ),
        can_interfaces=[can_interface],
        ethernet_interfaces=[eth_iface],
    )
    ecu = ECU(
        name="ECU1",
        controllers=[controller],
        topology=InternalTopology(),
        ecu_metadata=ECUMetadata(type="ecu", author="TestTeam", compatible_flync_version=BaseVersion(version="0.12.0")),
    )

    flync_model = FLYNCModel(
        ecus=[ecu],
        topology=FLYNCTopology(system_topology=SystemTopology(connections=[])),
        metadata=SystemMetadata(
            type="system", release=BaseVersion(version="0.12.0"), author="TestTeam", compatible_flync_version=BaseVersion(version="0.12.0")
        ),
        communication=FLYNCCommunicationConfig(channels=FLYNCChannelConfig(can_buses=[can_bus], pdus=[engine_status_pdu])),
    )
    workspace_path = Path(tmpdir) / "temp_workspace"
    ws = FLYNCWorkspace.load_model(flync_model=flync_model, workspace_name="generated_workspace", file_path=workspace_path)
    final_model = ws.flync_model
    assert json.dumps(flync_model.model_dump(), sort_keys=True) == json.dumps(final_model.model_dump(), sort_keys=True)


def test_container_pdu_extracted_and_routed_to_can(tmpdir):
    """
    Validates Ethernet-to-CAN forwarding where a ContainerPDU is received and a specific contained PDU is extracted and emitted on a CAN frame.
    """

    engine_speed_signal = Signal(name="EngineSpeed", bit_length=16, data_type="uint16", factor=0.125, offset=0)
    engine_status_pdu = StandardPDU(name="EngineStatusPDU", length=8, signals=[SignalInstance(signal=engine_speed_signal, bit_position=0)])
    container_pdu = ContainerPDU(
        name="PowertrainContainer",
        pdu_id=1,
        length=12,
        header=ContainerPDUHeader(id_length_bits=16, length_field_bits=16),
        contained_pdus=[ContainedPDURef(pdu_id=10, pdu_ref="EngineStatusPDU", offset=0)],
    )
    can_frame = CANFrame(
        name="EngineStatusFrame",
        length=8,
        can_id=0x100,
        id_format="standard_11bit",
        packed_pdus=[PDUInstance(pdu_ref="EngineStatusPDU", bit_position=0)],
    )
    can_bus = CANBus(name="CAN1_BUS", baud_rate=500000, frames=[can_frame])
    eth_socket = SocketTCP(
        name="ETH_SOCKET_1",
        endpoint_address="192.168.1.10",
        port_no=2000,
        tcp_profile=0,
        deployments=[
            PDUReceiver(pdu_ref="PowertrainContainer"),
            PDUForwarder(
                pdu_ref="PowertrainContainer",
                egresses=[
                    ForwarderEgress(
                        root=CANFrameEgress(egress_type="can_frame", bus_ref="CAN1_BUS", frame_ref=0x100, extract_pdu_ref="EngineStatusPDU")
                    )
                ],
            ),
        ],
    )
    eth_iface = EthernetInterface(
        name="ETH_IF_1",
        interface_config=EthernetInterfaceConfig(
            virtual_interfaces=[
                VirtualControllerInterface(
                    name="VLAN_1",
                    vlanid=0,
                    addresses=[IPv4AddressEndpoint(address="192.168.1.10", ipv4netmask=IPv4Address("255.255.255.0"), sockets=[])],
                    multicast=[],
                )
            ],
        ),
        sockets=[SocketContainer(name="ETH_CONTAINER_1", vlan_id=0, sockets=[eth_socket])],
    )
    can_interface = CANInterface(
        name="CAN_IF_1",
        bus_ref="CAN1_BUS",
        receiver_frames=[],
        sender_frames=[CANFrameRef(bus_ref="CAN1_BUS", frame_ref=0x100)],
        forwarder_frames=[],
    )
    controller = Controller(
        name="CTRL1",
        controller_metadata=EmbeddedMetadata(
            type="embedded", author="TestTeam", target_system="Device1", compatible_flync_version=BaseVersion(version="0.12.0")
        ),
        can_interfaces=[can_interface],
        ethernet_interfaces=[eth_iface],
    )
    ecu = ECU(
        name="ECU1",
        controllers=[controller],
        topology=InternalTopology(),
        ecu_metadata=ECUMetadata(type="ecu", author="TestTeam", compatible_flync_version=BaseVersion(version="0.12.0")),
    )

    flync_model = FLYNCModel(
        ecus=[ecu],
        topology=FLYNCTopology(system_topology=SystemTopology(connections=[])),
        metadata=SystemMetadata(
            type="system", release=BaseVersion(version="0.12.0"), author="TestTeam", compatible_flync_version=BaseVersion(version="0.12.0")
        ),
        communication=FLYNCCommunicationConfig(
            channels=FLYNCChannelConfig(can_buses=[can_bus], pdus=[engine_status_pdu], ethernet_pdu_containers=[container_pdu])
        ),
    )
    workspace_path = Path(tmpdir) / "temp_workspace"
    ws = FLYNCWorkspace.load_model(flync_model=flync_model, workspace_name="generated_workspace", file_path=workspace_path)
    final_model = ws.flync_model
    assert json.dumps(flync_model.model_dump(), sort_keys=True) == json.dumps(final_model.model_dump(), sort_keys=True)


def test_pdu_forwarded_between_two_ethernet_sockets(tmpdir):
    """
    Validates correct Ethernet-to-Ethernet forwarding where a ContainerPDU received on one socket is forwarded unchanged to another Ethernet socket.
    """
    vehicle_speed_signal = Signal(name="VehicleSpeed", bit_length=16, data_type="uint16", factor=0.01, offset=0)
    vehicle_status_pdu = StandardPDU(name="VehicleStatusPDU", length=8, signals=[SignalInstance(signal=vehicle_speed_signal, bit_position=0)])
    container_pdu = ContainerPDU(
        name="VehicleContainer",
        pdu_id=1,
        length=12,
        header=ContainerPDUHeader(id_length_bits=16, length_field_bits=16),
        contained_pdus=[ContainedPDURef(pdu_id=100, pdu_ref="VehicleStatusPDU", offset=0)],
    )
    ingress_socket = SocketTCP(
        name="ETH_SOCKET_INGRESS",
        endpoint_address="192.168.1.10",
        port_no=3000,
        tcp_profile=0,
        deployments=[
            PDUReceiver(pdu_ref="VehicleContainer"),
            PDUForwarder(
                pdu_ref="VehicleContainer",
                egresses=[ForwarderEgress(root=EthSocketEgress(egress_type="eth_socket", socket_ref="ETH_SOCKET_EGRESS"))],
            ),
        ],
    )
    egress_socket = SocketTCP(
        name="ETH_SOCKET_EGRESS", endpoint_address="239.1.1.1", port_no=4000, tcp_profile=0, deployments=[PDUSender(pdu_ref="VehicleContainer")]
    )
    eth_iface = EthernetInterface(
        name="ETH_IF_1",
        interface_config=EthernetInterfaceConfig(
            virtual_interfaces=[
                VirtualControllerInterface(
                    name="VLAN_1",
                    vlanid=0,
                    addresses=[IPv4AddressEndpoint(address="192.168.1.10", ipv4netmask=IPv4Address("255.255.255.0"), sockets=[])],
                    multicast=[],
                )
            ],
        ),
        sockets=[SocketContainer(name="ETH_CONTAINER_1", vlan_id=0, sockets=[ingress_socket, egress_socket])],
    )
    controller = Controller(
        name="CTRL1",
        controller_metadata=EmbeddedMetadata(
            type="embedded", author="TestTeam", target_system="Device1", compatible_flync_version=BaseVersion(version="0.12.0")
        ),
        can_interfaces=[],
        ethernet_interfaces=[eth_iface],
    )
    ecu = ECU(
        name="ECU1",
        controllers=[controller],
        topology=InternalTopology(),
        ecu_metadata=ECUMetadata(type="ecu", author="TestTeam", compatible_flync_version=BaseVersion(version="0.12.0")),
    )

    flync_model = FLYNCModel(
        ecus=[ecu],
        topology=FLYNCTopology(system_topology=SystemTopology(connections=[])),
        metadata=SystemMetadata(
            type="system", release=BaseVersion(version="0.12.0"), author="TestTeam", compatible_flync_version=BaseVersion(version="0.12.0")
        ),
        communication=FLYNCCommunicationConfig(
            channels=FLYNCChannelConfig(can_buses=[], pdus=[vehicle_status_pdu], ethernet_pdu_containers=[container_pdu])
        ),
    )
    workspace_path = Path(tmpdir) / "temp_workspace"
    ws = FLYNCWorkspace.load_model(flync_model=flync_model, workspace_name="generated_workspace", file_path=workspace_path)
    final_model = ws.flync_model
    assert json.dumps(flync_model.model_dump(), sort_keys=True) == json.dumps(final_model.model_dump(), sort_keys=True)


def test_container_pdu_fully_preserved_across_sockets(tmpdir):
    """
    Validates that a ContainerPDU is forwarded between Ethernet sockets while preserving its complete structure, including header definition and all contained PDUs.
    """
    engine_speed_signal = Signal(name="EngineSpeed", bit_length=16, data_type="uint16")
    coolant_temp_signal = Signal(name="CoolantTemperature", bit_length=8, data_type="uint8")
    engine_status_pdu = StandardPDU(name="EngineStatusPDU", length=8, signals=[SignalInstance(signal=engine_speed_signal, bit_position=0)])
    thermal_status_pdu = StandardPDU(name="ThermalStatusPDU", length=8, signals=[SignalInstance(signal=coolant_temp_signal, bit_position=0)])
    container_pdu = ContainerPDU(
        name="VehicleContainer",
        pdu_id=1,
        length=24,
        header=ContainerPDUHeader(id_length_bits=16, length_field_bits=16),
        contained_pdus=[
            ContainedPDURef(pdu_id=10, pdu_ref="EngineStatusPDU", offset=0),
            ContainedPDURef(pdu_id=20, pdu_ref="ThermalStatusPDU", offset=96),
        ],
    )
    ingress_socket = SocketTCP(
        name="ETH_SOCKET_INGRESS",
        endpoint_address="192.168.1.10",
        port_no=2000,
        tcp_profile=0,
        deployments=[
            PDUReceiver(pdu_ref="VehicleContainer"),
            PDUForwarder(
                pdu_ref="VehicleContainer",
                egresses=[ForwarderEgress(root=EthSocketEgress(egress_type="eth_socket", socket_ref="ETH_SOCKET_EGRESS"))],
            ),
        ],
    )
    egress_socket = SocketTCP(
        name="ETH_SOCKET_EGRESS", endpoint_address="239.1.1.100", port_no=3000, tcp_profile=0, deployments=[PDUSender(pdu_ref="VehicleContainer")]
    )
    eth_iface = EthernetInterface(
        name="ETH_IF_1",
        interface_config=EthernetInterfaceConfig(
            virtual_interfaces=[
                VirtualControllerInterface(
                    name="VLAN_1",
                    vlanid=0,
                    addresses=[IPv4AddressEndpoint(address="192.168.1.10", ipv4netmask=IPv4Address("255.255.255.0"), sockets=[])],
                    multicast=[],
                )
            ],
        ),
        sockets=[SocketContainer(name="ETH_CONTAINER_1", vlan_id=0, sockets=[ingress_socket, egress_socket])],
    )
    controller = Controller(
        name="CTRL1",
        controller_metadata=EmbeddedMetadata(
            type="embedded", author="TestTeam", target_system="Device1", compatible_flync_version=BaseVersion(version="0.12.0")
        ),
        can_interfaces=[],
        ethernet_interfaces=[eth_iface],
    )
    ecu = ECU(
        name="ECU1",
        controllers=[controller],
        topology=InternalTopology(),
        ecu_metadata=ECUMetadata(type="ecu", author="TestTeam", compatible_flync_version=BaseVersion(version="0.12.0")),
    )

    flync_model = FLYNCModel(
        ecus=[ecu],
        topology=FLYNCTopology(system_topology=SystemTopology(connections=[])),
        metadata=SystemMetadata(
            type="system", release=BaseVersion(version="0.12.0"), author="TestTeam", compatible_flync_version=BaseVersion(version="0.12.0")
        ),
        communication=FLYNCCommunicationConfig(
            channels=FLYNCChannelConfig(can_buses=[], pdus=[engine_status_pdu, thermal_status_pdu], ethernet_pdu_containers=[container_pdu])
        ),
    )
    workspace_path = Path(tmpdir) / "temp_workspace"
    ws = FLYNCWorkspace.load_model(flync_model=flync_model, workspace_name="generated_workspace", file_path=workspace_path)
    final_model = ws.flync_model
    assert json.dumps(flync_model.model_dump(), sort_keys=True) == json.dumps(final_model.model_dump(), sort_keys=True)


def test_multi_egress_ethernet_forwarding(tmpdir):
    """
    Validates that a single ContainerPDU can be forwarded from one Ethernet socket to multiple Ethernet sockets through multiple EthSocketEgress definitions.
    """

    vehicle_speed_signal = Signal(name="VehicleSpeed", bit_length=16, data_type="uint16")
    vehicle_status_pdu = StandardPDU(name="VehicleStatusPDU", length=8, signals=[SignalInstance(signal=vehicle_speed_signal, bit_position=0)])
    container_pdu = ContainerPDU(
        name="VehicleContainer",
        pdu_id=1,
        length=12,
        header=ContainerPDUHeader(id_length_bits=16, length_field_bits=16),
        contained_pdus=[ContainedPDURef(pdu_id=100, pdu_ref="VehicleStatusPDU", offset=0)],
    )
    ingress_socket = SocketTCP(
        name="ETH_SOCKET_INGRESS",
        endpoint_address="192.168.1.10",
        port_no=2000,
        tcp_profile=0,
        deployments=[
            PDUReceiver(pdu_ref="VehicleContainer"),
            PDUForwarder(
                pdu_ref="VehicleContainer",
                egresses=[
                    ForwarderEgress(root=EthSocketEgress(egress_type="eth_socket", socket_ref="ETH_SOCKET_EGRESS_1")),
                    ForwarderEgress(root=EthSocketEgress(egress_type="eth_socket", socket_ref="ETH_SOCKET_EGRESS_2")),
                    ForwarderEgress(root=EthSocketEgress(egress_type="eth_socket", socket_ref="ETH_SOCKET_EGRESS_3")),
                ],
            ),
        ],
    )
    egress_socket_1 = SocketTCP(
        name="ETH_SOCKET_EGRESS_1", endpoint_address="239.1.1.1", port_no=3001, tcp_profile=0, deployments=[PDUSender(pdu_ref="VehicleContainer")]
    )
    egress_socket_2 = SocketTCP(
        name="ETH_SOCKET_EGRESS_2", endpoint_address="239.1.1.2", port_no=3002, tcp_profile=0, deployments=[PDUSender(pdu_ref="VehicleContainer")]
    )
    egress_socket_3 = SocketTCP(
        name="ETH_SOCKET_EGRESS_3", endpoint_address="239.1.1.3", port_no=3003, tcp_profile=0, deployments=[PDUSender(pdu_ref="VehicleContainer")]
    )
    eth_iface = EthernetInterface(
        name="ETH_IF_1",
        interface_config=EthernetInterfaceConfig(
            virtual_interfaces=[
                VirtualControllerInterface(
                    name="VLAN_1",
                    vlanid=0,
                    addresses=[IPv4AddressEndpoint(address="192.168.1.10", ipv4netmask=IPv4Address("255.255.255.0"), sockets=[])],
                    multicast=[],
                )
            ],
        ),
        sockets=[SocketContainer(name="ETH_CONTAINER_1", vlan_id=0, sockets=[ingress_socket, egress_socket_1, egress_socket_2, egress_socket_3])],
    )
    controller = Controller(
        name="CTRL1",
        controller_metadata=EmbeddedMetadata(
            type="embedded", author="TestTeam", target_system="Device1", compatible_flync_version=BaseVersion(version="0.12.0")
        ),
        can_interfaces=[],
        ethernet_interfaces=[eth_iface],
    )
    ecu = ECU(
        name="ECU1",
        controllers=[controller],
        topology=InternalTopology(),
        ecu_metadata=ECUMetadata(type="ecu", author="TestTeam", compatible_flync_version=BaseVersion(version="0.12.0")),
    )

    flync_model = FLYNCModel(
        ecus=[ecu],
        topology=FLYNCTopology(system_topology=SystemTopology(connections=[])),
        metadata=SystemMetadata(
            type="system", release=BaseVersion(version="0.12.0"), author="TestTeam", compatible_flync_version=BaseVersion(version="0.12.0")
        ),
        communication=FLYNCCommunicationConfig(
            channels=FLYNCChannelConfig(can_buses=[], pdus=[vehicle_status_pdu], ethernet_pdu_containers=[container_pdu])
        ),
    )
    workspace_path = Path(tmpdir) / "temp_workspace"
    ws = FLYNCWorkspace.load_model(flync_model=flync_model, workspace_name="generated_workspace", file_path=workspace_path)
    final_model = ws.flync_model
    assert json.dumps(flync_model.model_dump(), sort_keys=True) == json.dumps(final_model.model_dump(), sort_keys=True)
