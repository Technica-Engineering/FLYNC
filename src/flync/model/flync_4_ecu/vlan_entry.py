from typing import List

from pydantic import (
    Field,
    field_serializer,
    field_validator,
)
from pydantic.networks import IPvAnyAddress
from pydantic_extra_types.mac_address import MacAddress

import flync.core.utils.common_validators as common_validators
from flync.core.base_models.base_model import FLYNCBaseModel


class MulticastGroup(FLYNCBaseModel):
    """
    Represents a multicast group configuration.

    This class defines a multicast group by associating a multicast
    destination address with a set of switch ports that participate
    in the group.

    Parameters
    ----------
    address : :class:`IPv4Address` or :class:`IPv6Address` or \
    :class:`MacAddress`
        The multicast address. Must be a valid MAC or IP multicast address.

    ports : list of str
        A list of switch port names that are part of the multicast group.
    """

    address: IPvAnyAddress | MacAddress = Field()
    ports: List[str] = Field()

    @field_validator("address", mode="after")
    @classmethod
    def validate_multicast_address(cls, v):
        return common_validators.validate_any_multicast_address(v)

    @field_serializer("address")
    def serialize_address(self, address):
        return str(address)


class VLANEntry(FLYNCBaseModel):
    """
    Represents a VLAN entry for a switch.

    Parameters
    ----------
    name : str
        Human-readable name for the VLAN.

    id : int
        VLAN ID (0-4095).

    default_priority : int
        Default frame priority for the VLAN (0-7).

    ports : list of str
        List of switch port names members of this VLAN.

    multicast : list of :class:`MulticastGroup`, optional
        List of multicast group configurations associated with this VLAN.
    """

    name: str = Field()
    id: int = Field(..., ge=0, le=4095)
    default_priority: int = Field(..., ge=0, le=7)
    ports: List[str] = Field()
    multicast: List[MulticastGroup] | None = Field(default=[])

    @field_validator("multicast", mode="before")
    @classmethod
    def normalize_multicast(cls, v):
        return common_validators.none_to_empty_list(v)
