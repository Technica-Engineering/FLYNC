from __future__ import annotations

from typing import (
    Annotated,
    ClassVar,
    Dict,
    List,
    Literal,
    Optional,
    Self,
    Type,
)

from pydantic import (
    AfterValidator,
    BeforeValidator,
    Field,
    PrivateAttr,
    StrictInt,
    field_serializer,
    model_validator,
)
from pydantic.networks import IPvAnyAddress
from pydantic_extra_types.mac_address import MacAddress

import flync.core.utils.common_validators as common_validators
from flync.core.base_models import NamedDictInstances, NamedListInstances
from flync.core.base_models.base_model import FLYNCBaseModel
from flync.core.utils.exceptions import err_minor
from flync.model.flync_4_ecu.controller import ControllerInterface
from flync.model.flync_4_ecu.phy import (
    BASET,
    BASET1,
    BASET1S,
    MII,
    RGMII,
    RMII,
    SGMII,
    XFI,
)
from flync.model.flync_4_metadata import EmbeddedMetadata
from flync.model.flync_4_security import MACsecConfig
from flync.model.flync_4_tsn import (
    FrameFilter,
    PTPConfig,
    Stream,
    TrafficClass,
)


class SwitchPort(NamedDictInstances):
    """
    Represents a Switch Port and its configuration.

    Parameters
    ----------
    name : str
        Name of the Switch Port.

    silicon_port_no : int
        Silicon hardware port number (vendor-specific).

    default_vlan_id : int
        VLAN ID to be added to an untagged frame ingressing on the port.

    mii_config : :class:`~flync.model.flync_4_ecu.phy.MII` or \
    :class:`~flync.model.flync_4_ecu.phy.RMII` or \
    :class:`~flync.model.flync_4_ecu.phy.SGMII` or \
    :class:`~flync.model.flync_4_ecu.phy.RGMII`, optional
        Media-independent interface configuration (e.g., MII or RMII).

    ptp_config : :class:`~flync.model.flync_4_tsn.PTPConfig`, \
    optional
        Precision Time Protocol configuration.

    ingress_streams : list of :class:`~flync.model.flync_4_tsn.Stream`, \
    optional
        Stream-based IEEE 802.1Qci configuration.

    traffic_classes : list of \
    :class:`~flync.model.flync_4_tsn.TrafficClass`, optional
        Traffic class definitions and traffic shaping configuration
        applied to egress port queues.

    macsec_config : \
    :class:`~flync.model.flync_4_security.MACsecConfig`, \
    optional
        MACsec configuration for the port.

    Private Attributes
    ------------------
    _type :
        The type of the object generated. Set to controller_interface.

    _mdi_config : :class:`~flync.model.flync_4_ecu.phy.BaseT1` or \
    :class:`~flync.model.flync_4_ecu.phy.BaseT1S` or \
    :class:`~flync.model.flync_4_ecu.phy.BaseT`

    _connected_component:
        The switch port, controller interface or ecu port connected
        to the switch port. This attribute
        is managed internally and is not part of the public API.

    """

    INSTANCES: ClassVar[Dict[str, "SwitchPort"]] = {}
    name: str = Field()
    silicon_port_no: int = Field(ge=0)
    default_vlan_id: int = Field(..., ge=0, le=4095)
    mii_config: Optional[MII | RMII | SGMII | RGMII | XFI] = Field(
        default=None, discriminator="type"
    )
    ptp_config: Optional[PTPConfig] = Field(default=None)
    ingress_streams: Optional[List[Stream]] = Field(default=[])
    traffic_classes: Annotated[
        Optional[List[TrafficClass]],
        AfterValidator(common_validators.validate_traffic_classes),
        BeforeValidator(common_validators.none_to_empty_list),
    ] = Field(default=[])
    macsec_config: Optional[MACsecConfig] = Field(default=None)
    _mdi_config: BASET1 | BASET1S | BASET | None = PrivateAttr(default=None)
    _connected_component = PrivateAttr(default=None)
    _type: Literal["switch_port"] = PrivateAttr(default="switch_port")

    @property
    def mdi_config(self):
        return self._mdi_config

    @property
    def type(self):
        return self._type

    @property
    def connected_component(self):
        return self._connected_component

    @model_validator(mode="after")
    def validate_traffic_classes(self):
        if self.mii_config and self.traffic_classes:
            common_validators.validate_cbs_idleslopes_fit_portspeed(
                self.traffic_classes,
                self.mii_config.speed,
            )
        return self

    def copy_mdi_config_to_switch(self, mdi_config):
        """
        Helper function. COpies the MDI config from ECU port to switch port
        """
        self._mdi_config = mdi_config

    def get_switch(self):
        """
        Helper function. Returns the switch that the port is a part of
        """

        for switch in Switch.INSTANCES:
            for port in switch.ports:
                if port.name == self.name:
                    return switch
        raise err_minor("The switch port is not a part of any switch")

    def get_multicast_connected_ports(self, address):
        """
        Helper function. Returns the switch ports that are part of
        the multicast address as thaat port
        """
        for vlan in self.get_switch().vlans:
            for addr in vlan.multicast:
                if addr.address == address:
                    if self.name in addr.ports:
                        return addr.ports
        return []


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

    address: Annotated[
        IPvAnyAddress | MacAddress,
        AfterValidator(common_validators.validate_any_multicast_address),
    ] = Field()
    ports: List[str] = Field()

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
    multicast: Annotated[
        Optional[List[MulticastGroup]],
        BeforeValidator(common_validators.none_to_empty_list),
    ] = Field(default=[])


