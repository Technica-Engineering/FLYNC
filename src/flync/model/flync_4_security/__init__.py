"""
This package provides security models for FLYNC.
"""

from .firewall import Firewall, FirewallRule
from .macsec import (
    IntegrityWithConfidentiality,
    IntegrityWithoutConfidentiality,
    MACsecConfig,
)

KEY = "SEC"
__all__ = [
    "Firewall",
    "FirewallRule",
    "IntegrityWithConfidentiality",
    "IntegrityWithoutConfidentiality",
    "MACsecConfig",
]
