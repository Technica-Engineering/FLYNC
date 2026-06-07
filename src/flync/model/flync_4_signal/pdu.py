from typing import List, Literal, Optional

from pydantic import Field, field_validator, model_validator

from flync.core.base_models import FLYNCBaseModel, UniqueName
from flync.core.utils.common_validators import (
    BitRange,
    check_bit_ranges_no_overlap,
    check_bit_ranges_within,
    collect_bit_ranges,
)
from flync.core.utils.exceptions import err_major, err_minor
from flync.model.flync_4_signal.signal import (
    SignalGroupInstance,
    SignalInstance,
    _signal_group_footprint,
    _signal_instance_range,
)

# ---------------------------------------------------------------------------
# PDU base
# ---------------------------------------------------------------------------


class PDU(UniqueName):
    """
    Protocol Data Unit base class.

    Parameters
    ----------
    name : str
        Unique name of the PDU.
    length : int
        Length of the PDU payload in bytes.
    pdu_usage : Literal[
                    "application",
                    "bap",
                    "diag_request",
                    "diag_response",
                    "diag_state",
                    "network_management",
                    "other",
                    "service",
                    "tpl",
                    "xcp_pre_configured",
                    "xcp_runtime_configured",
                ], optional
        Tag identifying special usage of the PDU.
        ``"application"`` marks the PDU as regular application.
        ``"bap"`` marks the PDU as BAP (FIBEX compatibility).
        ``"diag_request"`` marks the PDU as diagnostics request.
        ``"diag_response"`` marks the PDU as diagnostics response.
        ``"diag_state"`` marks the PDU as diagnostics state.
        ``"network_management"`` marks the PDU as Network Management.
        ``"other"`` marks the PDU as other usage.
        ``"service"`` marks the PDU as service.
        ``"tpl"`` marks the PDU as transport protocol PDU.
        ``"xcp_pre_configured"`` marks the PDU as static XCP PDU.
        ``"xcp_runtime_configured"`` marks the PDU as dynamic XCP PDU.

    description : str, optional
        Optional human-readable description.
    """

    name: str = Field()
    length: int = Field(gt=0)
    pdu_usage: Optional[
        Literal[
            "application",
            "bap",
            "diag_request",
            "diag_response",
            "diag_state",
            "network_management",
            "other",
            "service",
            "tpl",
            "xcp_pre_configured",
            "xcp_runtime_configured",
        ]
    ] = Field(default=None)
    description: Optional[str] = Field(default=None)


# ---------------------------------------------------------------------------
# StandardPDU
# ---------------------------------------------------------------------------


class StandardPDU(PDU):
    """
    Non-multiplexed PDU containing a flat list of signal instances.

    Parameters
    ----------
    signals : list of :class:`SignalInstance`
        Signal instances placed within this PDU.
    signal_groups : list of :class:`SignalGroupInstance`
        Signal group instances placed within this PDU.
    """

    type: Literal["standard"] = Field(default="standard")
    signals: List[SignalInstance] = Field(default_factory=list)
    signal_groups: List[SignalGroupInstance] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_signals_fit_in_pdu(self) -> "StandardPDU":
        """Check all placed signals are within bounds and do not overlap."""
        ranges = _collect_placed_ranges(self.signals, self.signal_groups)
        context = f"PDU '{self.name}'"
        check_bit_ranges_within(context, ranges, self.length * 8)
        check_bit_ranges_no_overlap(context, ranges)
        return self


# ---------------------------------------------------------------------------
# MuxGroup
# ---------------------------------------------------------------------------


class MuxGroup(FLYNCBaseModel):
    """
    Set of signals active for a specific multiplexer selector value.

    Parameters
    ----------
    selector_value : int
        The value of the selector signal that activates this group.
    pdu : :class:`StandardPDU`
        The PDU that is active for this selector_value.
    """

    selector_value: int = Field(ge=0)
    pdu: StandardPDU = Field()


# ---------------------------------------------------------------------------
# MultiplexedPDU
# ---------------------------------------------------------------------------


