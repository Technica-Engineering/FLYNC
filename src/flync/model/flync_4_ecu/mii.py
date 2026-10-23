"""
Defines the supported xMII configurations used in the FLYNC model.

"xMII" is the umbrella term for every interface in the MII role: the MAC-facing link
between a MAC and its PHY, or, PHY-less, between two MAC-side devices
(switch-to-switch, switch-to-SoC, switch-to-port-extender). It covers parallel
interfaces (MII, RMII, RGMII) and serial ones (SGMII, USGMII, USXGMII, XFI).
"""

from typing import Literal, NamedTuple, Optional, Self

from pydantic import Field, model_validator

from flync.core.base_models import FLYNCBaseModel
from flync.core.utils.exceptions import Category, err_major
from flync.core.validators.generic import validate_list_items_unique


class MII(FLYNCBaseModel):
    """
    Represents a Media Independent Interface (MII) configuration.

    Parameters
    ----------
    type : Literal["mii"]
        Interface type. Defaults to ``"mii"``.

    speed : int, optional
        Highest link speed this interface carries, in megabits per second. Valid values are 10 or 100.
        Defaults to 100 Mbps. The clock scales with the link rate (25/2.5 MHz), so a port may pair this with a slower MDI.

    mode : Literal["mac", "phy"]
        Operating mode, either MAC or PHY.
    """

    type: Literal["mii"] = Field(default="mii")
    speed: Optional[Literal[10, 100]] = Field(default=100)
    mode: Literal["mac", "phy"] = Field()


class RMII(FLYNCBaseModel):
    """
    Represents a Reduced Media Independent Interface (RMII)
    configuration.

    Parameters
    ----------
    type : Literal["rmii"]
        Interface type. Defaults to ``"rmii"``.

    speed : int, optional
        Highest link speed this interface carries, in megabits per second. Valid values are 10 or 100.
        Defaults to 100 Mbps. The 50 MHz reference clock never slows down; a 10 Mbps link is carried by holding each
        dibit for 10 clock cycles, so a port may pair this with a slower MDI.

    mode : Literal["mac", "phy"]
        Operating mode, either MAC or PHY.
    """

    type: Literal["rmii"] = Field(default="rmii")
    speed: Optional[Literal[10, 100]] = Field(default=100)
    mode: Literal["mac", "phy"] = Field()


class SGMII(FLYNCBaseModel):
    """
    Represents a Serial Gigabit Media Independent Interface
    (SGMII or SGMII+) configuration.

    Parameters
    ----------
    type : Literal["sgmii"]
        Interface type. Defaults to ``"sgmii"``.

    speed : int, optional
        Highest link speed this interface carries, in megabits per second. Valid values are 10, 100, 1000, or 2500.
        Defaults to 1000 Mbps. The serdes never slows down; a slower link is carried by repeating each code group
        (10x at 100 Mbps, 100x at 10 Mbps), so a port may pair this with a slower MDI.

    mode : Literal["mac", "phy"]
        Operating mode, either MAC or PHY.
    """

    type: Literal["sgmii"] = Field(default="sgmii")
    speed: Optional[Literal[10, 100, 1000, 2500]] = Field(default=1000)
    mode: Literal["mac", "phy"] = Field()


class RGMII(FLYNCBaseModel):
    """
    Represents a Reduced Gigabit Media Independent Interface (RGMII) configuration.

    Parameters
    ----------
    type : Literal["rgmii"]
        Interface type. Defaults to ``"rgmii"``.

    speed : int, optional
        Highest link speed this interface carries, in megabits per second. Valid values are 10, 100, or 1000.
        Defaults to 1000 Mbps. The clock scales with the link rate (125/25/2.5 MHz), so a port may pair this with a slower MDI.

    mode : Literal["mac", "phy"]
        Operating mode, either MAC or PHY.
    """

    type: Literal["rgmii"] = Field(default="rgmii")
    speed: Optional[Literal[10, 100, 1000]] = Field(default=1000)
    mode: Literal["mac", "phy"] = Field()


class XFI(FLYNCBaseModel):
    """
    Represents a 10-Gigabit Ethernet (10GbE) serial electrical interface
    (XFI) configuration.

    Parameters
    ----------
    type : Literal["xfi"]
        Interface type. Defaults to "xfi".

    speed : Literal[10000]
        Supported speed in Mbps. Defaults to 10000.

    mode : Literal["mac", "phy"]
        Operating mode of the interface, either MAC or PHY.
    """

    type: Literal["xfi"] = Field(default="xfi")
    speed: Literal[10000] = Field(default=10000)
    mode: Literal["mac", "phy"] = Field()


