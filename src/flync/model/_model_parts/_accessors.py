"""
Query/accessor methods for :class:`~flync.model.flync_model.FLYNCModel`.

Extracted from the top-level model so that :file:`flync_model.py` stays within SonarQube's per-file
line budget. These are pure readers -- they return data derived from the loaded model and do not
mutate it.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Dict, List, Optional, Tuple

from flync.model._model_parts._protocol import FLYNCModelProtocol
from flync.model._model_parts._types import SocketDeployment
from flync.model.flync_4_ecu import (
    ECU,
    ComputeNode,
    Controller,
    ECUPort,
    EthernetInterfaceConfig,
    SocketTCP,
    SocketUDP,
)
from flync.model.flync_4_signal.forwarder import CANFrameForwarder, PDUForwarder
from flync.model.flync_4_someip import SOMEIPServiceInterface
from flync.model.flync_4_topology.bus_topology import CANBusTopology, LINBusTopology
from flync.model.flync_4_topology.ethernet_multidrop import EthernetMultidropConnection


class AccessorMixin:
    """Queries over a loaded system model."""

    def get_can_bus_topology(self: FLYNCModelProtocol, bus_name: str) -> Optional[CANBusTopology]:
        """Return the derived CAN bus topology for ``bus_name``, or ``None`` if unknown."""
        return next((t for t in self.topology.can_bus_topology if t.bus_name == bus_name), None)

    def get_lin_bus_topology(self: FLYNCModelProtocol, bus_name: str) -> Optional[LINBusTopology]:
        """Return the derived LIN bus topology for ``bus_name``, or ``None`` if unknown."""
        return next((t for t in self.topology.lin_bus_topology if t.bus_name == bus_name), None)

    @property
    def multidrop_connections(self: FLYNCModelProtocol) -> List[EthernetMultidropConnection]:
        """Every multidrop connection in the system topology."""

        topology = self.topology.ethernet_topology if self.topology else None
        return [c for c in topology.connections if isinstance(c, EthernetMultidropConnection)] if topology else []

    def get_multidrop_connection(self: FLYNCModelProtocol, connection_id: str) -> Optional[EthernetMultidropConnection]:
        """Return the multidrop connection with ``connection_id``, or ``None`` if unknown."""

        return next((c for c in self.multidrop_connections if c.id == connection_id), None)

    def get_all_ecus(self: FLYNCModelProtocol) -> List[str]:
        """Return a list of all ECU names."""
        return [ecu.name for ecu in self.ecus]

    def get_ecu_by_name(self: FLYNCModelProtocol, ecu_name: str) -> ECU | None:
        """Retrieve an ECU by name."""
        for ecu in self.ecus:
            if ecu.name == ecu_name:
                return ecu
        return None

    def get_all_controllers(self: FLYNCModelProtocol) -> List[Controller]:
        """Return a list of all controllers in all ECUs."""
        controllers: list[Controller] = []
        for ecu in self.ecus:
            controllers.extend(ecu.controllers)
        return controllers

    def get_all_ecu_ports(self: FLYNCModelProtocol) -> List[ECUPort]:
        """Return a list of all ECU ports"""
        ecu_ports: list[ECUPort] = []
        for ecu in self.ecus:
            ecu_ports.extend(ecu.get_all_ports())
        return ecu_ports

    def get_all_ecu_ports_by_name(self: FLYNCModelProtocol) -> Dict[str, ECUPort]:
        """Return every ECU port keyed by its name."""
        return {e.name: e for e in self.get_all_ecu_ports()}

    def get_interface_by_name(self: FLYNCModelProtocol, name: str) -> EthernetInterfaceConfig | None:
        """Return the Ethernet interface config called ``name``, or ``None`` if unknown."""
        return next(
            (interface for interface in self.get_all_interfaces() if interface.name == name),
            None,
        )

    def get_all_interfaces(self: FLYNCModelProtocol) -> List[EthernetInterfaceConfig]:
        """Return the config of every Ethernet interface, compute node interfaces included."""
        return [eth_iface.interface_config for controller in self.get_all_controllers() for eth_iface in controller.iter_subtree_interfaces()]

    def get_all_interfaces_names(self: FLYNCModelProtocol) -> List[str]:
        """Return all the controller interface names"""
        all_interfaces: list[str] = []
        for ecu in self.get_all_ecus():
            all_interfaces.extend(self.get_interfaces_for_ecu(ecu))
        return all_interfaces

    def get_interfaces_for_ecu(self: FLYNCModelProtocol, ecu_name: str) -> List[str]:
        """Return a list of all interfaces for a given ECU."""
        ecu = self.get_ecu_by_name(ecu_name)
        if ecu:
            return [eth_iface.name for controller in ecu.controllers for eth_iface in controller.ethernet_interfaces or []]
        return []

    def get_ethernet_topology_info(self: FLYNCModelProtocol) -> dict[str, object] | None:
        """Return ethernet topology details, or ``None`` if no ethernet topology is defined."""
        return self.topology.ethernet_topology.model_dump() if self.topology.ethernet_topology else None

    def _iter_ecu_sockets(self: FLYNCModelProtocol) -> Iterator[tuple[ECU, SocketTCP | SocketUDP]]:
        """Yield ``(ecu, socket)`` for every :class:`Socket` across every ECU / controller / ethernet interface / VLAN container."""
        return (
            (ecu, socket)
            for ecu in self.ecus
            for controller in ecu.controllers
            for eth_iface in controller.ethernet_interfaces or []
            for socket_container in eth_iface.sockets or []
            for socket in socket_container.sockets or []
        )

    def _iter_all_sockets(self: FLYNCModelProtocol) -> Iterator[SocketTCP | SocketUDP]:
        """Yield every :class:`Socket` across every controller / ethernet interface / VLAN container."""
        return (socket for _ecu, socket in self._iter_ecu_sockets())

    def _iter_someip_multicast_udp_deployments(self: FLYNCModelProtocol) -> Iterator[tuple[SocketDeployment, SocketTCP | SocketUDP, ECU]]:
        """Yield ``(deployment, socket, ecu)`` for every SOME/IP deployment on a multicast UDP socket."""
        return (
            (deployment.root, socket, ecu)
            for ecu in self.ecus
            for ctrl in ecu.controllers
            for iface in ctrl.ethernet_interfaces or []
            for sock_con in iface.sockets or []
            for socket in sock_con.sockets or []
            for deployment in socket.deployments or []
            if deployment.root.deployment_type.startswith("someip_") and socket.endpoint_type == "multicast" and socket.protocol == "udp"
        )

    def get_all_pdu_forwarders(self: FLYNCModelProtocol) -> List[PDUForwarder]:
        """Return every PDUForwarder declared on any socket across all ECUs."""
        out: List[PDUForwarder] = []
        for socket in self._iter_all_sockets():
            for dep_root in socket.deployments or []:
                dep = dep_root.root
                if isinstance(dep, PDUForwarder):
                    out.append(dep)
        return out

    def get_all_can_frame_forwarders(self: FLYNCModelProtocol) -> List[CANFrameForwarder]:
        """Return every CANFrameForwarder declared on any CAN interface across all ECUs."""
        out: List[CANFrameForwarder] = []
        for controller in self.get_all_controllers():
            for can_iface in controller.can_interfaces or []:
                out.extend(can_iface.forwarder_frames or [])
        return out

    def get_all_someip_services(self: FLYNCModelProtocol) -> List[SOMEIPServiceInterface]:
        """Return all SOME/IP service interfaces declared in the system-wide someip_config."""
        if self.communication and self.communication.someip_config:
            return self.communication.someip_config.services
        return []

    def get_someip_services_by_identity(self: FLYNCModelProtocol) -> Dict[Tuple[int, int], SOMEIPServiceInterface]:
        """
        Return the system-wide SOME/IP service interfaces keyed by ``(service_id, major_version)``.
        """
        return {(svc.id, svc.major_version): svc for svc in self.get_all_someip_services()}

    def iter_app_binding_owners(self: FLYNCModelProtocol) -> Iterator[Controller | ComputeNode]:
        """
        Yield everything that can declare ``app_bindings`` — every controller and every compute node beneath it.

        A compute node binds its own applications to its own sockets, so it is a binding owner in its
        own right rather than being folded into its host controller.
        """
        for controller in self.get_all_controllers():
            yield controller
            yield from controller.iter_subtree_compute_nodes()
