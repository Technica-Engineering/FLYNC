# ============================================================================
# Imports
# ============================================================================

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from flync.model import FLYNCModel
from flync.model.flync_4_bus import CANBus
from flync.model.flync_4_communication.flync_channels import FLYNCChannelConfig
from flync.model.flync_4_communication.flync_communication import FLYNCCommunicationConfig
from flync.model.flync_4_ecu import (
    BASET1,
    ECU,
    MII,
    Controller,
    ECUPort,
    EthernetInterface,
    EthernetInterfaceConfig,
    InternalTopology,
    IPv4AddressEndpoint,
    SocketContainer,
    SocketUDP,
    Switch,
    SwitchPort,
    VirtualControllerInterface,
)
from flync.model.flync_4_ecu.can_interface import CANFrameRef, CANInterface
from flync.model.flync_4_ecu.internal_topology import (
    ECUPortToControllerInterface,
    ECUPortToSwitchPort,
    SwitchPortToControllerInterface,
)
from flync.model.flync_4_ecu.sockets import DeploymentUnion, PDUReceiver, PDUSender
from flync.model.flync_4_metadata import BaseVersion, ECUMetadata, EmbeddedMetadata, SystemMetadata
from flync.model.flync_4_signal import CANFrame, PDUInstance, StandardPDU
from flync.model.flync_4_signal.forwarder import EthSocketEgress, ForwarderEgress, PDUForwarder
from flync.model.flync_4_signal.frame import FrameCyclicTiming, FrameTransmissionTiming
from flync.model.flync_4_signal.pdu import ContainedPDURef, ContainerPDU, ContainerPDUHeader
from flync.model.flync_4_topology import EthernetTopology, ExternalConnection, FLYNCTopology
from flync.sdk.workspace.flync_workspace import FLYNCWorkspace
from tests.error_assertions import assert_single_error

# ============================================================================
# Constants
# ============================================================================

FLYNC_VERSION = BaseVersion(version_schema="semver", version="0.13.0")

NM_MULTICAST_ADDR = "239.0.0.1"
NM_UDP_PORT = 1200
NM_VLAN_ID = 40

NM_PDU_NAME = "NmPdu"
NM_CONTAINER_NAME = "NmContainerPdu"
NM_CONTAINER_PDU_ID = 0x0001

NM_PDU_PAYLOAD_BYTES = 8
NM_CONTAINER_BYTES = 12

NM_CAN_ID = 0x400
NM_FRAME_NAME = "NmFrame"
CAN_BUS_NAME = "can_bus_1"

NM_CYCLE_S = 0.020
NM_TIMEOUT_S = 0.060

# ============================================================================
# Helpers
# ============================================================================


def _make_ethernet_system_metadata(variant: str = "MulticastNM") -> SystemMetadata:
    return SystemMetadata(
        author="Tester",
        compatible_flync_version=FLYNC_VERSION,
        release=FLYNC_VERSION,
        platform="Ethernet_NM_Demo",
        variant=variant,
    )


def _make_ecu_metadata() -> ECUMetadata:
    return ECUMetadata(author="Tester", compatible_flync_version=FLYNC_VERSION)


def _make_controller_metadata() -> EmbeddedMetadata:
    return EmbeddedMetadata(
        author="Tester",
        compatible_flync_version=FLYNC_VERSION,
        target_system="flync_os",
    )


def _make_ethernet_nm_pdu() -> StandardPDU:
    return StandardPDU(
        name=NM_PDU_NAME,
        length=NM_PDU_PAYLOAD_BYTES,
        pdu_usage="network_management",
    )


def _make_ethernet_nm_container_pdu() -> ContainerPDU:
    return ContainerPDU(
        name=NM_CONTAINER_NAME,
        length=NM_CONTAINER_BYTES,
        pdu_id=NM_CONTAINER_PDU_ID,
        pdu_usage="network_management",
        header=ContainerPDUHeader(
            id_length_bits=16,  # 2-byte PDU-ID field in each slot header
            length_field_bits=16,  # 2-byte length field in each slot header
        ),
        contained_pdus=[
            ContainedPDURef(
                pdu_id=NM_CONTAINER_PDU_ID,
                pdu_ref=NM_PDU_NAME,  # references the NM StandardPDU by name
                offset=0,
            )
        ],
    )


def _make_nm_container_pdu() -> ContainerPDU:
    return _make_ethernet_nm_container_pdu()


def _make_comm_config(nm_pdu: StandardPDU, nm_container: ContainerPDU) -> FLYNCCommunicationConfig:
    return FLYNCCommunicationConfig(
        channels=FLYNCChannelConfig(
            pdus=[nm_pdu],
            ethernet_pdu_containers=[nm_container],
        )
    )


def _make_nm_tx_socket() -> SocketUDP:
    return SocketUDP(
        name="nm_tx_socket",
        endpoint_address=NM_MULTICAST_ADDR,
        port_no=NM_UDP_PORT,
        endpoint_type="multicast",
        multicast_tx=[NM_MULTICAST_ADDR],
        protocol="udp",
        deployments=[DeploymentUnion(root=PDUSender(pdu_ref=NM_CONTAINER_NAME))],
    )


def _make_nm_rx_socket(name: str = "nm_rx_socket") -> SocketUDP:
    return SocketUDP(
        name=name,
        endpoint_address=NM_MULTICAST_ADDR,
        port_no=NM_UDP_PORT,
        endpoint_type="multicast",
        protocol="udp",
        deployments=[DeploymentUnion(root=PDUReceiver(pdu_ref=NM_CONTAINER_NAME))],
    )


def _make_unicast_nm_socket(name: str, endpoint_address: str, is_sender: bool) -> SocketUDP:
    deployments = (
        [DeploymentUnion(root=PDUSender(pdu_ref=NM_CONTAINER_NAME))] if is_sender else [DeploymentUnion(root=PDUReceiver(pdu_ref=NM_CONTAINER_NAME))]
    )
    return SocketUDP(
        name=name,
        endpoint_address=endpoint_address,
        port_no=NM_UDP_PORT,
        endpoint_type="unicast",
        protocol="udp",
        deployments=deployments,
    )


def _mirror_mii(mii_config: MII | None) -> MII | None:
    """Return the peer-side MII config (opposite mode) so both ends of a connection are configured, or None."""

    if mii_config is None:
        return None
    return mii_config.model_copy(update={"mode": "phy" if mii_config.mode == "mac" else "mac"})


