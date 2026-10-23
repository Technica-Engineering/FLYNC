"""Defines the automotive Ethernet Switch and its components for FLYNC"""

from __future__ import annotations

from collections.abc import Collection
from typing import (
    TYPE_CHECKING,
    Annotated,
    List,
    Literal,
    Optional,
    Self,
)

from pydantic import (
    AfterValidator,
    BeforeValidator,
    Field,
    SerializationInfo,
    StrictInt,
    field_serializer,
    field_validator,
    model_validator,
)

from flync.core.annotations import (
    External,
    Implied,
    ImpliedStrategy,
    NamingStrategy,
    OutputStrategy,
)
from flync.core.base_models.base_model import FLYNCBaseModel
from flync.core.datatypes import Bitmask
from flync.core.datatypes.macaddress import FLYNCMacAddress
from flync.core.utils.exceptions import Category, err_major, err_minor, warn
from flync.core.validators import traffic_classes as traffic_class_validators
from flync.core.validators.address import validate_vlan_id
from flync.core.validators.connection_compatibility import (
    validate_cbs_idleslopes_fit_portspeed,
    validate_compulsory_mii_config_compatibility,
    validate_mii_subports,
)
from flync.core.validators.generic import (
    none_to_empty_list,
    validate_elements_in,
    validate_list_items_unique,
    validate_or_remove,
)
from flync.model.flync_4_ecu.controller import Controller
from flync.model.flync_4_ecu.mii import MII, RGMII, RMII, SGMII, USGMII, USXGMII, XFI, XMIIConfig, xmii_channel_capacity
from flync.model.flync_4_ecu.phy import BASET, BASET1, BASET1S
from flync.model.flync_4_ecu.port_extender import PortExtender
from flync.model.flync_4_ecu.vlan_entry import VLANEntry
from flync.model.flync_4_metadata import EmbeddedMetadata
from flync.model.flync_4_security import MACsecConfig
from flync.model.flync_4_tsn import (
    FrameFilter,
    PTPConfig,
    Stream,
    TrafficClass,
)

if TYPE_CHECKING:
    from flync.model.flync_4_ecu.controller import EthernetInterface
    from flync.model.flync_4_ecu.port import ECUPort


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


class PortScopedAction(FLYNCBaseModel):
    """
    Base class for TCAM actions whose ``ports`` list defaults to all switch ports
    when left empty or undefined.

    The expanded port list is made available at runtime (see
    :meth:`Switch._fill_empty_tcam_port_lists`), while the field serializer ensures
    serialization reflects the user's original input: an empty list is dumped as an
    empty list, and an omitted list stays omitted (under ``exclude_unset``).

    Parameters
    ----------
    ports : list of str, optional
        Switch ports to which this action applies. Defaults to all ports if omitted.
    """

    ports: Annotated[List[str], BeforeValidator(none_to_empty_list)] = Field(default_factory=list)
    _ports_autofilled: bool = False

    @field_serializer("ports", check_fields=False)
    def serialize_ports(self, ports: List[str], _info: SerializationInfo) -> list[str]:
        """Dump the user's original port list, not the runtime-expanded one."""
        return [] if self._ports_autofilled else ports


class Drop(PortScopedAction):
    """
    Action that discards traffic on the selected egress ports.

    Parameters
    ----------
    type : Literal["drop"]
        Discriminator used by Pydantic.

    ports : list of str, Optional
        Egress ports where the drop action should be applied. Defaults to all ports of the switch if kept empty or undefined.
    """

    type: Literal["drop"] = Field(default="drop")


class Mirror(PortScopedAction):
    """
    Action that mirrors incoming traffic to additional egress ports.

    Parameters
    ----------
    type : Literal["mirror"]
        Discriminator used by Pydantic.

    ports : list of str, Optional
        Egress ports that will receive the mirrored traffic. Defaults to all ports of the switch if kept empty or undefined.
    """

    type: Literal["mirror"] = Field(default="mirror")


class ForceEgress(PortScopedAction):
    """
    Action that forces a packet to leave through a given set of ports, bypassing the normal forwarding decision.

    Parameters
    ----------
    type : Literal["force_egress"]
        Discriminator used by Pydantic.

    ports : list of str, Optional
        Egress ports to which the messages are force-forwarded. Defaults to all ports of the switch if kept empty or undefined.
    """

    type: Literal["force_egress"] = Field(default="force_egress")


