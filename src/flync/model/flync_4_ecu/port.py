"""Defines the ECU Port model for FLYNC"""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, Literal, Optional, Self

from pydantic import Field, model_validator

if TYPE_CHECKING:
    from flync.model.flync_4_ecu.controller import EthernetInterface
    from flync.model.flync_4_ecu.ecu import ECU
    from flync.model.flync_4_ecu.switch import SwitchPort

from flync.core.base_models import FLYNCBaseModel
from flync.core.utils.exceptions import Category, err_major
from flync.model.flync_4_ecu.mii import (
    MII,
    RGMII,
    RMII,
    SGMII,
    USGMII,
    USXGMII,
    XFI,
    mii_carries_mdi_speed,
)
from flync.model.flync_4_ecu.phy import BASET, BASET1, BASET1S


class ECUPort(FLYNCBaseModel):
    """
    Represents an ECU port and its configuration.

    This class encapsulates both the media-dependent (MDI) and media-independent (MII) interface configurations for a port.

    Parameters
    ----------
    name : str
        Name of the ECU port.

    mdi_config : :class:`~flync.model.flync_4_ecu.phy.BASET1` or :class:`~flync.model.flync_4_ecu.phy.BASET1S` or \
    :class:`~flync.model.flync_4_ecu.phy.BASET`
        Media-dependent interface configuration, such as BASE-T1, BASE-T1S or BASE-T.

    mii_config : :class:`~flync.model.flync_4_ecu.mii.MII` or :class:`~flync.model.flync_4_ecu.mii.RMII` or \
    :class:`~flync.model.flync_4_ecu.mii.SGMII` or :class:`~flync.model.flync_4_ecu.mii.RGMII` or \
    :class:`~flync.model.flync_4_ecu.mii.XFI` or :class:`~flync.model.flync_4_ecu.mii.USXGMII` or \
    :class:`~flync.model.flync_4_ecu.mii.USGMII`, optional
        Media-independent interface configuration. ``None`` when this port is instead a channel of a
        sibling port's multi-port link; see ``mii_subport_of``.

    mii_subport_of : str, optional
        Name of a sibling :class:`ECUPort` on this ECU that carries a multi-port
        :class:`~flync.model.flync_4_ecu.mii.USXGMII`/:class:`~flync.model.flync_4_ecu.mii.USGMII` link, of which
        this port is one channel. Mutually exclusive with ``mii_config``. The port carrying the link occupies a channel too.

    mii_subport_id : int, optional
        Which channel this port occupies, matching a ``channels[*].subport_id`` of the link. With ``mii_subport_of`` it names
        the channel of that sibling's link; on the port that carries the link itself it names that port's own channel and
        defaults to 0.

    Private Attributes
    ------------------
    _ecu :
        The ECU of which the ECU Port is a part of.
    _connected_component:
        The switch port, controller interface or ecu port connected to the controller interface. This attribute
        is managed internally and is not part of the public API.
    _type:
        The type of the object generated. Set to ecu_port.
    """

    name: str = Field(min_length=1)
    mdi_config: BASET1 | BASET1S | BASET = Field(
        default_factory=BASET1,
        discriminator="mode",
        description="how to use this",
    )
    mii_config: Optional[MII | RMII | SGMII | RGMII | XFI | USXGMII | USGMII] = Field(default=None, discriminator="type")
    mii_subport_of: Optional[str] = Field(default=None)
    mii_subport_id: Optional[int] = Field(default=None, ge=0)
    _ecu: ECU | None = None
    _connected_components: list[SwitchPort | EthernetInterface | ECUPort] = []
    _type: Literal["ecu_port"] = "ecu_port"

    @property
    def ecu(self) -> ECU | None:
        return self._ecu

    @property
    def qualified_name(self) -> str:
        """``<ecu>:<port>`` for messages, or just the port name while the port is not yet bound to its ECU."""
        return f"{self._ecu.name}:{self.name}" if self._ecu is not None else self.name

    @property
    def type(self) -> Literal["ecu_port"]:
        return self._type

    @property
    def connected_components(self) -> list[SwitchPort | EthernetInterface | ECUPort]:
        return self._connected_components

    @model_validator(mode="after")
    def verify_mdi_and_mii_config_speeds_are_compatible(self) -> Self:
        """
        Ensure the MDI speed is one the MII configuration can carry.

        MII, RMII, SGMII and RGMII each cover a range of link speeds, by scaling their clock (MII, RGMII) or by
        replicating symbols at a fixed rate (RMII, SGMII), so their ``speed`` is a ceiling the MDI may sit below.
        XFI runs at 10G only, so there the two speeds have to be equal. USXGMII/USGMII only have a single
        ``speed`` when they carry one channel; a multi-port link has no single speed to compare against the
        MDI, so the check is skipped.
        """

        if self.mii_config is None or self.mii_config.speed is None:
            return self

        if not mii_carries_mdi_speed(self.mii_config, self.mdi_config.speed):
            raise err_major(
                f"MII and MDI config should have a compatible speed in ECU Ports. Port {self.name}",
                category=Category.CONSISTENCY,
                error_number="081",
            )
        return self

    def get_internal_connected_component(self, ecus: object = None) -> SwitchPort | EthernetInterface | None:
        """
        Return the component inside the ECU connected  to the ECU Port.

        Args:
            ecus: Deprecated and ignored, kept for backwards compatibility. Will be removed in a future release.
        """
        if ecus is not None:
            warnings.warn(
                "The 'ecus' argument of ECUPort.get_internal_connected_component() is ignored and deprecated; omit it.",
                DeprecationWarning,
                stacklevel=2,
            )

        return next(
            (c for c in self._connected_components if c.type != "ecu_port"),
            None,
        )
