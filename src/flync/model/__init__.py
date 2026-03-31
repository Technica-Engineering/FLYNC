"""
This package provides the main FLYNC model definitions and
aggregates all domain-specific model packages, including ECU,
topology, security, SOME/IP, TSN, metadata, and general configuration.
"""

from ..core.base_models.base_model import FLYNCBaseModel
from . import (
    flync_4_ecu,
    flync_4_general_configuration,
    flync_4_metadata,
    flync_4_security,
    flync_4_someip,
    flync_4_topology,
    flync_4_tsn,
)
from .flync_model import FLYNCModel

__all__ = [
    "flync_4_ecu",
    "flync_4_general_configuration",
    "flync_4_metadata",
    "flync_4_security",
    "flync_4_someip",
    "flync_4_topology",
    "flync_4_tsn",
    "FLYNCModel",
    "FLYNCBaseModel",
]