class VLANOverwrite(PortScopedAction):
    """
    Action that overwrites VLAN ID and/or PCP values on selected ports.

    Parameters
    ----------
    type : Literal["vlan_overwrite"]
        Discriminator used by Pydantic.

    overwrite_vlan_id : int, optional
        New VLAN identifier (0-4095).
        If ``None``, the VLAN ID is left unchanged.

    overwrite_vlan_pcp : int, optional
        New PCP value (0-7). If ``None``, the PCP value is left unchanged.

    ports : list of str, Optional
        Egress ports at which the overwriting should take place. Defaults to all ports of the switch if kept empty or undefined.
    """

    type: Literal["vlan_overwrite"] = Field(default="vlan_overwrite")
    overwrite_vlan_id: Annotated[Optional[int], AfterValidator(validate_vlan_id)] = Field(default=None)
    overwrite_vlan_pcp: Optional[int] = Field(default=None)


class RemoveVLAN(PortScopedAction):
    """
    Action that removes the VLAN tag from packets on the given ports.

    Parameters
    ----------
    type : Literal["remove_vlan"]
        Discriminator used by Pydantic.

    ports : list of str, Optional
        Egress ports where the VLAN tag will be removed. Defaults to all ports of the switch if kept empty or undefined.
    """

    type: Literal["remove_vlan"] = Field(default="remove_vlan")