def _make_ethernet_ecu(
    ecu_name: str,
    controller_name: str,
    ip_address: str,
    mac_address: str,
    socket: SocketUDP,
    port_name: str,
    port_role: str,
    multicast_groups: list[str] | None = None,
    vlan_id: int = 0,
    controller_mii_config: MII | None = None,
) -> ECU:
    endpoint = IPv4AddressEndpoint(
        address=ip_address,
        ipv4netmask="255.255.255.0",
        sockets=[socket] if socket.endpoint_type == "unicast" else [],
    )
    vci = VirtualControllerInterface(
        name="default",
        vlanid=vlan_id,
        addresses=[endpoint],
        multicast=multicast_groups or [],
    )
    ci = EthernetInterfaceConfig(
        mac_address=mac_address,
        mii_config=controller_mii_config,
        virtual_interfaces=[vci],
    )
    sc = SocketContainer(
        name=f"{socket.name}_sc",
        vlan_id=vlan_id,
        sockets=[socket],
    )
    eth = EthernetInterface(
        name="eth0",
        interface_config=ci,
        sockets=[sc],
    )
    ctrl = Controller(
        name=controller_name,
        controller_metadata=_make_controller_metadata(),
        ethernet_interfaces=[eth],
    )
    port = ECUPort(
        name=port_name,
        mdi_config=BASET1(
            mode="base_t1",
            speed=100,
            duplex="full",
            role=port_role,
            autonegotiation=False,
        ),
        mii_config=_mirror_mii(controller_mii_config),
    )
    topo = InternalTopology(
        connections=[
            ECUPortToControllerInterface(
                id=f"conn_{ecu_name}",
                ecu_port=port_name,
                controller_interface="eth0",
                controller=controller_name,
            )
        ]
    )
    return ECU(
        name=ecu_name,
        ports=[port],
        controllers=[ctrl],
        topology=topo,
        ecu_metadata=_make_ecu_metadata(),
    )


def _make_ethernet_ecu_with_sockets(
    ecu_name: str,
    controller_name: str,
    ip_address: str,
    mac_address: str,
    sockets: list[SocketUDP],
    port_name: str,
    port_role: str,
    multicast_groups: list[str] | None = None,
    vlan_id: int = 0,
    controller_mii_config: MII | None = None,
) -> ECU:
    endpoint = IPv4AddressEndpoint(
        address=ip_address,
        ipv4netmask="255.255.255.0",
        sockets=[sock for sock in sockets if sock.endpoint_type == "unicast"],
    )
    vci = VirtualControllerInterface(
        name="default",
        vlanid=vlan_id,
        addresses=[endpoint],
        multicast=multicast_groups or [],
    )
    ci = EthernetInterfaceConfig(
        mac_address=mac_address,
        mii_config=controller_mii_config,
        virtual_interfaces=[vci],
    )
    sc = SocketContainer(
        name=f"{controller_name}_sc",
        vlan_id=vlan_id,
        sockets=sockets,
    )
    eth = EthernetInterface(
        name="eth0",
        interface_config=ci,
        sockets=[sc],
    )
    ctrl = Controller(
        name=controller_name,
        controller_metadata=_make_controller_metadata(),
        ethernet_interfaces=[eth],
    )
    port = ECUPort(
        name=port_name,
        mdi_config=BASET1(
            mode="base_t1",
            speed=100,
            duplex="full",
            role=port_role,
            autonegotiation=False,
        ),
        mii_config=_mirror_mii(controller_mii_config),
    )
    topo = InternalTopology(
        connections=[
            ECUPortToControllerInterface(
                id=f"conn_{ecu_name}",
                ecu_port=port_name,
                controller_interface="eth0",
                controller=controller_name,
            )
        ]
    )
    return ECU(
        name=ecu_name,
        ports=[port],
        controllers=[ctrl],
        topology=topo,
        ecu_metadata=_make_ecu_metadata(),
    )


def _make_hpc_ecu(nm_tx_socket: SocketUDP) -> ECU:
    sc = SocketContainer(
        name="nm_tx_sc",
        vlan_id=NM_VLAN_ID,
        sockets=[nm_tx_socket],
    )

    mcast_ep = IPv4AddressEndpoint(
        address=NM_MULTICAST_ADDR,
        ipv4netmask="255.255.0.0",
        sockets=[nm_tx_socket],
    )

    vci = VirtualControllerInterface(
        name="vlan40",
        vlanid=NM_VLAN_ID,
        addresses=[mcast_ep],
    )

    ci = EthernetInterfaceConfig(
        mac_address="00:AA:BB:CC:40:01",
        mii_config=None,
        virtual_interfaces=[vci],
    )

    eth = EthernetInterface(
        name="eth0",
        interface_config=ci,
        sockets=[sc],
    )

    ctrl = Controller(
        name="hpc_ctrl",
        controller_metadata=_make_controller_metadata(),
        ethernet_interfaces=[eth],
    )

    port = ECUPort(
        name="hpc_port1",
        mdi_config=BASET1(
            mode="base_t1",
            speed=1000,
            duplex="full",
            role="master",
            autonegotiation=False,
        ),
        mii_config=None,
    )

    topo = InternalTopology(
        connections=[
            ECUPortToControllerInterface(
                id="conn_hpc",
                ecu_port="hpc_port1",
                controller_interface="eth0",
                controller="hpc_ctrl",
            )
        ]
    )

    return ECU(
        name="hpc_ecu",
        ports=[port],
        controllers=[ctrl],
        topology=topo,
        ecu_metadata=_make_ecu_metadata(),
    )


def _make_switch_ecu(
    port_name: str,
    controller_name: str,
    controller_ip: str,
    controller_mac: str,
    switch_name: str = "nm_switch",
) -> ECU:
    port = ECUPort(
        name=port_name,
        mdi_config=BASET1(
            mode="base_t1",
            speed=100,
            duplex="full",
            role="master",
            autonegotiation=False,
        ),
        mii_config=MII(speed=100, mode="mac"),
    )
    switch_ports = [
        SwitchPort(
            name="sw_ext",
            silicon_port_no=1,
            default_vlan_id=0,
            mii_config=MII(speed=100, mode="phy"),
        ),
        SwitchPort(
            name="sw_ctrl",
            silicon_port_no=2,
            default_vlan_id=0,
            mii_config=MII(speed=100, mode="phy"),
        ),
    ]
    switch = Switch(
        name=switch_name,
        ports=switch_ports,
        vlans=[],
        meta=_make_controller_metadata(),
    )
    endpoint = IPv4AddressEndpoint(
        address=controller_ip,
        ipv4netmask="255.255.255.0",
        sockets=[],
    )
    vci = VirtualControllerInterface(
        name="default",
        vlanid=0,
        addresses=[endpoint],
    )
    ci = EthernetInterfaceConfig(
        mac_address=controller_mac,
        mii_config=MII(
            speed=100,
            mode="mac",
        ),
        virtual_interfaces=[vci],
    )
    eth = EthernetInterface(
        name="eth0",
        interface_config=ci,
        sockets=[],
    )
    ctrl = Controller(
        name=controller_name,
        controller_metadata=_make_controller_metadata(),
        ethernet_interfaces=[eth],
    )
    topo = InternalTopology(
        connections=[
            ECUPortToSwitchPort(
                id="conn_port_to_switch",
                ecu_port=port_name,
                switch_port="sw_ext",
                switch=switch_name,
            ),
            SwitchPortToControllerInterface(
                id="conn_switch_to_controller",
                switch_port="sw_ctrl",
                switch=switch_name,
                controller_interface="eth0",
                controller=controller_name,
            ),
        ]
    )
    return ECU(
        name="switch_ecu",
        ports=[port],
        controllers=[ctrl],
        switches=[switch],
        topology=topo,
        ecu_metadata=_make_ecu_metadata(),
    )


