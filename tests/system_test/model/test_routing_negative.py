from ipaddress import IPv4Address

import pytest
from pydantic import ValidationError

from flync.model.flync_4_bus.can_bus import CANBus
from flync.model.flync_4_communication.flync_channels import FLYNCChannelConfig
from flync.model.flync_4_communication.flync_communication import FLYNCCommunicationConfig
from flync.model.flync_4_ecu import EthernetInterface, EthernetInterfaceConfig, SocketTCP, VirtualControllerInterface
from flync.model.flync_4_ecu.can_interface import CANFrameRef, CANInterface
from flync.model.flync_4_ecu.controller import Controller
from flync.model.flync_4_ecu.ecu import ECU
from flync.model.flync_4_ecu.internal_topology import InternalTopology
from flync.model.flync_4_ecu.socket_container import SocketContainer
from flync.model.flync_4_ecu.sockets import IPv4AddressEndpoint
from flync.model.flync_4_metadata.metadata import BaseVersion, ECUMetadata, EmbeddedMetadata, SystemMetadata
from flync.model.flync_4_signal import CANFrame, CANFrameEgress, CANFrameForwarder, PDUSender
from flync.model.flync_4_signal.forwarder import EthSocketEgress, ForwarderEgress
from flync.model.flync_4_signal.pdu import PDUInstance, SignalInstance, StandardPDU
from flync.model.flync_4_signal.signal import Signal
from flync.model.flync_4_topology.system_topology import FLYNCTopology, SystemTopology
from flync.model.flync_model import FLYNCModel
from tests.error_assertions import assert_single_error

FLYNC_VERSION = "0.13.0"


def _make_version() -> BaseVersion:
    """Return the FLYNC version used by every negative routing test."""
    return BaseVersion(version=FLYNC_VERSION)


def _make_system_metadata() -> SystemMetadata:
    """Return the common system metadata used by every negative routing test."""
    return SystemMetadata(type="system", release=_make_version(), author="TestTeam", compatible_flync_version=_make_version())


def _make_empty_topology() -> FLYNCTopology:
    """Return an empty system topology usable by every negative routing test."""
    return FLYNCTopology(system_topology=SystemTopology(connections=[]))


def _make_controller_metadata() -> EmbeddedMetadata:
    """Return the common controller metadata used by every negative routing test."""
    return EmbeddedMetadata(type="embedded", author="TestTeam", target_system="Device1", compatible_flync_version=_make_version())


def _make_ecu_metadata() -> ECUMetadata:
    """Return the common ECU metadata used by every negative routing test."""
    return ECUMetadata(type="ecu", author="TestTeam", compatible_flync_version=_make_version())


def test_duplicate_forwarder_rejected():
    """
    Rejects duplicate CANFrameForwarder definitions for the same frame_ref on a single CAN interface.
    """
    sample_frame = CANFrame(name="EngineStatus", length=8, can_id=0x100, id_format="standard_11bit", is_remote_frame=False)
    forwarder1 = CANFrameForwarder(frame_ref=sample_frame.name, egresses=[CANFrameEgress(frame_ref=sample_frame.can_id, bus_ref="CAN1")])
    forwarder2 = CANFrameForwarder(frame_ref=sample_frame.name, egresses=[CANFrameEgress(frame_ref=sample_frame.can_id, bus_ref="CAN1")])
    sender_frame = CANFrameRef(bus_ref="CAN1", frame_ref=sample_frame.can_id)

    with pytest.raises(ValidationError) as exc_info:
        CANInterface(
            name="IF1",
            bus_ref="CAN1",
            sender_frames=[sender_frame],
            receiver_frames=[],
            forwarder_frames=[forwarder1, forwarder2],
        )
    assert_single_error(exc_info, "FLYNC-ECU-MAJ-UNIQ-058", "duplicate frame_ref")


def test_forwarder_missing_frame():
    """
    Rejects a forwarder referencing a frame not declared in communication.channels.
    """
    can_bus = CANBus(name="CAN_BUS_1", baud_rate=10000, frames=[])

    forwarder = CANFrameForwarder(frame_ref="NonExistentFrame", egresses=[CANFrameEgress(frame_ref=0x999, bus_ref="CAN_BUS_1")])

    can_interface = CANInterface(name="IF1", bus_ref="CAN_BUS_1", sender_frames=[], receiver_frames=[], forwarder_frames=[forwarder])
    controller = Controller(
        name="CTRL1",
        controller_metadata=_make_controller_metadata(),
        can_interfaces=[can_interface],
        ethernet_interfaces=[],
    )

    ecu = ECU(
        name="ECU1",
        controllers=[controller],
        topology=InternalTopology(),
        ecu_metadata=_make_ecu_metadata(),
    )
    topology = _make_empty_topology()
    metadata = _make_system_metadata()
    communication = FLYNCCommunicationConfig(channels=FLYNCChannelConfig(can_buses=[can_bus]))

    with pytest.raises(ValidationError) as exc_info:
        FLYNCModel(ecus=[ecu], topology=topology, metadata=metadata, communication=communication)
    assert_single_error(exc_info, "FLYNC-CMN-MAJ-REF-039", "does not name any CAN or CAN FD frame declared")


