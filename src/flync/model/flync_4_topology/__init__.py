"""
This package provides system topology models for FLYNC
"""

from .system_topology import ExternalConnection, FLYNCTopology, SystemTopology

KEY = "TOP"
__all__ = [
    "ExternalConnection",
    "SystemTopology",
    "FLYNCTopology",
]
