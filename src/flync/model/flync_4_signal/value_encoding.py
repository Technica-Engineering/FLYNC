"""Value-encoding models for :class:`~flync.model.flync_4_signal.Signal`.

A :class:`ValueEncoding` describes how raw integer values transmitted on the
wire are converted into human-readable labels.  Three variants are supported,
selected by the ``type`` discriminator:

* :class:`TextTable` — maps inclusive raw value ranges to labels.  Use this
  for ordinary enumerated signals (gear position, operating mode), for
  reserved sentinel codes such as ``Signal_Not_Available`` (a single value
  is expressed by omitting ``to_value``, which defaults to ``from_value``),
  and when one label covers many contiguous raw values (e.g. ``0..9 = Low``).

* :class:`BitfieldTextTable` — decodes the signal as a set of independent
  :class:`BitfieldGroup` regions, each with its own enum of mutually
  exclusive states.  Use this when several unrelated small enums are
  packed into one signal.

* :class:`BitmaskFlags` — decodes the signal as a set of independent
  on/off flags, each identified by a disjoint :class:`BitmaskFlag` mask.
  Use this for partial-network relevance masks and similar feature-flag
  registers where multiple flags can be active simultaneously.
"""

from typing import Annotated, List, Literal, Union

from pydantic import Field, model_validator

from flync.core.base_models import FLYNCBaseModel
from flync.core.utils.common_validators import (
    check_bit_ranges_no_overlap,
    collect_bit_ranges,
)
from flync.core.utils.exceptions import err_major


class TextEntry(FLYNCBaseModel):
    """
    Mapping from an inclusive raw value range to a label.

    - For a **value range**:
      Use the keys ``from_value:`` and ``to_value:`` to define upper and lower bounds.

    - For a **single value**:
      Either define ``from_value`` and ``to_value`` with the same value or simply use the key ``value:``.

    Parameters
    ----------
    from_value : int
        Inclusive lower bound of the raw value range. Alias `value`
    to_value : int
        Inclusive upper bound of the raw value range. Optional; defaults to `from_value` for single-value entries.
    label : str
        Human-readable label for this range (e.g. ``"Low"``,
        ``"Medium"``).
    """

    from_value: int = Field(alias="value")
    to_value: int = Field(default_factory=lambda data: data.get("from_value", 0))
    label: str = Field()

    @model_validator(mode="before")
    @classmethod
    def _validate_value_input_format(cls, data: dict) -> dict:
        if not isinstance(data, dict):
            return data

        has_value = "value" in data
        has_from_value = "from_value" in data
        has_to_value = "to_value" in data

        if has_value and has_to_value:
            raise err_major(
                "TextEntry: cannot use both 'value' and 'to_value' — either use 'value' for a single value, "
                "or 'from_value' and 'to_value' for a range"
            )

        if has_from_value and not has_to_value:
            raise err_major(
                "TextEntry: 'from_value' must be paired with 'to_value' — either use 'value' for a single value, "
                "or 'from_value' and 'to_value' for a range"
            )

        return data

    @model_validator(mode="after")
    def _validate_bounds(self) -> "TextEntry":
        if self.to_value < self.from_value:
            raise err_major(
                "TextEntry '{label}': to_value ({to_value}) must not be less than from_value ({from_value})",
                label=self.label,
                to_value=self.to_value,
                from_value=self.from_value,
            )
        return self


class TextTable(FLYNCBaseModel):
    """
    Maps inclusive raw value ranges to text labels.

    A single raw value is expressed by omitting ``to_value`` (it defaults to
    ``from_value``), or by explicitly setting both equal (e.g. a reserved
    ``Signal_Not_Available`` code); a wider range covers many contiguous raw
    values with one label.

    Parameters
    ----------
    type : Literal["text_table"]
        Discriminator selecting this value-encoding variant.
    entries : list of :class:`TextEntry`
        Non-empty list of range-to-label mappings.  Ranges must not
        overlap and labels must be unique within the table.
    """

    type: Literal["text_table"] = "text_table"
    entries: List[TextEntry] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_no_overlap(self) -> "TextTable":
        ranges = collect_bit_ranges(
            self.entries,
            lambda e: (e.label, e.from_value, e.to_value + 1),
        )
        check_bit_ranges_no_overlap("TextTable", ranges)
        return self

    @model_validator(mode="after")
    def _validate_unique_labels(self) -> "TextTable":
        seen: set[str] = set()
        for e in self.entries:
            if e.label in seen:
                raise err_major("Duplicate label {label!r} in TextTable; each label must appear at most once", label=e.label)
            seen.add(e.label)
        return self


class BitfieldState(FLYNCBaseModel):
    """
    One named state within a :class:`BitfieldGroup`, compared against the
    raw value **after** the group's mask has been applied.

    Parameters
    ----------
    label : str
        Symbolic name of this state (e.g. ``"ProblemFailure"``).
    from_value : int
        Inclusive lower bound for ``(raw & group.mask)``.
    to_value : int
        Inclusive upper bound for ``(raw & group.mask)``.  Optional; defaults
        to ``from_value`` for an exact-match state.
    """

    label: str = Field()
    from_value: int = Field(ge=0)
    to_value: int = Field(ge=0, default_factory=lambda data: data.get("from_value", 0))

    @model_validator(mode="after")
    def _validate_bounds(self) -> "BitfieldState":
        if self.to_value < self.from_value:
            raise err_major(
                "BitfieldState '{label}': to_value ({to_value}) must not be less than from_value ({from_value})",
                label=self.label,
                to_value=self.to_value,
                from_value=self.from_value,
            )
        return self


