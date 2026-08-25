"""
Top-level system model aggregating ECUs, topology, metadata, and communication configuration in FLYNC.
"""

from typing import Annotated, Dict, List, Optional, Tuple

import typing_extensions
from pydantic import Field, model_validator
from pydantic_core import PydanticCustomError

from flync.core.annotations import External, NamingStrategy, OutputStrategy
from flync.core.base_models.base_model import FLYNCBaseModel
from flync.core.utils.base_utils import check_obj_in_list
from flync.core.utils.exceptions import Category, err_major, warn
from flync.core.utils.multicast import (
    collect_ipv6_solicited_node_rx,
    collect_ipv6_solicited_node_tx,
    compute_path,
    serialize_components,
)
from flync.core.validators.forwarder import (
    detect_forwarder_cycles,
    validate_forwarder_locality,
    validate_forwarder_refs,
    validate_pdu_deployment_refs,
)
from flync.core.validators.generic import validate_list_items_unique
from flync.core.validators.interface import (
    validate_interface_frame_refs,
)
from flync.core.validators.state_management import (
    validate_state_management,
)
from flync.model.flync_4_app import App
from flync.model.flync_4_communication import FLYNCCommunicationConfig
from flync.model.flync_4_ecu import (
    ECU,
    ECUPort,
    MulticastGroup,
    VirtualControllerInterface,
    VLANEntry,
)
from flync.model.flync_4_metadata import SystemMetadata
from flync.model.flync_4_signal.forwarder import CANFrameForwarder, PDUForwarder
from flync.model.flync_4_someip import SOMEIPServiceDeployment, SOMEIPServiceInterface
from flync.model.flync_4_topology import FLYNCTopology
from flync.model.flync_4_topology.bus_topology import (
    CANBusTopology,
    LINBusTopology,
    build_bus_topologies,
    validate_bus_topologies,
)