def test_forwarder_invalid_interface_routing():
    """
    Rejects CAN forwarding when routing violates interface or bus constraints.
    """
    engine_status = CANFrame(name="EngineStatus", length=8, can_id=0x100, id_format="standard_11bit", is_remote_frame=False)
    can_bus = CANBus(name="CAN1", baud_rate=10000, frames=[engine_status])
    forwarder = CANFrameForwarder(
        frame_ref="EngineStatus", egresses=[ForwarderEgress(root=CANFrameEgress(egress_type="can_frame", bus_ref="CAN1", frame_ref=0x100))]
    )
    can_interface = CANInterface(
        name="IF1", bus_ref="CAN1", receiver_frames=[], forwarder_frames=[forwarder], sender_frames=[CANFrameRef(bus_ref="CAN1", frame_ref=0x100)]
    )
    controller = Controller(
        name="CTRL1",
        controller_metadata=_make_controller_metadata(),
        can_interfaces=[can_interface],
        ethernet_interfaces=[],
    )
    ecu = ECU(name="ECU1", controllers=[controller], topology=InternalTopology(), ecu_metadata=_make_ecu_metadata())
    topology = _make_empty_topology()
    metadata = _make_system_metadata()
    communication = FLYNCCommunicationConfig(channels=FLYNCChannelConfig(can_buses=[can_bus]))

    with pytest.raises(ValidationError) as exc_info:
        FLYNCModel(ecus=[ecu], topology=topology, metadata=metadata, communication=communication)
    assert_single_error(exc_info, "FLYNC-CMN-MAJ-STRUCT-047", "Forwarder cycle detected")


def test_forwarder_invalid_target_bus():
    """
    Rejects CANFrameForwarder egresses targeting a bus with no interface on the controller.

    Both buses and both frames are declared on purpose: the missing interface on CAN2 has to be the only
    defect, otherwise the bus / frame reference passes would fail the workspace before the locality rule runs.
    """
    engine_status = CANFrame(name="EngineStatus", length=8, can_id=0x100, id_format="standard_11bit", is_remote_frame=False)
    engine_status_mirror = CANFrame(name="EngineStatusMirror", length=8, can_id=0x100, id_format="standard_11bit", is_remote_frame=False)
    can_bus_1 = CANBus(name="CAN1", baud_rate=10000, frames=[engine_status])
    can_bus_2 = CANBus(name="CAN2", baud_rate=10000, frames=[engine_status_mirror])
    forwarder = CANFrameForwarder(
        frame_ref="EngineStatus", egresses=[ForwarderEgress(root=CANFrameEgress(egress_type="can_frame", bus_ref="CAN2", frame_ref=0x100))]
    )
    can_interface = CANInterface(
        name="IF1", bus_ref="CAN1", receiver_frames=[], forwarder_frames=[forwarder], sender_frames=[CANFrameRef(bus_ref="CAN1", frame_ref=0x100)]
    )
    controller = Controller(
        name="CTRL1",
        controller_metadata=_make_controller_metadata(),
        can_interfaces=[can_interface],
        ethernet_interfaces=[],
    )
    ecu = ECU(name="ECU1", controllers=[controller], topology=InternalTopology(), ecu_metadata=_make_ecu_metadata())
    topology = _make_empty_topology()
    metadata = _make_system_metadata()
    communication = FLYNCCommunicationConfig(channels=FLYNCChannelConfig(can_buses=[can_bus_1, can_bus_2]))

    with pytest.raises(ValidationError) as exc_info:
        FLYNCModel(ecus=[ecu], topology=topology, metadata=metadata, communication=communication)
    assert_single_error(exc_info, "FLYNC-CMN-MAJ-REF-044", "which has no CAN interface on controller")


