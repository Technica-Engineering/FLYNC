"""
Multicast group membership model for virtual controller interfaces.

Defines :class:`MulticastGroupMembership`, describing participation of a virtual controller interface in a single multicast group (IPv4, IPv6 or
MAC) along with the direction (tx/rx), VLAN and optional source IP.
"""

from ipaddress import IPv4Address, IPv6Address
from typing import Annotated, Literal, Optional

from pydantic import AfterValidator, Field, PrivateAttr, model_validator
from pydantic.networks import IPvAnyAddress

import flync.core.utils.common_validators as common_validators
from flync.core.base_models import FLYNCBaseModel
from flync.core.datatypes.macaddress import FLYNCMacAddress
from flync.core.utils.common_validators import validate_vlan_id
from flync.core.utils.exceptions import err_minor
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
        IPvAnyAddress | FLYNCMacAddress,
        AfterValidator(common_validators.validate_any_multicast_address),
    ] = Field()
    description: Optional[str] = Field(default="")
    mode: Literal["tx"] | Literal["rx"] = Field(default="rx")
    vlan: Annotated[Optional[int], AfterValidator(validate_vlan_id)] = Field(default=0)
    src_ip: Optional[IPvAnyAddress] = Field(default=None)
    solicited_node_multicast: Optional[bool] = Field(default=False)
    _interface: ControllerInterface = PrivateAttr()

    @model_validator(mode="after")
    def validate_src_ip_set_on_tx_ip_groups(self):
        if (isinstance(self.group, (IPv4Address | IPv6Address))) and self.mode == "tx" and not self.src_ip:
            raise err_minor(
                f"Multicast group membership for {self.group} ({self.mode} / VLAN {self.vlan} ) could not be defined."
                "The field 'src_ip' must be defined for IP multicast senders!"
            )
        return self

    @property
    def interface(self):
        """Return the controller interface this membership belongs to."""
        return self._interface
