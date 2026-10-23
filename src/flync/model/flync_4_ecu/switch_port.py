"""Defines the automotive Ethernet Switch Port for FLYNC"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, List, Literal, Optional, Self

from pydantic import (
    AfterValidator,
    BeforeValidator,
    Field,
    model_validator,
)

from flync.core.base_models.base_model import FLYNCBaseModel
from flync.core.utils.exceptions import Category, err_minor
from flync.core.validators import traffic_classes as traffic_class_validators
from flync.core.validators.connection_compatibility import validate_cbs_idleslopes_fit_portspeed
from flync.core.validators.generic import (
    none_to_empty_list,
    validate_or_remove,
)
from flync.model.flync_4_ecu.mii import MII, RGMII, RMII, SGMII, USGMII, USXGMII, XFI
from flync.model.flync_4_ecu.phy import BASET, BASET1, BASET1S
from flync.model.flync_4_ecu.port_extender import PortExtender
from flync.model.flync_4_security import MACsecConfig
from flync.model.flync_4_tsn import (
    PTPConfig,
    Stream,
    TrafficClass,
)

if TYPE_CHECKING:
    from flync.model.flync_4_ecu.controller import EthernetInterface
    from flync.model.flync_4_ecu.port import ECUPort
    from flync.model.flync_4_ecu.switch import Switch


class SwitchPort(FLYNCBaseModel):
    """
    Represents a Switch Port and its configuration.

    Parameters
    ----------
    name : str
        Name of the Switch Port.

    silicon_port_no : int
        Silicon hardware port number (vendor-specific).
        Must be greater or equal to 0.

    default_vlan_id : int
        VLAN ID to be added to an untagged frame ingressing on the port (>= 0 and <= 4095).
        Use ``None`` for an untagged port (no default VLAN).

    mii_config : :class:`~flync.model.flync_4_ecu.mii.MII` or :class:`~flync.model.flync_4_ecu.mii.RMII` or \
    :class:`~flync.model.flync_4_ecu.mii.SGMII` or :class:`~flync.model.flync_4_ecu.mii.RGMII` or \
    :class:`~flync.model.flync_4_ecu.mii.XFI` or :class:`~flync.model.flync_4_ecu.mii.USXGMII` or \
    :class:`~flync.model.flync_4_ecu.mii.USGMII`, optional
        Media-independent interface configuration. ``None`` when this port is instead a channel of a
        sibling port's multi-port link; see ``mii_subport_of``.

    mii_subport_of : str, optional
        Name of a sibling :class:`SwitchPort` on this switch that carries a multi-port
        :class:`~flync.model.flync_4_ecu.mii.USXGMII`/:class:`~flync.model.flync_4_ecu.mii.USGMII` link, of which
        this port is one channel. Mutually exclusive with ``mii_config``. The port carrying the link occupies a channel too.

    mii_subport_id : int, optional
        Which channel this port occupies, matching a ``channels[*].subport_id`` of the link. With ``mii_subport_of`` it names
        the channel of that sibling's link; on the port that carries the link itself it names that port's own channel and
        defaults to 0.

    ptp_config : :class:`~flync.model.flync_4_tsn.PTPConfig`, optional
        Precision Time Protocol configuration.

    ingress_streams : list of :class:`~flync.model.flync_4_tsn.Stream`, optional
        Stream-based IEEE 802.1Qci configuration.

    traffic_classes : list of :class:`~flync.model.flync_4_tsn.TrafficClass`, optional
        Traffic class definitions and traffic shaping configuration applied to egress port queues.

    macsec_config : :class:`~flync.model.flync_4_security.MACsecConfig`, optional
        MACsec configuration for the port.

    Private Attributes
    ------------------
    _type :
        The type of the object generated. Set to controller_interface.

    _port_extender : :class:`~flync.model.flync_4_ecu.port_extender.PortExtender`
        The extender this port sits on, ``None`` for a native port. Managed internally.

    _mdi_config : :class:`~flync.model.flync_4_ecu.phy.BASET1` or :class:`~flync.model.flync_4_ecu.phy.BASET1S` or \
    :class:`~flync.model.flync_4_ecu.phy.BASET`

    _connected_component:
        The switch port, controller interface or ecu port connected to the switch port.
        This attribute is managed internally and is not part of the public API.

    """

    name: str = Field(min_length=1)
    silicon_port_no: int = Field(ge=0)
    default_vlan_id: int = Field(..., ge=0, le=4095)
    mii_config: Optional[MII | RMII | SGMII | RGMII | XFI | USXGMII | USGMII] = Field(default=None, discriminator="type")
    mii_subport_of: Optional[str] = Field(default=None)
    mii_subport_id: Optional[int] = Field(default=None, ge=0)
    ptp_config: Annotated[
        Optional[PTPConfig],
        BeforeValidator(validate_or_remove("PTP config", PTPConfig)),
    ] = Field(default=None)
    ingress_streams: Annotated[
        Optional[List[Stream]],
        BeforeValidator(validate_or_remove("ingress streams", List[Stream])),
        BeforeValidator(none_to_empty_list),
    ] = Field(default=[])
    traffic_classes: Annotated[
        Optional[List[TrafficClass]],
        AfterValidator(traffic_class_validators.validate_traffic_classes),
        BeforeValidator(validate_or_remove("traffic classes", List[TrafficClass])),
        BeforeValidator(none_to_empty_list),
    ] = Field(default=[])
    macsec_config: Annotated[
        Optional[MACsecConfig],
        BeforeValidator(validate_or_remove("MACsec config", MACsecConfig)),
    ] = Field(default=None)
    _mdi_config: BASET1 | BASET1S | BASET | None = None
    _connected_component: ECUPort | EthernetInterface | SwitchPort | PortExtender | None = None
    _type: Literal["switch_port"] = "switch_port"
    _switch: Optional[Switch] = None
    _port_extender: Optional[PortExtender] = None

    @property
    def mdi_config(self) -> BASET1 | BASET1S | BASET | None:
        return self._mdi_config

    @property
    def port_extender(self) -> Optional[PortExtender]:
        """The extender this port sits on, or ``None``."""
        return self._port_extender

    @property
    def type(self) -> Literal["switch_port"]:
        return self._type

    @property
    def connected_component(self) -> ECUPort | EthernetInterface | SwitchPort | PortExtender | None:
        return self._connected_component

    @property
    def switch(self) -> Optional[Switch]:
        return self._switch

    @model_validator(mode="after")
    def validate_traffic_classes(self) -> Self:
        if self.mii_config and self.mii_config.speed is not None and self.traffic_classes:
            validate_cbs_idleslopes_fit_portspeed(
                self.traffic_classes,
                self.mii_config.speed,
            )
        return self

    def copy_mdi_config_to_switch(self, mdi_config: BASET1 | BASET1S | BASET) -> None:
        """
        Helper function.
        Copies the MDI config from ECU port to switch port.
        """

        self._mdi_config = mdi_config

    def get_switch(self) -> Switch:
        """
        Helper function.
        Returns the switch that the port is a part of.
        """

        if self._switch is None:
            raise err_minor(f"The switch port {self.name} is not a part of any switch", category=Category.STRUCTURAL, error_number="087")
        return self._switch

    def get_vlan_connected_ports(self, vlan: int | None) -> list[SwitchPort]:
        """
        Helper function.
        Returns the switch ports that are part of the same VLAN as that port.
        """

        ports = []
        for vlan_entry in self.get_switch().vlans:
            if vlan_entry.id == vlan:
                ports.extend(vlan_entry.ports)
        ports_obj = [sp for sport in ports for sp in self.get_switch().ports if sp.name == sport]
        return ports_obj

    def is_part_of_vlan(self, vlan: int | None) -> bool:
        for vlan_entry in self.get_switch().vlans:
            if vlan_entry.id == vlan and self.name in vlan_entry.ports:
                return True
        return False