class MultiplexedPDU(PDU):
    """
    PDU with a selector signal that determines which signal group is active.

    Parameters
    ----------
    selector_signal : :class:`SignalInstance`
        The selector signal whose value determines the active mux group.
    static_signals : list of :class:`SignalInstance`
        Signals that are always present regardless of the active mux group.
    mux_groups : list of :class:`MuxGroup`
        One entry per distinct selector value.
    """

    type: Literal["multiplexed"] = Field(default="multiplexed")
    selector_signal: SignalInstance = Field()
    static_group: Optional[StandardPDU] = Field(default=None)
    mux_groups: List[MuxGroup] = Field(default_factory=list, min_length=1)

    @model_validator(mode="after")
    def validate_unique_selector_values(self) -> "MultiplexedPDU":
        """Ensure no two mux groups share the same selector value."""
        values = [g.selector_value for g in self.mux_groups]
        duplicates = [v for v in values if values.count(v) > 1]
        if duplicates:
            raise err_minor(
                "MultiplexedPDU '{name}' has duplicate selector_value(s): {duplicates}",
                name=self.name,
                duplicates=sorted(set(duplicates)),
            )
        return self

    @model_validator(mode="after")
    def validate_selector_value_ranges(self) -> "MultiplexedPDU":
        """Ensure selector_values fit within the selector signal's width."""
        max_value = (1 << self.selector_signal.signal.bit_length) - 1
        out_of_range = sorted({g.selector_value for g in self.mux_groups if g.selector_value > max_value})
        if out_of_range:
            raise err_minor(
                "MultiplexedPDU '{name}': selector_signal '{sig}' has "
                "bit_length={bl}, so valid selector values are [0, {max}]; "
                "out-of-range selector_value(s): {bad}",
                name=self.name,
                sig=self.selector_signal.signal.name,
                bl=self.selector_signal.signal.bit_length,
                max=max_value,
                bad=out_of_range,
            )
        return self

    @model_validator(mode="after")
    def validate_selector_overlap(self) -> "MultiplexedPDU":
        """Ensure mux group and static signals do not overlap the selector."""
        sel_bp = self.selector_signal.bit_position
        if sel_bp is None:
            return self
        sel_range: BitRange = (
            self.selector_signal.signal.name,
            sel_bp,
            sel_bp + self.selector_signal.signal.bit_length,
        )
        for group in self.mux_groups:
            group_signals = getattr(group.pdu, "signals", [])
            group_signal_groups = getattr(group.pdu, "signal_groups", [])
            group_ranges = _collect_placed_ranges(group_signals, group_signal_groups)
            check_bit_ranges_no_overlap(
                f"MultiplexedPDU '{self.name}' mux_group(selector={group.selector_value}) vs selector",
                [sel_range, *group_ranges],
            )
        if self.static_group is not None:
            static_signals = getattr(self.static_group, "signals", [])
            static_ranges = _collect_placed_ranges(static_signals, [])
            check_bit_ranges_no_overlap(
                f"MultiplexedPDU '{self.name}' static_group vs selector",
                [sel_range, *static_ranges],
            )
        return self


# ---------------------------------------------------------------------------
# PDU references
# ---------------------------------------------------------------------------


class ContainedPDURef(FLYNCBaseModel):
    """
    Reference to a PDU packed inside a :class:`ContainerPDU`.

    Parameters
    ----------
    pdu_id : int
        Numeric identifier placed in the slot header for this contained PDU.
    pdu_ref : str
        Name of the referenced PDU.
    offset : int, optional
        Bit offset of this slot (header + payload) within the container payload.
        When multiple PDUs are packed sequentially this encodes the start position
        of each slot so receivers can locate it without parsing preceding slots.
    """

    pdu_id: int = Field()
    pdu_ref: str = Field()
    offset: Optional[int] = Field(default=0, ge=0)


class PDUInstance(FLYNCBaseModel):
    """
    Placement of a PDU at a specific bit offset within a CAN or LIN frame.

    Parameters
    ----------
    pdu_ref : str
        Name of the referenced PDU.
    bit_position : int, optional
        Non-negative bit offset where this PDU begins within the frame.
    update_bit_position : int, optional
        Bit position of the update indication bit, when applicable.
    """

    pdu_ref: str = Field()
    bit_position: Optional[int] = Field(default=None, ge=0)
    update_bit_position: Optional[int] = Field(default=None, ge=0)