def test_forwarding_invalid_sender():
    """
    Rejects forwarding when sender declarations are inconsistent across interfaces.

    Both buses and both frames are declared on purpose: the missing sender_frames entry on IF2 has to be the
    only defect, otherwise the bus / frame reference passes would fail the workspace before this rule runs.
    """
    engine_status = CANFrame(name="EngineStatus", length=8, can_id=0x100, id_format="standard_11bit", is_remote_frame=False)
    engine_status_mirror = CANFrame(name="EngineStatusMirror", length=8, can_id=0x100, id_format="standard_11bit", is_remote_frame=False)
    can_bus_1 = CANBus(name="CAN1", baud_rate=10000, frames=[engine_status])
    can_bus_2 = CANBus(name="CAN2", baud_rate=10000, frames=[engine_status_mirror])
    forwarder = CANFrameForwarder(
        frame_ref="EngineStatus", egresses=[ForwarderEgress(root=CANFrameEgress(egress_type="can_frame", bus_ref="CAN2", frame_ref=0x100))]
    )
    can_interface_1 = CANInterface(
        name="IF1", bus_ref="CAN1", receiver_frames=[], forwarder_frames=[forwarder], sender_frames=[CANFrameRef(bus_ref="CAN1", frame_ref=0x100)]
    )
    can_interface_2 = CANInterface(name="IF2", bus_ref="CAN2", receiver_frames=[], sender_frames=[], forwarder_frames=[])
    controller = Controller(
        name="CTRL1",
        controller_metadata=_make_controller_metadata(),
        can_interfaces=[can_interface_1, can_interface_2],
        ethernet_interfaces=[],
    )
    ecu = ECU(name="ECU1", controllers=[controller], topology=InternalTopology(), ecu_metadata=_make_ecu_metadata())
    topology = _make_empty_topology()
    metadata = _make_system_metadata()
    communication = FLYNCCommunicationConfig(channels=FLYNCChannelConfig(can_buses=[can_bus_1, can_bus_2]))

    with pytest.raises(ValidationError) as exc_info:
        FLYNCModel(ecus=[ecu], topology=topology, metadata=metadata, communication=communication)
    assert_single_error(exc_info, "FLYNC-CMN-MAJ-CONS-045", "does not list it in sender_frames of that interface")


def test_forwarding_locality_violation():
    """
    Rejects CAN forwarding when locality rules between interfaces are violated.

    IF2 receives the egress frame but never sends it, so declaring it as a receiver is not enough to make the
    egress legal. Both buses and both frames are declared so that this is the only defect in the fixture.
    """
    engine_status = CANFrame(name="EngineStatus", length=8, can_id=0x100, id_format="standard_11bit", is_remote_frame=False)
    engine_status_mirror = CANFrame(name="EngineStatusMirror", length=8, can_id=0x100, id_format="standard_11bit", is_remote_frame=False)
    can_bus_1 = CANBus(name="CAN1", baud_rate=10000, frames=[engine_status])
    can_bus_2 = CANBus(name="CAN2", baud_rate=10000, frames=[engine_status_mirror])
    forwarder = CANFrameForwarder(
        frame_ref="EngineStatus", egresses=[ForwarderEgress(root=CANFrameEgress(egress_type="can_frame", bus_ref="CAN2", frame_ref=0x100))]
    )
    can_interface_1 = CANInterface(
        name="IF1", bus_ref="CAN1", receiver_frames=[], forwarder_frames=[forwarder], sender_frames=[CANFrameRef(bus_ref="CAN1", frame_ref=0x100)]
    )
    can_interface_2 = CANInterface(
        name="IF2", bus_ref="CAN2", receiver_frames=[CANFrameRef(bus_ref="CAN2", frame_ref=0x100)], sender_frames=[], forwarder_frames=[]
    )
    controller = Controller(
        name="CTRL1",
        controller_metadata=_make_controller_metadata(),
        can_interfaces=[can_interface_1, can_interface_2],
        ethernet_interfaces=[],
    )
    ecu = ECU(name="ECU1", controllers=[controller], topology=InternalTopology(), ecu_metadata=_make_ecu_metadata())
    topology = _make_empty_topology()
    metadata = _make_system_metadata()
    communication = FLYNCCommunicationConfig(channels=FLYNCChannelConfig(can_buses=[can_bus_1, can_bus_2]))

    with pytest.raises(ValidationError) as exc_info:
        FLYNCModel(ecus=[ecu], topology=topology, metadata=metadata, communication=communication)
    assert_single_error(exc_info, "FLYNC-CMN-MAJ-CONS-045", "does not list it in sender_frames of that interface")


