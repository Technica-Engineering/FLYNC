"""Defines the automotive Ethernet Switch and its components for FLYNC"""

from __future__ import annotations

import re
from typing import (
    Annotated,
    Any,
    List,
    Literal,
    Optional,
    Self,
)

from pydantic import (
    AfterValidator,
    BeforeValidator,
    Field,
    PrivateAttr,
    StrictInt,
    field_serializer,
    field_validator,
    model_validator,
)

import flync.core.utils.common_validators as common_validators
from flync.core.base_models.base_model import FLYNCBaseModel
from flync.core.utils.common_validators import validate_vlan_id
from flync.core.utils.exceptions import err_minor
from flync.model.flync_4_ecu.controller import EthernetInterfaceConfig
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
from flync.model.flync_4_ecu.vlan_entry import VLANEntry
from flync.model.flync_4_metadata import EmbeddedMetadata
from flync.model.flync_4_security import MACsecConfig
from flync.model.flync_4_tsn import (
    FrameFilter,
    PTPConfig,
    Stream,
    TrafficClass,
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

    default_vlan_id : int
        VLAN ID to be added to an untagged frame ingressing on the port.
        Use ``None`` for an untagged port (no default VLAN).

    mii_config : :class:`~flync.model.flync_4_ecu.phy.MII` or :class:`~flync.model.flync_4_ecu.phy.RMII` or \
    :class:`~flync.model.flync_4_ecu.phy.SGMII` or :class:`~flync.model.flync_4_ecu.phy.RGMII`, optional
        Media-independent interface configuration (e.g., MII or RMII).

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

    _mdi_config : :class:`~flync.model.flync_4_ecu.phy.BaseT1` or :class:`~flync.model.flync_4_ecu.phy.BaseT1S` or \
    :class:`~flync.model.flync_4_ecu.phy.BaseT`

    _connected_component:
        The switch port, controller interface or ecu port connected to the switch port.
        This attribute is managed internally and is not part of the public API.

    """

    name: str = Field()
    silicon_port_no: int = Field(ge=0)
    default_vlan_id: int = Field(..., ge=0, le=4095)
    mii_config: Optional[MII | RMII | SGMII | RGMII | XFI] = Field(default=None, discriminator="type")
    ptp_config: Annotated[
        Optional[PTPConfig],
        BeforeValidator(common_validators.validate_or_remove("PTP config", PTPConfig)),
    ] = Field(default=None)
    ingress_streams: Annotated[
        Optional[List[Stream]],
        BeforeValidator(common_validators.validate_or_remove("ingress streams", List[Stream])),
        BeforeValidator(common_validators.none_to_empty_list),
    ] = Field(default=[])
    traffic_classes: Annotated[
        Optional[List[TrafficClass]],
        AfterValidator(common_validators.validate_traffic_classes),
        BeforeValidator(common_validators.validate_or_remove("traffic classes", List[TrafficClass])),
        BeforeValidator(common_validators.none_to_empty_list),
    ] = Field(default=[])
    macsec_config: Annotated[
        Optional[MACsecConfig],
        BeforeValidator(common_validators.validate_or_remove("MACsec config", MACsecConfig)),
    ] = Field(default=None)
    _mdi_config: BASET1 | BASET1S | BASET | None = PrivateAttr(default=None)
    _connected_component: Optional[Any] = PrivateAttr(default=None)
    _type: Literal["switch_port"] = PrivateAttr(default="switch_port")
    _switch: Optional["Switch"] = PrivateAttr(default=None)

    @property
    def mdi_config(self):
        return self._mdi_config

    @property
    def type(self):
        return self._type

    @property
    def connected_component(self):
        return self._connected_component

    @property
    def switch(self) -> Optional["Switch"]:
        return self._switch

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
        Helper function.
        Copies the MDI config from ECU port to switch port.
        """

        self._mdi_config = mdi_config

    def get_switch(self):
        """
        Helper function.
        Returns the switch that the port is a part of.
        """

        if self._switch is None:
            raise err_minor(f"The switch port {self.name} is not a part of any switch")
        return self._switch

    def get_vlan_connected_ports(self, vlan):
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

    def is_part_of_vlan(self, vlan):
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
    """

    _ports_autofilled: bool = PrivateAttr(default=False)

    @field_serializer("ports", check_fields=False)
    def serialize_ports(self, ports: Optional[List[str]], _info):
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
    ports: Optional[List[str]] = Field(default_factory=list)


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
    ports: Optional[List[str]] = Field(default_factory=list)


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
    ports: Optional[List[str]] = Field(default_factory=list)


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
    ports: Optional[List[str]] = Field(default_factory=list)


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
    ports: Optional[List[str]] = Field(default_factory=list)


class FrameMask(FLYNCBaseModel):
    """
    Byte-level pattern matching of an Ethernet frame.
    The inspectable frame window defaults to 96 bytes but may be overwritten with ``frame_window``.

    The rule matches frames by comparing raw byte patterns at a specific offset.
    The ``mask`` controls which bits are checked: only bits set to 1 in the mask
    are significant for the comparison. Bits set to 0 in the mask are ignored.

    For example, a frame at byte offset 12 matches if ``(frame[12:14] & mask) == (data & mask)``.

    Parameters
    ----------

    offset : int
        Byte position in the frame where the pattern match begins. Must be 0 to [frame_window - 1]
        to stay within the inspectable window. For example, offset=12 starts matching
        at the 13th byte (after MAC and EtherType headers).

    data : str
        Expected byte pattern. Input format must be a quoted string to prevent serialization mismatches and loss of leading zeros.
        The string can represent either:

        * a hexadecimal value ``"0x0800"`` (normalized to upper-case with a 0x prefix)
        * binary representation like ``"0101010101010101"`` (stored in verbatim).

    mask : str
        Bitmask controlling which bits to check. Accepts the very same input
        formats as ``data`` and must describe the same number of bytes.

    frame_window : int, Optional
        Maximum number of leading frame bytes a :class:`FrameMask` may inspect. Defaults to 96.
    """

    offset: int = Field(...)
    data: str = Field(...)
    mask: str = Field(...)
    frame_window: int = Field(default=96)

    @field_validator("data", "mask", mode="before")
    @classmethod
    def _require_string(cls, value, info):
        # Unquoted YAML numbers arrive as int and lose their format/width.
        if not isinstance(value, str):
            raise err_minor(
                f"{info.field_name} must be a quoted string: a hex literal like "
                f'"0x0800" or a binary string like "100101010111". Got '
                f"{type(value).__name__} {value!r}; wrap the value in quotes."
            )
        return value

    @field_validator("data", "mask", mode="after")
    @classmethod
    def _normalize_format(cls, value, info):
        hex_regex = re.compile(r"^0[xX][0-9a-fA-F]+$")
        bin_regex = re.compile(r"^[01]+$")
        v = value.strip().replace("_", "").replace(" ", "")
        if hex_regex.match(v):
            return "0x" + v[2:].upper()
        if bin_regex.match(v):
            return v
        raise err_minor(f'{info.field_name} must be a 0x-hex literal (e.g. "0x0800") or a binary string of 0/1 (e.g. "100101010111"); got {value!r}')

    @staticmethod
    def _bit_width(v: str) -> int:
        return 4 * len(v[2:]) if v[:2].lower() == "0x" else len(v)

    @property
    def bits(self) -> str:
        """Canonical binary view of `data` (unified access for consumers)."""
        return self.data if self.data[:2].lower() != "0x" else bin(int(self.data, 16))[2:].zfill(self._bit_width(self.data))

    @model_validator(mode="after")
    def validate_widths_and_window(self) -> Self:
        d, m = self._bit_width(self.data), self._bit_width(self.mask)
        if d != m:
            raise err_minor("'data' and 'mask' must describe the same number of bits")
        if not 0 <= self.offset < self.frame_window:
            raise err_minor(f"offset must be between 0 and {self.frame_window - 1}, got {self.offset}")
        byte_span = -(-d // 8)  # ceil(bits/8); patterns need not be byte-aligned
        if self.offset + byte_span > self.frame_window:
            raise err_minor(f"pattern at offset {self.offset} extends beyond byte {self.frame_window - 1} (max inspectable frame position)")
        return self


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
        Packet-matching filter for layer-based matching on MAC/IP/VLAN/ports.
        Mutually exclusive with ``frame_mask``. Either ``match_filter`` or ``frame_mask`` must be provided.

    frame_mask : :class:`~FrameMask`, optional
        Packet-matching criterion for byte-level pattern matching on raw frame data.
        Mutually exclusive with ``match_filter``. Either ``match_filter`` or ``frame_mask`` must be provided.

    match_ports : list of str, Optional
        Ports to which the rule is bound. Defaults to all ports of the switch if kept empty or undefined.

    action : list of :class:`Drop` or :class:`Mirror` or :class:`ForceEgress` or :class:`VLANOverwrite` or :class:`RemoveVLAN`
        One or more actions performed when the rule matches.
        The ``type`` field of each action class acts as the discriminating key for Pydantic.

    vehicle_state : int, optional
        Vehicle-state value (0-255) the rule is matched against. The rule applies
        only when ``(current_state & vehicle_state_mask) == vehicle_state``.
        ``None`` (default) means the rule is not gated on vehicle state.

    vehicle_state_mask : int, optional
        Bitmask (1-255) selecting which bits of the vehicle-state register are
        significant. Defaults to ``0xFF`` (all bits) when ``vehicle_state`` is set
        but no mask is given. Must not be set on its own without ``vehicle_state``.
    """

    name: str = Field()
    id: StrictInt = Field()
    match_filter: Optional[FrameFilter] = Field(default=None)
    frame_mask: Optional[FrameMask] = Field(default=None)
    match_ports: Optional[List[str]] = Field(default_factory=list)
    action: List[(Drop | Mirror | VLANOverwrite | ForceEgress | RemoveVLAN)] = Field()
    vehicle_state: Optional[int] = Field(default=None, ge=0, le=255)
    vehicle_state_mask: Optional[int] = Field(default=None, gt=0, le=255)
    _match_ports_autofilled: bool = PrivateAttr(default=False)

    @field_serializer("match_ports")
    def serialize_match_ports(self, match_ports: Optional[List[str]], _info):
        """Dump the user's original port list, not the runtime-expanded one."""
        return [] if self._match_ports_autofilled else match_ports

    @model_validator(mode="after")
    def validate_vehicle_state(self):
        """
        Validate the vehicle-state matching parameters:
        - a mask without a value is invalid,
        - a value without a mask defaults the mask to all bits (0xFF),
        - the value must not set bits outside the mask.
        """

        if self.vehicle_state is None:
            if self.vehicle_state_mask is not None:
                raise err_minor(
                    "TCAM Rule '{name}': vehicle_state_mask requires vehicle_state to be set.",
                    name=self.name,
                )
            return self

        if self.vehicle_state_mask is None:
            self.vehicle_state_mask = 0xFF

        if self.vehicle_state & (~self.vehicle_state_mask & 0xFF):
            raise err_minor(
                "TCAM Rule '{name}': vehicle_state has bits set outside vehicle_state_mask.",
                name=self.name,
            )
        return self

    @model_validator(mode="after")
    def validate_match_filter_or_mask_exclusive(self) -> Self:
        """
        Validate that exactly one of ``match_filter`` or ``frame_mask`` is provided, not both or neither.

        Raises:
            err_minor: If both or neither match criteria are provided.
        """
        has_filter = self.match_filter is not None
        has_mask = self.frame_mask is not None

        if has_filter and has_mask:
            raise err_minor("Cannot specify both match_filter and frame_mask; use only one")
        if not has_filter and not has_mask:
            raise err_minor("Must specify either match_filter or frame_mask")
        return self

    @model_validator(mode="after")
    def validate_exclusive_drop_force_mirror(self):
        """
        Validate that a TCAM rule does **not** use more than one of the mutually‑exclusive actions *drop*, *force_egress* or *mirror* on the
        same port.

        Args:
            self (TCAMRule): The model instance being validated.

        Raises:
            err_minor: If a port appears in more than one of the actions ``drop``, ``force_egress`` or ``mirror these actions per port.
        """

        all_ports = []
        for action in self.action:
            if action.type in ["drop", "force_egress", "mirror"]:
                all_ports += action.ports

        if len(all_ports) != len(set(all_ports)):
            raise err_minor(
                "A TCAM Rule can either drop OR force egress OR mirror on one port.",
            )
        return self

    @model_validator(mode="after")
    def validate_exclusive_vlan_action(self):
        """
        Validate that a TCAM rule does **not** mix the VLAN actions *remove_vlan* and *vlan_overwrite* on the same port.

        Args:
            self (TCAMRule): The model instance being validated.

        Raises:
            err_minor
                ``vlan_overwrite`` actions.  Only one of these actions may be applied to a given port.
        """

        all_ports = []
        for action in self.action:
            if action.type in ["remove_vlan", "vlan_overwrite"]:
                all_ports += action.ports

        if len(all_ports) != len(set(all_ports)):
            raise err_minor(
                "A TCAM Rule can either remove OR overwrite a vlan on one port.",
            )
        return self


class Switch(FLYNCBaseModel):
    """
    Represents an automotive Ethernet network switch configuration.

    Parameters
    ----------
    meta : :class:`~flync.model.flync_4_metadata.metadata.EmbeddedMetadata`
        Metadata associated with the switch, such as vendor-specific or implementation-specific attributes.

    name : str
        Name of the switch.

    ports : list of :class:`SwitchPort`
        List of external (connected to ECU ports) or internal (connected to internal ECU interfaces) switch ports.

    vlans : list of :class:`~flync.model.flync_4_ecu.vlan_entry.VLANEntry`
        List of VLAN entries configured on the switch.

    host_controller : :class:`~flync.model.flync_4_ecu.controller.EthernetInterfaceConfig`, optional
        Internal controller interface that manages the switch.

    tcam_rules : list of :class:`TCAMRule`, optional
        List of TCAM rules configured on the switch.
        These rules define packet-matching conditions and associated actions applied to ingress or egress traffic.

    """

    name: str = Field()
    tcam_rules: Annotated[
        Optional[List[TCAMRule]],
        BeforeValidator(common_validators.none_to_empty_list),
    ] = Field(default=[])
    ports: List[SwitchPort] = Field()
    vlans: List[VLANEntry] = Field()
    host_controller: Optional[EthernetInterfaceConfig] = Field(default=None)
    meta: EmbeddedMetadata = Field()

    @model_validator(mode="after")
    def validate_unique_port_number(self):
        """
        Validate if the silicon port numbers for all the different switch ports are unique

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
    def validate_unique_port_names(self):
        """Validate port names are unique across this switch's ports."""
        common_validators.validate_list_items_unique(
            [p.name for p in self.ports],
            "Switch Ports (name)",
        )
        return self

    @model_validator(mode="after")
    def validate_ipv_mapping(self) -> Self:
        """
        Check if internal priority value of traffic classes is defined in ingress streams
        """

        for port in self.ports:
            if port.traffic_classes:
                for tr in port.traffic_classes:

                    if tr.internal_priority_values:
                        for iv in tr.internal_priority_values:
                            found_stream = False
                            for port_find in self.ports:
                                if port_find.ingress_streams:
                                    for stream in port_find.ingress_streams:
                                        if stream.ipv == iv:
                                            found_stream = True
                            if not found_stream:
                                raise err_minor(f"Not able to find any streams with internal priority values {iv}. Traffic class {tr.name}")
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
            if port.traffic_classes:
                for tr in port.traffic_classes:
                    if tr.selection_mechanisms and tr.selection_mechanisms.type == "ats":
                        found_ats = False
                        for port_find in self.ports:
                            if port_find.ingress_streams:
                                for stream in port_find.ingress_streams:
                                    if stream.ats:
                                        found_ats = True
                        if not found_ats:
                            raise err_minor(f"No ATS Instance found for traffic class {tr.name}")

        return self

    @model_validator(mode="after")
    def validate_ports_in_tcam_exist(self):
        """
        Validate that every port referenced in TCAM rules exists on the switch.

        Raises:
            err_minor: If a port listed in a TCAM rule (match_ports or action.ports) is not present in the switch's port list.
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
        """
        Validate that each TCAM rule has a unique identifier.

        Raises:
            err_minor: Duplicate ``id`` values found among the TCAM rules.
        """

        ids = [tcam.id for tcam in self.tcam_rules]
        common_validators.validate_list_items_unique(ids, "tcam_rules (id)")
        return self

    @model_validator(mode="after")
    def validate_tcam_name_unique(self):
        """
        Validate that each TCAM rule has a unique name.

        Raises:
            err_minor: Duplicate ``name`` values found among the TCAM rules.
        """

        names = [tcam.name for tcam in self.tcam_rules]
        common_validators.validate_list_items_unique(names, "tcam_rules (name)")

        return self

    def get_mac(self):
        return self.host_controller.mac_address

    def find_switch_port(self, port_name: str) -> SwitchPort:
        return next(p for p in self.ports if p.name == port_name)

    def model_post_init(self, __context):
        for port in self.ports:
            port._switch = self

        if self.host_controller is not None:
            self.host_controller._name = f"{self.name}_host"

        self._fill_empty_tcam_port_lists()
        return super().model_post_init(__context)

    def _fill_empty_tcam_port_lists(self):
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

        all_port_names = [port.name for port in self.ports]

        for rule in self.tcam_rules:
            if not rule.match_ports:
                object.__setattr__(rule, "match_ports", all_port_names.copy())
                object.__setattr__(rule, "_match_ports_autofilled", True)

            for action in rule.action:
                if not action.ports:
                    object.__setattr__(action, "ports", all_port_names.copy())
                    object.__setattr__(action, "_ports_autofilled", True)
