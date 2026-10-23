"""
Defines the port extender model for FLYNC.

A port extender is a chip that adds ports to its controlling switch. It makes no forwarding decisions.
Its ports are therefore ordinary ``SwitchPort`` entries of the switch, which the extender lists by name.
"""

from __future__ import annotations

from collections.abc import Collection
from typing import TYPE_CHECKING, Annotated, List, Literal, Optional

from pydantic import Field

from flync.core.annotations.reference import Reference
from flync.core.base_models.base_model import FLYNCBaseModel
from flync.core.utils.exceptions import Category, err_major, err_minor, warn
from flync.core.validators.connection_compatibility import validate_compulsory_mii_config_compatibility
from flync.core.validators.generic import validate_list_items_unique
from flync.model.flync_4_ecu.mii import (
    MII,
    RGMII,
    RMII,
    SGMII,
    USGMII,
    USXGMII,
    XFI,
    XMIIConfig,
    xmii_channel_capacity,
)

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


def get_extender_uplink_ports(switch: Switch) -> frozenset[str]:
    """Return the names of the switch ports that terminate an extender uplink."""
    return frozenset(extender.uplink.switch_port_name for extender in switch.port_extenders or [])


def get_channelized_uplink_ports(switch: Switch) -> frozenset[str]:
    """Return the names of the switch ports that terminate a channelized extender uplink."""
    return frozenset(extender.uplink.switch_port_name for extender in switch.port_extenders or [] if extender.uplink.type == "channelized")


def bind_port_extenders(switch: Switch) -> None:
    """
    Bind each extender to its switch, its ports and its uplink port.

    The connected component of an uplink port is the extender. Unresolved references stay ``None``.
    """

    by_name = {port.name: port for port in switch.ports}
    for extender in switch.port_extenders:
        extender._switch = switch
        for name in extender.ports:
            if name in by_name:
                by_name[name]._port_extender = extender
        uplink = extender.uplink
        uplink._switch_port = by_name.get(uplink.switch_port_name)
        if uplink._switch_port is not None:
            uplink._switch_port._connected_component = extender


def validate_extender_names(switch: Switch) -> None:
    """
    Validate that extender names are unique within this switch.

    Raises:
        err_major: Two extenders share a name.
    """

    validate_list_items_unique([extender.name for extender in switch.port_extenders], "Port Extenders (name)")


def validate_extender_port_references(switch: Switch) -> None:
    """
    Validate that every listed extender port is a port of this switch and is listed once.

    Raises:
        err_major: An extender lists an unknown port.

        err_major: A port is listed twice.
    """

    names = {port.name for port in switch.ports}
    for extender in switch.port_extenders:
        for name in extender.ports:
            if name not in names:
                raise err_major(
                    "Port extender '{extender}' lists port '{port}', which is not a port of this switch.",
                    extender=extender.name,
                    port=name,
                    category=Category.REFERENCE,
                    error_number="391",
                )
    validate_list_items_unique([name for extender in switch.port_extenders for name in extender.ports], "Port Extenders (ports)")


def validate_extender_uplinks(switch: Switch) -> None:
    """
    Validate the uplink port of every extender.

    Raises:
        err_major: Two extenders share an uplink port.

        err_major: The uplink port is not a port of this switch.

        err_major: The uplink port sits on another extender (cascading is not supported).
    """

    validate_list_items_unique([extender.uplink.switch_port_name for extender in switch.port_extenders], "Port Extenders (uplink switch_port)")
    names = {port.name for port in switch.ports}
    for extender in switch.port_extenders:
        name = extender.uplink.switch_port_name
        if name not in names:
            raise err_major(
                "Uplink port '{port}' of extender '{extender}' is not a port of this switch.",
                port=name,
                extender=extender.name,
                category=Category.REFERENCE,
                error_number="392",
            )
        parent = next((other for other in switch.port_extenders if name in other.ports), None)
        if parent is not None:
            raise err_major(
                "Uplink port '{port}' of extender '{extender}' is itself a port of extender '{parent}'. Cascading extenders are not supported.",
                port=name,
                extender=extender.name,
                parent=parent.name,
                category=Category.COMPATIBILITY,
                error_number="393",
            )


def validate_extender_port_channels(switch: Switch) -> None:
    """
    Validate how an extender port reaches the uplink.

    On a channelized uplink a port needs ``mii_subport_of`` (the uplink port) and ``mii_subport_id``. On a tagged uplink it sets neither
    nor ``mii_config``.

    Raises:
        err_major: A channelized extender port lacks ``mii_subport_of`` or ``mii_subport_id``.

        err_major: A tagged extender port sets ``mii_config``, ``mii_subport_of`` or ``mii_subport_id``.
    """

    by_name = {port.name: port for port in switch.ports}
    for extender in switch.port_extenders:
        uplink = extender.uplink
        for port in (by_name[name] for name in extender.ports):
            if uplink.type == "channelized":
                if port.mii_subport_of != uplink.switch_port_name or port.mii_subport_id is None:
                    raise err_major(
                        "Switch port '{port}' sits on extender '{extender}', whose uplink is channelized: it needs mii_subport_of "
                        "'{uplink}' and a mii_subport_id (its channel on the lane).",
                        port=port.name,
                        extender=extender.name,
                        uplink=uplink.switch_port_name,
                        category=Category.CONSISTENCY,
                        error_number="394",
                    )
            elif port.mii_config is not None or port.mii_subport_of is not None or port.mii_subport_id is not None:
                raise err_major(
                    "Switch port '{port}' sits on extender '{extender}', whose uplink is tagged: it cannot set mii_config, mii_subport_of or "
                    "mii_subport_id. The tag, not a channel, tells its frames apart.",
                    port=port.name,
                    extender=extender.name,
                    category=Category.CONSISTENCY,
                    error_number="395",
                )


