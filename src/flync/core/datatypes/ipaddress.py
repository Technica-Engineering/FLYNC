"""Defines IPv4 and IPv6 address models."""

from ipaddress import IPv4Address, IPv6Address
from typing import Annotated

from pydantic import AfterValidator, Field, field_serializer

from flync.core.base_models.base_model import FLYNCBaseModel
from flync.core.validators.address import validate_ip_multicast

SOLICITED_NODE_MULTICAST_PREFIX = 0xFF02_0000_0000_0000_0000_0001_FF00_0000
"""The solicited-node multicast prefix ``FF02::1:FF00:0/104`` (RFC 4291, section 2.7.1) as an integer."""


class IPv4AddressEntry(FLYNCBaseModel):
    """
    Represents an IPv4 address entry for a network interface.

    Parameters
    ----------
    address : :class:`IPv4Address`
        The IPv4 address. "0.0.0.0" means dynamic.

    ipv4netmask : :class:`IPv4Address`
        The subnet mask in IPv4 format.
    """

    address: IPv4Address = Field()
    ipv4netmask: IPv4Address = Field()

    @field_serializer("address", "ipv4netmask")
    def serialize_address(self, address: IPv4Address) -> str:
        return str(address)


class IPv4Multicast(IPv4AddressEntry):
    """
    Represents a Multicast IPv4 address entry for a network interface.
    """

    address: Annotated[
        IPv4Address,
        AfterValidator(validate_ip_multicast),
    ] = Field()


class IPv6AddressEntry(FLYNCBaseModel):
    """
    Represents an IPv6 address entry for a network interface.

    Parameters
    ----------
    address : :class:`IPv6Address`
        The IPv6 address. "::" means dynamic.

    ipv6prefix : int
        The prefix length (0-128).
    """

    address: IPv6Address = Field()
    ipv6prefix: int = Field(..., ge=0, le=128)

    @field_serializer("address")
    def serialize_address(self, address: IPv6Address) -> str:
        return str(address).lower()

    def derive_multicast_address(self) -> IPv6Address:
        """
        Derives the corresponding solicited-node multicast address by taking the last 24 bits of the unicast address
        and appending them to the prefix FF02::1:FF00:0/104

        Returns
        -------
        :class:`IPv6Address`
            The derived multicast address.
        """

        unicast_int = int(self.address)
        derived_multicast_int = SOLICITED_NODE_MULTICAST_PREFIX | (unicast_int & 0xFFFFFF)
        return IPv6Address(derived_multicast_int)


class IPv6Multicast(IPv6AddressEntry):
    """
    Represents a Multicast IPv4 address entry for a network interface.
    """

    address: Annotated[
        IPv6Address,
        AfterValidator(validate_ip_multicast),
    ] = Field()
