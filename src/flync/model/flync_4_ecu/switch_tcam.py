"""Defines TCAM actions and rules for automotive Ethernet Switches"""

from __future__ import annotations

from typing import Annotated, List, Literal, Optional, Self

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

from flync.core.base_models.base_model import FLYNCBaseModel
from flync.core.datatypes import Bitmask
from flync.core.utils.exceptions import Category, err_minor, warn
from flync.core.validators.address import validate_vlan_id
from flync.core.validators.generic import none_to_empty_list
from flync.model.flync_4_tsn import FrameFilter


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
