"""
This package provides metadata models for FLYNC,
including system, ECU, hardware, software, and service-related
metadata definitions.
"""

from .metadata import (
    BaseMetadata,
    BaseVersion,
    ECUMetadata,
    EmbeddedMetadata,
    HardwareBaseMetadata,
    SocketsPerVLANMetadata,
    SoftwareBaseMetadata,
    SOMEIPServiceMetadata,
    SystemMetadata,
)

__all__ = [
    "BaseMetadata",
    "BaseVersion",
    "ECUMetadata",
    "EmbeddedMetadata",
    "HardwareBaseMetadata",
    "SoftwareBaseMetadata",
    "SocketsPerVLANMetadata",
    "SOMEIPServiceMetadata",
    "SystemMetadata",
]