def _make_zonal_ecu(
    index: int,
    unicast_ip: str,
    mac_suffix: int,
    nm_rx_socket: SocketUDP,
) -> ECU:
    sc = SocketContainer(
        name=f"nm_rx_sc_z{index}",
        vlan_id=NM_VLAN_ID,
        sockets=[nm_rx_socket],
    )

    unicast_ep = IPv4AddressEndpoint(
        address=unicast_ip,
        ipv4netmask="255.255.255.0",
    )

    vci = VirtualControllerInterface(
        name="vlan40",
        vlanid=NM_VLAN_ID,
        addresses=[unicast_ep],
        multicast=[NM_MULTICAST_ADDR],  # IGMP join → subscribe to NM group
    )

    ci = EthernetInterfaceConfig(
        mac_address=f"00:AA:BB:CC:40:{mac_suffix:02X}",
        mii_config=None,
        virtual_interfaces=[vci],
    )

    eth = EthernetInterface(
        name="eth0",
        interface_config=ci,
        sockets=[sc],
    )

    ctrl = Controller(
        name=f"zonal{index}_ctrl",
        controller_metadata=_make_controller_metadata(),
        ethernet_interfaces=[eth],
    )

    port = ECUPort(
        name=f"zonal{index}_port1",
        mdi_config=BASET1(
            mode="base_t1",
            speed=1000,
            duplex="full",
            role="slave",
            autonegotiation=False,
        ),
        mii_config=None,
    )

    topo = InternalTopology(
        connections=[
            ECUPortToControllerInterface(
                id=f"conn_z{index}",
                ecu_port=f"zonal{index}_port1",
                controller_interface="eth0",
                controller=f"zonal{index}_ctrl",
            )
        ]
    )

    return ECU(
        name=f"zonal_ecu_{index}",
        ports=[port],
        controllers=[ctrl],
        topology=topo,
        ecu_metadata=_make_ecu_metadata(),
    )


def _make_ethernet_topology(*port_pairs: tuple[str, str]) -> FLYNCTopology:
    connections = [ExternalConnection(id=f"link_{i}", ecu1_port=p1, ecu2_port=p2) for i, (p1, p2) in enumerate(port_pairs, start=1)]
    return FLYNCTopology(system_topology=EthernetTopology(connections=connections))


def _make_system_metadata() -> SystemMetadata:
    return SystemMetadata(
        author="Tester",
        compatible_flync_version=FLYNC_VERSION,
        release=FLYNC_VERSION,
        platform="CAN_NM_Demo",
        variant="NMTimeout",
    )


def _make_nm_pdu() -> StandardPDU:
    return StandardPDU(
        name=NM_PDU_NAME,
        length=8,
        pdu_usage="network_management",
    )


def _make_nm_frame_with_timing() -> CANFrame:
    return CANFrame(
        name=NM_FRAME_NAME,
        length=8,
        can_id=NM_CAN_ID,
        id_format="standard_11bit",
        frame_usage="network_management",
        timing=FrameTransmissionTiming(
            cyclic_timings=[FrameCyclicTiming(cycle=NM_CYCLE_S)],
            debounce_time=NM_TIMEOUT_S,
        ),
        packed_pdus=[PDUInstance(pdu_ref=NM_PDU_NAME, bit_position=0)],
    )


def _make_nm_frame_no_timing() -> CANFrame:
    return CANFrame(
        name=NM_FRAME_NAME,
        length=8,
        can_id=NM_CAN_ID,
        id_format="standard_11bit",
        frame_usage="network_management",
        packed_pdus=[PDUInstance(pdu_ref=NM_PDU_NAME, bit_position=0)],
    )


def _make_can_bus(nm_frame: CANFrame) -> CANBus:
    return CANBus(
        name=CAN_BUS_NAME,
        baud_rate=500_000,
        fd_enabled=False,
        frames=[nm_frame],
    )


def _make_can_comm_config(nm_pdu: StandardPDU, can_bus: CANBus) -> FLYNCCommunicationConfig:
    return FLYNCCommunicationConfig(channels=FLYNCChannelConfig(pdus=[nm_pdu], can_buses=[can_bus]))


def _make_active_ecu(
    name: str,
    port_name: str,
    port_role: str,
    is_sender: bool,
) -> ECU:
    port = ECUPort(
        name=port_name,
        mdi_config=BASET1(
            mode="base_t1",
            speed=100,
            duplex="full",
            role=port_role,
            autonegotiation=False,
        ),
        mii_config=None,
    )
    can_iface = CANInterface(
        name="can0",
        bus_ref=CAN_BUS_NAME,
        sender_frames=([CANFrameRef(bus_ref=CAN_BUS_NAME, frame_ref=NM_CAN_ID)] if is_sender else []),
        receiver_frames=([] if is_sender else [CANFrameRef(bus_ref=CAN_BUS_NAME, frame_ref=NM_CAN_ID)]),
    )
    ctrl = Controller(
        name=f"{name}_ctrl",
        controller_metadata=EmbeddedMetadata(
            author="Tester",
            compatible_flync_version=FLYNC_VERSION,
            target_system="flync_os",
        ),
        can_interfaces=[can_iface],
    )
    return ECU(
        name=name,
        ports=[port],
        controllers=[ctrl],
        topology=InternalTopology(connections=[]),
        ecu_metadata=ECUMetadata(
            author="Tester",
            compatible_flync_version=FLYNC_VERSION,
        ),
    )


def _make_sleeping_ecu(
    name: str,
    port_name: str,
    port_role: str,
) -> ECU:
    port = ECUPort(
        name=port_name,
        mdi_config=BASET1(
            mode="base_t1",
            speed=100,
            duplex="full",
            role=port_role,
            autonegotiation=False,
        ),
        mii_config=None,
    )
    can_iface = CANInterface(
        name="can0",
        bus_ref=CAN_BUS_NAME,
        sender_frames=[],
        receiver_frames=[],
    )
    ctrl = Controller(
        name=f"{name}_ctrl",
        controller_metadata=EmbeddedMetadata(
            author="Tester",
            compatible_flync_version=FLYNC_VERSION,
            target_system="flync_os",
        ),
        can_interfaces=[can_iface],
    )
    return ECU(
        name=name,
        ports=[port],
        controllers=[ctrl],
        topology=InternalTopology(connections=[]),
        ecu_metadata=ECUMetadata(
            author="Tester",
            compatible_flync_version=FLYNC_VERSION,
        ),
    )