class _Variant(NamedTuple):
    """One USXGMII/USGMII variant: its channel count, highest speed per channel and PCH capability."""

    ports: int
    per_port_max: int
    pch_capable: bool = False


_USXGMII_SPEEDS = frozenset({10, 100, 1000, 2500, 5000, 10000})

_USXGMII_VARIANTS: dict[str, _Variant] = {
    "usxgmii_10g_sxgmii": _Variant(ports=1, per_port_max=10000),
    "usxgmii_5g_sxgmii": _Variant(ports=1, per_port_max=5000),
    "usxgmii_10g_dxgmii": _Variant(ports=2, per_port_max=5000, pch_capable=True),
    "usxgmii_5g_dxgmii": _Variant(ports=2, per_port_max=2500, pch_capable=True),
    "usxgmii_10g_qxgmii": _Variant(ports=4, per_port_max=2500, pch_capable=True),
    "usxgmii_20g_qxgmii": _Variant(ports=4, per_port_max=5000, pch_capable=True),
    "usxgmii_20g_dxgmii": _Variant(ports=2, per_port_max=10000, pch_capable=True),
    "usxgmii_20g_oxgmii": _Variant(ports=8, per_port_max=2500, pch_capable=True),
}

_USGMII_SPEEDS = frozenset({10, 100, 1000})

_USGMII_VARIANTS: dict[str, _Variant] = {
    "q_usgmii": _Variant(ports=4, per_port_max=1000, pch_capable=True),
    "o_usgmii": _Variant(ports=8, per_port_max=1000, pch_capable=True),
}


class USXGMIIChannel(FLYNCBaseModel):
    """
    Represents one logical channel carried by a :class:`USXGMII` link.

    Parameters
    ----------
    subport_id : int, optional
        0-based index of this channel within the link. Defaults to 0.

    speed : int
        Speed this channel carries, in megabits per second.
    """

    subport_id: int = Field(default=0, ge=0)
    speed: int = Field(gt=0)


