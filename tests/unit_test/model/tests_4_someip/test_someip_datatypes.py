import pytest
from pydantic import ValidationError

from flync.model.flync_4_someip import Enum, Int8, UInt8
from flync.model.flync_4_someip.someip_datatypes import EnumEntry


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