class FrameMask(Bitmask):
    """
    Byte-level pattern matching of an Ethernet frame, i.e. a :class:`~flync.core.datatypes.Bitmask` bound to a frame position.

    A frame matches if ``(frame[offset:offset + byte_length] & mask) == data``, e.g. a
    two-byte pattern at ``offset=12`` matches on the EtherType field.

    Parameters
    ----------

    offset : int
        Byte position in the frame where the pattern match begins.
        Must be greater or equal to 0.
    """

    offset: int = Field(ge=0)

    @property
    def byte_length(self) -> int:
        """Number of frame bytes inspected, derived from the bit width of the ``data`` literal."""
        return -(-self._width // 8)


class TCAMRule(FLYNCBaseModel):
    """
    Definition of a TCAM (ternary content-addressable memory) rule for a
    switch.

    Parameters
    ----------
    name : str
        Name for the description of the TCAM rule (minimum length 1).

    id : StrictInt
        Unique TCAM rule ID.
        Must be greater or equal to 0.

    match_filter : :class:`~flync.model.flync_4_tsn.FrameFilter`, optional
        Packet-matching filter for layer-based matching on MAC/IP/VLAN/ports.
        Mutually exclusive with ``frame_mask``.

    frame_mask : list of :class:`~FrameMask`, optional
        Packet-matching criteria for byte-level pattern matching on raw frame data.
        The masks of one rule must inspect disjoint byte ranges of the frame.

    frame_window : int, optional
        Maximum number of leading frame bytes the ``frame_mask`` entries may inspect.
        Unbounded when omitted.
        Must be greater or equal to 1.

    match_ports : list of str, Optional
        Ports to which the rule is bound. Defaults to all ports of the switch if kept empty or undefined.

    action : list of :class:`Drop` or :class:`Mirror` or :class:`ForceEgress` or :class:`VLANOverwrite` or :class:`RemoveVLAN`
        One or more actions performed when the rule matches.
        The ``type`` field of each action class acts as the discriminating key for Pydantic.

        A single port must not be targeted by more than one of *drop*, *force_egress* or
        *mirror*, nor by more than one of *remove_vlan* or *vlan_overwrite*.

    vehicle_state : :class:`~flync.core.datatypes.Bitmask`, optional
        Vehicle-state pattern the rule is gated on: it applies only when
        ``(current_state & vehicle_state.mask) == vehicle_state.data``. Both ``data`` and
        ``mask`` must fit in the 8-bit vehicle-state register. ``None`` (default) means the
        rule is not gated on vehicle state.
    """

    name: str = Field(min_length=1)
    id: StrictInt = Field(ge=0)
    match_filter: Optional[FrameFilter] = Field(default=None)
    frame_mask: Annotated[Optional[List[FrameMask]], BeforeValidator(none_to_empty_list)] = Field(default_factory=list)
    frame_window: Optional[int] = Field(default=None, ge=1)
    match_ports: Annotated[List[str], BeforeValidator(none_to_empty_list)] = Field(default_factory=list)
    action: Annotated[List[(Drop | Mirror | VLANOverwrite | ForceEgress | RemoveVLAN)], BeforeValidator(none_to_empty_list)] = Field(
        default_factory=list
    )
    vehicle_state: Optional[Bitmask] = Field(default=None)
    _match_ports_autofilled: bool = False

    @field_serializer("match_ports")
    def serialize_match_ports(self, match_ports: List[str], _info: SerializationInfo) -> list[str]:
        """Dump the user's original port list, not the runtime-expanded one."""
        return [] if self._match_ports_autofilled else match_ports

    @field_validator("vehicle_state")
    @classmethod
    def validate_vehicle_state_range(cls, value: Optional[Bitmask]) -> Optional[Bitmask]:
        """``vehicle_state`` is matched against an 8-bit register, so both ``data`` and ``mask`` must fit in a byte."""
        if value is not None and max(value.data, value.mask or 0) > 0xFF:
            raise err_minor(
                f"'vehicle_state' data and mask must each be <= 0xFF (255); got data={value.data}, mask={value.mask}",
                category=Category.VALUE_RANGE,
                error_number="231",
            )
        return value

    @model_validator(mode="after")
    def validate_match_filter_or_mask_exclusive(self) -> Self:
        """Validate that a rule matches either on layers (``match_filter``) or on raw bytes (``frame_mask``), not on both."""

        if self.match_filter is not None and self.frame_mask:
            raise err_minor("Cannot specify both match_filter and frame_mask; use only one", category=Category.STRUCTURAL, error_number="183")
        return self

    @model_validator(mode="after")
    def validate_frame_masks(self) -> Self:
        """Validate that the frame masks inspect disjoint byte ranges and stay inside ``frame_window``."""

        if self.frame_window is not None and not self.frame_mask:
            warn(
                f"TCAM rule {self.name}: 'frame_window' is defined but frame_mask is not. The frame window is not processed in this case.",
                category=Category.COMPATIBILITY,
                error_number="235",
            )

        masks = sorted(self.frame_mask or [], key=lambda frame_mask: frame_mask.offset)
        for previous, current in zip(masks, masks[1:]):
            if current.offset < previous.offset + previous.byte_length:
                raise err_minor(
                    f"TCAM rule {self.name}: frame_masks must not overlap; the mask at offset {previous.offset} covers "
                    f"{previous.byte_length} byte(s) and overlaps the mask at offset {current.offset}.",
                    category=Category.CONSISTENCY,
                    error_number="232",
                )

        for frame_mask in masks:
            if self.frame_window is not None and frame_mask.offset + frame_mask.byte_length > self.frame_window:
                raise err_minor(
                    f"TCAM rule {self.name}: the frame_mask at offset {frame_mask.offset} covers {frame_mask.byte_length} byte(s) and "
                    f"thus exceeds the frame_window of {self.frame_window} byte(s).",
                    category=Category.VALUE_RANGE,
                    error_number="233",
                )
        return self

    @model_validator(mode="after")
    def validate_exclusive_drop_force_mirror(self) -> Self:
        """Validate that no port is targeted by more than one of the mutually-exclusive actions *drop*, *force_egress* or *mirror*."""
        self._check_exclusive_drop_force_mirror()
        return self

    def _check_exclusive_drop_force_mirror(self) -> None:
        all_ports: list[str] = []
        for action in self.action or []:
            if action.type in ["drop", "force_egress", "mirror"]:
                all_ports += action.ports or []

        if len(all_ports) != len(set(all_ports)):
            raise err_minor(
                "A TCAM Rule can either drop OR force egress OR mirror on one port.",
                category=Category.CONSISTENCY,
                error_number="088",
            )

    @model_validator(mode="after")
    def validate_exclusive_vlan_action(self) -> Self:
        """Validate that no port is targeted by both VLAN actions *remove_vlan* and *vlan_overwrite*."""
        self._check_exclusive_vlan_action()
        return self

    def _check_exclusive_vlan_action(self) -> None:
        all_ports: list[str] = []
        for action in self.action or []:
            if action.type in ["remove_vlan", "vlan_overwrite"]:
                all_ports += action.ports or []

        if len(all_ports) != len(set(all_ports)):
            raise err_minor(
                "A TCAM Rule can either remove OR overwrite a vlan on one port.",
                category=Category.CONSISTENCY,
                error_number="089",
            )


class SwitchConfig(FLYNCBaseModel):
    """
    Core switch configuration data stored in ``switch.flync.yaml``.

    This model holds the switch metadata, ports, VLANs, and TCAM rules.
    It is loaded from the ``switch.flync.yaml`` file inside each switch folder.

    Parameters
    ----------
    meta : :class:`~flync.model.flync_4_metadata.metadata.EmbeddedMetadata`
        Metadata associated with the switch.

    ports : list of :class:`SwitchPort`
        List of switch ports, including those that sit on port extenders.

    vlans : list of :class:`~flync.model.flync_4_ecu.vlan_entry.VLANEntry`
        List of VLAN entries configured on the switch.

    tcam_rules : list of :class:`TCAMRule`, optional
        List of TCAM rules configured on the switch.
    dynamic_address_aging_time : int, optional
        Aging time, in seconds, for dynamically learned address entries in the switch's Filtering Database (FDB).
        A learned MAC address is removed if no matching frame is seen within this interval.
        Must be a positive value.

    port_extenders : list of :class:`~flync.model.flync_4_ecu.port_extender.PortExtender`, optional
        Port extenders controlled by this switch. Each lists the names of its ports from ``ports``.
    """

    meta: EmbeddedMetadata = Field()
    tcam_rules: Annotated[
        Optional[List[TCAMRule]],
        BeforeValidator(none_to_empty_list),
    ] = Field(default=[])
    ports: List[SwitchPort] = Field()
    vlans: List[VLANEntry] = Field()
    dynamic_address_aging_time: Optional[StrictInt] = Field(default=None, gt=0)
    port_extenders: Annotated[
        Optional[List[PortExtender]],
        BeforeValidator(none_to_empty_list),
    ] = Field(default_factory=list)


class Switch(FLYNCBaseModel):
    """
    Represents an automotive Ethernet network switch configuration.

    Parameters
    ----------
    name : str
        Name of the switch. Implied from the folder name.

    switch_config : :class:`SwitchConfig`
        The core switch configuration loaded from ``switch.flync.yaml``.

    host_controller : :class:`~flync.model.flync_4_ecu.controller.Controller`, optional
        The host controller managing the switch, stored in the
        ``switch_host_controller/`` sub-folder.
    """

    name: Annotated[
        str,
        Implied(strategy=ImpliedStrategy.FOLDER_NAME),
    ] = Field()
    switch_config: Annotated[
        SwitchConfig,
        External(
            output_structure=OutputStrategy.SINGLE_FILE | OutputStrategy.OMMIT_ROOT,
            naming_strategy=NamingStrategy.FIXED_PATH,
            path="switch",
        ),
    ] = Field()
    host_controller: Annotated[
        Optional[Controller],
        External(
            output_structure=OutputStrategy.FOLDER,
            naming_strategy=NamingStrategy.FIXED_PATH,
            path="switch_host_controller",
        ),
    ] = Field(default=None)

    @property
    def meta(self) -> EmbeddedMetadata:
        """Proxy to the underlying switch config metadata."""
        return self.switch_config.meta

    @property
    def tcam_rules(self) -> Optional[List[TCAMRule]]:
        """Proxy to the underlying switch config TCAM rules."""
        return self.switch_config.tcam_rules

    @property
    def ports(self) -> List[SwitchPort]:
        """Proxy to the underlying switch config ports."""
        return self.switch_config.ports

    @property
    def vlans(self) -> List[VLANEntry]:
        """Proxy to the underlying switch config VLANs."""
        return self.switch_config.vlans

    @property
    def port_extenders(self) -> List[PortExtender]:
        """Proxy to the underlying switch config port extenders."""
        return self.switch_config.port_extenders or []

    @model_validator(mode="after")
    def validate_unique_port_number(self) -> Self:
        """
        Validate if the silicon port numbers for all the different switch ports are unique

        Raises:
            Validation error if a silicon port number is repeated
        """

        silicon_port_numbers = []
        for port in self.ports:
            silicon_port_numbers.append(port.silicon_port_no)
        validate_list_items_unique(
            silicon_port_numbers,
            "Switch Ports (silicon_port_number)",
        )
        return self

    @model_validator(mode="after")
    def validate_unique_port_names(self) -> Self:
        """Validate port names are unique across this switch's ports."""
        validate_list_items_unique(
            [p.name for p in self.ports],
            "Switch Ports (name)",
        )
        return self

    @property
    def extender_uplink_ports(self) -> frozenset[str]:
        """Names of the switch ports that terminate an extender uplink."""
        return frozenset(extender.uplink.switch_port_name for extender in self.port_extenders or [])

    @model_validator(mode="after")
    def validate_unique_extender_names(self) -> Self:
        """
        Validate that extender names are unique within this switch.

        Raises:
            err_major: Two extenders share a name.
        """

        validate_list_items_unique([extender.name for extender in self.port_extenders], "Port Extenders (name)")
        return self

    @model_validator(mode="after")
    def validate_extender_ports(self) -> Self:
        """
        Validate that every listed extender port is a port of this switch and is listed once.

        Raises:
            err_major: An extender lists an unknown port.

            err_major: A port is listed twice.
        """

        names = {port.name for port in self.ports}
        for extender in self.port_extenders:
            for name in extender.ports:
                if name not in names:
                    raise err_major(
                        "Port extender '{extender}' lists port '{port}', which is not a port of this switch.",
                        extender=extender.name,
                        port=name,
                        category=Category.REFERENCE,
                        error_number="391",
                    )
        validate_list_items_unique([name for extender in self.port_extenders for name in extender.ports], "Port Extenders (ports)")
        return self

    @model_validator(mode="after")
    def validate_extender_uplinks(self) -> Self:
        """
        Validate the uplink port of every extender.

        Raises:
            err_major: Two extenders share an uplink port.

            err_major: The uplink port is not a port of this switch.

            err_major: The uplink port sits on another extender (cascading is not supported).
        """

        validate_list_items_unique([extender.uplink.switch_port_name for extender in self.port_extenders], "Port Extenders (uplink switch_port)")
        names = {port.name for port in self.ports}
        for extender in self.port_extenders:
            name = extender.uplink.switch_port_name
            if name not in names:
                raise err_major(
                    "Uplink port '{port}' of extender '{extender}' is not a port of this switch.",
                    port=name,
                    extender=extender.name,
                    category=Category.REFERENCE,
                    error_number="392",
                )
            parent = next((other for other in self.port_extenders if name in other.ports), None)
            if parent is not None:
                raise err_major(
                    "Uplink port '{port}' of extender '{extender}' is itself a port of extender '{parent}'. Cascading extenders are not supported.",
                    port=name,
                    extender=extender.name,
                    parent=parent.name,
                    category=Category.COMPATIBILITY,
                    error_number="393",
                )
        return self

    @model_validator(mode="after")
    def validate_extender_port_channels(self) -> Self:
        """
        Validate how an extender port reaches the uplink.

        On a channelized uplink a port needs ``mii_subport_of`` (the uplink port) and ``mii_subport_id``. On a tagged uplink it sets neither
        nor ``mii_config``.

        Raises:
            err_major: A channelized extender port lacks ``mii_subport_of`` or ``mii_subport_id``.

            err_major: A tagged extender port sets ``mii_config``, ``mii_subport_of`` or ``mii_subport_id``.
        """

        by_name = {port.name: port for port in self.ports}
        for extender in self.port_extenders:
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
        return self

    @model_validator(mode="after")
    def validate_extender_uplink_links(self) -> Self:
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

        by_name = {port.name: port for port in self.ports}
        for extender in self.port_extenders or []:
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
        return self

    @model_validator(mode="after")
    def warn_extender_without_ports(self) -> Self:
        """Warn about an extender without ports."""

        for extender in self.port_extenders:
            if not extender.ports:
                warn(
                    f"Port extender '{extender.name}' has no ports.",
                    category=Category.STRUCTURAL,
                    error_number="403",
                )
        return self

    @model_validator(mode="after")
    def validate_uplink_port_usage(self) -> Self:
        """
        Raise err_minor on forwarding or TSN configuration on an uplink port.

        The uplink port is a lane to the extender, not a forwarding endpoint.
        """

        uplinks = self.extender_uplink_ports
        for vlan in self.vlans or []:
            _validate_uplink_not_listed(uplinks, vlan.ports, f"VLAN '{vlan.name}'")
            for group in vlan.multicast or []:
                _validate_uplink_not_listed(uplinks, group.ports, f"multicast group {group.address} of VLAN '{vlan.name}'")
        for rule in self.tcam_rules or []:
            _validate_uplink_not_listed(uplinks, rule.match_ports, f"TCAM rule '{rule.name}' (match_ports)")
            for action in rule.action or []:
                _validate_uplink_not_listed(uplinks, action.ports, f"TCAM rule '{rule.name}' (action '{action.type}')")
        for port in self.ports:
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
        return self

    @model_validator(mode="after")
    def validate_mii_subports(self) -> Self:
        """Validate mii_subport_of/mii_subport_id references between this switch's ports."""
        lanes = frozenset(extender.uplink.switch_port_name for extender in self.port_extenders or [] if extender.uplink.type == "channelized")
        validate_mii_subports(self.ports, "Switch Ports", lanes)
        return self

    def _has_stream_with_ipv(self, ipv: int) -> bool:
        """
        Check whether any ingress stream on any port of this switch uses the given internal priority value.

        Args:
            ipv: The internal priority value to look for.

        Returns:
            bool: True if a matching ingress stream exists, False otherwise.
        """

        return any(stream.ipv == ipv for p in self.ports for stream in (p.ingress_streams or []))

    def _has_ats_stream(self) -> bool:
        """
        Check whether any ingress stream on any port of this switch defines an ATS instance.

        Returns:
            bool: True if an ingress stream with an ATS instance exists, False otherwise.
        """

        return any(stream.ats for p in self.ports for stream in (p.ingress_streams or []))

    @model_validator(mode="after")
    def validate_ipv_mapping(self) -> Self:
        """
        Check if internal priority value of traffic classes is defined in ingress streams
        """

        for port in self.ports:
            for tr in port.traffic_classes or []:
                for iv in tr.internal_priority_values or []:
                    if not self._has_stream_with_ipv(iv):
                        raise err_minor(
                            f"Not able to find any streams with internal priority values {iv}. Traffic class {tr.name}",
                            category=Category.REFERENCE,
                            error_number="090",
                        )
        return self

    @model_validator(mode="after")
    def validate_ats_instances(self) -> Self:
        """
        Check if the shaper is ATS, the instance is defined # on some port on ingress

        Raises:
            err_minor: No ATS Instance found for traffic class

        Returns:
            _type_: Self
        """

        for port in self.ports:
            for tr in port.traffic_classes or []:
                if tr.selection_mechanisms and tr.selection_mechanisms.type == "ats" and not self._has_ats_stream():
                    raise err_minor(f"No ATS Instance found for traffic class {tr.name}", category=Category.REFERENCE, error_number="091")

        return self

    @model_validator(mode="after")
    def validate_ports_in_tcam_exist(self) -> Self:
        """
        Validate that every port referenced in TCAM rules exists on the switch.

        Raises:
            err_minor: If a port listed in a TCAM rule (match_ports or action.ports) is not present in the switch's port list.
        """

        if not self.tcam_rules:
            return self
        switch_port_names = [port.name for port in self.ports]
        tcam_ports: list[str] = []
        for tcam_rule in self.tcam_rules:
            tcam_ports += tcam_rule.match_ports or []
            for action in tcam_rule.action or []:
                tcam_ports += action.ports or []

        validate_elements_in(
            tcam_ports,
            switch_port_names,
            "TCAM Ports must exist on the Switch.",
        )
        return self

    @model_validator(mode="after")
    def validate_ports_in_vlan_entries_exist(self) -> Self:
        """
        Validate that every port referenced in VLAN entries exists on the switch.

        Raises:
            err_minor: If a port listed in a VLAN entry (ports or multicast.ports) is not present in the switch's port list.
        """

        if not self.vlans:
            return self
        switch_port_names = [port.name for port in self.ports]
        vlan_ports = []
        for vlan_entry in self.vlans:
            vlan_ports += vlan_entry.ports
            for multicast_group in vlan_entry.multicast or []:
                vlan_ports += multicast_group.ports

        validate_elements_in(
            vlan_ports,
            switch_port_names,
            "VLAN Ports must exist on the Switch.",
        )
        return self

    @model_validator(mode="after")
    def validate_tcam_ids_unique(self) -> Self:
        """
        Validate that each TCAM rule has a unique identifier.

        Raises:
            err_minor: Duplicate ``id`` values found among the TCAM rules.
        """

        ids = [tcam.id for tcam in (self.tcam_rules or [])]
        validate_list_items_unique(ids, "tcam_rules (id)")
        return self

    @model_validator(mode="after")
    def validate_tcam_name_unique(self) -> Self:
        """
        Validate that each TCAM rule has a unique name.

        Raises:
            err_minor: Duplicate ``name`` values found among the TCAM rules.
        """

        names = [tcam.name for tcam in (self.tcam_rules or [])]
        validate_list_items_unique(names, "tcam_rules (name)")

        return self

    def get_mac(self) -> FLYNCMacAddress | None:
        """Return MAC address from the host controller's first ethernet interface."""
        host = self.host_controller
        if host is None:
            return None
        macs = host.get_all_macs()
        return macs[0] if macs else None

    def find_switch_port(self, port_name: str) -> SwitchPort:
        return next(p for p in self.ports if p.name == port_name)

    def find_port_extender(self, extender_name: str) -> Optional[PortExtender]:
        """Return the port extender with the given name, or ``None``."""
        return next((extender for extender in self.port_extenders or [] if extender.name == extender_name), None)

    def _bind_port_extenders(self) -> None:
        """
        Bind each extender to this switch, its ports and its uplink port.

        The connected component of an uplink port is the extender. Unresolved references stay ``None``.
        """

        by_name = {port.name: port for port in self.ports}
        for extender in self.port_extenders:
            extender._switch = self
            for name in extender.ports:
                if name in by_name:
                    by_name[name]._port_extender = extender
            uplink = extender.uplink
            uplink._switch_port = by_name.get(uplink.switch_port_name)
            if uplink._switch_port is not None:
                uplink._switch_port._connected_component = extender

    def model_post_init(self, __context: object) -> None:
        for port in self.ports:
            port._switch = self

        self._bind_port_extenders()

        self._fill_empty_tcam_port_lists()
        super().model_post_init(__context)

    def _fill_empty_tcam_port_lists(self) -> None:
        """
        Fill empty or omitted port lists in TCAM rules with all available switch ports.

        The expanded list is assigned directly via ``object.__setattr__`` so it is fully
        accessible at runtime without being recorded in the model's "fields set". This keeps
        serialization faithful to the user's original input: the field serializers on
        :class:`TCAMRule` and :class:`PortScopedAction` dump an explicit empty list as ``[]``,
        while an omitted list stays omitted (under ``exclude_unset``).
        """
        if not self.tcam_rules:
            return

        # "All ports" leaves out extender uplinks: they are lanes.
        uplinks = self.extender_uplink_ports
        all_port_names = [port.name for port in self.ports if port.name not in uplinks]

        for rule in self.tcam_rules:
            if not rule.match_ports:
                object.__setattr__(rule, "match_ports", all_port_names.copy())
                object.__setattr__(rule, "_match_ports_autofilled", True)

            for action in rule.action:
                if not action.ports:
                    object.__setattr__(action, "ports", all_port_names.copy())
                    object.__setattr__(action, "_ports_autofilled", True)

            # The port-based exclusivity checks ran on the (still empty) user input, so re-run them on the expanded lists.
            rule._check_exclusive_drop_force_mirror()
            rule._check_exclusive_vlan_action()
