from typing import List, Literal, Optional, Tuple

from pydantic import Field, field_validator, model_validator

from flync.core.base_models import FLYNCBaseModel, UniqueName
from flync.core.utils.exceptions import err_minor
from flync.model.flync_4_signal.signal import (
    SignalGroupInstance,
    SignalInstance,
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
    pdu_usage : str, optional
        Optional string describing the usage of the PDU.
    description : str, optional
        Optional human-readable description.
    """

    name: str = Field()
    length: int = Field(gt=0)
    pdu_usage: Optional[str] = Field(default=None)
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
        _check_overflow(self.name, ranges, self.length * 8)
        _check_overlap(f"PDU '{self.name}'", ranges)
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
    signals : list of :class:`SignalInstance`
        Signal instances active for this mux value.
    signal_groups : list of :class:`SignalGroupInstance`
        Signal group instances active for this mux value.
    """

    selector_value: int = Field(ge=0)
    signals: List[SignalInstance] = Field(default_factory=list)
    signal_groups: List[SignalGroupInstance] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_intra_group_overlap(self) -> "MuxGroup":
        """Ensure signals within this mux group do not overlap each other."""
        ranges = _collect_placed_ranges(self.signals, self.signal_groups)
        _check_overlap(f"MuxGroup(selector={self.selector_value})", ranges)
        return self


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
    static_signals: List[SignalInstance] = Field(default_factory=list)
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
        sel_range: Tuple[str, int, int] = (
            self.selector_signal.signal.name,
            sel_bp,
            sel_bp + self.selector_signal.signal.bit_length,
        )
        for group in self.mux_groups:
            group_ranges = _collect_placed_ranges(group.signals, group.signal_groups)
            _check_overlap(
                f"MultiplexedPDU '{self.name}' " f"mux_group(selector={group.selector_value}) vs selector",
                [sel_range, *group_ranges],
            )
        if self.static_signals:
            static_ranges = _collect_placed_ranges(self.static_signals, [])
            _check_overlap(
                f"MultiplexedPDU '{self.name}' static_signals vs selector",
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

    id_length_bits: int = Field(gt=0)
    length_field_bits: int = Field(gt=0)

    @field_validator("id_length_bits", "length_field_bits")
    @classmethod
    def must_be_byte_aligned(cls, v: int) -> int:
        if v % 8 != 0:
            raise ValueError(f"must be a multiple of 8, got {v}")
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


# ---------------------------------------------------------------------------
# Bit-range helpers
# ---------------------------------------------------------------------------


def _collect_placed_ranges(
    signals: List[SignalInstance],
    signal_groups: List[SignalGroupInstance],
) -> List[Tuple[str, int, int]]:
    """Return ``(name, start_bit, end_bit_exclusive)`` for all placed items."""
    ranges: List[Tuple[str, int, int]] = []
    for si in signals:
        if si.bit_position is not None:
            ranges.append(
                (
                    si.signal.name,
                    si.bit_position,
                    si.bit_position + si.signal.bit_length,
                )
            )
    for sgi in signal_groups:
        if sgi.bit_position is None:
            continue
        total_bits = sum(s.bit_length for s in sgi.signal_group.signals)
        if total_bits > 0:
            ranges.append(
                (
                    sgi.signal_group.name,
                    sgi.bit_position,
                    sgi.bit_position + total_bits,
                )
            )
    return ranges


def _check_overflow(
    pdu_name: str,
    ranges: List[Tuple[str, int, int]],
    pdu_bits: int,
) -> None:
    """Raise ``err_minor`` when any range exceeds ``pdu_bits``."""
    for item_name, start, end in ranges:
        if end > pdu_bits:
            raise err_minor(
                "PDU '{pdu_name}': signal/group '{item}' bit range [{start}, {end}) overflows PDU length of {bits} bits",
                pdu_name=pdu_name,
                item=item_name,
                start=start,
                end=end,
                bits=pdu_bits,
            )


def _check_overlap(
    context: str,
    ranges: List[Tuple[str, int, int]],
) -> None:
    """Raise ``err_minor`` when any two ranges intersect."""
    for i, (name_a, start_a, end_a) in enumerate(ranges):
        for j in range(i + 1, len(ranges)):
            name_b, start_b, end_b = ranges[j]
            if start_a < end_b and start_b < end_a:
                raise err_minor(
                    "{context}: '{a}' [{sa}, {ea}) and '{b}' [{sb}, {eb}) overlap",
                    context=context,
                    a=name_a,
                    sa=start_a,
                    ea=end_a,
                    b=name_b,
                    sb=start_b,
                    eb=end_b,
                )