class BitfieldGroup(FLYNCBaseModel):
    """
    One named region of bits within a signal, with its own enum of states.

    Matching logic for a state ``s`` of this group is
    ``s.from_value <= (raw & mask) <= s.to_value``.  Exactly one state is
    active per group at any time.

    Parameters
    ----------
    name : str
        Name of the bitfield group (e.g. ``"Problem"``).
    mask : int
        Bitmask selecting the bits that belong to this group.  Must be
        strictly positive and fit within the owning signal's
        ``bit_length`` (checked at signal level).
    states : list of :class:`BitfieldState`
        Non-empty list of states defined for this group.  State values
        must lie inside ``mask`` and may not overlap; labels must be
        unique within the group.
    """

    name: str = Field()
    mask: int = Field(gt=0)
    states: List[BitfieldState] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_states(self) -> "BitfieldGroup":
        seen: set[str] = set()
        for s in self.states:
            if s.label in seen:
                raise err_major("BitfieldGroup '{name}': duplicate state label {label!r}", name=self.name, label=s.label)
            seen.add(s.label)
            if (s.from_value | s.to_value) & ~self.mask:
                raise err_major(
                    "BitfieldGroup '{name}': state '{label}' range [{from_value}, {to_value}] has bits outside mask {mask}",
                    name=self.name,
                    label=s.label,
                    from_value=s.from_value,
                    to_value=s.to_value,
                    mask=f"{self.mask:#x}",
                )
        ranges = collect_bit_ranges(
            self.states,
            lambda s: (s.label, s.from_value, s.to_value + 1),
        )
        check_bit_ranges_no_overlap(f"BitfieldGroup '{self.name}'", ranges)
        return self


class BitfieldTextTable(FLYNCBaseModel):
    """
    Decodes a signal as a set of independent :class:`BitfieldGroup` regions.

    Each group occupies a disjoint mask of the signal's bits and carries
    its own enum of mutually exclusive states.  Use :class:`BitmaskFlags`
    instead when the bits represent independent on/off flags rather than
    sub-enums.

    Parameters
    ----------
    type : Literal["bitfield_text_table"]
        Discriminator selecting this value-encoding variant.
    groups : list of :class:`BitfieldGroup`
        Non-empty list of bitfield groups.  Group names must be unique and
        group masks must be pairwise disjoint (no shared bits).
    """

    type: Literal["bitfield_text_table"] = "bitfield_text_table"
    groups: List[BitfieldGroup] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_groups(self) -> "BitfieldTextTable":
        seen: set[str] = set()
        accumulated_mask = 0
        for g in self.groups:
            if g.name in seen:
                raise err_major("BitfieldTextTable: duplicate group name {name!r}", name=g.name)
            seen.add(g.name)
            if accumulated_mask & g.mask:
                raise err_major(
                    "BitfieldTextTable: group '{name}' mask {mask} overlaps another group's mask",
                    name=g.name,
                    mask=f"{g.mask:#x}",
                )
            accumulated_mask |= g.mask
        return self


class BitmaskFlag(FLYNCBaseModel):
    """
    One named on/off flag inside a :class:`BitmaskFlags` encoding.

    A flag is considered active when ``(raw & mask) == mask`` — i.e.
    every bit of ``mask`` is set in the raw signal value.  A single
    ``BitmaskFlag`` may cover one bit (the common case) or several bits
    that must all be set together.

    Parameters
    ----------
    mask : int
        Bitmask identifying this flag.  Must be strictly positive and
        fit within the owning signal's ``bit_length`` (checked at
        signal level).
    label : str
        Human-readable name of the flag (e.g. ``"MirrorLeft"``).
    """

    mask: int = Field(gt=0)
    label: str = Field()


class BitmaskFlags(FLYNCBaseModel):
    """
    Decodes a signal as a set of independent on/off flags.

    Each :class:`BitmaskFlag` is active iff ``(raw & flag.mask) == flag.mask``;
    the decoded value of the signal is the **set** of active flag labels.
    Several flags can be active at the same time.

    Typical use case: a partial-network relevance vector where each bit
    names one vehicle function as currently relevant or awake.

    Use :class:`BitfieldTextTable` instead when the bits represent
    mutually exclusive sub-enums rather than independent flags.

    Parameters
    ----------
    type : Literal["bitmask_flags"]
        Discriminator selecting this value-encoding variant.
    flags : list of :class:`BitmaskFlag`
        Non-empty list of flags.  Labels must be unique and masks must
        be pairwise disjoint (no shared bits).
    """

    type: Literal["bitmask_flags"] = "bitmask_flags"
    flags: List[BitmaskFlag] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_flags(self) -> "BitmaskFlags":
        seen: set[str] = set()
        accumulated_mask = 0
        for f in self.flags:
            if f.label in seen:
                raise err_major("BitmaskFlags: duplicate flag label {label!r}", label=f.label)
            seen.add(f.label)
            if accumulated_mask & f.mask:
                raise err_major(
                    "BitmaskFlags: flag '{label}' mask {mask} overlaps another flag's mask",
                    label=f.label,
                    mask=f"{f.mask:#x}",
                )
            accumulated_mask |= f.mask
        return self


ValueEncoding = Annotated[
    Union[TextTable, BitfieldTextTable, BitmaskFlags],
    Field(discriminator="type"),
]