def test_forwarding_can_to_ethernet_without_pdu():
    """
    Validates that CAN-to-Ethernet forwarding is rejected when the CAN frame does not contain a resolvable single PDU for Ethernet egress.

    The interface resolves against the declared bus on purpose: the frame without a packed PDU has to be the
    only defect, otherwise the bus reference pass would fail the workspace before the egress rule runs.
    """
    engine_status = CANFrame(name="EngineStatus", length=8, can_id=0x100, id_format="standard_11bit")
    can_bus = CANBus(name="CAN1_BUS", baud_rate=10000, frames=[engine_status])
    forwarder = CANFrameForwarder(
        frame_ref="EngineStatus",
        egresses=[ForwarderEgress(root=EthSocketEgress(egress_type="eth_socket", socket_ref="ETH_SOCKET_1"))],
    )
    can_interface = CANInterface(
        name="CAN_IF_1",
        bus_ref="CAN1_BUS",
        receiver_frames=[],
        sender_frames=[CANFrameRef(bus_ref="CAN1_BUS", frame_ref=0x100)],
        forwarder_frames=[forwarder],
    )
    controller = Controller(
        name="CTRL1",
        controller_metadata=_make_controller_metadata(),
        can_interfaces=[can_interface],
        ethernet_interfaces=[],
    )

    ecu = ECU(
        name="ECU1",
        controllers=[controller],
        topology=InternalTopology(),
        ecu_metadata=_make_ecu_metadata(),
    )
    topology = _make_empty_topology()
    metadata = _make_system_metadata()
    communication = FLYNCCommunicationConfig(channels=FLYNCChannelConfig(can_buses=[can_bus]))

    with pytest.raises(ValidationError) as exc_info:
        FLYNCModel(ecus=[ecu], topology=topology, metadata=metadata, communication=communication)
    assert_single_error(exc_info, "FLYNC-CMN-MAJ-REF-046", "cannot resolve egress PDU; ingress frame has no single packed PDU")


def test_invalid_extract_pdu_ref_on_standard_pdu():
    """
    Confirms that using 'extract_pdu_ref' on a CANFrameForwarder with a StandardPDU ingress raises a validation error.
    This property is only valid for ContainerPDUs.
    """
    engine_speed_signal = Signal(name="EngineSpeed", bit_length=16, data_type="uint16", factor=0.125, offset=0)

    engine_status_pdu = StandardPDU(name="EngineStatusPDU", length=8, signals=[SignalInstance(signal=engine_speed_signal, bit_position=0)])

    engine_status_frame = CANFrame(
        name="EngineStatus", length=8, can_id=0x100, id_format="standard_11bit", packed_pdus=[PDUInstance(pdu_ref="EngineStatusPDU", bit_position=0)]
    )

    can_bus = CANBus(name="CAN1_BUS", baud_rate=10000, frames=[engine_status_frame])

    forwarder = CANFrameForwarder(
        frame_ref="EngineStatus",
        egresses=[ForwarderEgress(root=EthSocketEgress(egress_type="eth_socket", socket_ref="ETH_SOCKET_1", extract_pdu_ref="EngineStatusPDU"))],
    )

    can_interface = CANInterface(
        name="CAN_IF_1",
        bus_ref="CAN1_BUS",
        receiver_frames=[],
        sender_frames=[CANFrameRef(bus_ref="CAN1_BUS", frame_ref=0x100)],
        forwarder_frames=[forwarder],
    )

    controller = Controller(
        name="CTRL1",
        controller_metadata=_make_controller_metadata(),
        can_interfaces=[can_interface],
        ethernet_interfaces=[],
    )

    ecu = ECU(
        name="ECU1",
        controllers=[controller],
        topology=InternalTopology(),
        ecu_metadata=_make_ecu_metadata(),
    )
    topology = _make_empty_topology()
    metadata = _make_system_metadata()
    communication = FLYNCCommunicationConfig(channels=FLYNCChannelConfig(can_buses=[can_bus], pdus=[engine_status_pdu]))

    with pytest.raises(ValidationError) as exc_info:
        FLYNCModel(ecus=[ecu], topology=topology, metadata=metadata, communication=communication)
    assert_single_error(exc_info, "FLYNC-CMN-MIN-CONS-035", "is only valid when ingress is a ContainerPDU")