def validate_extender_uplink_links(switch: Switch) -> None:
    """
    Validate both ends of every uplink against the uplink type.

    The ends are checked like any xMII link (opposite modes, same type and speed). A channelized uplink also needs a multi-port lane
    with matching channels, and a tagged uplink a single-port xMII.

    Raises:
        err_major: The ends differ in mode, speed or type, or one has no xMII.

        err_major: A channelized uplink does not use a multi-port lane.

        err_major: A tagged uplink uses a multi-port lane.

        err_major: The lane channels differ between the two ends.
    """

    by_name = {port.name: port for port in switch.ports}
    for extender in switch.port_extenders or []:
        uplink_port = by_name[extender.uplink.switch_port_name]
        validate_compulsory_mii_config_compatibility(uplink_port, extender, extender.name)
        lane = uplink_port.mii_config
        if lane is None:  # the compulsory check above raised already
            continue
        multi_port = xmii_channel_capacity(lane) > 1
        if extender.uplink.type == "channelized":
            if not multi_port:
                raise err_major(
                    "Extender '{extender}' has a channelized uplink, which needs a multi-port USXGMII or USGMII lane, "
                    "but '{lane}' carries one port.",
                    extender=extender.name,
                    lane=lane.type,
                    category=Category.COMPATIBILITY,
                    error_number="396",
                )
            if _channel_signature(lane) != _channel_signature(extender.uplink.mii_config):
                raise err_major(
                    "The lane of uplink '{port}' differs between the switch and extender '{extender}': channels {switch_channels} against "
                    "{extender_channels}.",
                    port=uplink_port.name,
                    extender=extender.name,
                    switch_channels=_channel_signature(lane),
                    extender_channels=_channel_signature(extender.uplink.mii_config),
                    category=Category.COMPATIBILITY,
                    error_number="398",
                )
        elif multi_port:
            raise err_major(
                "Extender '{extender}' has a tagged uplink, which needs a single-port xMII, but '{lane}' is a multi-port lane. "
                "Use a channelized uplink for it.",
                extender=extender.name,
                lane=lane.type,
                category=Category.COMPATIBILITY,
                error_number="397",
            )


def warn_extender_without_ports(switch: Switch) -> None:
    """Warn about an extender without ports."""

    for extender in switch.port_extenders:
        if not extender.ports:
            warn(
                f"Port extender '{extender.name}' has no ports.",
                category=Category.STRUCTURAL,
                error_number="403",
            )


def validate_uplink_port_usage(switch: Switch) -> None:
    """
    Raise err_minor on forwarding or TSN configuration on an uplink port.

    The uplink port is a lane to the extender, not a forwarding endpoint.
    """

    uplinks = get_extender_uplink_ports(switch)
    for vlan in switch.vlans or []:
        _validate_uplink_not_listed(uplinks, vlan.ports, f"VLAN '{vlan.name}'")
        for group in vlan.multicast or []:
            _validate_uplink_not_listed(uplinks, group.ports, f"multicast group {group.address} of VLAN '{vlan.name}'")
    for rule in switch.tcam_rules or []:
        _validate_uplink_not_listed(uplinks, rule.match_ports, f"TCAM rule '{rule.name}' (match_ports)")
        for action in rule.action or []:
            _validate_uplink_not_listed(uplinks, action.ports, f"TCAM rule '{rule.name}' (action '{action.type}')")
    for port in switch.ports:
        if port.name not in uplinks:
            continue
        configured = [field for field in ("ptp_config", "ingress_streams", "traffic_classes", "macsec_config") if getattr(port, field)]
        if configured:
            raise err_minor(
                "Uplink port '{port}' carries {configured}, but it is a lane to an extender, not a forwarding endpoint.",
                port=port.name,
                configured=", ".join(configured),
                category=Category.CONSISTENCY,
                error_number="402",
            )


def _channel_signature(mii_config: XMIIConfig) -> list[tuple[int, int]]:
    """The ``(subport_id, speed)`` pairs of a multi-port xMII; empty for a single-port xMII."""
    channels = mii_config.channels if isinstance(mii_config, (USXGMII, USGMII)) else []
    return sorted((channel.subport_id, channel.speed) for channel in channels)


def _validate_uplink_not_listed(uplinks: frozenset[str], listed_ports: Collection[str] | None, where: str) -> None:
    """Raise err_minor if an uplink port is named in ``listed_ports``."""
    for name in sorted(uplinks.intersection(listed_ports or [])):
        raise err_minor(
            "Uplink port '{port}' is listed in {where}, but it is a lane to an extender, not a forwarding endpoint.",
            port=name,
            where=where,
            category=Category.CONSISTENCY,
            error_number="401",
        )
