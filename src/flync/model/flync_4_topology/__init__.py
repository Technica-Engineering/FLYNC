"""
This package provides topology models for FLYNC
"""

from .bus_topology import BusAttachmentPoint, BusTopology, CANBusTopology, LINBusTopology
from .ethernet_topology import EthernetTopology, ExternalConnection, FLYNCTopology

KEY = "TOP"
__all__ = [
    "ExternalConnection",
    "EthernetTopology",
    "FLYNCTopology",
    "BusAttachmentPoint",
    "BusTopology",
    "CANBusTopology",
    "LINBusTopology",
]