# ---------------------------------------------------------------------------
# ContainerPDU
# ---------------------------------------------------------------------------


class ContainerPDUHeader(FLYNCBaseModel):
    """
    Per-slot header configuration for a :class:`ContainerPDU`.

    Parameters
    ----------
    id_length_bits : int
        Bit length of the PDU ID field
    length_field_bits : int
        Bit length of the payload-length field
    """

    id_length_bits: int = Field()
    length_field_bits: int = Field()

    @field_validator("id_length_bits", "length_field_bits")
    @classmethod
    def must_be_byte_aligned(cls, v: int) -> int:
        if v % 8 != 0:
            raise err_major("must be a multiple of 8, got {value}", value=v)
        return v


class ContainerPDU(PDU):
    """
    Ethernet Container PDU that packs multiple PDUs into one frame payload.

    Each contained PDU is prefixed with a header carrying its ID and length,
    allowing the receiver to demultiplex the slots at runtime.

    Parameters
    ----------
    pdu_id : int
        Numeric identifier for this container PDU on the network.
    header : :class:`ContainerPDUHeader`
        Per-slot header format specifying the bit widths of the ID and length fields.
    contained_pdus : list of :class:`ContainedPDURef`
        PDUs packed inside this container, each referenced by name.
    """

    type: Literal["container"] = Field(default="container")
    pdu_id: int = Field(ge=0)
    header: ContainerPDUHeader = Field()
    contained_pdus: List[ContainedPDURef] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_minimum_container_size(self) -> "ContainerPDU":
        """Ensure container length covers the per-slot header overhead."""
        overhead_bits = self.header.id_length_bits + self.header.length_field_bits
        overhead = overhead_bits // 8  # bits → bytes (always byte-aligned)
        minimum = len(self.contained_pdus) * overhead
        if self.length < minimum:
            raise err_minor(
                "ContainerPDU '{name}': length {length} B is too small to "
                "hold {count} slot header(s) at {overhead} B each "
                "(minimum {minimum} B before payload bytes are counted)",
                name=self.name,
                length=self.length,
                count=len(self.contained_pdus),
                overhead=overhead,
                minimum=minimum,
            )
        return self

    @model_validator(mode="after")
    def validate_one_pdu_if_header_length_is_one(self) -> "ContainerPDU":
        """Ensure container length covers the per-slot header overhead."""

        if self.header.id_length_bits == 0 and self.header.length_field_bits == 0 and len(self.contained_pdus) != 1:
            raise err_minor("If header length is 0, there should be only one contained PDU")
        if (self.header.id_length_bits == 0 and self.header.length_field_bits != 0) or (
            self.header.id_length_bits != 0 and self.header.length_field_bits == 0
        ):
            raise err_minor("Both or None of the fields id_length_bits, and  length_field_bits should be zero")

        return self


# ---------------------------------------------------------------------------
# Bit-range helpers
# ---------------------------------------------------------------------------


def _signal_group_instance_range(sgi: SignalGroupInstance) -> Optional[BitRange]:
    """Return the bit range of a placed :class:`SignalGroupInstance` or ``None``.

    The group's footprint is the largest end-bit reached by any of its placed
    signal instances; ``None`` is returned when the group itself is unplaced
    or none of its signal instances have a ``bit_position``.
    """
    if sgi.bit_position is None:
        return None
    footprint = _signal_group_footprint(sgi.signal_group)
    if footprint <= 0:
        return None
    return (
        sgi.signal_group.name,
        sgi.bit_position,
        sgi.bit_position + footprint,
    )


def _collect_placed_ranges(
    signals: List[SignalInstance],
    signal_groups: List[SignalGroupInstance],
) -> List[BitRange]:
    """Return ``(name, start_bit, end_bit_exclusive)`` for all placed items."""
    return [
        *collect_bit_ranges(signals, _signal_instance_range),
        *collect_bit_ranges(signal_groups, _signal_group_instance_range),
    ]