def _make_can_topology(port1: str, port2: str) -> FLYNCTopology:
    return FLYNCTopology(
        system_topology=EthernetTopology(
            connections=[
                ExternalConnection(
                    id="can_bus_link",
                    ecu1_port=port1,
                    ecu2_port=port2,
                )
            ]
        )
    )


def _roundtrip(flync_model: FLYNCModel, tmpdir) -> None:
    workspace_path = Path(tmpdir) / "temp_workspace"
    ws = FLYNCWorkspace.load_model(
        flync_model=flync_model,
        workspace_name="generated_workspace",
        file_path=workspace_path,
    )
    final_model = ws.flync_model
    assert json.dumps(flync_model.model_dump(), sort_keys=True) == json.dumps(final_model.model_dump(), sort_keys=True)


# ============================================================================
# Tests
# ============================================================================


def test_Simple_CAN_ECU_Normal_NM_Operation(tmpdir):
    """
    Validates normal CAN Network Management operation with one ECU sending
    NM messages and another receiving them on the same CAN bus. The test
    also verifies model integrity after a save/load roundtrip.
    """
    nm_pdu = _make_nm_pdu()
    nm_frame = _make_nm_frame_no_timing()
    can_bus = _make_can_bus(nm_frame)

    sender = _make_active_ecu(
        name="ecu_sender",
        port_name="sender_port1",
        port_role="master",
        is_sender=True,
    )

    receiver = _make_active_ecu(
        name="ecu_receiver",
        port_name="receiver_port1",
        port_role="slave",
        is_sender=False,
    )

    model = FLYNCModel(
        ecus=[sender, receiver],
        communication=_make_can_comm_config(nm_pdu, can_bus),
        topology=_make_can_topology(
            "sender_port1",
            "receiver_port1",
        ),
        metadata=SystemMetadata(
            author="Tester",
            compatible_flync_version=FLYNC_VERSION,
            release=FLYNC_VERSION,
            platform="CAN_NM_Demo",
            variant="NormalOperation",
        ),
    )

    _roundtrip(model, tmpdir)


def test_Simple_Ethernet_ECU_Multicast_NM(tmpdir):
    """
    Validates a multicast Ethernet Network Management (NM) scenario where one HPC ECU sends NM messages over VLAN 40 and three zonal ECUs receive them.
    Ensures correct construction of the NM PDU/container stack, multicast TX/RX socket configuration, ECU connectivity, VLAN setup, and IGMP-like group membership.
    Verifies that all ECUs remain active and that the full model stays consistent after a workspace roundtrip (save/load).
    """
    nm_pdu = _make_nm_pdu()
    nm_container = _make_nm_container_pdu()
    comm = _make_comm_config(nm_pdu, nm_container)

    nm_tx = _make_nm_tx_socket()
    nm_rx1 = _make_nm_rx_socket("nm_rx_socket_z1")
    nm_rx2 = _make_nm_rx_socket("nm_rx_socket_z2")
    nm_rx3 = _make_nm_rx_socket("nm_rx_socket_z3")

    hpc = _make_hpc_ecu(nm_tx)
    z1 = _make_zonal_ecu(1, "192.168.40.10", 0x10, nm_rx1)
    z2 = _make_zonal_ecu(2, "192.168.40.20", 0x20, nm_rx2)
    z3 = _make_zonal_ecu(3, "192.168.40.30", 0x30, nm_rx3)

    topo = _make_ethernet_topology(
        ("hpc_port1", "zonal1_port1"),
        ("hpc_port1", "zonal2_port1"),
        ("hpc_port1", "zonal3_port1"),
    )

    flync_model = FLYNCModel(
        ecus=[hpc, z1, z2, z3],
        communication=comm,
        topology=topo,
        metadata=_make_system_metadata(),
    )

    channel_pdus = flync_model.communication.channels.pdus
    channel_containers = flync_model.communication.channels.ethernet_pdu_containers

    assert any(p.name == NM_PDU_NAME for p in channel_pdus), f"StandardPDU '{NM_PDU_NAME}' must be in communication.channels.pdus"
    assert any(
        c.name == NM_CONTAINER_NAME for c in channel_containers
    ), f"ContainerPDU '{NM_CONTAINER_NAME}' must be in communication.channels.ethernet_pdu_containers"

    container = next(c for c in channel_containers if c.name == NM_CONTAINER_NAME)

    assert container.pdu_usage == "network_management"
    assert container.header.id_length_bits == 16
    assert container.header.length_field_bits == 16
    assert len(container.contained_pdus) == 1
    assert container.contained_pdus[0].pdu_ref == NM_PDU_NAME
    assert container.contained_pdus[0].offset == 0

    nm_pdu_found = next(p for p in channel_pdus if p.name == NM_PDU_NAME)
    assert nm_pdu_found.length == NM_PDU_PAYLOAD_BYTES
    assert nm_pdu_found.pdu_usage == "network_management"

    hpc_ctrl = flync_model.ecus[0].controllers[0]
    hpc_eth = hpc_ctrl.ethernet_interfaces[0]
    hpc_sc = hpc_eth.sockets[0]
    hpc_udp = hpc_sc.sockets[0]

    assert hpc_udp.protocol == "udp"
    assert str(hpc_udp.endpoint_address) == NM_MULTICAST_ADDR
    assert hpc_udp.port_no == NM_UDP_PORT
    assert hpc_udp.endpoint_type == "multicast"
    assert str(hpc_udp.multicast_tx[0]) == NM_MULTICAST_ADDR
    assert len(hpc_udp.deployments) == 1
    assert hpc_udp.deployments[0].root.deployment_type == "pdu_sender"
    assert hpc_udp.deployments[0].root.pdu_ref == NM_CONTAINER_NAME

    hpc_groups = hpc.multicast_groups
    assert len(hpc_groups) == 1
    assert str(hpc_groups[0].group) == NM_MULTICAST_ADDR
    assert hpc_groups[0].mode == "tx"
    assert hpc_groups[0].vlan == NM_VLAN_ID

    for idx, zonal in enumerate([z1, z2, z3], start=1):
        zonal_ctrl = zonal.controllers[0]
        zonal_eth = zonal_ctrl.ethernet_interfaces[0]
        zonal_sc = zonal_eth.sockets[0]
        zonal_udp = zonal_sc.sockets[0]

        assert zonal_udp.protocol == "udp"
        assert str(zonal_udp.endpoint_address) == NM_MULTICAST_ADDR
        assert zonal_udp.port_no == NM_UDP_PORT
        assert zonal_udp.endpoint_type == "multicast"
        assert zonal_udp.multicast_tx == []
        assert len(zonal_udp.deployments) == 1
        assert zonal_udp.deployments[0].root.deployment_type == "pdu_receiver"
        assert zonal_udp.deployments[0].root.pdu_ref == NM_CONTAINER_NAME

        z_groups = zonal.multicast_groups
        assert len(z_groups) == 1
        assert str(z_groups[0].group) == NM_MULTICAST_ADDR
        assert z_groups[0].mode == "rx"
        assert z_groups[0].vlan == NM_VLAN_ID

    hpc_vci = hpc_ctrl.ethernet_interfaces[0].interface_config.virtual_interfaces[0]
    assert hpc_vci.vlanid == NM_VLAN_ID

    for zonal in [z1, z2, z3]:
        z_vci = zonal.controllers[0].ethernet_interfaces[0].interface_config.virtual_interfaces[0]
        assert z_vci.vlanid == NM_VLAN_ID
        assert NM_MULTICAST_ADDR in [str(a) for a in z_vci.multicast]

    assert hpc_eth.sockets[0].vlan_id == NM_VLAN_ID
    for zonal in [z1, z2, z3]:
        assert zonal.controllers[0].ethernet_interfaces[0].sockets[0].vlan_id == NM_VLAN_ID

    conns = flync_model.topology.ethernet_topology.connections
    assert len(conns) == 3

    zonal_ports = {c.ecu2_port_name for c in conns}
    assert zonal_ports == {"zonal1_port1", "zonal2_port1", "zonal3_port1"}
    assert all(c.ecu1_port_name == "hpc_port1" for c in conns)

    _roundtrip(flync_model, tmpdir)