class USXGMII(FLYNCBaseModel):
    """
    Represents a USXGMII-family (64B/66B) interface configuration, carrying one or more logical channels
    over a single serial link.

    Parameters
    ----------
    type : Literal["usxgmii_10g_sxgmii", "usxgmii_5g_sxgmii", "usxgmii_10g_dxgmii", \
    "usxgmii_5g_dxgmii", "usxgmii_10g_qxgmii", "usxgmii_20g_qxgmii", "usxgmii_20g_dxgmii", "usxgmii_20g_oxgmii"]
        Variant, which fixes the number of channels and the maximum speed per channel. The ``sxgmii`` variants
        carry one channel; ``dxgmii``, ``qxgmii`` and ``oxgmii`` carry 2, 4 and 8. Defaults to ``"usxgmii_10g_sxgmii"``.

    mode : Literal["mac", "phy"]
        Operating mode, either MAC or PHY.

    channels : list of :class:`USXGMIIChannel`
        The channels that have a port attached, at least one. List only slots with a port attached; unused slots carry
        idle and are omitted. Every listed channel is occupied by exactly one port: the port carrying the link (the one
        holding this ``mii_config``) takes the channel named by its ``mii_subport_id`` (default 0), and each ``mii_subport_of``
        port takes another. The exception is the uplink port of a channelized port extender, which is a pure lane and occupies none.

    pch_enabled : bool, optional
        Whether the Packet Control Header is used. Only valid on multi-port variants. Defaults to ``False``.

    pch_extension_type : Literal["ignore", "ptp", "preemption_ptp"], optional
        PCH extension field. Requires ``pch_enabled``.

    fec_enabled : bool, optional
        Whether RS-FEC (Clause 108) is used. Defaults to ``False``.

    alignment_marker_interval : int, optional
        Alignment-marker interval in blocks. Defaults to 16400. With ``fec_enabled`` it must be ``80 * n - 4``
        for a positive integer ``n``.
    """

    type: Literal[
        "usxgmii_10g_sxgmii",
        "usxgmii_5g_sxgmii",
        "usxgmii_10g_dxgmii",
        "usxgmii_5g_dxgmii",
        "usxgmii_10g_qxgmii",
        "usxgmii_20g_qxgmii",
        "usxgmii_20g_dxgmii",
        "usxgmii_20g_oxgmii",
    ] = Field(default="usxgmii_10g_sxgmii")
    mode: Literal["mac", "phy"] = Field()
    channels: list[USXGMIIChannel] = Field(min_length=1)
    pch_enabled: bool = Field(default=False)
    pch_extension_type: Optional[Literal["ignore", "ptp", "preemption_ptp"]] = Field(default=None)

    @property
    def speed(self) -> Optional[int]:
        """The link's network speed, when it carries exactly one channel; ``None`` for a multi-port link."""

        return self.channels[0].speed if len(self.channels) == 1 else None

    @model_validator(mode="after")
    def validate_channels(self) -> Self:
        """Validate channel count, subport_id range/uniqueness, and per-channel speed against this variant."""

        variant = _USXGMII_VARIANTS[self.type]
        if len(self.channels) > variant.ports:
            raise err_major(
                "USXGMII '{type}' supports at most {max_channels} channel(s), got {channels}.",
                type=self.type,
                max_channels=variant.ports,
                channels=len(self.channels),
                category=Category.VALUE_RANGE,
                error_number="377",
            )

        validate_list_items_unique([channel.subport_id for channel in self.channels], f"USXGMII '{self.type}' channel subport_id")

        allowed_speeds = {speed for speed in _USXGMII_SPEEDS if speed <= variant.per_port_max}
        for channel in self.channels:
            if channel.subport_id >= variant.ports:
                raise err_major(
                    "USXGMII '{type}' channel subport_id {subport_id} is out of range; valid range is 0..{max_subport_id}.",
                    type=self.type,
                    subport_id=channel.subport_id,
                    max_subport_id=variant.ports - 1,
                    category=Category.VALUE_RANGE,
                    error_number="378",
                )
            if channel.speed not in allowed_speeds:
                raise err_major(
                    "USXGMII '{type}' does not support speed {speed} Mbps on channel {subport_id}. Valid speeds are {valid_speeds}.",
                    type=self.type,
                    speed=channel.speed,
                    subport_id=channel.subport_id,
                    valid_speeds=sorted(allowed_speeds),
                    category=Category.VALUE_RANGE,
                    error_number="379",
                )
        return self

    @model_validator(mode="after")
    def validate_pch(self) -> Self:
        """Validate PCH fields against this variant's PCH capability."""

        if self.pch_extension_type is not None and not self.pch_enabled:
            raise err_major(
                "USXGMII '{type}' sets pch_extension_type without pch_enabled.",
                type=self.type,
                category=Category.CONSISTENCY,
                error_number="380",
            )
        if self.pch_enabled and not _USXGMII_VARIANTS[self.type].pch_capable:
            raise err_major(
                "USXGMII '{type}' does not support the Packet Control Header.",
                type=self.type,
                category=Category.COMPATIBILITY,
                error_number="381",
            )
        return self

    fec_enabled: bool = Field(default=False)
    alignment_marker_interval: int = Field(default=16400, gt=0)

    @model_validator(mode="after")
    def validate_alignment_marker_interval(self) -> Self:
        """With FEC enabled, the alignment-marker interval must satisfy ``80 * n - 4`` for some positive integer ``n``."""

        if self.fec_enabled and (self.alignment_marker_interval + 4) % 80 != 0:
            raise err_major(
                "USXGMII '{type}' has fec_enabled set, so alignment_marker_interval ({interval}) must satisfy 80 * n - 4 for a positive integer n.",
                type=self.type,
                interval=self.alignment_marker_interval,
                category=Category.VALUE_RANGE,
                error_number="382",
            )
        return self


class USGMIIChannel(FLYNCBaseModel):
    """
    Represents one logical channel carried by a :class:`USGMII` link.

    Parameters
    ----------
    subport_id : int, optional
        Position of this channel in the link's round-robin rotation (0..N-1). On a
        multi-port PHY this equals the PHY's network port number. Defaults to 0.

    speed : int
        Highest speed this channel carries, in megabits per second. Rate adaptation
        lets the link run slower, so the port may pair this with a slower MDI.
    """

    subport_id: int = Field(default=0, ge=0)
    speed: int = Field(gt=0)


