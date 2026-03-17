"""this module contains classes to model datatypes"""

from .base import Datatype
from .bitrange import BitRange
from .ipaddress import (
    IPv4AddressEntry,
    IPv4Multicast,
    IPv6AddressEntry,
    IPv6Multicast,
)
from .macaddress import MACAddressEntry, MACAddressMulticast, MACAddressUnicast
from .value_range import ValueRange
from .value_table import ValueTable

__all__ = [
    "BitRange",
    "Datatype",
    "IPv4AddressEntry",
    "IPv6AddressEntry",
    "IPv4Multicast",
    "IPv6Multicast",
    "MACAddressEntry",
    "MACAddressUnicast",
    "MACAddressMulticast",
    "ValueRange",
    "ValueTable",
]
