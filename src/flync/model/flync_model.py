"""
Top-level system model aggregating ECUs, topology, metadata, and communication configuration in FLYNC.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, List, Optional, Self, Tuple

from pydantic import Field, model_validator
from pydantic_core import PydanticCustomError

from flync.core.annotations import External, NamingStrategy, OutputStrategy
from flync.core.base_models.base_model import FLYNCBaseModel
from flync.core.utils.exceptions import Category, err_major, warn
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
from flync.model._model_parts import AccessorMixin, BindingMixin, MulticastMixin
from flync.model._model_parts._app_refs import (
    validate_app_ipc_refs,
    validate_app_signal_refs,
    warn_app_signal_refs_without_interface,
)
from flync.model._model_parts._j1939 import (
    check_can_frame_spn,
    check_j1939_bus_pgn_uniqueness,
    j1939_buses,
)
from flync.model.flync_4_app import App
from flync.model.flync_4_communication import FLYNCCommunicationConfig
from flync.model.flync_4_diagnostics import DoIPServerDeployment
from flync.model.flync_4_ecu import (
    ECU,
    VirtualControllerInterface,
    VLANEntry,
)
from flync.model.flync_4_instrumentation import Instrumentation
from flync.model.flync_4_instrumentation.measurement_point import bind_measurement_points
from flync.model.flync_4_metadata import SystemMetadata
from flync.model.flync_4_signal import J1939Frame
from flync.model.flync_4_someip import SOMEIPServiceProvider
from flync.model.flync_4_topology import FLYNCTopology
from flync.model.flync_4_topology.bus_topology import (
    build_bus_topologies,
    validate_bus_topologies,
)
from flync.model.flync_4_topology.ethernet_multidrop import (
    EthernetMultidropConnection,
    validate_multidrop_connections,
    wire_multidrop_connections,
)
from flync.model.flync_4_topology.ethernet_topology import validate_no_multidrop_in_point_to_point, warn_unconnected_ports

if TYPE_CHECKING:
    from flync.core.utils.base_utils import NetworkComponent
    from flync.core.utils.multicast.multicast_paths import ParentMap


class FLYNCModel(FLYNCBaseModel, AccessorMixin, BindingMixin, MulticastMixin):
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

    instrumentation : :class:`~flync.model.flync_4_instrumentation.Instrumentation`, optional
        Optional measurement and logging overlay - the measurement points recording this system.
        Absent for a system that is not being measured, which is the ordinary case for a
        production configuration.
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
    ] = Field(default=None)
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
    instrumentation: Annotated[
        Optional[Instrumentation],
        External(
            output_structure=OutputStrategy.FOLDER,
            naming_strategy=NamingStrategy.FIELD_NAME,
        ),
    ] = Field(default=None, description="Optional measurement and logging overlay recording this system.")

    _EXCLUDED_NAME_CHECK_CLASSES: Tuple[type, ...] = (
        VirtualControllerInterface,
        VLANEntry,
    )

    @model_validator(mode="before")
    @classmethod
    def warn_experimental(cls, data: object) -> object:
        """Experimental Classes"""
        if isinstance(data, dict) and data.get("apps") is not None:
            warn("Apps are currently experimental! Subject to change, please use with care.", category=Category.LIFECYCLE, error_number="188")
        return data

    @model_validator(mode="before")
    @classmethod
    def default_absent_topology(cls, data: object) -> object:
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
    def skip_broken_ecus(cls, data: object) -> object:
        """
        Remove None ECUs from the list before validation.

        When an ECU file fails to load the workspace inserts None into the ecus list.
        JErrors are already reported at the ECU level, so the None entries are silently dropped here to prevent a cascade of
        FLYNCModel-level errors for the same root cause.
        """

        if isinstance(data, dict):
            ecus = data.get("ecus")
            if isinstance(ecus, list) and any(e is None for e in ecus):
                data["ecus"] = [e for e in ecus if e is not None]
        return data

    def model_post_init(self, context: object) -> None:
        """
        Perform post-initialization processing after the model is created.

        Following steps are performed:

        1. Populate the solicited-node RX multicast group memberships for each IPv6 address configured in any ECU.

        2. Populate the solicited-node TX multicast group memberships for each ECU based on the RX entries for the same multicast group and VLAN.
        """

        self._populate_ipv6_solicited_node_multicasts_rx()
        self._populate_ipv6_solicited_node_multicasts_tx()

    @model_validator(mode="after")
    def validate_unique_ecu_names(self) -> Self:
        validate_list_items_unique([ecu.name for ecu in self.ecus], "ECU names")
        return self

    @model_validator(mode="after")
    def validate_unique_port_names(self) -> Self:
        all_ports = [port.name for ecu in self.ecus for port in ecu.get_all_ports()]
        validate_list_items_unique(all_ports, "ECU port names")
        return self

    @model_validator(mode="after")
    def validate_unique_app_names(self) -> Self:
        validate_list_items_unique([app.name for app in self.apps or []], "App names")
        return self

    @model_validator(mode="after")
    def resolve_external_connections(self) -> Self:
        if self.topology.ethernet_topology is None:
            return self
        ports_by_name = self.get_all_ecu_ports_by_name()
        for conn in self.topology.ethernet_topology.connections:
            try:
                conn.bind(ports_by_name)
            except PydanticCustomError as e:
                # A multidrop connection reports a missing port as a hard error of its own, not as this warning.
                if isinstance(conn, EthernetMultidropConnection):
                    raise
                warn(str(e), category=Category.REFERENCE, error_number="164")

        # After binding, not inside it: the except above would turn this into warning 164 and lose the error's own id.
        validate_no_multidrop_in_point_to_point(self.topology.ethernet_topology.connections)
        return self

    @model_validator(mode="after")
    def wire_multidrop_ports(self) -> Self:
        """
        Join the ports sharing a multidrop segment, so the passes below see a segment as the connection it is.

        Sits here rather than with the rest of the topology derivation because everything that walks the graph runs before that:
        unconnected-port reporting next, multicast path analysis further down.
        """

        wire_multidrop_connections(self.multidrop_connections)
        return self

    @model_validator(mode="after")
    def validate_no_unconnected_ecu_ports(self) -> Self:
        """Must not require an ethernet topology: a workspace that wires only CAN/LIN has no ``topology/`` file, but its ports
        still deserve an unconnected report."""

        claimed = {id(node.ecu_port) for conn in self.multidrop_connections for node in conn.nodes if node.ecu_port is not None}
        warn_unconnected_ports(self.get_all_ecu_ports(), claimed)
        return self

    @model_validator(mode="after")
    def require_ethernet_topology_when_used(self) -> Self:
        """
        The ethernet topology (``topology/ethernet_topology.flync.yaml``) is optional, but system-wide features that
        rely on inter-ECU Ethernet connectivity (cross-ECU multicast, SOME/IP multicast) cannot be validated without
        it. Raise instead of silently skipping those checks.
        """

        if self.topology.ethernet_topology is not None:
            return self
        reasons = self._ethernet_topology_dependent_features()
        if reasons:
            raise err_major(
                "The ethernet topology file (topology/ethernet_topology.flync.yaml) is required because system-wide "
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

    @model_validator(mode="after")
    def validate_unique_ips(self) -> Self:
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
    def check_tx_rx_multicast_group(self) -> Self:
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
    def validate_multicast_paths(self) -> Self:
        try:
            paths: dict[str, list[list[NetworkComponent]]] = {}
            parents: dict[str, list[ParentMap]] = {}
            vlans_dict: dict[str, int | None] = {}
            separ = "/VLAN"
            for key, mcast in self._iter_tx_multicasts(separ):
                self._record_tx_multicast_path(key, mcast, paths, parents, vlans_dict)
            self.check_rx_are_reached(separ, paths, parents, vlans_dict)
        except PydanticCustomError as e:
            warn(str(e), category=Category.CONSISTENCY, error_number="170")
        return self

    @model_validator(mode="after")
    def validate_no_someip_multicast_on_tcp(self) -> Self:
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
            f"({[mcast.eventgroups for mcast in provider.multicast_config or []]}); "
            f"SOME/IP eventgroup multicast requires a UDP socket",
            category=Category.CONSISTENCY,
            error_number="218",
        )

    @model_validator(mode="after")
    def validate_unique_macs(self) -> Self:
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
    def validate_bus_interface_frame_refs(self) -> Self:
        """Workspace-level bus interface pass: every CAN / LIN interface names a declared bus of its own kind and resolves its frame refs."""

        validate_interface_frame_refs(self)
        return self

    @model_validator(mode="after")
    def validate_forwarders(self) -> Self:
        """Workspace-level forwarder/deployment pass: ref resolution, same-controller locality + direction safety, and cycle detection."""

        validate_pdu_deployment_refs(
            self
        )  # Verifies every pdu_sender / pdu_receiver references a declared PDU of any kind, forwarder-involved or standalone.
        validate_forwarder_refs(self)  # Verifies all PDU and frame references resolve and the forwarded payload fits the egress CAN frame.
        validate_forwarder_locality(self)  # Verifies each egress targets a same-controller carrier with a compatible pdu_sender or sender_frames.
        detect_forwarder_cycles(self)  # Verifies the forwarder graph is acyclic.
        return self

    @model_validator(mode="after")
    def validate_j1939_pdu_consistency(self) -> Self:
        """A PDU packed by a CAN (non-J1939) frame must never carry SPN (``FLYNC-GEN-MAJ-CONS-251``)."""

        if self.communication and self.communication.channels and self.communication.channels.can_buses:
            channels = self.communication.channels
            pdu_registry = channels._pdu_registry()
            checked: set[str] = set()
            for bus in channels.can_buses or []:
                for frame in bus.frames:
                    if not isinstance(frame, J1939Frame):
                        check_can_frame_spn(frame, pdu_registry, checked)
        return self

    @model_validator(mode="after")
    def validate_j1939_application_buses_only_j1939_frames(self) -> Self:
        """A bus attached through a J1939-capable CAN interface may only carry ``J1939Frame`` frames, never CAN ones."""

        j1939_bus_set = j1939_buses(self)
        if j1939_bus_set and self.communication and self.communication.channels and self.communication.channels.can_buses:
            for bus in self.communication.channels.can_buses:
                if bus.name not in j1939_bus_set:
                    continue
                offenders = [frame.name for frame in bus.frames if not isinstance(frame, J1939Frame)]
                if offenders:
                    raise err_major(
                        "CANBus '{bus}' is attached through a J1939-capable CAN interface but carries non-J1939 frame(s): {frames}. "
                        "J1939 buses may only carry J1939 frames.",
                        bus=bus.name,
                        frames=", ".join(offenders),
                        category=Category.CONSISTENCY,
                        error_number="369",
                    )
        return self

    @model_validator(mode="after")
    def validate_j1939_frames_on_j1939_application_buses(self) -> Self:
        """``J1939Frame`` frames may only be deployed on a bus attached through a J1939-capable CAN interface."""

        if self.communication and self.communication.channels and self.communication.channels.can_buses:
            j1939_bus_set = j1939_buses(self)
            for bus in self.communication.channels.can_buses:
                if bus.name in j1939_bus_set:
                    continue
                offenders = [frame.name for frame in bus.frames if isinstance(frame, J1939Frame)]
                if offenders:
                    raise err_major(
                        "CANBus '{bus}' is not attached through any J1939-capable CAN interface, but it carries J1939 frame(s): {frames}. "
                        "J1939 frames are only allowed on J1939 buses.",
                        bus=bus.name,
                        frames=", ".join(offenders),
                        category=Category.CONSISTENCY,
                        error_number="368",
                    )
        return self

    @model_validator(mode="after")
    def validate_j1939_sa_uniqueness(self) -> Self:
        """Two J1939 nodes on the same CAN bus must not claim the same source address (SA).

        A controller (one CAN interface) is a single J1939 node, so an ECU exposes multiple nodes by
        declaring several J1939-capable CAN interfaces (possibly on different controllers). Each node must
        hold a distinct SA on the bus it attaches to, or address claiming would collide at runtime.
        """

        seen: dict[tuple[str, int], str] = {}
        for controller in self.get_all_controllers():
            for iface in controller.can_interfaces or []:
                if not iface.is_j1939() or iface.source_address is None:
                    continue
                key = (iface.bus_ref, iface.source_address)
                if key in seen:
                    raise err_major(
                        "CAN bus '{bus}' has more than one J1939 node claiming source address (SA) {sa}: "
                        "{first} and {second}. Each J1939 node on a bus must hold a distinct SA.",
                        bus=iface.bus_ref,
                        sa=iface.source_address,
                        first=seen[key],
                        second=iface.name,
                        category=Category.UNIQUENESS,
                        error_number="373",
                    )
                seen[key] = iface.name
        return self

    @model_validator(mode="after")
    def validate_j1939_bus_nodes_are_j1939(self) -> Self:
        """Every node on a J1939 bus (one carrying ``J1939Frame`` frames) must declare ``j1939_name``.

        A bus is identified as a J1939 bus by carrying ``J1939Frame`` frames. Any CAN interface attached to
        it -- whether or not it declares sender/receiver frames -- must then provide a ``j1939_name``: the
        NAME is what identifies a node in the J1939 address-claiming scheme. ``source_address`` remains
        optional and is claimed at runtime.
        """

        if not self.communication or not self.communication.channels or not self.communication.channels.can_buses:
            return self
        j1939_bus_names = {
            bus.name for bus in self.communication.channels.can_buses if any(isinstance(frame, J1939Frame) for frame in bus.frames or [])
        }
        if not j1939_bus_names:
            return self
        offenders: list[str] = []
        for controller in self.get_all_controllers():
            for iface in controller.can_interfaces or []:
                if iface.bus_ref not in j1939_bus_names:
                    continue
                if iface.j1939_name is None:
                    offenders.append(iface.name)
        if offenders:
            raise err_major(
                "CAN bus(es) '{buses}' carry J1939 frame(s), but node(s) {nodes} attached to them are missing "
                "j1939_name. Every node on a J1939 bus must declare a NAME.",
                buses=", ".join(sorted(j1939_bus_names)),
                nodes=", ".join(sorted(set(offenders))),
                category=Category.CONSISTENCY,
                error_number="361",
            )
        return self

    @model_validator(mode="after")
    def validate_j1939_pgn_uniqueness(self) -> Self:
        """Two ``J1939Frame`` frames on the same CAN bus must not share a Parameter Group Number (PGN).

        In J1939 the PGN (built from the frame's data page / extended data page / PDU Format / PDU Specific) identifies
        a message on the bus independently of priority and source address, so two frames declaring the same PGN on the
        same bus are indistinguishable. The CAN ``can_id`` uniqueness check skips J1939 frames on purpose, so this pass
        is the J1939 equivalent.
        """

        if self.communication and self.communication.channels and self.communication.channels.can_buses:
            for bus in self.communication.channels.can_buses:
                check_j1939_bus_pgn_uniqueness(bus)
        return self

    @model_validator(mode="after")
    def validate_service_refs_in_apps(self) -> Self:
        """Validate that applications are referencing existing services."""
        known_services = self.get_someip_services_by_identity()
        for app in self.apps or []:
            for ref in (app.service_consumer_refs or []) + (app.service_provider_refs or []):
                if (ref.service_id, ref.major_version) not in known_services:
                    raise err_major(
                        f"App {app.name} references service (service_id={ref.service_id:#06x}, major_version={ref.major_version}) "
                        "that is not defined in the system's SOME/IP configuration.",
                        category=Category.REFERENCE,
                        error_number="186",
                    )
        return self

    @model_validator(mode="after")
    def validate_app_refs_in_controller_bindings(self) -> Self:
        """Validate that app_bindings of ecu controllers and their compute nodes are referencing existing apps."""
        apps_by_name = {app.name: app for app in self.apps or []}
        for owner in self.iter_app_binding_owners():
            if owner.app_bindings:
                owner.app_bindings.resolve_apps(apps_by_name, owner.name)
        return self

    @model_validator(mode="after")
    def validate_app_bindings_consume_deployed_services(self) -> Self:
        """Every app bound to a controller must have its service_consumer_refs matched by a someip_consumer
        deployment on that same controller."""
        services_by_identity = self.get_someip_services_by_identity()
        for controller, consumed_instances, app, ref in self._iter_bound_app_consumer_refs():
            svc = services_by_identity.get((ref.service_id, ref.major_version))
            key = (ref.service_id, ref.major_version, ref.instance_id) if svc else None
            if key is None or key not in consumed_instances:
                raise err_major(
                    f"App '{app.name}' bound to controller '{controller.name}' expects to consume "
                    f"(service_id={ref.service_id:#06x}, instance_id={ref.instance_id}, major_version={ref.major_version}), "
                    "but the controller does not deploy it as a SOME/IP consumer.",
                    category=Category.CONSISTENCY,
                    error_number="245",
                )
        return self

    @model_validator(mode="after")
    def validate_app_signal_refs_resolve(self) -> Self:
        """Validate that CAN / J1939 frame and PDU references of apps resolve on the referenced CAN bus."""
        validate_app_signal_refs(self)
        return self

    @model_validator(mode="after")
    def validate_app_signal_refs_match_interfaces(self) -> Self:
        """Warn when a controller binding an app has no CAN interface declaring the app's frames."""
        warn_app_signal_refs_without_interface(self)
        return self

    @model_validator(mode="after")
    def validate_app_ipc_channel_refs(self) -> Self:
        """Validate that the IPC references of apps resolve to IPC channels of the ECU hosting them."""
        validate_app_ipc_refs(self)
        return self

    @model_validator(mode="after")
    def validate_state_management_groups(self) -> Self:
        """Workspace-level state management pass: group refs, derived member sets, NM PDU binding, and reachability."""
        validate_state_management(self)
        return self

    @model_validator(mode="after")
    def build_and_validate_bus_topologies(self) -> Self:
        """Derive the system-wide CAN, LIN and Ethernet multidrop topology from bus definitions and ECU interfaces, then validate it."""

        can_topos, lin_topos, can_defs, lin_defs, j1939_buses_set = build_bus_topologies(self)
        self.topology.can_bus_topology = can_topos
        self.topology.lin_bus_topology = lin_topos
        validate_bus_topologies(can_topos, lin_topos, can_defs, lin_defs, j1939_buses_set)

        validate_multidrop_connections(self.multidrop_connections)
        return self

    @model_validator(mode="after")
    def bind_instrumentation(self) -> Self:
        """Workspace-level measurement pass: resolve measurement points against the loaded model."""
        bind_measurement_points(
            self.instrumentation.measurement_points if self.instrumentation else None,
            self,
        )
        return self

    @model_validator(mode="after")
    def resolve_tcp_profiles(self) -> Self:
        if self.communication:
            tcp_by_id = {t.tcp_profile_id: t for t in (self.communication.tcp_profiles or [])}
            self._bind_tcp_profiles(tcp_by_id)
        return self

    @model_validator(mode="after")
    def resolve_someip_deployments(self) -> Self:
        if self.communication and self.communication.someip_config:
            someip = self.communication.someip_config
            services_by_key = {(s.id, s.major_version): s for s in someip.services}
            sd_timings_by_id = {t.profile_id: t for t in someip.sd_config.sd_timings} if someip.sd_config else {}
            self._bind_someip_sockets(services_by_key, sd_timings_by_id)
        return self

    @model_validator(mode="after")
    def resolve_diagnostics_deployments(self) -> Self:
        if self.communication and self.communication.diagnostics_config:
            diagnostics = self.communication.diagnostics_config
            self._bind_diagnostics_sockets(diagnostics.doip_timings_by_id(), diagnostics.uds_servers_by_name())
        return self

    @model_validator(mode="after")
    def validate_unique_doip_logical_addresses(self) -> Self:
        """
        Raise ``err_major`` if two ``DoIPServerDeployment``\\ s anywhere in the system declare the same
        ``logical_address`` - DoIP logical addresses must be unique across the vehicle, not just per socket.
        """

        seen: dict[int, str] = {}
        for socket in self._iter_all_sockets():
            for dep_union in socket.deployments or []:
                dep = dep_union.root
                if not isinstance(dep, DoIPServerDeployment):
                    continue
                logical_address = dep.logical_address
                if logical_address in seen and seen[logical_address] != dep.name:
                    raise err_major(
                        f"Duplicate DoIP logical_address {logical_address:#06x} used by '{seen[logical_address]}' and '{dep.name}'",
                        category=Category.UNIQUENESS,
                        error_number="276",
                    )
                seen[logical_address] = dep.name
        return self

    @model_validator(mode="after")
    def validate_multicast_someip(self) -> Self:
        """
        Validate multicast configuration for SOME/IP consumers and providers

        For provider: check if the parent socket has a multicast_tx entry

        Defined after :meth:`resolve_someip_deployments`: the message identifies the offending service through
        ``_service_ref``, which only exists once the deployments have been bound.
        """

        deployments = list(self._iter_someip_multicast_udp_deployments())

        providers = [(root, socket, ecu) for root, socket, ecu in deployments if isinstance(root, SOMEIPServiceProvider)]

        # Providers need to have multicast_tx in socket
        for provider, socket, _ecu in providers:
            svc = provider._service_ref
            # An unbound deployment (no someip_config declared) still names its service by id / major_version.
            svc_label = f"{svc.name}, {svc.id:#06x}, {svc.major_version}" if svc else f"{provider.service:#06x}, {provider.major_version}"
            for mcast_config in provider.multicast_config or []:
                if mcast_config.ip_address not in (socket.multicast_tx or []):
                    raise err_major(
                        f"Deployed provided service ({svc_label}) "
                        f"has multicast configuration for eventgroups ({mcast_config.eventgroups}/{mcast_config.ip_address}), "
                        f"but socket ({socket.name}) does not indicate by multicast_tx entry ({socket.multicast_tx})",
                        category=Category.CONSISTENCY,
                        error_number="171",
                    )

        return self
