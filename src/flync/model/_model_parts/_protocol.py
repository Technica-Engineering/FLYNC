"""
Structural type of the composed :class:`~flync.model.flync_model.FLYNCModel`.

The domain mixins in this package are plain classes (not Pydantic models) that are always composed
into ``FLYNCModel`` at import time. Because Pydantic v2 would treat annotated attributes on a
non-model base class as fields, the mixins cannot declare ``self.ecus`` etc. directly; instead each
mixin method types its ``self`` parameter as this protocol so mypy can resolve the shared fields and
sibling methods without polluting the model schema.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, Dict, List, Optional, Protocol

from flync.model._model_parts._types import SocketDeployment
from flync.model.flync_4_app import App, ServiceConsumerReference
from flync.model.flync_4_communication import FLYNCCommunicationConfig
from flync.model.flync_4_ecu import (
    ECU,
    ComputeNode,
    Controller,
    ECUPort,
    EthernetInterface,
    EthernetInterfaceConfig,
    MulticastGroupMembership,
    SocketTCP,
    SocketUDP,
    SwitchPort,
    VLANEntry,
)
from flync.model.flync_4_signal.forwarder import CANFrameForwarder, PDUForwarder
from flync.model.flync_4_someip import SOMEIPServiceInterface
from flync.model.flync_4_topology import FLYNCTopology
from flync.model.flync_4_topology.bus_topology import CANBusTopology, LINBusTopology
from flync.model.flync_4_topology.ethernet_multidrop import EthernetMultidropConnection

if TYPE_CHECKING:
    from flync.core.utils.base_utils import NetworkComponent
    from flync.core.utils.multicast.multicast_paths import ParentMap


class FLYNCModelProtocol(Protocol):
    """The slice of the :class:`FLYNCModel` surface the mixins rely on."""

    ecus: List[ECU]
    topology: FLYNCTopology
    communication: Optional[FLYNCCommunicationConfig]

    def get_can_bus_topology(self, bus_name: str) -> Optional[CANBusTopology]: ...

    def get_lin_bus_topology(self, bus_name: str) -> Optional[LINBusTopology]: ...

    @property
    def multidrop_connections(self) -> List[EthernetMultidropConnection]: ...

    def get_multidrop_connection(self, connection_id: str) -> Optional[EthernetMultidropConnection]: ...

    def get_all_ecus(self) -> List[str]: ...

    def get_ecu_by_name(self, ecu_name: str) -> ECU | None: ...

    def get_all_controllers(self) -> List[Controller]: ...

    def get_all_ecu_ports(self) -> List[ECUPort]: ...

    def get_all_ecu_ports_by_name(self) -> Dict[str, ECUPort]: ...

    def get_interface_by_name(self, name: str) -> EthernetInterfaceConfig | None: ...

    def get_all_interfaces(self) -> List[EthernetInterfaceConfig]: ...

    def get_all_interfaces_names(self) -> List[str]: ...

    def get_interfaces_for_ecu(self, ecu_name: str) -> List[str]: ...

    def get_ethernet_topology_info(self) -> dict[str, object] | None: ...

    def _iter_ecu_sockets(self) -> Iterator[tuple[ECU, SocketTCP | SocketUDP]]: ...

    def _iter_all_sockets(self) -> Iterator[SocketTCP | SocketUDP]: ...

    def _iter_someip_multicast_udp_deployments(self) -> Iterator[tuple[SocketDeployment, SocketTCP | SocketUDP, ECU]]: ...

    def get_all_pdu_forwarders(self) -> List[PDUForwarder]: ...

    def get_all_can_frame_forwarders(self) -> List[CANFrameForwarder]: ...

    def get_all_someip_services(self) -> List[SOMEIPServiceInterface]: ...

    def get_someip_services_by_identity(self) -> Dict[tuple[int, int], SOMEIPServiceInterface]: ...

    def iter_app_binding_owners(self) -> Iterator[Controller | ComputeNode]: ...

    def _iter_bound_app_consumer_refs(
        self,
    ) -> Iterator[tuple[Controller | ComputeNode, set[tuple[int, int, int]], App, ServiceConsumerReference]]: ...

    def _ethernet_topology_dependent_features(self) -> List[str]: ...

    def _iter_tx_multicasts(self, separ: str) -> Iterator[tuple[str, MulticastGroupMembership]]: ...

    def _record_tx_multicast_path(
        self,
        key: str,
        mcast: MulticastGroupMembership,
        paths: dict[str, list[list[NetworkComponent]]],
        parents: dict[str, list[ParentMap]],
        vlans_dict: dict[str, int | None],
    ) -> None: ...

    def check_rx_are_reached(
        self,
        separ: str,
        paths: dict[str, list[list[NetworkComponent]]],
        parents: dict[str, list[ParentMap]],
        vlans_dict: dict[str, int | None],
    ) -> None: ...

    def _register_rx_target(
        self,
        rx_targets: dict[str, list[EthernetInterface]],
        mcast: MulticastGroupMembership,
        separ: str,
        paths: dict[str, list[list[NetworkComponent]]],
    ) -> None: ...

    def append_mcast(self, vlan: int, comp: SwitchPort, mcast_addr: str) -> None: ...

    def _append_mcast_to_vlan_entry(self, v_entry: VLANEntry, comp: SwitchPort, mcast_addr: str) -> None: ...

    def load_switch_multicast(
        self,
        vlans_dict: dict[str, int | None],
        paths: dict[str, list[list[NetworkComponent]]],
        parents: dict[str, list[ParentMap]],
        rx_targets: dict[str, list[EthernetInterface]],
    ) -> None: ...

    def _collect_used_switch_ports(
        self,
        targets: list[EthernetInterface],
        paths: list[list[NetworkComponent]],
        parents: list[ParentMap],
    ) -> dict[int, SwitchPort]: ...
