"""
Defines the port extender model for FLYNC.

A port extender is a chip that adds ports to its controlling switch. It makes no forwarding decisions.
Its ports are therefore ordinary ``SwitchPort`` entries of the switch, which the extender lists by name.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, List, Literal, Optional

from pydantic import Field

from flync.core.annotations.reference import Reference
from flync.core.base_models.base_model import FLYNCBaseModel
from flync.core.utils.exceptions import Category, err_minor
from flync.model.flync_4_ecu.mii import MII, RGMII, RMII, SGMII, USGMII, USXGMII, XFI

if TYPE_CHECKING:
    from flync.model.flync_4_ecu.switch import Switch, SwitchPort


class PortExtenderTag(FLYNCBaseModel):
    """
    Port tag that marks the extender port a frame belongs to on a tagged uplink.

    Parameters
    ----------
    format : Literal["ieee_802_1br", "proprietary"]
        IEEE 802.1BR E-tag or a proprietary tag.
    """

    format: Literal["ieee_802_1br", "proprietary"] = Field()


class ExtenderUplink(FLYNCBaseModel):
    """
    Base class of the uplink variants.

    Parameters
    ----------
    switch_port_name : str
        Switch port that terminates the uplink (alias: ``switch_port``).

    Private Attributes
    ------------------
    _switch_port : :class:`~flync.model.flync_4_ecu.switch.SwitchPort`
        The resolved uplink port. Managed internally.
    """

    switch_port_name: Annotated[str, Reference(source="_switch_port")] = Field(alias="switch_port", min_length=1)
    _switch_port: Optional[SwitchPort] = None

    @property
    def switch_port(self) -> Optional[SwitchPort]:
        """The resolved uplink port, or ``None`` while unbound."""
        return self._switch_port


class TaggedUplink(ExtenderUplink):
    """
    Uplink that carries the frames of all extender ports on one link, each marked with a port tag.

    The uplink may be oversubscribed.

    Parameters
    ----------
    type : Literal["tagged"]
        Uplink type.

    tag : :class:`PortExtenderTag`
        Port tag carried on the link.

    mii_config : :class:`~flync.model.flync_4_ecu.mii.MII` or :class:`~flync.model.flync_4_ecu.mii.RMII` or \
    :class:`~flync.model.flync_4_ecu.mii.SGMII` or :class:`~flync.model.flync_4_ecu.mii.RGMII` or \
    :class:`~flync.model.flync_4_ecu.mii.XFI` or :class:`~flync.model.flync_4_ecu.mii.USXGMII` or \
    :class:`~flync.model.flync_4_ecu.mii.USGMII`
        The extender's end of the link. The switch's uplink port declares the other end with the opposite ``mode``.
    """

    type: Literal["tagged"] = Field(default="tagged")
    tag: PortExtenderTag = Field()
    mii_config: MII | RMII | SGMII | RGMII | XFI | USXGMII | USGMII = Field(discriminator="type")


class ChannelizedUplink(ExtenderUplink):
    """
    Uplink on which a multi-port xMII lane gives every extender port a fixed channel, so no tag is needed.

    A port's channel is its ``mii_subport_id``; its ``mii_subport_of`` names the uplink port.

    Parameters
    ----------
    type : Literal["channelized"]
        Uplink type.

    mii_config : :class:`~flync.model.flync_4_ecu.mii.USXGMII` or :class:`~flync.model.flync_4_ecu.mii.USGMII`
        The extender's end of the lane. The switch's uplink port declares the other end with the opposite ``mode``.
    """

    type: Literal["channelized"] = Field(default="channelized")
    mii_config: USXGMII | USGMII = Field(discriminator="type")


class PortExtender(FLYNCBaseModel):
    """
    A port extender controlled by one switch, declared under ``port_extenders`` in ``switch.flync.yaml``.

    It holds no forwarding configuration (VLANs, TCAM rules, address table): the controlling switch decides.

    Parameters
    ----------
    name : str
        Name of the extender, unique within its switch.

    uplink : :class:`TaggedUplink` or :class:`ChannelizedUplink`
        The uplink to the switch. ``type`` selects the variant.

    ports : list of str
        Names of the switch ports that sit on this extender.

    Private Attributes
    ------------------
    _type :
        The type of the object generated. Set to port_extender.

    _switch : :class:`~flync.model.flync_4_ecu.switch.Switch`
        The controlling switch. Managed internally.
    """

    name: str = Field(min_length=1)
    uplink: TaggedUplink | ChannelizedUplink = Field(discriminator="type")
    ports: List[str] = Field(default_factory=list)
    _type: Literal["port_extender"] = "port_extender"
    _switch: Optional[Switch] = None

    @property
    def type(self) -> Literal["port_extender"]:
        """Object type tag, ``"port_extender"``."""
        return self._type

    @property
    def switch(self) -> Optional[Switch]:
        """The controlling switch, or ``None`` while unbound."""
        return self._switch

    @property
    def mii_config(self) -> MII | RMII | SGMII | RGMII | XFI | USXGMII | USGMII:
        """The extender's end of the uplink xMII."""
        return self.uplink.mii_config

    def get_ports(self) -> list[SwitchPort]:
        """Return the switch ports that sit on this extender."""
        if self._switch is None:
            return []
        by_name = {port.name: port for port in self._switch.ports}
        return [by_name[name] for name in self.ports if name in by_name]

    def validate_not_oversubscribed(self) -> None:
        """
        Raise err_minor when the ports of a tagged extender together exceed the uplink speed.
        """

        uplink = self.uplink
        if uplink.type != "tagged" or uplink.mii_config.speed is None:
            return
        speeds = [port.mdi_config.speed for port in self.get_ports() if port.mdi_config is not None]
        if sum(speeds) > uplink.mii_config.speed:
            raise err_minor(
                "Extender '{extender}' is oversubscribed: its {ports} ports add up to {total} Mb/s ({breakdown}), "
                "more than its {uplink_type} uplink carries ({uplink_speed} Mb/s).",
                extender=self.name,
                ports=len(speeds),
                total=sum(speeds),
                breakdown=" + ".join(str(speed) for speed in speeds),
                uplink_type=uplink.mii_config.type,
                uplink_speed=uplink.mii_config.speed,
                category=Category.CONSISTENCY,
                error_number="400",
            )
