"""
This package provides models for representing an ECU in the FLYNC architecture, including controllers, ports, switches, sockets,
and internal topology definitions.
"""

from .controller import (
    ComputeNodes,
    Controller,
    ControllerInterface,
    EthernetInterface,
    L2Bridge,
    L2BridgePort,
    VirtualControllerInterface,
)
from .ecu import ECU
from .internal_topology import InternalTopology
from .mac_multicast_endpoint import (
    AVTPMulticastEndpoint,
    MACMulticastEndpoint,
    MACMulticastEndpoints,
)
from .multicast_groups import MulticastGroupMembership
from .phy import BASET, BASET1, BASET1S, MII, RGMII, RMII, SGMII, XFI
from .port import ECUPort
from .socket_container import SocketContainer
from .sockets import (
    IPv4AddressEndpoint,
    IPv6AddressEndpoint,
    Socket,
    SocketTCP,
    SocketUDP,
    TCPOption,
    UDPOption,
)
from .switch import (
    RouteEntry,
    Switch,
    SwitchHostController,
    SwitchPort,
    TCAMRule,
    TrafficClass,
)
from .vlan_entry import MulticastGroup, VLANEntry

__all__ = [
    "ComputeNodes",
    "Controller",
    "ControllerInterface",
    "EthernetInterface",
    "L2Bridge",
    "L2BridgePort",
    "VirtualControllerInterface",
    "IPv4AddressEndpoint",
    "IPv6AddressEndpoint",
    "Socket",
    "TCPOption",
    "UDPOption",
    "SocketTCP",
    "SocketUDP",
    "SocketContainer",
    "ECU",
    "InternalTopology",
    "MII",
    "RMII",
    "RGMII",
    "SGMII",
    "XFI",
    "BASET",
    "BASET1",
    "BASET1S",
    "ECUPort",
    "RouteEntry",
    "Switch",
    "SwitchHostController",
    "SwitchPort",
    "VLANEntry",
    "MulticastGroup",
    "TCAMRule",
    "TrafficClass",
    "MulticastGroupMembership",
    "AVTPMulticastEndpoint",
    "MACMulticastEndpoint",
    "MACMulticastEndpoints",
]