class USGMII(FLYNCBaseModel):
    """
    Represents a USGMII-family (8B/10B) interface configuration, carrying one or more logical channels
    over a single serial link.

    Parameters
    ----------
    type : Literal["q_usgmii", "o_usgmii"]
        Variant, which fixes the number of channels: ``q_usgmii`` carries 4, ``o_usgmii`` carries 8. Defaults to ``"q_usgmii"``.

    mode : Literal["mac", "phy"]
        Operating mode, either MAC or PHY.

    channels : list of :class:`USGMIIChannel`
        The channels that have a port attached, at least one. List only slots with a port attached; unused slots carry
        idle and are omitted. Every listed channel is occupied by exactly one port: the port carrying the link (the one
        holding this ``mii_config``) takes the channel named by its ``mii_subport_id`` (default 0), and each ``mii_subport_of``
        port takes another. The exception is the uplink port of a channelized port extender, which is a pure lane and occupies none.

    pch_enabled : bool, optional
        Whether the Packet Control Header is used. Defaults to ``False``.

    pch_extension_type : Literal["ignore", "ptp", "preemption_ptp"], optional
        PCH extension field. Requires ``pch_enabled``.
    """

    type: Literal["q_usgmii", "o_usgmii"] = Field(default="q_usgmii")
    mode: Literal["mac", "phy"] = Field()
    channels: list[USGMIIChannel] = Field(min_length=1)
    pch_enabled: bool = Field(default=False)
    pch_extension_type: Optional[Literal["ignore", "ptp", "preemption_ptp"]] = Field(default=None)

    @property
    def speed(self) -> Optional[int]:
        """The link's network speed, when it carries exactly one channel; ``None`` for a multi-port link."""

        return self.channels[0].speed if len(self.channels) == 1 else None

    @model_validator(mode="after")
    def validate_channels(self) -> Self:
        """Validate channel count, subport_id range/uniqueness, and per-channel speed against this variant."""

        variant = _USGMII_VARIANTS[self.type]
        if len(self.channels) > variant.ports:
            raise err_major(
                "USGMII '{type}' supports at most {max_channels} channel(s), got {channels}.",
                type=self.type,
                max_channels=variant.ports,
                channels=len(self.channels),
                category=Category.VALUE_RANGE,
                error_number="404",
            )

        validate_list_items_unique([channel.subport_id for channel in self.channels], f"USGMII '{self.type}' channel subport_id")

        allowed_speeds = {speed for speed in _USGMII_SPEEDS if speed <= variant.per_port_max}
        for channel in self.channels:
            if channel.subport_id >= variant.ports:
                raise err_major(
                    "USGMII '{type}' channel subport_id {subport_id} is out of range; valid range is 0..{max_subport_id}.",
                    type=self.type,
                    subport_id=channel.subport_id,
                    max_subport_id=variant.ports - 1,
                    category=Category.VALUE_RANGE,
                    error_number="405",
                )
            if channel.speed not in allowed_speeds:
                raise err_major(
                    "USGMII '{type}' does not support speed {speed} Mbps on channel {subport_id}. Valid speeds are {valid_speeds}.",
                    type=self.type,
                    speed=channel.speed,
                    subport_id=channel.subport_id,
                    valid_speeds=sorted(allowed_speeds),
                    category=Category.VALUE_RANGE,
                    error_number="406",
                )
        return self

    @model_validator(mode="after")
    def validate_pch(self) -> Self:
        """Validate that a PCH extension type is only set together with ``pch_enabled``."""

        if self.pch_extension_type is not None and not self.pch_enabled:
            raise err_major(
                "USGMII '{type}' sets pch_extension_type without pch_enabled.",
                type=self.type,
                category=Category.CONSISTENCY,
                error_number="407",
            )
        return self


MULTI_SPEED_MIIS = (MII, RMII, SGMII, RGMII, USXGMII, USGMII)

XMIIConfig = MII | RMII | SGMII | RGMII | XFI | USXGMII | USGMII
"""Every xMII configuration a port, interface or extender uplink can carry."""


def xmii_channel_capacity(mii_config: XMIIConfig) -> int:
    """
    Tell how many channels (ports) an xMII can carry.

    A USXGMII or USGMII variant carries as many channels as its variant has ports; every other xMII is single-port.

    Args:
        mii_config: The xMII configuration to inspect.

    Returns:
        int: The number of channels, 1 for a single-port interface.
    """

    if isinstance(mii_config, USXGMII):
        return _USXGMII_VARIANTS[mii_config.type].ports
    if isinstance(mii_config, USGMII):
        return _USGMII_VARIANTS[mii_config.type].ports
    return 1


def mii_carries_mdi_speed(mii_config: XMIIConfig, mdi_speed: int, mii_speed: Optional[int] = None) -> bool:
    """
    Tell whether an xMII can carry an MDI running at ``mdi_speed``.

    A multi-speed xMII (see ``MULTI_SPEED_MIIS``) treats its speed as a ceiling the MDI may sit below; any other xMII
    (XFI) runs at one speed only, so the two must be equal.

    Args:
        mii_config: The xMII configuration whose type decides the rule.

        mdi_speed (int): Speed of the MDI, in megabits per second.

        mii_speed (int, optional): Speed to compare against. Defaults to ``mii_config.speed``; pass a channel's speed to
            check one channel of a multi-port link.

    Returns:
        bool: ``True`` if the xMII can carry the MDI speed. An xMII that declares no speed carries any.
    """

    mii_speed = mii_config.speed if mii_speed is None else mii_speed
    if mii_speed is None:
        return True
    if isinstance(mii_config, MULTI_SPEED_MIIS):
        return mdi_speed <= mii_speed
    return mdi_speed == mii_speed
