"""Builders for real, fully-validated FLYNC model objects used as test fixtures.

Building through real Pydantic models (rather than ``MagicMock``) means these fixtures run every
model validator, so a model change that breaks an assumption a caller relies on breaks the tests
that use these builders too - that is the point, not a cost. See AGENTS.md "Writing tests".

Every builder takes keyword-only overrides with a default that a test can assert on verbatim, so
a test only has to name the one value it cares about and let everything else keep its default.

This module is not named ``test_*``, so ``sonar.test.inclusions=**/test_*.py`` correctly excludes
it from test-code metrics (see ``sonar-project.properties``).
"""

from __future__ import annotations

from typing import Optional

from flync.model.flync_4_communication.flync_communication import FLYNCCommunicationConfig
from flync.model.flync_4_ecu import (
    ECU,
    Controller,
    EthernetInterface,
    EthernetInterfaceConfig,
    VirtualControllerInterface,
)
from flync.model.flync_4_ecu.internal_topology import ECUPortToControllerInterface, ECUPortToSwitchPort, InternalTopology
from flync.model.flync_4_ecu.phy import BASET1
from flync.model.flync_4_ecu.port import ECUPort
from flync.model.flync_4_ecu.socket_container import SocketContainer
from flync.model.flync_4_ecu.sockets import IPv4AddressEndpoint
from flync.model.flync_4_ecu.switch import Switch, SwitchConfig, SwitchPort, VLANEntry
from flync.model.flync_4_metadata.metadata import BaseVersion, ECUMetadata, EmbeddedMetadata, SOMEIPServiceMetadata, SystemMetadata
from flync.model.flync_4_someip import SOMEIPServiceInterface
from flync.model.flync_4_topology.ethernet_topology import EthernetTopology, FLYNCTopology
from flync.model.flync_model import FLYNCModel

FLYNC_VERSION = "0.13.0"


def make_version(version: str = FLYNC_VERSION) -> BaseVersion:
    """Return the FLYNC schema version used by every builder in this module."""
    return BaseVersion(version=version)


def make_system_metadata(*, author: str = "TestTeam") -> SystemMetadata:
    """Return system metadata for a :class:`FLYNCModel`."""
    return SystemMetadata(type="system", release=make_version(), author=author, compatible_flync_version=make_version())


def make_ecu_metadata(*, author: str = "TestTeam") -> ECUMetadata:
    """Return ECU metadata."""
    return ECUMetadata(type="ecu", author=author, compatible_flync_version=make_version())


def make_controller_metadata(*, author: str = "TestTeam", target_system: str = "Device1") -> EmbeddedMetadata:
    """Return embedded metadata, used by both controllers and switches."""
    return EmbeddedMetadata(type="embedded", author=author, target_system=target_system, compatible_flync_version=make_version())


def make_empty_topology() -> FLYNCTopology:
    """Return a system topology with no inter-ECU connections."""
    return FLYNCTopology(ethernet_topology=EthernetTopology(connections=[]))


def make_ethernet_ecu_ports_and_topology(controller_name: str, iface_name: str) -> tuple[list[ECUPort], InternalTopology]:
    """Build the minimal ECU port and internal topology wiring required for one Ethernet interface."""

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


def make_ipv4_address(*, address: str = "10.0.20.5", netmask: str = "255.255.255.0") -> IPv4AddressEndpoint:
    """Return one IPv4 address/netmask pair. The CLI formats this as ``<address>/<prefix>``."""
    return IPv4AddressEndpoint(address=address, ipv4netmask=netmask)


def make_vci(
    *,
    name: str = "vi10",
    vlanid: Optional[int] = 10,
    addresses: Optional[list] = None,
) -> VirtualControllerInterface:
    """Return a virtual controller interface with one IPv4 address by default."""
    return VirtualControllerInterface(name=name, vlanid=vlanid, addresses=addresses if addresses is not None else [make_ipv4_address()])


def make_eth_interface(
    *,
    name: str = "ETH0",
    mac: str = "AA:BB:CC:DD:EE:FF",
    vcis: Optional[list] = None,
    compute_nodes: Optional[list] = None,
    sockets: Optional[list] = None,
) -> EthernetInterface:
    """Return an Ethernet interface with one virtual interface and no sockets by default."""
    return EthernetInterface(
        name=name,
        interface_config=EthernetInterfaceConfig(
            mac_address=mac,
            virtual_interfaces=vcis if vcis is not None else [make_vci()],
            compute_nodes=compute_nodes or [],
        ),
        sockets=sockets or [],
    )


def make_socket_container(*, vlan_id: Optional[int] = 10, sockets: Optional[list] = None) -> SocketContainer:
    """Return a socket container scoped to one VLAN."""
    return SocketContainer(name=f"container_vlan_{vlan_id}", vlan_id=vlan_id, sockets=sockets or [])


