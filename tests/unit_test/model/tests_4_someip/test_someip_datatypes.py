import pytest
from pydantic import ValidationError

from flync.model.flync_4_someip import Bitfield, Enum, Int8, UInt8
from flync.model.flync_4_someip.someip_datatypes import BitfieldEntry, EnumEntry
from tests.error_assertions import assert_single_error


def _bit_entries(count: int, start: int = 0) -> list[dict]:
    """``count`` consecutive bitfield entries beginning at bit ``start``."""
    return [{"name": f"field_{position}", "bitposition": position} for position in range(start, start + count)]


class TestBitfield:
    """Every entry of a :class:`Bitfield` must fit into the declared length and claim a bitposition of its own."""

    @pytest.mark.parametrize(
        "length, fields",
        [
            pytest.param(8, None, id="no_fields"),
            pytest.param(8, _bit_entries(8), id="fields_fill_length"),
            pytest.param(8, _bit_entries(1, start=7), id="last_bit_only"),
            pytest.param(16, _bit_entries(3), id="fewer_fields_than_length"),
            pytest.param(64, _bit_entries(64), id="max_length_filled"),
            pytest.param(8, [{"name": "B", "bitposition": 3}, {"name": "A", "bitposition": 1}], id="unordered_unique_bitpositions"),
        ],
    )
    def test_positive_fields_within_length(self, length, fields):
        """Entries inside the declared length are accepted; leaving bits undefined and declaring them out of order is allowed."""
        bitfield = Bitfield(name="bf", length=length, fields=fields)
        assert bitfield.fields == ([BitfieldEntry(**field) for field in fields] if fields else None)

    @pytest.mark.parametrize(
        "length, fields, error_id, message_fragment",
        [
            pytest.param(
                8,
                _bit_entries(9),
                "FLYNC-SOM-MIN-CONS-138",
                "Number of defined fields (9) exceeds the bitfield length (8)",
                id="one_field_too_many",
            ),
            pytest.param(
                8,
                _bit_entries(7) + [{"name": "H", "bitposition": 8}],
                "FLYNC-SOM-MIN-VAL-139",
                "Bitposition of H is out of range. Must be < 8, got 8.",
                id="bitposition_at_length",
            ),
            pytest.param(
                16,
                [{"name": "H", "bitposition": 20}],
                "FLYNC-SOM-MIN-VAL-139",
                "Bitposition of H is out of range. Must be < 16, got 20.",
                id="bitposition_beyond_length",
            ),
            pytest.param(
                8,
                [{"name": "A", "bitposition": -1}],
                None,
                "fields.0.bitposition: Input should be greater than or equal to 0",
                id="negative_bitposition",
            ),
            pytest.param(
                8,
                _bit_entries(6) + [{"name": "H", "bitposition": 7}, {"name": "H", "bitposition": 7}],
                "FLYNC-SOM-MIN-UNIQ-246",
                "Bitposition 7 is claimed by 'H' and 'H'.",
                id="duplicated_entry_within_length",
            ),
            pytest.param(
                8,
                [{"name": "A", "bitposition": 0}, {"name": "B", "bitposition": 0}],
                "FLYNC-SOM-MIN-UNIQ-246",
                "Bitposition 0 is claimed by 'A' and 'B'.",
                id="two_names_on_one_bitposition",
            ),
        ],
    )
    def test_negative_invalid_fields(self, length, fields, error_id, message_fragment):
        """Each rejected bitfield is pinned to the id of the rule it breaks: size, range, or bitposition uniqueness."""
        with pytest.raises(ValidationError) as exc_info:
            Bitfield(name="corrupt_bitfield", length=length, fields=fields)
        assert_single_error(exc_info, error_id, message_fragment)


class TestEnumEntries:
    """Tests for the entry validation of :class:`Enum`."""

    def test_valid_entries(self):
        """Entries with unique values inside the base type range are accepted."""
        enum = Enum(
            name="MyEnum",
            entries=[EnumEntry(value=value, name=f"entry_{value}") for value in range(4)],
        )
        assert isinstance(enum.base_type, UInt8)
        assert len(enum.entries) == 4

    def test_duplicate_value_raises(self):
        """We expect a ValidationError when two entries share the same value."""
        entries = [EnumEntry(value=1, name="first"), EnumEntry(value=1, name="second")]

        with pytest.raises(ValidationError) as exc_info:
            Enum(name="MyEnum", entries=entries)
        assert "Duplicate enum value: 1" in str(exc_info.value)

    def test_value_above_base_type_range_raises(self):
        """We expect a ValidationError when a value does not fit into the unsigned base type."""
        entries = [EnumEntry(value=256, name="too_big")]

        with pytest.raises(ValidationError) as exc_info:
            Enum(name="MyEnum", entries=entries)
        assert "exceeds valid range for UInt8" in str(exc_info.value)

    def test_negative_value_in_int8_range_ok(self):
        """Negative values are accepted for a signed base type."""
        enum = Enum(name="MyEnum", base_type=Int8(), entries=[EnumEntry(value=-128, name="minimum")])
        assert enum.entries[0].value == -128

    def test_value_below_int8_range_raises(self):
        """We expect a ValidationError when a value is below the signed base type minimum."""
        base_type = Int8()
        entries = [EnumEntry(value=-129, name="too_small")]

        with pytest.raises(ValidationError) as exc_info:
            Enum(name="MyEnum", base_type=base_type, entries=entries)
        assert "exceeds valid range for Int8" in str(exc_info.value)

    def test_invalid_base_type_reports_cleanly(self):
        """An invalid base type is reported as ValidationError instead of crashing the entry validation."""
        entries = [EnumEntry(value=256, name="too_big")]

        with pytest.raises(ValidationError) as exc_info:
            Enum(name="MyEnum", base_type={"type": "nonsense"}, entries=entries)
        assert "base_type" in str(exc_info.value)