def test_Simple_Ethernet_ECU_Multicast_NM_pdu_chain_structure():
    """
    Structural composition of the NM PDU chain: the ContainerPDU wraps exactly
    the NM StandardPDU, and the TX/RX multicast sockets bind that container via
    a pdu_sender / pdu_receiver deployment respectively.
    """
    nm_pdu = _make_nm_pdu()
    nm_container = _make_nm_container_pdu()
    nm_tx = _make_nm_tx_socket()
    nm_rx = _make_nm_rx_socket()

    # The container wraps exactly the NM PDU (single contained PDU, referenced by name).
    assert [contained.pdu_ref for contained in nm_container.contained_pdus] == [nm_pdu.name]

    # Both sockets bind that same container, in opposite directions.
    assert nm_tx.deployments[0].root.pdu_ref == nm_container.name
    assert nm_tx.deployments[0].root.deployment_type == "pdu_sender"
    assert nm_rx.deployments[0].root.pdu_ref == nm_container.name
    assert nm_rx.deployments[0].root.deployment_type == "pdu_receiver"


def test_Simple_Ethernet_ECU_Multicast_NM_vlan_isolation():
    """
    Checks VLAN 40 consistency for the NM transport: every HPC and Zonal
    SocketContainer and VirtualControllerInterface sits on VLAN 40, and every
    Zonal VCI subscribes to the NM multicast group. This is a structural
    consistency check — the model does not enforce cross-VLAN isolation at
    construction time, so no rejection of other-VLAN traffic is asserted here.
    """
    nm_tx = _make_nm_tx_socket()
    nm_rx1 = _make_nm_rx_socket("nm_rx_z1")
    nm_rx2 = _make_nm_rx_socket("nm_rx_z2")

    hpc = _make_hpc_ecu(nm_tx)
    z1 = _make_zonal_ecu(1, "192.168.40.10", 0x10, nm_rx1)
    z2 = _make_zonal_ecu(2, "192.168.40.20", 0x20, nm_rx2)

    for ecu in [hpc, z1, z2]:
        for ctrl in ecu.controllers:
            for eth in ctrl.ethernet_interfaces:
                for sc in eth.sockets:
                    assert sc.vlan_id == NM_VLAN_ID, f"{ecu.name}: SocketContainer must be on VLAN {NM_VLAN_ID}"
                for vci in eth.interface_config.virtual_interfaces:
                    assert vci.vlanid == NM_VLAN_ID, f"{ecu.name}: VCI must be on VLAN {NM_VLAN_ID}"

    for zonal in [z1, z2]:
        for ctrl in zonal.controllers:
            for eth in ctrl.ethernet_interfaces:
                for vci in eth.interface_config.virtual_interfaces:
                    mcast_strs = [str(m) for m in vci.multicast]
                    assert NM_MULTICAST_ADDR in mcast_strs, f"{zonal.name}: must subscribe to NM multicast {NM_MULTICAST_ADDR}"


def test_Simple_Ethernet_ECU_Multicast_NM_single_sender_multiple_receivers(tmpdir):
    """
    Validates the 1-to-N multicast Network Management (NM) topology with a single sender and multiple receivers.
    Ensures that exactly one ECU acts as the PDUSender while all others act as PDUReceivers, demonstrating correct multicast distribution and scalability.
    Verifies correct deployment counts across the system and confirms model consistency after a workspace roundtrip.
    """
    nm_pdu = _make_nm_pdu()
    nm_container = _make_nm_container_pdu()
    nm_tx = _make_nm_tx_socket()
    nm_rxs = [_make_nm_rx_socket(f"nm_rx_z{i}") for i in range(1, 5)]

    hpc = _make_hpc_ecu(nm_tx)
    zonals = [_make_zonal_ecu(i, f"192.168.40.{i * 10}", i * 0x10, nm_rxs[i - 1]) for i in range(1, 5)]

    topo = _make_ethernet_topology(*[("hpc_port1", f"zonal{i}_port1") for i in range(1, 5)])

    model = FLYNCModel(
        ecus=[hpc, *zonals],
        communication=_make_comm_config(nm_pdu, nm_container),
        topology=topo,
        metadata=_make_system_metadata(),
    )

    sender_count = 0
    receiver_count = 0

    for ecu in model.ecus:
        for ctrl in ecu.controllers:
            for eth in ctrl.ethernet_interfaces:
                for sc in eth.sockets:
                    for sock in sc.sockets:
                        for dep in sock.deployments:
                            if dep.root.deployment_type == "pdu_sender":
                                sender_count += 1
                            elif dep.root.deployment_type == "pdu_receiver":
                                receiver_count += 1

    assert sender_count == 1, f"Exactly one PDUSender expected; found {sender_count}"
    assert receiver_count == 4, f"Exactly four PDUReceiver expected; found {receiver_count}"

    _roundtrip(model, tmpdir)


