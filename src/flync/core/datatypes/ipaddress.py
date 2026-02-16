from ipaddress import IPv4Address, IPv6Address

from pydantic import Field, field_serializer

from flync.core.base_models.base_model import FLYNCBaseModel


class IPv4AddressEntry(FLYNCBaseModel):
    """
    Represents an IPv4 address entry for a network interface.

    Parameters
    ----------
    address : :class:`IPv4Address`
        The IPv4 address.

    ipv4netmask : :class:`IPv4Address`
        The subnet mask in IPv4 format.
    """

    address: IPv4Address = Field()
    ipv4netmask: IPv4Address = Field()

    @field_serializer("address", "ipv4netmask")
    def serialize_ipv4(self, address: IPv4Address):
        return str(address)


class IPv6AddressEntry(FLYNCBaseModel):
    """
    Represents an IPv6 address entry for a network interface.

    Parameters
    ----------
    address : :class:`IPv6Address`
        The IPv6 address.

    ipv6prefix : int
        The prefix length (0-128).
    """

    address: IPv6Address = Field()
    ipv6prefix: int = Field(..., ge=0, le=128)

    @field_serializer("address")
    def serialize_ipv6(self, address: IPv6Address):
        if address is not None:
            return str(address).upper()
