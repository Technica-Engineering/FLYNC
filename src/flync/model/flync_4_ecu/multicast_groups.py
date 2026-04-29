"""Multicast group membership model for virtual controller interfaces.

Defines :class:`MulticastGroupMembership`, describing participation of a
virtual controller interface in a single multicast group (IPv4, IPv6 or
MAC) along with the direction (tx/rx), VLAN and optional source IP.
"""

from typing import Annotated, Literal, Optional

from pydantic import AfterValidator, Field, PrivateAttr
from pydantic.networks import IPvAnyAddress
from pydantic_extra_types.mac_address import MacAddress

import flync.core.utils.common_validators as common_validators
from flync.core.base_models import FLYNCBaseModel
from flync.core.utils.common_validators import validate_vlan_id
from flync.model.flync_4_ecu.controller import ControllerInterface


class MulticastGroupMembership(FLYNCBaseModel):
    """
    Represents a multicast group membership for virtual controller interfaces.

    Parameters
    ----------
    group : IPv4Multicast or IPv6Multicast or MACAddressMulticast
        Multicast group address.
    description : str, optional
        Description of the multicast group membership.
    mode : "tx" or "rx", optional
        Mode of multicast group membership.
    vlan : int, optional
        VLAN ID associated with the multicast group membership.
        Use ``None`` for untagged.
    src_ip : str, optional
        Source IP address. Only applicable for "tx" mode.
    """

    group: Annotated[
        IPvAnyAddress | MacAddress,
        AfterValidator(common_validators.validate_any_multicast_address),
    ] = Field()
    description: Optional[str] = Field(default="")
    mode: Literal["tx"] | Literal["rx"] = Field(default="tx")
    vlan: Annotated[Optional[int], AfterValidator(validate_vlan_id)] = Field(
        default=0
    )
    src_ip: Optional[IPvAnyAddress] = Field(default=None)
    solicited_node_multicast: Optional[bool] = Field(default=False)
    _interface: ControllerInterface = PrivateAttr()

    @property
    def interface(self):
        """Return the controller interface this membership belongs to."""
        return self._interface