def test_Simple_Ethernet_ECU_Unicast_NM_active(tmpdir):
    """
    Validates a UDP unicast Network Management (NM) communication between a single sender ECU and a single receiver ECU.
    Ensures correct ECU configuration, including IP addressing, MAC addressing, and proper assignment of PDUSender and PDUReceiver roles.
    Verifies that the unicast NM model is correctly built and remains consistent after a workspace roundtrip.
    """
    nm_pdu = _make_ethernet_nm_pdu()
    nm_container = _make_ethernet_nm_container_pdu()
    nm_tx = _make_unicast_nm_socket("nm_unicast_tx", "192.168.1.10", is_sender=True)
    nm_rx = _make_unicast_nm_socket("nm_unicast_rx", "192.168.1.20", is_sender=False)

    sender = _make_ethernet_ecu(
        ecu_name="unicast_sender",
        controller_name="sender_ctrl",
        ip_address="192.168.1.10",
        mac_address="00:AA:BB:CC:10:01",
        socket=nm_tx,
        port_name="sender_port1",
        port_role="master",
    )
    receiver = _make_ethernet_ecu(
        ecu_name="unicast_receiver",
        controller_name="receiver_ctrl",
        ip_address="192.168.1.20",
        mac_address="00:AA:BB:CC:10:02",
        socket=nm_rx,
        port_name="receiver_port1",
        port_role="slave",
    )

    model = FLYNCModel(
        ecus=[sender, receiver],
        communication=_make_comm_config(nm_pdu, nm_container),
        topology=_make_ethernet_topology(("sender_port1", "receiver_port1")),
        metadata=_make_ethernet_system_metadata(variant="UnicastNM"),
    )

    sender_socket = sender.controllers[0].ethernet_interfaces[0].sockets[0].sockets[0]
    receiver_socket = receiver.controllers[0].ethernet_interfaces[0].sockets[0].sockets[0]

    assert sender_socket.endpoint_type == "unicast"
    assert str(sender_socket.endpoint_address) == "192.168.1.10"
    assert sender_socket.multicast_tx == []
    assert sender_socket.deployments[0].root.deployment_type == "pdu_sender"

    assert receiver_socket.endpoint_type == "unicast"
    assert str(receiver_socket.endpoint_address) == "192.168.1.20"
    assert receiver_socket.deployments[0].root.deployment_type == "pdu_receiver"

    _roundtrip(model, tmpdir)


def test_Simple_Ethernet_ECU_Multicast_NM_single_receiver(tmpdir):
    """
    Validates a multicast Network Management (NM) setup with a single sender ECU and a single receiver ECU.
    Ensures correct multicast configuration for both TX and RX sockets, including proper multicast group usage and receiver subscription mode.
    Verifies that the model is correctly constructed and remains consistent after a workspace roundtrip.
    """
    nm_pdu = _make_nm_pdu()
    nm_container = _make_nm_container_pdu()
    comm = _make_comm_config(nm_pdu, nm_container)

    nm_tx = _make_nm_tx_socket()
    nm_rx = _make_nm_rx_socket("nm_rx_socket_z1")
    hpc = _make_hpc_ecu(nm_tx)
    z1 = _make_zonal_ecu(1, "192.168.40.10", 0x10, nm_rx)

    model = FLYNCModel(
        ecus=[hpc, z1],
        communication=comm,
        topology=_make_ethernet_topology(("hpc_port1", "zonal1_port1")),
        metadata=_make_ethernet_system_metadata(variant="MulticastSingleReceiver"),
    )

    tx_socket = hpc.controllers[0].ethernet_interfaces[0].sockets[0].sockets[0]
    rx_socket = z1.controllers[0].ethernet_interfaces[0].sockets[0].sockets[0]

    assert tx_socket.endpoint_type == "multicast"
    assert rx_socket.endpoint_type == "multicast"
    assert [str(a) for a in tx_socket.multicast_tx] == [NM_MULTICAST_ADDR]
    assert rx_socket.multicast_tx == []
    assert z1.multicast_groups[0].mode == "rx"

    _roundtrip(model, tmpdir)


def test_Simple_Ethernet_ECU_NM_sleep_and_wake_states():
    """
    Structural check of the sleep/active split: ECUs modelled as asleep carry
    no NM socket deployments, while an awake receiver ECU carries a
    pdu_receiver deployment. Runtime sleep/wake behaviour itself is out of
    scope for the static model.
    """
    sleeping_tx = _make_unicast_nm_socket("nm_unicast_tx_sleep", "192.168.2.10", is_sender=True)
    sleeping_tx.deployments = []
    sleeping_rx = _make_unicast_nm_socket("nm_unicast_rx_sleep", "192.168.2.20", is_sender=False)
    sleeping_rx.deployments = []

    sleepy_sender = _make_ethernet_ecu(
        ecu_name="sleepy_sender",
        controller_name="sleepy_ctrl",
        ip_address="192.168.2.10",
        mac_address="00:AA:BB:CC:20:01",
        socket=sleeping_tx,
        port_name="sleepy_port1",
        port_role="master",
    )
    sleepy_receiver = _make_ethernet_ecu(
        ecu_name="sleepy_receiver",
        controller_name="sleepy_rcv_ctrl",
        ip_address="192.168.2.20",
        mac_address="00:AA:BB:CC:20:02",
        socket=sleeping_rx,
        port_name="sleepy_port2",
        port_role="slave",
    )

    awake_socket = _make_unicast_nm_socket("nm_unicast_rx_awake", "192.168.2.30", is_sender=False)
    awake_receiver = _make_ethernet_ecu(
        ecu_name="awake_receiver",
        controller_name="awake_ctrl",
        ip_address="192.168.2.30",
        mac_address="00:AA:BB:CC:20:03",
        socket=awake_socket,
        port_name="awake_port1",
        port_role="slave",
    )

    assert sleepy_sender.controllers[0].ethernet_interfaces[0].sockets[0].sockets[0].deployments == []
    assert sleepy_receiver.controllers[0].ethernet_interfaces[0].sockets[0].sockets[0].deployments == []
    assert awake_receiver.controllers[0].ethernet_interfaces[0].sockets[0].sockets[0].deployments[0].root.deployment_type == "pdu_receiver"


def test_Switch_ECU_Controller_and_switch_topology():
    """
    Validates that a Switch ECU maintains a correct and fully connected topology even when the controller is considered inactive or asleep.
    Ensures proper bidirectional linkage between switch ports and controller interface, including correct component type associations.
    Verifies that the switch structure and its connections remain consistent and well-formed within the ECU model.
    """
    switch_ecu = _make_switch_ecu(
        port_name="switch_port1",
        controller_name="sleep_ctrl",
        controller_ip="192.168.50.10",
        controller_mac="00:AA:BB:CC:50:01",
    )

    switch = switch_ecu.switches[0]
    assert switch.name == "nm_switch"
    assert len(switch.ports) == 2
    assert switch.ports[0].connected_component is not None
    assert switch.ports[1].connected_component is not None
    assert switch.ports[1].connected_component.type == "controller_interface"
    assert switch_ecu.controllers[0].ethernet_interfaces[0].connected_component != []
    assert switch_ecu.controllers[0].ethernet_interfaces[0].connected_component[0].type == "switch_port"


