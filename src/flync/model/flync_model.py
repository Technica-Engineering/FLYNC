"""
Top-level system model aggregating ECUs, topology, metadata, and communication configuration in FLYNC.
"""

from typing import Annotated, Any, Dict, List, Optional, Self, Tuple

from pydantic import Field, model_validator
from pydantic_core import PydanticCustomError

from flync.core.annotations import External, NamingStrategy, OutputStrategy
from flync.core.base_models.base_model import FLYNCBaseModel
from flync.core.utils.base_utils import check_obj_in_list
from flync.core.utils.exceptions import Category, err_major, warn
from flync.core.utils.multicast import (
    backtrack_to_source,
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
from flync.model.flync_4_diagnostics import DoIPDiscoveryDeployment, DoIPServerDeployment
from flync.model.flync_4_ecu import (
    ECU,
    ECUPort,
    MulticastGroup,
    VirtualControllerInterface,
    VLANEntry,
)
from flync.model.flync_4_instrumentation import Instrumentation
from flync.model.flync_4_instrumentation.measurement_point import bind_measurement_points
from flync.model.flync_4_metadata import SystemMetadata
from flync.model.flync_4_signal import ContainerPDU, J1939Frame, MultiplexedPDU, StandardPDU
from flync.model.flync_4_signal.forwarder import CANFrameForwarder, PDUForwarder
from flync.model.flync_4_someip import SOMEIPServiceDeployment, SOMEIPServiceInterface, SOMEIPServiceProvider
from flync.model.flync_4_topology import FLYNCTopology
from flync.model.flync_4_topology.bus_topology import (
    CANBusTopology,
    LINBusTopology,
    build_bus_topologies,
    validate_bus_topologies,
)
from flync.model.flync_4_topology.ethernet_multidrop import (
    EthernetMultidropConnection,
    validate_multidrop_connections,
    wire_multidrop_connections,
)
from flync.model.flync_4_topology.ethernet_topology import validate_no_multidrop_in_point_to_point, warn_unconnected_ports


def _compute_j1939_pgn(frame: J1939Frame) -> int:
    """Return the 18-bit J1939 Parameter Group Number (PGN) of *frame*.

    The PGN is formed from the Extended Data Page (EDP), Data Page (DP), PDU Format (PF) and PDU Specific (PS)
    fields: ``(EDP << 17) | (DP << 16) | (PF << 8) | PS``. For PDU1 (``pdu_format`` < 240) the ``pdu_specific``
    byte is a Destination Address, not part of the PGN, so it contributes 0.
    """

    ps = frame.pdu_specific if frame.pdu_format >= 240 else 0
    return (frame.extended_data_page << 17) | (frame.data_page << 16) | (frame.pdu_format << 8) | ps


def _j1939_buses(model: "FLYNCModel") -> set:
    """Return the set of CAN bus names attached through a J1939-capable ``CANInterface``.

    A CAN interface participates in J1939 when it declares a ``j1939_name`` or a source ``address``. Those buses
    must only carry ``J1939Frame`` frames (and, conversely, ``J1939Frame`` frames may only live on one of them).
    """
    buses: set = set()
    for controller in model.get_all_controllers():
        for can_iface in controller.can_interfaces or []:
            if can_iface.is_j1939():
                buses.add(can_iface.bus_ref)
    return buses


def _signal_spn_names(signals) -> List[str]:
    """Return the name of each signal instance in *signals* that carries an SPN."""
    names: list = []
    for si in signals:
        if si.signal.spn is not None:
            names.append(si.signal.name)
    return names


def _pdu_own_spn_signal_names(pdu) -> List[Tuple[str, str]]:
    """Return ``(pdu_name, signal_name)`` for the SPN-bearing signals declared directly by *pdu*."""
    name = pdu.name
    found: list = []
    if isinstance(pdu, StandardPDU):
        found.extend((name, signal_name) for signal_name in _signal_spn_names(pdu.signals))
        for sgi in pdu.signal_groups:
            found.extend((name, signal_name) for signal_name in _signal_spn_names(sgi.signal_group.signals))
    elif isinstance(pdu, MultiplexedPDU):
        selector = pdu.selector_signal.signal
        if selector.spn is not None:
            found.append((name, selector.name))
    return found


def _enqueue_pdu_children(stack: list, pdu_registry, pdu) -> None:
    """Push the child PDUs referenced by *pdu* (located in *pdu_registry*) onto *stack*."""
    if isinstance(pdu, MultiplexedPDU):
        refs = [inst.pdu_ref for inst in pdu.static_group or []]
        refs.extend(group.pdu.pdu_ref for group in pdu.mux_groups)
    elif isinstance(pdu, ContainerPDU):
        refs = [inst.pdu_ref for inst in pdu.contained_pdus]
    else:
        refs = []
    for ref in refs:
        child = pdu_registry.get(ref)
        if child is not None:
            stack.append(child)


def _iter_pdu_spn_signal_names(pdu, pdu_registry):
    """Yield ``(pdu_name, signal_name)`` for every SPN-bearing signal instance in a PDU subtree."""
    seen_pdus: set = set()
    stack = [pdu]
    while stack:
        current = stack.pop()
        if id(current) in seen_pdus:
            continue
        seen_pdus.add(id(current))
        yield from _pdu_own_spn_signal_names(current)
        _enqueue_pdu_children(stack, pdu_registry, current)


def _check_can_frame_spn(frame, pdu_registry, checked: set) -> None:
    """Raise ``err_major`` if a CAN (non-J1939) *frame* packs a PDU that carries an SPN."""
    for inst in frame.packed_pdus:
        if inst.pdu_ref not in pdu_registry or inst.pdu_ref in checked:
            continue
        checked.add(inst.pdu_ref)
        pdu = pdu_registry[inst.pdu_ref]
        offenders = list(_iter_pdu_spn_signal_names(pdu, pdu_registry))
        if offenders:
            names = ", ".join(f"{pdu}.{signal}" for pdu, signal in offenders)
            raise err_major(
                "CAN PDU '{pdu}' must not carry SPN (SPN is only allowed on J1939 PDUs): {names}.",
                pdu=inst.pdu_ref,
                names=names,
                category=Category.CONSISTENCY,
                error_number="367",
            )


def _check_j1939_bus_pgn_uniqueness(bus) -> None:
    """Raise ``err_major`` if *bus* carries two J1939 frames sharing the same PGN."""
    seen: dict = {}
    duplicate_frames: list = []
    for frame in bus.frames or []:
        if not isinstance(frame, J1939Frame):
            continue
        pgn = _compute_j1939_pgn(frame)
        if pgn in seen:
            duplicate_frames.append(frame.name)
        else:
            seen[pgn] = frame.name
    if duplicate_frames:
        raise err_major(
            "CANBus '{bus}' carries J1939 frame(s) with a duplicated PGN {pgn}: {frames}. Each J1939 frame on a bus must have a unique PGN.",
            bus=bus.name,
            pgn=pgn,
            frames=", ".join(duplicate_frames),
            category=Category.UNIQUENESS,
            error_number="346",
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
    def warn_experimental(cls, data):
        """Experimental Classes"""
        if "apps" in data and data["apps"] is not None:
            warn("Apps are currently experimental! Subject to change, please use with care.", category=Category.LIFECYCLE, error_number="188")
        return data

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
                for mcast in ecu.multicast_groups or []:
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
            paths: dict[str, list[Any]] = {}
            parents: dict[str, list[Any]] = {}
            vlans_dict: dict[str, int | None] = {}
            separ = "/VLAN"
            for key, mcast in self._iter_tx_multicasts(separ):
                self._record_tx_multicast_path(key, mcast, paths, parents, vlans_dict)
            self.check_rx_are_reached(separ, paths, parents, vlans_dict)
        except PydanticCustomError as e:
            warn(str(e), category=Category.CONSISTENCY, error_number="170")
        return self

    def _iter_tx_multicasts(self, separ):
        """Yield ``(key, mcast)`` for every ``tx`` multicast group membership across all ECUs."""
        return ((str(mcast.group) + separ + str(mcast.vlan), mcast) for ecu in self.ecus for mcast in ecu.multicast_groups if mcast.mode == "tx")

    def _record_tx_multicast_path(self, key, mcast, paths, parents, vlans_dict):
        """Compute one TX multicast group's reachability path and record it, warning if the sender cannot
        itself be reached back from within the components it floods."""
        vlans_dict[key] = mcast.vlan
        path, parent = compute_path(mcast.vlan, mcast._interface)
        if not check_obj_in_list(mcast._interface, path):
            warn(
                "Invalid Multicast Address Configuration. There are several RX that the TX Endpoint at "
                f"{mcast._interface.name} cannot reach. {serialize_components(path)}",
                category=Category.CONSISTENCY,
                error_number="169",
            )
        paths.setdefault(key, []).append(path)
        parents.setdefault(key, []).append(parent)

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
            f"({[mcast.eventgroups for mcast in provider.multicast_config]}); "
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
    def validate_j1939_pdu_consistency(self):
        """A PDU packed by a CAN (non-J1939) frame must never carry SPN (``FLYNC-GEN-MAJ-CONS-251``)."""

        if self.communication and self.communication.channels and self.communication.channels.can_buses:
            channels = self.communication.channels
            pdu_registry = channels._pdu_registry()
            checked: set = set()
            for bus in channels.can_buses:
                for frame in bus.frames:
                    if not isinstance(frame, J1939Frame):
                        _check_can_frame_spn(frame, pdu_registry, checked)
        return self

    @model_validator(mode="after")
    def validate_j1939_application_buses_only_j1939_frames(self):
        """A bus attached through a J1939-capable CAN interface may only carry ``J1939Frame`` frames, never CAN ones."""

        j1939_buses = _j1939_buses(self)
        if j1939_buses and self.communication and self.communication.channels and self.communication.channels.can_buses:
            for bus in self.communication.channels.can_buses:
                if bus.name not in j1939_buses:
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
    def validate_j1939_frames_on_j1939_application_buses(self):
        """``J1939Frame`` frames may only be deployed on a bus attached through a J1939-capable CAN interface."""

        if self.communication and self.communication.channels and self.communication.channels.can_buses:
            j1939_buses = _j1939_buses(self)
            for bus in self.communication.channels.can_buses:
                if bus.name in j1939_buses:
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
    def validate_j1939_sa_uniqueness(self):
        """Two J1939 nodes on the same CAN bus must not claim the same source address (SA).

        A controller (one CAN interface) is a single J1939 node, so an ECU exposes multiple nodes by
        declaring several J1939-capable CAN interfaces (possibly on different controllers). Each node must
        hold a distinct SA on the bus it attaches to, or address claiming would collide at runtime.
        """

        seen: dict = {}
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
    def validate_j1939_bus_nodes_are_j1939(self):
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
        offenders: list = []
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
    def validate_j1939_pgn_uniqueness(self):
        """Two ``J1939Frame`` frames on the same CAN bus must not share a Parameter Group Number (PGN).

        In J1939 the PGN (built from the frame's data page / extended data page / PDU Format / PDU Specific) identifies
        a message on the bus independently of priority and source address, so two frames declaring the same PGN on the
        same bus are indistinguishable. The CAN ``can_id`` uniqueness check skips J1939 frames on purpose, so this pass
        is the J1939 equivalent.
        """

        if self.communication and self.communication.channels and self.communication.channels.can_buses:
            for bus in self.communication.channels.can_buses:
                _check_j1939_bus_pgn_uniqueness(bus)
        return self

    @model_validator(mode="after")
    def validate_service_refs_in_apps(self):
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
            if key not in consumed_instances:
                raise err_major(
                    f"App '{app.name}' bound to controller '{controller.name}' expects to consume "
                    f"(service_id={ref.service_id:#06x}, instance_id={ref.instance_id}, major_version={ref.major_version}), "
                    "but the controller does not deploy it as a SOME/IP consumer.",
                    category=Category.CONSISTENCY,
                    error_number="245",
                )
        return self

    @model_validator(mode="after")
    def validate_state_management_groups(self) -> Self:
        """Workspace-level state management pass: group refs, derived member sets, NM PDU binding, and reachability."""
        validate_state_management(self)
        return self

    @model_validator(mode="after")
    def build_and_validate_bus_topologies(self) -> Self:
        """Derive the system-wide CAN, LIN and Ethernet multidrop topology from bus definitions and ECU interfaces, then validate it."""

        can_topos, lin_topos, can_defs, lin_defs, j1939_buses = build_bus_topologies(self)
        self.topology.can_bus_topology = can_topos
        self.topology.lin_bus_topology = lin_topos
        validate_bus_topologies(can_topos, lin_topos, can_defs, lin_defs, j1939_buses)

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

    def get_can_bus_topology(self, bus_name: str) -> Optional[CANBusTopology]:
        """Return the derived CAN bus topology for ``bus_name``, or ``None`` if unknown."""
        return next((t for t in self.topology.can_bus_topology if t.bus_name == bus_name), None)

    def get_lin_bus_topology(self, bus_name: str) -> Optional[LINBusTopology]:
        """Return the derived LIN bus topology for ``bus_name``, or ``None`` if unknown."""
        return next((t for t in self.topology.lin_bus_topology if t.bus_name == bus_name), None)

    @property
    def multidrop_connections(self) -> List[EthernetMultidropConnection]:
        """Every multidrop connection in the system topology."""

        topology = self.topology.ethernet_topology if self.topology else None
        return [c for c in topology.connections if isinstance(c, EthernetMultidropConnection)] if topology else []

    def get_multidrop_connection(self, connection_id: str) -> Optional[EthernetMultidropConnection]:
        """Return the multidrop connection with ``connection_id``, or ``None`` if unknown."""

        return next((c for c in self.multidrop_connections if c.id == connection_id), None)

    def check_rx_are_reached(self, separ, paths, parents, vlans_dict):
        rx_targets = {}
        for ecu in self.ecus:
            for mcast in ecu.multicast_groups:
                key = str(mcast.group) + separ + str(mcast.vlan)
                if mcast.mode != "rx":
                    continue
                if key not in paths:
                    warn(
                        f"Invalid Multicast Address Configuration. There are no TX endpoints for this address {key} ",
                        category=Category.CONSISTENCY,
                        error_number="173",
                    )
                elif not any(check_obj_in_list(mcast._interface, path) for path in paths[key]):
                    warn(
                        f"Invalid Multicast Address Configuration. The RX interface for address {key} "
                        f"- {mcast._interface.name} cannot be reached by the TX ports.",
                        category=Category.CONSISTENCY,
                        error_number="174",
                    )
                else:
                    rx_targets.setdefault(key, []).append(mcast._interface)

        self.load_switch_multicast(vlans_dict, paths, parents, rx_targets)

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
                self._append_mcast_to_vlan_entry(v_entry, comp, mcast_addr)

    def _append_mcast_to_vlan_entry(self, v_entry, comp, mcast_addr):
        """Add ``comp`` to every existing multicast group of ``v_entry`` whose address matches
        ``mcast_addr``, or create a new one if none matches."""
        found_mcast = False
        for addr in v_entry.multicast:
            if str(addr.address) != mcast_addr:
                continue
            found_mcast = True
            if comp.name not in addr.ports:
                addr.ports.append(comp.name)
        if not found_mcast:
            v_entry.multicast.append(MulticastGroup(address=mcast_addr, ports=[comp.name]))

    def load_switch_multicast(self, vlans_dict, paths, parents, rx_targets):
        for key, targets in rx_targets.items():
            used_ports = self._collect_used_switch_ports(targets, paths.get(key, []), parents.get(key, []))
            if not used_ports:
                continue
            ip = key.split("/")[0]
            for comp in used_ports.values():
                self.append_mcast(vlans_dict[key], comp, ip)

    def _collect_used_switch_ports(self, targets, paths, parents):
        """Return, keyed by ``id()``, every switch port that sits on some sender's real path to one of
        ``targets`` -- ``paths``/``parents`` are the per-sender results from :func:`compute_path` for one
        multicast key."""
        used_ports = {}
        for path, parent in zip(paths, parents):
            for target in targets:
                if not check_obj_in_list(target, path):
                    continue
                for comp in backtrack_to_source(target, parent):
                    if comp.type == "switch_port":
                        used_ports[id(comp)] = comp
        return used_ports

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

    def get_all_ecu_ports(self) -> List[ECUPort]:
        """Return a list of all ECU ports"""
        ecu_ports = []
        for ecu in self.ecus:
            ecu_ports.extend(ecu.get_all_ports())
        return ecu_ports

    def get_all_ecu_ports_by_name(self) -> Dict[str, ECUPort]:
        return {e.name: e for e in self.get_all_ecu_ports()}

    def get_interface_by_name(self, name):
        return next(
            (interface for interface in self.get_all_interfaces() if interface.name == name),
            None,
        )

    def get_all_interfaces(self):
        """Return the config of every Ethernet interface, compute node interfaces included."""
        return [eth_iface.interface_config for controller in self.get_all_controllers() for eth_iface in controller.iter_subtree_interfaces()]

    def iter_app_binding_owners(self):
        """
        Yield everything that can declare ``app_bindings`` — every controller and every compute node beneath it.

        A compute node binds its own applications to its own sockets, so it is a binding owner in its
        own right rather than being folded into its host controller.
        """
        for controller in self.get_all_controllers():
            yield controller
            yield from controller.iter_subtree_compute_nodes()

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
    def resolve_tcp_profiles(self) -> Self:
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
    def resolve_someip_deployments(self) -> Self:
        if self.communication and self.communication.someip_config:
            someip = self.communication.someip_config
            services_by_key = {(s.id, s.major_version): s for s in someip.services}
            sd_timings_by_id = {t.profile_id: t for t in someip.sd_config.sd_timings} if someip.sd_config else {}
            self._bind_someip_sockets(services_by_key, sd_timings_by_id)
        return self

    def _bind_diagnostics_sockets(self, timings_by_id, servers_by_name):
        for sock in self._iter_all_sockets():
            for dep_union in sock.deployments or []:
                dep = dep_union.root
                if isinstance(dep, DoIPServerDeployment):
                    dep.bind(servers_by_name, timings_by_id)
                elif isinstance(dep, DoIPDiscoveryDeployment):
                    dep.bind(timings_by_id)

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

        seen: dict = {}
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

        deployments = [
            (deployment.root, socket, ecu)
            for ecu in self.ecus
            for ctrl in ecu.controllers
            for iface in (ctrl.ethernet_interfaces or [])
            for sock_con in (iface.sockets or [])
            for socket in (sock_con.sockets or [])
            for deployment in (socket.deployments or [])
            if deployment.root.deployment_type.startswith("someip_") and socket.endpoint_type == "multicast" and socket.protocol == "udp"
        ]

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

    def get_someip_services_by_identity(self) -> Dict[Tuple[int, int], SOMEIPServiceInterface]:
        """
        Return the system-wide SOME/IP service interfaces keyed by ``(service_id, major_version)``.
        """
        return {(svc.id, svc.major_version): svc for svc in self.get_all_someip_services()}

    def _iter_bound_app_consumer_refs(self):
        """
        Yield ``(controller, consumed_instances, app, ref)`` for every consumer reference of every app bound to a
        controller, where ``consumed_instances`` is that controller's set of SOME/IP consumer service triples.
        """

        for owner in self.iter_app_binding_owners():
            if not owner.app_bindings:
                continue
            consumed_instances = owner.get_consumed_service_instances()
            for app in owner.app_bindings.apps:
                for ref in app.service_consumer_refs or []:
                    yield owner, consumed_instances, app, ref

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
