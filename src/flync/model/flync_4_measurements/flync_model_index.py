"""Indexing helpers for resolving a Measurement Point's ``observes`` entries against an
already-loaded FLYNC model."""

from typing import TYPE_CHECKING, Dict, Set, Tuple, Union

from flync.model.flync_4_bus import CANBus, LINBus
from flync.model.flync_4_ecu import EthernetInterface, VirtualControllerInterface

if TYPE_CHECKING:
    from flync.model.flync_model import FLYNCModel


def collect_buses_by_name(flync_model: "FLYNCModel") -> Dict[str, Union[CANBus, LINBus]]:
    """Every CAN/LIN bus in the model, keyed by name."""
    channels = flync_model.communication.channels if flync_model.communication is not None else None
    buses: Dict[str, Union[CANBus, LINBus]] = {}
    if channels is not None:
        for can_bus in channels.can_buses or []:
            buses[can_bus.name] = can_bus
        for lin_bus in channels.lin_buses or []:
            buses[lin_bus.name] = lin_bus
    return buses


def collect_ethernet_interfaces_by_name(flync_model: "FLYNCModel") -> Dict[str, EthernetInterface]:
    """Every :class:`~flync.model.flync_4_ecu.controller.EthernetInterface` in the model, keyed by
    name.

    Uses ``controller.ethernet_interfaces`` rather than ``FLYNCModel.get_all_interfaces()``, which
    returns each interface's nested ``EthernetInterfaceConfig`` instead of the
    :class:`EthernetInterface` itself.
    """
    return {eth_iface.name: eth_iface for controller in flync_model.get_all_controllers() for eth_iface in (controller.ethernet_interfaces or [])}


def collect_virtual_interfaces(flync_model: "FLYNCModel") -> Tuple[Dict[str, VirtualControllerInterface], Set[str]]:
    """Every VLAN sub-interface in the model keyed by name, and the names that collide.

    Only ``vlanid`` is guaranteed unique in FLYNC, not name, so a colliding name is excluded from
    the first return value and reported separately - letting a caller distinguish "ambiguous" from
    "unknown".
    """
    seen: Dict[str, VirtualControllerInterface] = {}
    ambiguous: Set[str] = set()

    def record(vci: VirtualControllerInterface) -> None:
        """Track `vci` by name, moving a repeated name into `ambiguous`."""
        if vci.name in seen:
            ambiguous.add(vci.name)
            return
        seen[vci.name] = vci

    for controller in flync_model.get_all_controllers():
        for eth_iface in controller.iter_subtree_interfaces():
            for vci in eth_iface.interface_config.virtual_interfaces or []:
                record(vci)

    for name in ambiguous:
        del seen[name]
    return seen, ambiguous