def make_controller(*, name: str = "CTRL0", ethernet_interfaces: Optional[list] = None) -> Controller:
    """Return a controller with one Ethernet interface by default."""
    return Controller(
        name=name,
        controller_metadata=make_controller_metadata(),
        ethernet_interfaces=ethernet_interfaces if ethernet_interfaces is not None else [make_eth_interface()],
    )


def make_ethernet_ecu(*, name: str = "ECU1", controllers: Optional[list] = None) -> ECU:
    """Return an ECU with one controller, deriving the ECU ports/topology its Ethernet interfaces need."""
    controllers = controllers if controllers is not None else [make_controller()]
    ports: list[ECUPort] = []
    connections: list = []
    for controller in controllers:
        for iface in controller.ethernet_interfaces or []:
            iface_ports, iface_topology = make_ethernet_ecu_ports_and_topology(controller.name, iface.name)
            ports.extend(iface_ports)
            connections.extend(iface_topology.connections)
    return ECU(
        name=name,
        controllers=controllers,
        ports=ports,
        topology=InternalTopology(connections=connections),
        ecu_metadata=make_ecu_metadata(),
    )


def make_switch_port(*, name: str = "SP0", silicon_port_no: int = 0, default_vlan_id: int = 10) -> SwitchPort:
    """Return a switch port."""
    return SwitchPort(name=name, silicon_port_no=silicon_port_no, default_vlan_id=default_vlan_id)


def make_vlan_entry(*, name: str = "vlan10", vlan_id: int = 10, ports: tuple[str, ...] = ("SP0",)) -> VLANEntry:
    """Return a VLAN entry naming the switch ports that belong to it."""
    return VLANEntry(name=name, id=vlan_id, default_priority=0, ports=list(ports))


def make_switch(
    *,
    name: str = "SW0",
    ports: Optional[list] = None,
    vlans: Optional[list] = None,
    host_controller: Optional[Controller] = None,
) -> Switch:
    """Return a switch with one port on one VLAN by default."""
    ports = ports if ports is not None else [make_switch_port()]
    vlans = vlans if vlans is not None else [make_vlan_entry(ports=tuple(p.name for p in ports))]
    config = SwitchConfig(meta=make_controller_metadata(), ports=ports, vlans=vlans)
    return Switch(name=name, switch_config=config, host_controller=host_controller)


def make_ecu_with_switch(*, name: str = "ECU1", switch: Optional[Switch] = None) -> ECU:
    """Return an ECU with one switch, wiring an ECU port to each switch port through the internal topology."""
    switch = switch if switch is not None else make_switch()
    connections = []
    ports = []
    for switch_port in switch.switch_config.ports:
        ecu_port = ECUPort(name=f"{switch_port.name}_port", mdi_config=BASET1())
        ports.append(ecu_port)
        connections.append(
            ECUPortToSwitchPort(id=f"conn_{switch_port.name}", ecu_port=ecu_port.name, switch_port=switch_port.name, switch=switch.name)
        )
    return ECU(
        name=name,
        controllers=[],
        switches=[switch],
        ports=ports,
        topology=InternalTopology(connections=connections),
        ecu_metadata=make_ecu_metadata(),
    )


def make_model(
    *,
    ecus: Optional[list] = None,
    topology: Optional[FLYNCTopology] = None,
    communication: Optional[FLYNCCommunicationConfig] = None,
) -> FLYNCModel:
    """Return a minimal, fully-validated :class:`FLYNCModel` wrapping *ecus*."""
    return FLYNCModel(
        ecus=ecus if ecus is not None else [make_ethernet_ecu()],
        topology=topology if topology is not None else make_empty_topology(),
        metadata=make_system_metadata(),
        communication=communication if communication is not None else FLYNCCommunicationConfig(),
    )


def make_someip_service_metadata(*, author: str = "TestTeam") -> SOMEIPServiceMetadata:
    """Return metadata for a :class:`SOMEIPServiceInterface`."""
    return SOMEIPServiceMetadata(author=author, compatible_flync_version=make_version())


def make_someip_service(*, name: str = "MyService", service_id: int = 0x0101, major_version: int = 1) -> SOMEIPServiceInterface:
    """Return a standalone SOME/IP service interface declaration.

    This validates independently of any deployment or SD/TCP wiring - it is the "service
    catalog" entry a real workspace would declare under ``communication/someip/services/``, not
    a deployed instance. See ``make_someip_deployed_ecu`` for a deployed provider.
    """
    return SOMEIPServiceInterface(name=name, id=service_id, major_version=major_version, meta=make_someip_service_metadata())
