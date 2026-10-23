"""
Multicast path analysis and wiring for :class:`~flync.model.flync_model.FLYNCModel`.

This carries the solicited-node multicast population (done during ``model_post_init``) plus the
sender-to-receiver reachability analysis and the switch-port multicast provisioning that the
topology passes rely on. Beware of reordering: these run only after ``model_post_init`` has
populated the solicited-node groups, and everything that walks the graph depends on that.
"""

from __future__ import annotations

from collections.abc import Iterator
from ipaddress import IPv4Address, IPv6Address, ip_address
from typing import TYPE_CHECKING, List

from pydantic_extra_types.mac_address import MacAddress

from flync.core.utils.base_utils import check_obj_in_list
from flync.core.utils.exceptions import Category, warn
from flync.core.utils.multicast import (
    backtrack_to_source,
    collect_ipv6_solicited_node_rx,
    collect_ipv6_solicited_node_tx,
    compute_path,
    serialize_components,
)
from flync.model._model_parts._protocol import FLYNCModelProtocol
from flync.model.flync_4_ecu import (
    EthernetInterface,
    MulticastGroup,
    MulticastGroupMembership,
    SwitchPort,
    VLANEntry,
)

if TYPE_CHECKING:
    from flync.core.utils.base_utils import NetworkComponent
    from flync.core.utils.multicast.multicast_paths import ParentMap


def _parse_group_address(text: str) -> IPv4Address | IPv6Address | MacAddress:
    """Turn the address part of a multicast key (``str(group)``) back into the typed address it was built from."""
    try:
        return ip_address(text)
    except ValueError:
        return MacAddress(text)