class Drop(FLYNCBaseModel):
    """
    Action that discards traffic on the selected egress ports.

    Parameters
    ----------
    type : Literal["drop"]
        Discriminator used by Pydantic.

    ports : list of str
        Egress ports where the drop action should be applied.
    """

    type: Literal["drop"] = Field(default="drop")
    ports: List[str] = Field()


class Mirror(FLYNCBaseModel):
    """
    Action that mirrors incoming traffic to additional egress ports.

    Parameters
    ----------
    type : Literal["mirror"]
        Discriminator used by Pydantic.

    ports : list of str
        Egress ports that will receive the mirrored traffic.
    """

    type: Literal["mirror"] = Field(default="mirror")
    ports: List[str] = Field()


class ForceEgress(FLYNCBaseModel):
    """
    Action that forces a packet to leave through a given set of ports,
    bypassing the normal forwarding decision.

    Parameters
    ----------
    type : Literal["force_egress"]
        Discriminator used by Pydantic.

    ports : list of str
        Egress ports to which the messages are force-forwarded.
    """

    type: Literal["force_egress"] = Field(default="force_egress")
    ports: List[str] = Field()


class VLANOverwrite(FLYNCBaseModel):
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

    ports : list of str
        Egress ports at which the overwriting should take place.
    """

    type: Literal["vlan_overwrite"] = Field(default="vlan_overwrite")
    overwrite_vlan_id: Optional[int] = Field(default=None)
    overwrite_vlan_pcp: Optional[int] = Field(default=None)
    ports: List[str] = Field()


class RemoveVLAN(FLYNCBaseModel):
    """
    Action that removes the VLAN tag from packets on the given ports.

    Parameters
    ----------
    type : Literal["remove_vlan"]
        Discriminator used by Pydantic.

    ports : list of str
        Egress ports where the VLAN tag will be removed.
    """

    type: Literal["remove_vlan"] = Field(default="remove_vlan")
    ports: List[str] = Field()


class TCAMRule(FLYNCBaseModel):
    """
    Definition of a TCAM (ternary content-addressable memory) rule for a
    switch.

    Parameters
    ----------
    name : str
        Name for the description of the TCAM rule.

    id : StrictInt
        Unique TCAM rule ID.

    match_filter : :class:`~flync.model.flync_4_tsn.FrameFilter`
        Packet-matching filter used to decide whether the rule applies.

    match_ports : list of str
        Ports to which the rule is bound.

    action : list of :class:`Drop` or :class:`Mirror` or \
    :class:`ForceEgress` or :class:`VLANOverwrite` or \
    :class:`RemoveVLAN`
        One or more actions performed when the rule matches.
        The ``type`` field of each action class acts as the discriminating
        key for Pydantic.
    """

    name: str = Field()
    id: StrictInt = Field()
    match_filter: FrameFilter = Field()
    match_ports: List[str] = Field()
    action: List[
        (Drop | Mirror | VLANOverwrite | ForceEgress | RemoveVLAN)
    ] = Field()

    @model_validator(mode="after")
    def validate_exclusive_drop_force_mirror(self):
        """Validate that a TCAM rule does **not** use more than one of the
        mutually‑exclusive actions *drop*, *force_egress* or *mirror* on the
        same port.

        Args:
            self (TCAMRule): The model instance being validated.

        Raises:
            err_minor: If a port appears in more than one of the actions
                ``drop``, ``force_egress`` or ``mirror these actions per port.
        """
        all_ports = []
        for action in self.action:
            if action.type in ["drop", "force_egress", "mirror"]:
                all_ports += action.ports

        if len(all_ports) != len(set(all_ports)):
            raise err_minor(
                "A TCAM Rule can either drop OR force egress OR ",
                "mirror on one port.",
            )
        return self

    @model_validator(mode="after")
    def validate_exclusive_vlan_action(self):
        """Validate that a TCAM rule does **not** mix the VLAN actions
        *remove_vlan* and *vlan_overwrite* on the same port.

        Args:
            self (TCAMRule): The model instance being validated.

        Raises:
            err_minor
                ``vlan_overwrite`` actions.  Only one of these actions may be
                applied to a given port.
        """
        all_ports = []
        for action in self.action:
            if action.type in ["remove_vlan", "vlan_overwrite"]:
                all_ports += action.ports

        if len(all_ports) != len(set(all_ports)):
            raise err_minor(
                "A TCAM Rule can either remove OR ",
                "overwrite a vlan on one port.",
            )
        return self


class Switch(NamedListInstances):
    """
    Represents an automotive Ethernet network switch configuration.

    Parameters
    ----------
    meta : :class:`~flync.model.flync_4_metadata.metadata.EmbeddedMetadata`
        Metadata associated with the switch, such as vendor-specific
        or implementation-specific attributes.

    name : str
        Name of the switch.

    ports : list of :class:`SwitchPort`
        List of external (connected to ECU ports) or internal
        (connected to internal ECU interfaces) switch ports.

    vlans : list of :class:`VLANEntry`
        List of VLAN entries configured on the switch.

    host_controller : \
    :class:`~flync.model.flync_4_ecu.ControllerInterface`, optional
        Switch host controller configuration, if the switch is managed
        by an internal controller.

    tcam_rules : list of :class:`TCAMRule`, optional
        List of TCAM rules configured on the switch. These rules define
        packet-matching conditions and associated actions applied to
        ingress or egress traffic.

    """

    INSTANCES: ClassVar[List[Type["Switch"]]] = []
    name: str = Field()
    tcam_rules: Annotated[
        Optional[List[TCAMRule]],
        BeforeValidator(common_validators.none_to_empty_list),
    ] = Field(default=[])
    ports: List[SwitchPort] = Field()
    vlans: List[VLANEntry] = Field()
    host_controller: Optional[ControllerInterface] = Field(default=None)
    meta: EmbeddedMetadata = Field()

    @model_validator(mode="after")
    def validate_unique_port_number(self):
        """
        Validate if the silicon port numbers for all the
        different switch ports are unique

        Raises:
            Validation error if a silicon port number is repeated
        """
        silicon_port_numbers = []
        for port in self.ports:
            silicon_port_numbers.append(port.silicon_port_no)
        common_validators.validate_list_items_unique(
            silicon_port_numbers,
            "Switch Ports (silicon_port_number)",
        )
        return self

    @model_validator(mode="after")
    def validate_ipv_mapping(self) -> Self:
        """
        Check if internal priority value of traffic classes
        is defined in ingress streams
        """
        for port in self.ports:
            if port.traffic_classes:
                for tr in port.traffic_classes:

                    if tr.internal_priority_values:
                        for iv in tr.internal_priority_values:
                            found_stream = False
                            for port_find in self.ports:
                                if port_find.ingress_streams:
                                    for str in port_find.ingress_streams:
                                        if str.ipv == iv:
                                            found_stream = True
                            if not found_stream:
                                raise err_minor(
                                    f"Not able to find any streams with "
                                    f"internal priority values {iv}. "
                                    f"Traffic class {tr.name}"
                                )
        return self

    @model_validator(mode="after")
    def validate_ats_instances(self) -> Self:
        """Check if the shaper is ATS, the instance is defined
        # on some port on ingress

        Raises:
            err_minor: No ATS Instance found for traffic class

        Returns:
            _type_: Self
        """
        for port in self.ports:
            if port.traffic_classes:
                for tr in port.traffic_classes:
                    if (
                        tr.selection_mechanisms
                        and tr.selection_mechanisms.type == "ats"
                    ):
                        found_ats = False
                        for port_find in self.ports:
                            if port_find.ingress_streams:
                                for str in port_find.ingress_streams:
                                    if str.ats:
                                        found_ats = True
                        if not found_ats:
                            raise err_minor(
                                f"No ATS Instance found for traffic class "
                                f"{tr.name}"
                            )

        return self

    @model_validator(mode="after")
    def validate_ports_in_tcam_exist(self):
        """Validate that every port referenced in TCAM rules exists on the
        switch.

        Raises:
            err_minor: If a port listed in a TCAM rule (match_ports or
                action.ports) is not present in the switch's port list.
        """
        if not self.tcam_rules:
            return self
        switch_port_names = [port.name for port in self.ports]
        tcam_ports = []
        for tcam_rule in self.tcam_rules:
            tcam_ports += tcam_rule.match_ports
            for action in tcam_rule.action:
                tcam_ports += action.ports

        common_validators.validate_elements_in(
            tcam_ports,
            switch_port_names,
            "TCAM Ports must exist on the Switch.",
        )
        return self

    @model_validator(mode="after")
    def validate_tcam_ids_unique(self):
        """Validate that each TCAM rule has a unique identifier.

        Raises:
            err_minor: Duplicate ``id`` values found among the TCAM rules.
        """
        ids = [tcam.id for tcam in self.tcam_rules]
        common_validators.validate_list_items_unique(ids, "tcam_rules (id)")
        return self

    @model_validator(mode="after")
    def validate_tcam_name_unique(self):
        """Validate that each TCAM rule has a unique name.

        Raises:
            err_minor: Duplicate ``name`` values found among the TCAM rules.
        """
        names = [tcam.name for tcam in self.tcam_rules]
        common_validators.validate_list_items_unique(
            names, "tcam_rules (name)"
        )

        return self