class FLYNCModel(FLYNCBaseModel):
    """
    Represents the top-level FLYNC configuration model for a system.

    This model aggregates all ECUs, system topology, metadata, and communication configuration settings for the entire system.

    Parameters
    ----------
    apps : list of :class:`~flync.model.flync_4_app.App`, optional
        Applications of the system.

    ecus : list of :class:`~flync.model.flync_4_ecu.ecu.ECU`
        List of ECU definitions included in the system.

    topology : :class:`~flync.model.flync_4_topology.FLYNCTopology`
        The system-wide topology including external ECU connections and optional multicast paths.

    metadata : :class:`~flync.model.flync_4_metadata.SystemMetadata`
        System-level metadata including OEM, platform, and hardware/software information.

    communication : :class:`~flync.model.flync_4_communication.FLYNCCommunicationConfig`, optional
        Optional communication configuration settings applicable system-wide.
    """

    apps: Annotated[
        Optional[List[App]],
        External(
            output_structure=OutputStrategy.FOLDER,
            naming_strategy=NamingStrategy.FIELD_NAME,
        ),
    ] = Field(default=None, description="Applications of the system.")

    communication: Annotated[
        Optional[FLYNCCommunicationConfig],
        External(
            output_structure=OutputStrategy.FOLDER,
            naming_strategy=NamingStrategy.FIELD_NAME,
        ),
    ] = Field(alias="general", default=None)
    ecus: Annotated[
        List[ECU],
        External(
            output_structure=OutputStrategy.FOLDER,
            naming_strategy=NamingStrategy.FIELD_NAME,
        ),
    ]
    topology: Annotated[
        FLYNCTopology,
        External(
            output_structure=OutputStrategy.FOLDER,
            naming_strategy=NamingStrategy.FIELD_NAME,
        ),
    ] = Field(default_factory=FLYNCTopology)
    metadata: Annotated[
        SystemMetadata,
        External(
            output_structure=OutputStrategy.SINGLE_FILE | OutputStrategy.OMMIT_ROOT,
            naming_strategy=NamingStrategy.FIXED_PATH,
            path="system_metadata",
        ),
    ]

    _EXCLUDED_NAME_CHECK_CLASSES: Tuple[type, ...] = (
        VirtualControllerInterface,
        VLANEntry,
    )

    @model_validator(mode="before")
    def warn_deprecated(cls, data):
        if "general" in data:
            warn("The 'general' attribute is deprecated. Please use 'communication' instead.", category=Category.LIFECYCLE, error_number="162")
        return data

    @model_validator(mode="before")
    def warn_experimental(cls, data):
        """Experimental Classes"""
        if "apps" in data and data["apps"] is not None:
            warn("Apps are currently experimental! Subject to change, please use with care.", category=Category.LIFECYCLE, error_number="188")
        return data

    @property
    @typing_extensions.deprecated("The `general` attribute is deprecated, use `communication` instead.")
    def general(self) -> Optional[FLYNCCommunicationConfig]:
        warn("The 'general' attribute is deprecated. Please use 'communication' instead.", category=Category.LIFECYCLE, error_number="163")
        return self.communication

    @model_validator(mode="before")
    @classmethod
    def default_absent_topology(cls, data):
        """
        Treat an absent ``topology/`` folder as the default (empty) topology for a CAN/LIN-only workspace.

        When no topology folder exists the workspace loader supplies ``None`` for ``topology``; drop the key so the
        ``default_factory`` builds an empty :class:`~flync.model.flync_4_topology.FLYNCTopology` (with no ethernet
        topology) instead of raising a misleading "input should be a valid dictionary" error.
        """

        if isinstance(data, dict) and data.get("topology", "") is None:
            data.pop("topology")
        return data

    @model_validator(mode="before")
    @classmethod
    def skip_broken_ecus(cls, data):
        """
        Remove None ECUs from the list before validation.

        When an ECU file fails to load the workspace inserts None into the ecus list.
        JErrors are already reported at the ECU level, so the None entries are silently dropped here to prevent a cascade of
        FLYNCModel-level errors for the same root cause.
        """

        if isinstance(data, dict):
            ecus = data.get("ecus") or []
            if isinstance(ecus, list) and any(e is None for e in ecus):
                data["ecus"] = [e for e in ecus if e is not None]
        return data

    def model_post_init(self, context):
        """
        Perform post-initialization processing after the model is created.

        Following steps are performed:

        1. Populate the solicited-node RX multicast group memberships for each IPv6 address configured in any ECU.

        2. Populate the solicited-node TX multicast group memberships for each ECU based on the RX entries for the same multicast group and VLAN.
        """

        self.__populate_ipv6_solicited_node_multicasts_rx()
        self.__populate_ipv6_solicited_node_multicasts_tx()

    @model_validator(mode="after")
    def validate_unique_ecu_names(self):
        validate_list_items_unique([ecu.name for ecu in self.ecus], "ECU names")
        return self

    @model_validator(mode="after")
    def validate_unique_port_names(self):
        all_ports = [port.name for ecu in self.ecus for port in ecu.get_all_ports()]
        validate_list_items_unique(all_ports, "ECU port names")
        return self

    @model_validator(mode="after")
    def validate_unique_app_names(self):
        validate_list_items_unique([app.name for app in self.apps or []], "App names")
        return self

    @model_validator(mode="after")
    def resolve_external_connections(self):
        if self.topology.ethernet_topology is None:
            return self
        ports_by_name = self.get_all_ecu_ports_by_name()
        for conn in self.topology.ethernet_topology.connections:
            try:
                conn.bind(ports_by_name)
            except PydanticCustomError as e:
                warn(str(e), category=Category.REFERENCE, error_number="164")
        return self

    @model_validator(mode="after")
    def validate_no_unconnected_ecu_ports(self):
        if self.topology.ethernet_topology is not None:
            self.topology.ethernet_topology.validate_no_unconnected_ports(self.get_all_ecu_ports())
        return self

    @model_validator(mode="after")
    def require_ethernet_topology_when_used(self):
        """
        The ethernet topology (``topology/system_topology.flync.yaml``) is optional, but system-wide features that
        rely on inter-ECU Ethernet connectivity (cross-ECU multicast, SOME/IP multicast) cannot be validated without
        it. Raise instead of silently skipping those checks.
        """

        if self.topology.ethernet_topology is not None:
            return self
        reasons = self._ethernet_topology_dependent_features()
        if reasons:
            raise err_major(
                "The ethernet topology file (topology/system_topology.flync.yaml) is required because system-wide "
                "Ethernet features are used: {reasons}",
                reasons=reasons,
                category=Category.REQUIRED,
                error_number="219",
            )
        if len([ecu for ecu in self.ecus if ecu.ports]) >= 2:
            warn(
                "Multiple ECUs declare Ethernet ports but no ethernet topology (external connections) is defined.",
                category=Category.CONSISTENCY,
                error_number="220",
            )
        return self

    def _ethernet_topology_dependent_features(self) -> List[str]:
        """Return human-readable reasons the ethernet topology is required, or an empty list if it is not."""

        if len([ecu for ecu in self.ecus if ecu.ports]) < 2:
            # Single (or zero) Ethernet ECUs: multicast fully resolves from internal topology alone.
            return []

        reasons = []
        if any(mcast for ecu in self.ecus for mcast in (ecu.multicast_groups or []) if not mcast.solicited_node_multicast):
            reasons.append("multicast group memberships are configured")
        someip_multicast = [
            socket
            for ecu in self.ecus
            for ctrl in ecu.controllers
            for iface in ctrl.ethernet_interfaces or []
            for sock_con in iface.sockets or []
            for socket in sock_con.sockets or []
            for deployment in socket.deployments or []
            if deployment.root.deployment_type.startswith("someip_") and socket.endpoint_type == "multicast" and socket.protocol == "udp"
        ]
        if someip_multicast:
            reasons.append("SOME/IP multicast deployments are configured")
        return reasons

    @model_validator(mode="after")
    def validate_unique_ips(self):
        """
        Validate all IPs are unique system wide
        """

        try:
            all_ips = []
            for ecu in self.ecus:
                new_ips = ecu.get_all_ips()
                for ip in new_ips:
                    if ip not in all_ips:
                        all_ips.append(ip)
                    elif str(ip) not in ("0.0.0.0", "::"):
                        warn(f"The IP {ip} is repeated in ECU {ecu.name}", category=Category.UNIQUENESS, error_number="165")
        except PydanticCustomError as e:
            warn(str(e), category=Category.UNIQUENESS, error_number="166")
        return self

    @model_validator(mode="after")
    def check_tx_rx_multicast_group(self):
        try:
            tx_list = []
            rx_list = []
            separ = "/VLAN"
            for ecu in self.ecus:
                for mcast in ecu.multicast_groups:
                    key = str(mcast.group) + separ + str(mcast.vlan)
                    if mcast.mode == "tx":
                        tx_list.append(key)
                    if mcast.mode == "rx":
                        rx_list.append(key)

            for rx in rx_list:
                if rx not in tx_list:
                    warn(
                        f"Invalid Multicast Configuration. There is a multicast rx configured for the address {rx} but no tx.",
                        category=Category.CONSISTENCY,
                        error_number="167",
                    )
        except PydanticCustomError as e:
            warn(str(e), category=Category.CONSISTENCY, error_number="168")
        return self

    @model_validator(mode="after")
    def validate_multicast_paths(self):
        try:
            paths = {}
            vlans_dict = {}
            separ = "/VLAN"
            for ecu in self.ecus:
                for mcast in ecu.multicast_groups:
                    key = str(mcast.group) + separ + str(mcast.vlan)
                    vlans_dict[key] = mcast.vlan
                    if (mcast.mode == "tx") and key not in paths:

                        paths[key] = compute_path(mcast.vlan, mcast._interface)
                    if (mcast.mode == "tx") and key in paths and not check_obj_in_list(mcast._interface, paths[key]):
                        warn(
                            "Invalid Multicast Address Configuration. There are several RX that the TX Endpoint at "
                            f"{mcast._interface.name} cannot reach. {serialize_components(paths[key])}",
                            category=Category.CONSISTENCY,
                            error_number="169",
                        )
            self.check_rx_are_reached(separ, paths, vlans_dict)
        except PydanticCustomError as e:
            warn(str(e), category=Category.CONSISTENCY, error_number="170")
        return self

    @model_validator(mode="after")
    def validate_no_someip_multicast_on_tcp(self):
        """
        Validate that no SOME/IP eventgroup multicast is configured on a TCP socket.

        TCP is a point-to-point transport, so it cannot carry the eventgroup multicast of a provided
        service - that deployment belongs on a UDP socket.
        """

        offender = next(
            (
                (ecu, socket, deployment.root)
                for ecu, socket in self._iter_ecu_sockets()
                if socket.protocol == "tcp"
                for deployment in socket.deployments or []
                if deployment.root.deployment_type == "someip_provider" and deployment.root.multicast_config
            ),
            None,
        )
        if offender is None:
            return self

        ecu, socket, provider = offender
        raise err_major(
            f"Deployed provided service on TCP socket ({socket.name}) of ECU ({ecu.name}) has multicast "
            f"configuration for eventgroups "
            f"({[mcast.eventgroups for mcast in provider.multicast_config]}); "
            f"SOME/IP eventgroup multicast requires a UDP socket",
            category=Category.CONSISTENCY,
            error_number="218",
        )

    @model_validator(mode="after")
    def validate_unique_macs(self):
        """
        Validate all MACs are unique system wide
        """

        all_macs = []
        for ecu in self.ecus:
            new_macs = ecu.get_all_macs()
            for mac in new_macs:
                if mac not in all_macs:
                    all_macs.append(mac)
                else:
                    raise err_major(f"The MAC {mac} is repeated in ECU {ecu.name}", category=Category.UNIQUENESS, error_number="172")
        return self

    @model_validator(mode="after")
    def validate_bus_interface_frame_refs(self):
        """Workspace-level bus interface pass: every CAN / LIN interface names a declared bus of its own kind and resolves its frame refs."""

        validate_interface_frame_refs(self)
        return self

    @model_validator(mode="after")
    def validate_forwarders(self):
        """Workspace-level forwarder/deployment pass: ref resolution, same-controller locality + direction safety, and cycle detection."""

        validate_pdu_deployment_refs(
            self
        )  # Verifies every pdu_sender / pdu_receiver references a declared PDU of any kind, forwarder-involved or standalone.
        validate_forwarder_refs(self)  # Verifies all PDU and frame references resolve and the forwarded payload fits the egress CAN frame.
        validate_forwarder_locality(self)  # Verifies each egress targets a same-controller carrier with a compatible pdu_sender or sender_frames.
        detect_forwarder_cycles(self)  # Verifies the forwarder graph is acyclic.
        return self

    @model_validator(mode="after")
    def validate_service_refs_in_apps(self):
        """Validate that applications are referencing existing services."""
        known_services = self.get_someip_services_by_identity()
        for app in self.apps or []:
            for ref in (app.service_consumer_refs or []) + (app.service_provider_refs or []):
                if (ref.service_name, ref.major_version) not in known_services:
                    raise err_major(
                        f"App {app.name} references service ({ref.service_name}, major_version={ref.major_version}) "
                        "that is not defined in the system's SOME/IP configuration.",
                        category=Category.REFERENCE,
                        error_number="186",
                    )
        return self

    @model_validator(mode="after")
    def validate_app_refs_in_controller_bindings(self):
        """Validate that app_bindings of ecu controllers are referencing existing apps."""
        apps_by_name = {app.name: app for app in self.apps or []}
        for controller in self.get_all_controllers():
            if controller.app_bindings:
                controller.app_bindings.resolve_apps(apps_by_name, controller.name)
        return self

    @model_validator(mode="after")
    def validate_app_bindings_consume_deployed_services(self):
        """Every app bound to a controller must have its service_consumer_refs matched by a someip_consumer
        deployment on that same controller."""
        services_by_identity = self.get_someip_services_by_identity()
        for controller, consumed_instances, app, ref in self._iter_bound_app_consumer_refs():
            svc = services_by_identity.get((ref.service_name, ref.major_version))
            key = (svc.id, ref.major_version, ref.instance_id) if svc else None
            if key not in consumed_instances:
                raise err_major(
                    f"App '{app.name}' bound to controller '{controller.name}' expects to consume "
                    f"({ref.service_name}, instance_id={ref.instance_id}, major_version={ref.major_version}), "
                    "but the controller does not deploy it as a SOME/IP consumer.",
                    category=Category.CONSISTENCY,
                    error_number="245",
                )
        return self

    @model_validator(mode="after")
    def validate_state_management_groups(self):
        """Workspace-level state management pass: group refs, derived member sets, NM PDU binding, and reachability."""
        validate_state_management(self)
        return self

    @model_validator(mode="after")
    def build_and_validate_bus_topologies(self):
        """Derive the system-wide CAN/LIN bus topology from bus definitions and ECU interfaces, then validate it."""

        can_topos, lin_topos, can_defs, lin_defs = build_bus_topologies(self)
        self.topology.can_bus_topology = can_topos
        self.topology.lin_bus_topology = lin_topos
        validate_bus_topologies(can_topos, lin_topos, can_defs, lin_defs)
        return self

    def get_can_bus_topology(self, bus_name: str) -> Optional["CANBusTopology"]:
        """Return the derived CAN bus topology for ``bus_name``, or ``None`` if unknown."""
        return next((t for t in self.topology.can_bus_topology if t.bus_name == bus_name), None)

    def get_lin_bus_topology(self, bus_name: str) -> Optional["LINBusTopology"]:
        """Return the derived LIN bus topology for ``bus_name``, or ``None`` if unknown."""
        return next((t for t in self.topology.lin_bus_topology if t.bus_name == bus_name), None)

    def check_rx_are_reached(self, separ, paths, vlans_dict):
        for ecu in self.ecus:
            for mcast in ecu.multicast_groups:
                key = str(mcast.group) + separ + str(mcast.vlan)
                if (mcast.mode == "rx") and key not in paths:

                    warn(
                        f"Invalid Multicast Address Configuration. There are no TX endpoints for this address {key} ",
                        category=Category.CONSISTENCY,
                        error_number="173",
                    )
                if (mcast.mode == "rx") and key in paths and not check_obj_in_list(mcast._interface, paths[key]):
                    warn(
                        f"Invalid Multicast Address Configuration. The RX interface for address {key} "
                        f"- {mcast._interface.name} cannot be reached by the TX ports.",
                        category=Category.CONSISTENCY,
                        error_number="174",
                    )

        self.load_switch_multicast(vlans_dict, paths)

        return self

    def __populate_ipv6_solicited_node_multicasts_rx(self):
        """
        Populate the solicited-node multicast group memberships for each IPv6 address configured in any ECU.
        """

        for ecu in self.ecus:
            update_ecu_multicast = collect_ipv6_solicited_node_rx(ecu)
            if ecu.name in update_ecu_multicast:
                ecu.multicast_groups.append(update_ecu_multicast[ecu.name])
        return self

    def __populate_ipv6_solicited_node_multicasts_tx(self):
        """
        Populate the solicited-node multicast group memberships for each IPv6 address configured in any ECU as TX if there is a RX for the
        same multicast group and VLAN.
        """

        multicasts = [mc for ecu in self.ecus for mc in ecu.multicast_groups if mc.solicited_node_multicast]

        for ecu in self.ecus:
            update_ecu_multicast = collect_ipv6_solicited_node_tx(ecu, multicasts)
            if ecu.name in update_ecu_multicast:
                ecu.multicast_groups.append(update_ecu_multicast[ecu.name])
        return self

    def append_mcast(self, vlan, comp, mcast_addr):
        for v_entry in comp.get_switch().vlans:
            if v_entry.id == vlan:
                found_mcast = False
                for addr in v_entry.multicast:
                    if str(addr.address) == mcast_addr:
                        found_mcast = True
                        addr.ports.append(comp.name)
                if not found_mcast:
                    new_mcast_group = MulticastGroup(address=mcast_addr, ports=[comp.name])
                    v_entry.multicast.append(new_mcast_group)

    def load_switch_multicast(self, vlans_dict, paths):
        for key, value in paths.items():
            for comp in value:
                if comp.type == "switch_port":
                    ip = key.split("/")[0]
                    self.append_mcast(vlans_dict[key], comp, ip)

    def get_all_ecus(self):
        """Return a list of all ECU names."""
        return [ecu.name for ecu in self.ecus]

    def get_ecu_by_name(self, ecu_name: str):
        """Retrieve an ECU by name."""
        for ecu in self.ecus:
            if ecu.name == ecu_name:
                return ecu
        return None

    def get_all_controllers(self):
        """Return a list of all controllers in all ECUs."""
        controllers = []
        for ecu in self.ecus:
            controllers.extend(ecu.controllers)
        return controllers

    def get_all_ecu_ports(self) -> List["ECUPort"]:
        """Return a list of all ECU ports"""
        ecu_ports = []
        for ecu in self.ecus:
            ecu_ports.extend(ecu.get_all_ports())
        return ecu_ports

    def get_all_ecu_ports_by_name(self) -> Dict[str, "ECUPort"]:
        return {e.name: e for e in self.get_all_ecu_ports()}

    def get_interface_by_name(self, name):
        return next(
            (interface for interface in self.get_all_interfaces() if interface.name == name),
            None,
        )

    def get_all_interfaces(self):
        return [eth_iface.interface_config for controller in self.get_all_controllers() for eth_iface in controller.ethernet_interfaces]

    def get_all_interfaces_names(self):
        """Return all the controller interface names"""
        all_interfaces = []
        for ecu in self.get_all_ecus():
            all_interfaces.extend(self.get_interfaces_for_ecu(ecu))
        return all_interfaces

    def get_interfaces_for_ecu(self, ecu_name: str):
        """Return a list of all interfaces for a given ECU."""
        ecu = self.get_ecu_by_name(ecu_name)
        if ecu:
            return [eth_iface.name for controller in ecu.controllers for eth_iface in controller.ethernet_interfaces]
        return []

    def get_ethernet_topology_info(self):
        """Return ethernet topology details, or ``None`` if no ethernet topology is defined."""
        return self.topology.ethernet_topology.model_dump() if self.topology.ethernet_topology else None

    def _bind_tcp_profiles(self, tcp_by_id):
        for sock in self._iter_all_sockets():
            if hasattr(sock, "bind"):
                sock.bind(tcp_by_id)

    @model_validator(mode="after")
    def resolve_tcp_profiles(self):
        if self.communication:
            tcp_by_id = {t.tcp_profile_id: t for t in (self.communication.tcp_profiles or [])}
            self._bind_tcp_profiles(tcp_by_id)
        return self

    def _bind_someip_sockets(self, services_by_key, sd_timings_by_id):
        for sock in self._iter_all_sockets():
            for dep_union in sock.deployments or []:
                dep = dep_union.root
                if isinstance(dep, SOMEIPServiceDeployment):
                    dep.bind(services_by_key, sd_timings_by_id)

    @model_validator(mode="after")
    def resolve_someip_deployments(self):
        if self.communication and self.communication.someip_config:
            someip = self.communication.someip_config
            services_by_key = {(s.id, s.major_version): s for s in someip.services}
            sd_timings_by_id = {t.profile_id: t for t in someip.sd_config.sd_timings} if someip.sd_config else {}
            self._bind_someip_sockets(services_by_key, sd_timings_by_id)
        return self

    @model_validator(mode="after")
    def validate_multicast_someip(self):
        """
        Validate multicast configuration for SOME/IP consumers and providers

        For provider: check if the parent socket has a multicast_tx entry

        Defined after :meth:`resolve_someip_deployments`: the message identifies the offending service through
        ``_service_ref``, which only exists once the deployments have been bound.
        """

        deployments = [
            (deployment.root, socket, ecu)
            for ecu in self.ecus
            for ctrl in ecu.controllers
            for iface in ctrl.ethernet_interfaces
            for sock_con in iface.sockets
            for socket in sock_con.sockets
            for deployment in socket.deployments
            if deployment.root.deployment_type.startswith("someip_") and socket.endpoint_type == "multicast" and socket.protocol == "udp"
        ]

        providers = [dpl for dpl in deployments if dpl[0].deployment_type == "someip_provider"]

        # Providers need to have multicast_tx in socket
        for provider, socket, _ecu in providers:
            svc = provider._service_ref
            # An unbound deployment (no someip_config declared) still names its service by id / major_version.
            svc_label = f"{svc.name}, {svc.id:#06x}, {svc.major_version}" if svc else f"{provider.service:#06x}, {provider.major_version}"
            for mcast_config in provider.multicast_config or []:
                if mcast_config.ip_address not in socket.multicast_tx:
                    raise err_major(
                        f"Deployed provided service ({svc_label}) "
                        f"has multicast configuration for eventgroups ({mcast_config.eventgroups}/{mcast_config.ip_address}), "
                        f"but socket ({socket.name}) does not indicate by multicast_tx entry ({socket.multicast_tx})",
                        category=Category.CONSISTENCY,
                        error_number="171",
                    )

        return self

    def _iter_ecu_sockets(self):
        """Yield ``(ecu, socket)`` for every :class:`Socket` across every ECU / controller / ethernet interface / VLAN container."""
        return (
            (ecu, socket)
            for ecu in self.ecus
            for controller in ecu.controllers
            for eth_iface in controller.ethernet_interfaces or []
            for socket_container in eth_iface.sockets or []
            for socket in socket_container.sockets or []
        )

    def _iter_all_sockets(self):
        """Yield every :class:`Socket` across every controller / ethernet interface / VLAN container."""
        return (socket for _ecu, socket in self._iter_ecu_sockets())

    def get_all_someip_services(self) -> List[SOMEIPServiceInterface]:
        """Return all SOME/IP service interfaces declared in the system-wide someip_config."""
        if self.communication and self.communication.someip_config:
            return self.communication.someip_config.services
        return []

    def get_someip_services_by_identity(self) -> Dict[Tuple[str, int], SOMEIPServiceInterface]:
        """
        Return the system-wide SOME/IP service interfaces keyed by ``(name, major_version)``.
        """
        return {(svc.name, svc.major_version): svc for svc in self.get_all_someip_services()}

    def _iter_bound_app_consumer_refs(self):
        """
        Yield ``(controller, consumed_instances, app, ref)`` for every consumer reference of every app bound to a
        controller, where ``consumed_instances`` is that controller's set of SOME/IP consumer service triples.
        """

        for controller in self.get_all_controllers():
            if not controller.app_bindings:
                continue
            consumed_instances = controller.get_consumed_service_instances()
            for app in controller.app_bindings.apps:
                for ref in app.service_consumer_refs or []:
                    yield controller, consumed_instances, app, ref

    def get_all_pdu_forwarders(self) -> List[PDUForwarder]:
        """Return every PDUForwarder declared on any socket across all ECUs."""
        out: List[PDUForwarder] = []
        for socket in self._iter_all_sockets():
            for dep_root in socket.deployments or []:
                dep = dep_root.root
                if isinstance(dep, PDUForwarder):
                    out.append(dep)
        return out

    def get_all_can_frame_forwarders(self) -> List[CANFrameForwarder]:
        """Return every CANFrameForwarder declared on any CAN interface across all ECUs."""
        out: List[CANFrameForwarder] = []
        for controller in self.get_all_controllers():
            for can_iface in controller.can_interfaces or []:
                out.extend(can_iface.forwarder_frames or [])
        return out