class MulticastMixin:
    """Solicited-node population, multicast reachability and switch multicast wiring."""

    def _populate_ipv6_solicited_node_multicasts_rx(self: FLYNCModelProtocol) -> None:
        """
        Populate the solicited-node multicast group memberships for each IPv6 address configured in any ECU.
        """

        for ecu in self.ecus:
            update_ecu_multicast = collect_ipv6_solicited_node_rx(ecu)
            if ecu.name in update_ecu_multicast:
                ecu.multicast_groups.append(update_ecu_multicast[ecu.name])

    def _populate_ipv6_solicited_node_multicasts_tx(self: FLYNCModelProtocol) -> None:
        """
        Populate the solicited-node multicast group memberships for each IPv6 address configured in any ECU as TX if there is a RX for the
        same multicast group and VLAN.
        """

        multicasts = [mc for ecu in self.ecus for mc in ecu.multicast_groups if mc.solicited_node_multicast]

        for ecu in self.ecus:
            update_ecu_multicast = collect_ipv6_solicited_node_tx(ecu, multicasts)
            if ecu.name in update_ecu_multicast:
                ecu.multicast_groups.append(update_ecu_multicast[ecu.name])

    def _ethernet_topology_dependent_features(self: FLYNCModelProtocol) -> List[str]:
        """Return human-readable reasons the ethernet topology is required, or an empty list if it is not."""

        if len([ecu for ecu in self.ecus if ecu.ports]) < 2:
            # Single (or zero) Ethernet ECUs: multicast fully resolves from internal topology alone.
            return []

        reasons = []
        if any(mcast for ecu in self.ecus for mcast in (ecu.multicast_groups or []) if not mcast.solicited_node_multicast):
            reasons.append("multicast group memberships are configured")
        if next(self._iter_someip_multicast_udp_deployments(), None) is not None:
            reasons.append("SOME/IP multicast deployments are configured")
        return reasons

    def _iter_tx_multicasts(self: FLYNCModelProtocol, separ: str) -> Iterator[tuple[str, MulticastGroupMembership]]:
        """Yield ``(key, mcast)`` for every ``tx`` multicast group membership across all ECUs."""
        return ((str(mcast.group) + separ + str(mcast.vlan), mcast) for ecu in self.ecus for mcast in ecu.multicast_groups if mcast.mode == "tx")

    @staticmethod
    def _record_tx_multicast_path(
        key: str,
        mcast: MulticastGroupMembership,
        paths: dict[str, list[list[NetworkComponent]]],
        parents: dict[str, list[ParentMap]],
        vlans_dict: dict[str, int | None],
    ) -> None:
        """Compute one TX multicast group's reachability path and record it, warning if the sender cannot
        itself be reached back from within the components it floods."""
        vlans_dict[key] = mcast.vlan
        interface = mcast._interface
        path, parent = compute_path(mcast.vlan, interface)
        if not check_obj_in_list(interface, path):
            interface_name = interface.name if interface is not None else "<unresolved interface>"
            warn(
                "Invalid Multicast Address Configuration. There are several RX that the TX Endpoint at "
                f"{interface_name} cannot reach. {serialize_components(path)}",
                category=Category.CONSISTENCY,
                error_number="169",
            )
        paths.setdefault(key, []).append(path)
        parents.setdefault(key, []).append(parent)

    def check_rx_are_reached(
        self: FLYNCModelProtocol,
        separ: str,
        paths: dict[str, list[list[NetworkComponent]]],
        parents: dict[str, list[ParentMap]],
        vlans_dict: dict[str, int | None],
    ) -> None:
        """Check every RX membership is reachable from a TX endpoint, then wire the switch multicast tables accordingly."""
        rx_targets: dict[str, list[EthernetInterface]] = {}
        for ecu in self.ecus:
            for mcast in ecu.multicast_groups:
                self._register_rx_target(rx_targets, mcast, separ, paths)
        self.load_switch_multicast(vlans_dict, paths, parents, rx_targets)

    @staticmethod
    def _register_rx_target(
        rx_targets: dict[str, list[EthernetInterface]],
        mcast: MulticastGroupMembership,
        separ: str,
        paths: dict[str, list[list[NetworkComponent]]],
    ) -> None:
        """Register a multicast RX interface as a reachable target, warning when it cannot be reached."""
        if mcast.mode != "rx":
            return
        key = str(mcast.group) + separ + str(mcast.vlan)
        if key not in paths:
            warn(
                f"Invalid Multicast Address Configuration. There are no TX endpoints for this address {key} ",
                category=Category.CONSISTENCY,
                error_number="173",
            )
            return
        if not any(check_obj_in_list(mcast._interface, path) for path in paths[key]):
            interface_name = mcast._interface.name if mcast._interface is not None else "<unresolved interface>"
            warn(
                f"Invalid Multicast Address Configuration. The RX interface for address {key} "
                f"- {interface_name} cannot be reached by the TX ports.",
                category=Category.CONSISTENCY,
                error_number="174",
            )
            return
        interface = mcast._interface
        if interface is not None:
            rx_targets.setdefault(key, []).append(interface)

    @staticmethod
    def append_mcast(vlan: int, comp: SwitchPort, mcast_addr: str) -> None:
        """Add switch port ``comp`` to the multicast group ``mcast_addr`` of the VLAN entry ``vlan`` on its switch."""
        for v_entry in comp.get_switch().vlans:
            if v_entry.id == vlan:
                MulticastMixin._append_mcast_to_vlan_entry(v_entry, comp, mcast_addr)

    @staticmethod
    def _append_mcast_to_vlan_entry(
        v_entry: VLANEntry,
        comp: SwitchPort,
        mcast_addr: str,
    ) -> None:
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
            v_entry.multicast.append(MulticastGroup(address=_parse_group_address(mcast_addr), ports=[comp.name]))

    def load_switch_multicast(
        self: FLYNCModelProtocol,
        vlans_dict: dict[str, int | None],
        paths: dict[str, list[list[NetworkComponent]]],
        parents: dict[str, list[ParentMap]],
        rx_targets: dict[str, list[EthernetInterface]],
    ) -> None:
        """Provision the switch ports carrying each multicast key's traffic to its RX targets with that group."""
        for key, targets in rx_targets.items():
            used_ports = self._collect_used_switch_ports(targets, paths.get(key, []), parents.get(key, []))
            if not used_ports:
                continue
            ip = key.split("/")[0]
            vlan = vlans_dict[key]
            for comp in used_ports.values():
                if vlan is not None:
                    self.append_mcast(vlan, comp, ip)

    @staticmethod
    def _collect_used_switch_ports(
        targets: list[EthernetInterface],
        paths: list[list[NetworkComponent]],
        parents: list[ParentMap],
    ) -> dict[int, SwitchPort]:
        """Return, keyed by ``id()``, every switch port that sits on some sender's real path to one of
        ``targets`` -- ``paths``/``parents`` are the per-sender results from :func:`compute_path` for one
        multicast key."""
        used_ports: dict[int, SwitchPort] = {}
        for path, parent in zip(paths, parents):
            for target in targets:
                if not check_obj_in_list(target, path):
                    continue
                for comp in backtrack_to_source(target, parent):
                    if comp.type == "switch_port":
                        used_ports[id(comp)] = comp
        return used_ports
