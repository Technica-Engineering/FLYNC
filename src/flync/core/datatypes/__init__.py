"""This module contains classes to model datatypes"""

from .base import Datatype
from .bitrange import BitRange
from .ethertypes import Ethertype, serialize_ethertype, validate_ethertype_input
from .ipaddress import (
    IPv4AddressEntry,
    IPv4Multicast,
    IPv6AddressEntry,
    IPv6Multicast,
)
from .macaddress import FLYNCMacAddress, MACAddressEntry, MACAddressMulticast, MACAddressUnicast
from .value_range import ValueRange
from .value_table import ValueTable

__all__ = [
    "serialize_ethertype",
    "BitRange",
    "Datatype",
    "Ethertype",
    "IPv4AddressEntry",
    "IPv6AddressEntry",
    "IPv4Multicast",
    "IPv6Multicast",
    "FLYNCMacAddress",
    "MACAddressEntry",
    "MACAddressUnicast",
    "MACAddressMulticast",
    "validate_ethertype_input",
    "ValueRange",
    "ValueTable",
]