def test_forwarding_can_to_ethernet_missing_pdu_deployment():
    """
    Validates that CAN-to-Ethernet forwarding is rejected when the target Ethernet socket does not define a PDU sender
    deployment for the forwarded PDU.
    """
    engine_speed_signal = Signal(name="EngineSpeed", bit_length=16, data_type="uint16", factor=0.125, offset=0)

    eth_iface = EthernetInterface(
        name="ETH_IF_1",
        interface_config=EthernetInterfaceConfig(
            virtual_interfaces=[
                VirtualControllerInterface(
                    name="VLAN_1",
                    vlanid=0,
                    addresses=[
                        IPv4AddressEndpoint(
                            address="192.168.1.10",
                            ipv4netmask=IPv4Address("255.255.255.0"),
                            sockets=[],
                        )
                    ],
                    multicast=[],
                )
            ],
        ),
        sockets=[
            SocketContainer(
                name="ETH_CONTAINER_1",
                vlan_id=0,
                sockets=[SocketTCP(name="ETH_SOCKET_1", endpoint_address="192.168.1.10", port_no=5000, tcp_profile=1)],
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
        forwarder_frames=[forwarder],
    )

    controller = Controller(
        name="CTRL1",
        controller_metadata=_make_controller_metadata(),
        can_interfaces=[can_interface],
        ethernet_interfaces=[eth_iface],
    )

    ecu = ECU(
        name="ECU1",
        controllers=[controller],
        topology=InternalTopology(),
        ecu_metadata=_make_ecu_metadata(),
    )
    topology = _make_empty_topology()
    metadata = _make_system_metadata()
    communication = FLYNCCommunicationConfig(channels=FLYNCChannelConfig(can_buses=[can_bus], pdus=[engine_status_pdu]))

    with pytest.raises(ValidationError) as exc_info:
        FLYNCModel(ecus=[ecu], topology=topology, metadata=metadata, communication=communication)
    assert_single_error(exc_info, "FLYNC-CMN-MAJ-CONS-043", "has no pdu_sender deployment for PDU")


def test_forwarding_can_to_ethernet_with_extract_pdu_ref_not_containerPDU():
    """
    Validates that CAN-to-Ethernet forwarding fails when `extract_pdu_ref` is used with a StandardPDU ingress instead of a ContainerPDU.
    """
    engine_speed_signal = Signal(name="EngineSpeed", bit_length=16, data_type="uint16", factor=0.125, offset=0)

    engine_status_pdu = StandardPDU(name="EngineStatusPDU", length=8, signals=[SignalInstance(signal=engine_speed_signal, bit_position=0)])

    can_frame = CANFrame(
        name="EngineStatusFrame",
        length=8,
        can_id=0x100,
        id_format="standard_11bit",
        packed_pdus=[PDUInstance(pdu_ref="EngineStatusPDU", bit_position=0)],
    )

    can_bus = CANBus(name="CAN1_BUS", baud_rate=10000, frames=[can_frame])

    forwarder = CANFrameForwarder(
        frame_ref="EngineStatusFrame",
        egresses=[ForwarderEgress(root=EthSocketEgress(egress_type="eth_socket", socket_ref="ETH_SOCKET_1", extract_pdu_ref="EngineStatusPDU"))],
    )

    can_interface = CANInterface(
        name="CAN_IF_1",
        bus_ref="CAN1_BUS",
        receiver_frames=[],
        sender_frames=[CANFrameRef(bus_ref="CAN1_BUS", frame_ref=0x100)],
        forwarder_frames=[forwarder],
    )

    eth_iface = EthernetInterface(
        name="ETH_IF_1",
        interface_config=EthernetInterfaceConfig(
            virtual_interfaces=[
                VirtualControllerInterface(
                    name="VLAN_1",
                    vlanid=0,
                    addresses=[
                        IPv4AddressEndpoint(
                            address="192.168.1.10",
                            ipv4netmask=IPv4Address("255.255.255.0"),
                            sockets=[],
                        )
                    ],
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

    controller = Controller(
        name="CTRL1",
        controller_metadata=_make_controller_metadata(),
        can_interfaces=[can_interface],
        ethernet_interfaces=[eth_iface],
    )

    ecu = ECU(
        name="ECU1",
        controllers=[controller],
        topology=InternalTopology(),
        ecu_metadata=_make_ecu_metadata(),
    )
    topology = _make_empty_topology()
    metadata = _make_system_metadata()
    communication = FLYNCCommunicationConfig(channels=FLYNCChannelConfig(can_buses=[can_bus], pdus=[engine_status_pdu], ethernet_pdu_containers=[]))

    with pytest.raises(ValidationError) as exc_info:
        FLYNCModel(ecus=[ecu], topology=topology, metadata=metadata, communication=communication)
    assert_single_error(exc_info, "FLYNC-CMN-MIN-CONS-035", "is only valid when ingress is a ContainerPDU")
