from typing import Literal, Optional

from pydantic import Field, PrivateAttr
from pydantic.networks import IPvAnyAddress
from pydantic_extra_types.mac_address import MacAddress

from flync.core.base_models import FLYNCBaseModel
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
    mode : "tx", "rx", or "bidir", optional
        Mode of multicast group membership. Defaults to "bidir".
    vlan : int, optional
        VLAN ID associated with the multicast group membership, if applicable.
    src_ip : str, optional
        Source IP address. Only applicable for "tx" mode.
    """

    group: IPvAnyAddress | MacAddress = Field()
    description: Optional[str] = Field(default="")
    mode: Literal["tx"] | Literal["rx"] | Literal["bidir"] = Field(
        default="bidir"
    )
    vlan: Optional[int] = Field(default=0)
    src_ip: Optional[IPvAnyAddress] = Field(default=None)
    solicited_node_multicast: Optional[bool] = Field(default=False)
    _interface: ControllerInterface = PrivateAttr()

    @property
    def interface(self):
        return self._interface