def test_Switch_ECU_NM_forwarder_wakes_controller(tmpdir):
    """
    Checks the static NM-forwarding configuration in a Switch ECU: the RX
    socket carries a PDUForwarder whose egress targets the TX socket, and the
    downstream ECU carries a pdu_receiver deployment. Verifies the forwarder
    egress wiring and model consistency after a roundtrip — not the runtime
    forwarding or a controller wake-up, which the static model does not model.
    """
    nm_pdu = _make_nm_pdu()
    nm_container = _make_nm_container_pdu()
    comm = _make_comm_config(nm_pdu, nm_container)

    rx_socket_a = _make_unicast_nm_socket("nm_a_rx", "192.168.60.10", is_sender=False)
    tx_socket_a = _make_unicast_nm_socket("nm_a_tx", "192.168.60.10", is_sender=True)
    rx_socket_a.deployments.append(
        DeploymentUnion(
            root=PDUForwarder(
                pdu_ref=NM_CONTAINER_NAME,
                egresses=[ForwarderEgress(root=EthSocketEgress(socket_ref="nm_a_tx"))],
            )
        )
    )
    active_a = _make_ethernet_ecu_with_sockets(
        ecu_name="switch_a",
        controller_name="switch_ctrl_a",
        ip_address="192.168.60.10",
        mac_address="00:AA:BB:CC:60:01",
        sockets=[rx_socket_a, tx_socket_a],
        port_name="switch_a_port",
        port_role="master",
    )

    rx_socket = _make_unicast_nm_socket("nm_b_rx", "192.168.60.20", is_sender=False)
    passive_b = _make_ethernet_ecu(
        ecu_name="switch_b",
        controller_name="switch_ctrl_b",
        ip_address="192.168.60.20",
        mac_address="00:AA:BB:CC:60:02",
        socket=rx_socket,
        port_name="switch_b_port",
        port_role="slave",
    )

    model = FLYNCModel(
        ecus=[active_a, passive_b],
        communication=comm,
        topology=_make_ethernet_topology(("switch_a_port", "switch_b_port")),
        metadata=_make_ethernet_system_metadata(variant="SwitchForwarding"),
    )

    forwarders = [
        dep.root
        for socket in active_a.controllers[0].ethernet_interfaces[0].sockets[0].sockets
        for dep in socket.deployments
        if dep.root.deployment_type == "pdu_forwarder"
    ]

    assert len(forwarders) == 1
    assert forwarders[0].egresses[0].root.socket_ref == "nm_a_tx"
    assert passive_b.controllers[0].ethernet_interfaces[0].sockets[0].sockets[0].deployments[0].root.deployment_type == "pdu_receiver"

    _roundtrip(model, tmpdir)


def test_Switch_ECU_PDU_forwarder_switch_topology(tmpdir):
    """
    Validates NM forwarding in a multi-controller Switch ECU with complex internal topology.
    Ensures correct switch structure, including multiple switch ports and proper connectivity between external ports and controller interfaces.
    Verifies PDUForwarder configuration and correct egress routing within the switch-based NM forwarding architecture.
    """
    nm_pdu = _make_nm_pdu()
    nm_container = _make_nm_container_pdu()
    comm = _make_comm_config(nm_pdu, nm_container)

    switch_ports = [
        SwitchPort(
            name="sw_a",
            silicon_port_no=1,
            default_vlan_id=0,
            mii_config=MII(speed=100, mode="phy"),
        ),
        SwitchPort(
            name="sw_b",
            silicon_port_no=2,
            default_vlan_id=0,
            mii_config=MII(speed=100, mode="phy"),
        ),
        SwitchPort(
            name="sw_ext",
            silicon_port_no=3,
            default_vlan_id=0,
            mii_config=MII(speed=100, mode="phy"),
        ),
    ]
    switch = Switch(name="multi_switch", ports=switch_ports, vlans=[], meta=_make_controller_metadata())

    socket_a_rx = _make_unicast_nm_socket("nm_a_rx", "192.168.70.10", is_sender=False)
    socket_a_tx = _make_unicast_nm_socket("nm_a_tx", "192.168.70.10", is_sender=True)
    socket_a_rx.deployments.append(
        DeploymentUnion(
            root=PDUForwarder(
                pdu_ref=NM_CONTAINER_NAME,
                egresses=[ForwarderEgress(root=EthSocketEgress(socket_ref="nm_a_tx"))],
            )
        )
    )
    controller_a = _make_ethernet_ecu_with_sockets(
        ecu_name="complex_a",
        controller_name="complex_ctrl_a",
        ip_address="192.168.70.10",
        mac_address="00:AA:BB:CC:70:01",
        sockets=[socket_a_rx, socket_a_tx],
        port_name="complex_a_port",
        port_role="master",
        controller_mii_config=MII(speed=100, mode="mac"),
    )

    socket_b = _make_unicast_nm_socket("nm_b_rx", "192.168.70.20", is_sender=False)
    controller_b = _make_ethernet_ecu(
        ecu_name="complex_b",
        controller_name="complex_ctrl_b",
        ip_address="192.168.70.20",
        mac_address="00:AA:BB:CC:70:02",
        socket=socket_b,
        port_name="complex_b_port",
        port_role="slave",
        controller_mii_config=MII(speed=100, mode="mac"),
    )

    port_ext = ECUPort(
        name="complex_ext_port",
        mdi_config=BASET1(
            mode="base_t1",
            speed=100,
            duplex="full",
            role="master",
            autonegotiation=False,
        ),
        mii_config=MII(speed=100, mode="mac"),
    )
    ext_ecu = ECU(
        name="complex_switch_ecu",
        ports=[port_ext],
        controllers=[controller_a.controllers[0], controller_b.controllers[0]],
        switches=[switch],
        topology=InternalTopology(
            connections=[
                ECUPortToSwitchPort(
                    id="conn_ext_to_sw",
                    ecu_port="complex_ext_port",
                    switch_port="sw_ext",
                    switch="multi_switch",
                ),
                SwitchPortToControllerInterface(
                    id="conn_sw_a",
                    switch_port="sw_a",
                    switch="multi_switch",
                    controller_interface="eth0",
                    controller="complex_ctrl_a",
                ),
                SwitchPortToControllerInterface(
                    id="conn_sw_b",
                    switch_port="sw_b",
                    switch="multi_switch",
                    controller_interface="eth0",
                    controller="complex_ctrl_b",
                ),
            ]
        ),
        ecu_metadata=_make_ecu_metadata(),
    )

    model = FLYNCModel(
        ecus=[ext_ecu],
        communication=comm,
        topology=_make_ethernet_topology(("complex_ext_port", "complex_ext_port")),
        metadata=_make_ethernet_system_metadata(variant="ComplexSwitchNM"),
    )

    assert len(ext_ecu.switches) == 1
    assert len(ext_ecu.switches[0].ports) == 3
    assert ext_ecu.switches[0].ports[0].connected_component is not None
    assert ext_ecu.switches[0].ports[1].connected_component is not None
    assert ext_ecu.switches[0].ports[2].connected_component is not None

    forwarders = [
        dep.root
        for socket in controller_a.controllers[0].ethernet_interfaces[0].sockets[0].sockets
        for dep in socket.deployments
        if dep.root.deployment_type == "pdu_forwarder"
    ]
    assert len(forwarders) == 1
    assert forwarders[0].egresses[0].root.socket_ref == "nm_a_tx"

    _roundtrip(model, tmpdir)


def test_Simple_CAN_ECU_NM_Timeout_sleep_phase(tmpdir):
    """
    CAN NM sleep phase: with the NM frame present on the bus but every ECU
    modelled as asleep, no CAN interface declares sender or receiver frames,
    and the bus-carried NM frame has no cyclic timing (TX stopped). Model stays
    consistent across a workspace roundtrip.
    """
    nm_pdu = _make_nm_pdu()
    nm_frame = _make_nm_frame_no_timing()  # no cyclic timing → TX stopped
    can_bus = _make_can_bus(nm_frame)

    ecu_sender_sleeping = _make_sleeping_ecu("ecu_sender", "sender_port1", "master")
    ecu_receiver_sleeping = _make_sleeping_ecu("ecu_receiver", "receiver_port1", "slave")

    flync_model = FLYNCModel(
        ecus=[ecu_sender_sleeping, ecu_receiver_sleeping],
        communication=_make_can_comm_config(nm_pdu, can_bus),
        topology=_make_can_topology("sender_port1", "receiver_port1"),
        metadata=_make_system_metadata(),
    )

    for ecu in flync_model.ecus:
        for ctrl in ecu.controllers:
            for iface in ctrl.can_interfaces:
                assert iface.sender_frames == [], f"{ecu.name}: sleeping ECU must have no sender_frames"
                assert iface.receiver_frames == [], f"{ecu.name}: sleeping ECU must have no receiver_frames"

    bus_frame = flync_model.communication.channels.can_buses[0].frames[0]
    assert bus_frame.timing is None, "Post-timeout NM frame must carry no FrameTransmissionTiming (sender has stopped transmitting)"

    _roundtrip(flync_model, tmpdir)


def test_Simple_CAN_ECU_NM_Timeout_state_transition():
    """
    Contrasts an active and a sleeping CAN ECU: the active sender declares
    exactly one sender frame, the sleeping ECU declares neither sender nor
    receiver frames — the structural signature of the active→sleep transition.
    """
    ecu_active = _make_active_ecu("ecu_sender_active", "port_active", "master", is_sender=True)
    ecu_sleeping = _make_sleeping_ecu("ecu_sender_sleeping", "port_sleeping", "master")

    active_iface = ecu_active.controllers[0].can_interfaces[0]
    assert len(active_iface.sender_frames) == 1, "Active ECU must have sender_frames"

    sleeping_iface = ecu_sleeping.controllers[0].can_interfaces[0]
    assert sleeping_iface.sender_frames == [], "Sleeping ECU must have empty sender_frames"
    assert sleeping_iface.receiver_frames == [], "Sleeping ECU must have empty receiver_frames"


def test_Simple_CAN_ECU_NM_Timeout_active_phase(tmpdir):
    """
    Active CAN NM phase: the sender declares exactly one NM sender frame and
    the receiver one receiver frame, both resolving to the NM frame carried on
    the bus (which carries the cyclic TX timing). Model stays consistent across
    a workspace roundtrip.
    """
    nm_pdu = _make_nm_pdu()
    nm_frame = _make_nm_frame_with_timing()
    can_bus = _make_can_bus(nm_frame)

    ecu_sender = _make_active_ecu("ecu_sender", "sender_port1", "master", is_sender=True)
    ecu_receiver = _make_active_ecu("ecu_receiver", "receiver_port1", "slave", is_sender=False)

    flync_model = FLYNCModel(
        ecus=[ecu_sender, ecu_receiver],
        communication=_make_can_comm_config(nm_pdu, can_bus),
        topology=_make_can_topology("sender_port1", "receiver_port1"),
        metadata=_make_system_metadata(),
    )

    sender_iface = flync_model.ecus[0].controllers[0].can_interfaces[0]
    assert len(sender_iface.sender_frames) == 1, "Sender must declare exactly one NM frame"
    assert sender_iface.sender_frames[0].frame_ref == NM_CAN_ID
    assert sender_iface.sender_frames[0].bus_ref == CAN_BUS_NAME

    receiver_iface = flync_model.ecus[1].controllers[0].can_interfaces[0]
    assert len(receiver_iface.receiver_frames) == 1
    assert receiver_iface.receiver_frames[0].frame_ref == NM_CAN_ID

    # The sender's frame_ref resolves to the NM frame the bus actually carries,
    # and that frame holds the cyclic TX timing.
    bus_frame = flync_model.communication.channels.can_buses[0].frames[0]
    assert bus_frame.can_id == sender_iface.sender_frames[0].frame_ref
    assert bus_frame.timing is not None and len(bus_frame.timing.cyclic_timings) == 1

    _roundtrip(flync_model, tmpdir)


# ============================================================================
# Model-level negatives (need the full model + catalogue, hence co-located here)
# ============================================================================


def test_multicast_receiver_unknown_pdu_ref_raises():
    """An NM PDUReceiver whose pdu_ref is absent from the catalogue is rejected at model validation."""
    nm_pdu = _make_nm_pdu()
    nm_container = _make_nm_container_pdu()
    nm_tx = _make_nm_tx_socket()
    bad_rx = _make_nm_rx_socket("nm_rx_bad")
    bad_rx.deployments = [DeploymentUnion(root=PDUReceiver(pdu_ref="DoesNotExist"))]

    hpc = _make_hpc_ecu(nm_tx)
    z1 = _make_zonal_ecu(1, "192.168.40.10", 0x10, bad_rx)

    communication = _make_comm_config(nm_pdu, nm_container)
    topology = _make_ethernet_topology(("hpc_port1", "zonal1_port1"))
    metadata = _make_system_metadata()

    with pytest.raises(ValidationError) as exc_info:
        FLYNCModel(ecus=[hpc, z1], communication=communication, topology=topology, metadata=metadata)
    assert_single_error(exc_info, "FLYNC-CMN-MAJ-REF-175", "pdu_ref 'DoesNotExist'")


def test_duplicate_nm_pdu_in_catalog_raises():
    """Two NM PDUs sharing the same name in the catalogue are rejected."""
    duplicate_pdus = [_make_nm_pdu(), _make_nm_pdu()]
    containers = [_make_nm_container_pdu()]

    # The duplicate-name check lives on FLYNCChannelConfig, so that is the call under test.
    with pytest.raises(ValidationError) as exc_info:
        FLYNCChannelConfig(pdus=duplicate_pdus, ethernet_pdu_containers=containers)
    assert_single_error(exc_info, "FLYNC-CMN-MAJ-UNIQ-009", "Duplicates found in PDUs")
