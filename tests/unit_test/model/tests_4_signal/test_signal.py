import pytest
from pydantic import ValidationError

from flync.model.flync_4_signal.signal import (
    BitfieldGroup,
    BitfieldState,
    BitfieldTextTable,
    BitmaskFlag,
    BitmaskFlags,
    InstancePlacement,
    Signal,
    SignalDataType,
    SignalGroup,
    SignalGroupInstance,
    SignalInstance,
    TextEntry,
    TextTable,
)

# ---------------------------------------------------------------------------
# SignalDataType helpers
# ---------------------------------------------------------------------------


def test_positive_signal_data_type_all_values():
    expected = {
        "uint8",
        "uint16",
        "uint32",
        "uint64",
        "int8",
        "int16",
        "int32",
        "int64",
        "float32",
        "float64",
        "char",
        "bytearray",
    }
    assert {dt.value for dt in SignalDataType} == expected


def test_positive_signal_data_type_natural_bit_width():
    assert SignalDataType.UINT8.natural_bit_width() == 8
    assert SignalDataType.UINT16.natural_bit_width() == 16
    assert SignalDataType.UINT32.natural_bit_width() == 32
    assert SignalDataType.UINT64.natural_bit_width() == 64
    assert SignalDataType.INT8.natural_bit_width() == 8
    assert SignalDataType.INT16.natural_bit_width() == 16
    assert SignalDataType.INT32.natural_bit_width() == 32
    assert SignalDataType.INT64.natural_bit_width() == 64
    assert SignalDataType.FLOAT32.natural_bit_width() == 32
    assert SignalDataType.FLOAT64.natural_bit_width() == 64
    assert SignalDataType.CHAR.natural_bit_width() == 8
    assert SignalDataType.BYTEARRAY.natural_bit_width() == 8


def test_positive_signal_data_type_is_float():
    assert SignalDataType.FLOAT32.is_float() is True
    assert SignalDataType.FLOAT64.is_float() is True
    assert SignalDataType.UINT8.is_float() is False
    assert SignalDataType.INT32.is_float() is False
    assert SignalDataType.CHAR.is_float() is False


def test_positive_signal_data_type_is_unsigned_integer():
    for dt in (
        SignalDataType.UINT8,
        SignalDataType.UINT16,
        SignalDataType.UINT32,
        SignalDataType.UINT64,
    ):
        assert dt.is_unsigned_integer() is True
    for dt in (
        SignalDataType.INT8,
        SignalDataType.FLOAT32,
        SignalDataType.CHAR,
        SignalDataType.BYTEARRAY,
    ):
        assert dt.is_unsigned_integer() is False


def test_positive_signal_data_type_is_signed_integer():
    for dt in (
        SignalDataType.INT8,
        SignalDataType.INT16,
        SignalDataType.INT32,
        SignalDataType.INT64,
    ):
        assert dt.is_signed_integer() is True
    for dt in (
        SignalDataType.UINT8,
        SignalDataType.FLOAT64,
        SignalDataType.CHAR,
        SignalDataType.BYTEARRAY,
    ):
        assert dt.is_signed_integer() is False


# ---------------------------------------------------------------------------
# TextEntry / TextTable
# ---------------------------------------------------------------------------


def test_positive_text_entry_single_value_explicit():
    """Explicit form: both from_value and to_value provided."""
    entry = TextEntry(from_value=0, to_value=0, label="Off")
    assert entry.from_value == 0
    assert entry.to_value == 0
    assert entry.label == "Off"


def test_positive_text_entry_single_value_terse():
    """Terse form: use 'value' alias for a single value."""
    entry = TextEntry(value=5, label="X")
    assert entry.from_value == 5
    assert entry.to_value == 5


def test_positive_text_entry_terse_via_dict():
    """Terse form via model_validate (YAML path) using 'value' alias."""
    entry = TextEntry.model_validate({"value": 7, "label": "Y"})
    assert entry.from_value == 7
    assert entry.to_value == 7


def test_positive_text_entry_terse_dump_omits_to_value():
    """Terse entries round-trip tersely: unset to_value is not serialized."""
    entry = TextEntry.model_validate({"value": 7, "label": "Y"})
    assert entry.to_value == 7
    assert "to_value" not in entry.model_dump(exclude_unset=True)


def test_positive_text_entry_negative_value():
    entry = TextEntry(value=-1, label="Error")
    assert entry.from_value == -1
    assert entry.to_value == -1


def test_positive_range_text_entry_basic():
    entry = TextEntry(from_value=10, to_value=20, label="MidRange")
    assert entry.from_value == 10
    assert entry.to_value == 20


def test_negative_text_entry_value_and_to_value_together():
    with pytest.raises(ValidationError, match="cannot use both 'value' and 'to_value'"):
        TextEntry.model_validate({"value": 5, "to_value": 10, "label": "Invalid"})


def test_negative_text_entry_from_value_alone():
    with pytest.raises(ValidationError, match="'from_value' must be paired with 'to_value'"):
        TextEntry.model_validate({"from_value": 5, "label": "Invalid"})


def test_positive_text_table_model_validate():
    table = TextTable.model_validate(
        {
            "type": "text_table",
            "entries": [{"from_value": 3, "to_value": 3, "label": "Active"}],
        }
    )
    assert isinstance(table, TextTable)
    assert table.entries[0].label == "Active"


def test_positive_range_text_table_model_validate():
    table = TextTable.model_validate(
        {
            "type": "text_table",
            "entries": [{"from_value": 0, "to_value": 9, "label": "Low"}],
        }
    )
    assert isinstance(table, TextTable)
    assert table.entries[0].to_value == 9


def test_positive_bitfield_text_table_model_validate():
    table = BitfieldTextTable.model_validate(
        {
            "type": "bitfield_text_table",
            "groups": [
                {
                    "name": "Problem",
                    "mask": 0xFF,
                    "states": [{"label": "None", "from_value": 0, "to_value": 0}],
                },
            ],
        }
    )
    assert isinstance(table, BitfieldTextTable)
    assert table.groups[0].mask == 0xFF


def test_positive_bitmask_flags_model_validate():
    table = BitmaskFlags.model_validate(
        {
            "type": "bitmask_flags",
            "flags": [
                {"mask": 0x01, "label": "MirrorLeft"},
                {"mask": 0x02, "label": "MirrorRight"},
            ],
        }
    )
    assert isinstance(table, BitmaskFlags)
    assert len(table.flags) == 2


# ---------------------------------------------------------------------------
# Signal — positive tests
# ---------------------------------------------------------------------------


def test_positive_signal_minimal():
    sig = Signal(name="temperature", bit_length=8, data_type=SignalDataType.UINT8)
    assert sig.name == "temperature"
    assert sig.bit_length == 8
    assert sig.data_type == SignalDataType.UINT8
    assert sig.factor == 1.0
    assert sig.offset == 0.0


def test_positive_signal_with_optional_fields():
    sig = Signal(
        name="speed",
        bit_length=16,
        data_type=SignalDataType.UINT16,
        description="Vehicle speed",
        factor=0.1,
        offset=0.0,
        lower_limit=0.0,
        upper_limit=250.0,
        unit="km/h",
    )
    assert sig.unit == "km/h"
    assert sig.factor == 0.1


@pytest.mark.parametrize(
    "data_type, bit_length",
    [
        pytest.param(SignalDataType.UINT8, 8, id="uint8"),
        pytest.param(SignalDataType.UINT8, 4, id="uint8_4bit"),
        pytest.param(SignalDataType.UINT16, 12, id="uint16_12bit"),
        pytest.param(SignalDataType.UINT32, 32, id="uint32"),
        pytest.param(SignalDataType.UINT64, 64, id="uint64"),
        pytest.param(SignalDataType.INT8, 8, id="int8"),
        pytest.param(SignalDataType.INT16, 16, id="int16"),
        pytest.param(SignalDataType.INT32, 32, id="int32"),
        pytest.param(SignalDataType.INT64, 64, id="int64"),
        pytest.param(SignalDataType.CHAR, 8, id="char"),
        pytest.param(SignalDataType.CHAR, 48, id="char"),
        pytest.param(SignalDataType.BYTEARRAY, 24, id="bytearray_24bit"),
        pytest.param(SignalDataType.BYTEARRAY, 8, id="bytearray_1bit"),
    ],
)
def test_positive_signal_all_types(data_type, bit_length):
    sig = Signal(
        name=f"sig_{data_type.value}",
        bit_length=bit_length,
        data_type=data_type,
    )
    assert isinstance(sig, Signal)


def test_positive_signal_float32():
    sig = Signal(name="torque", bit_length=32, data_type=SignalDataType.FLOAT32)
    assert sig.data_type == SignalDataType.FLOAT32


def test_positive_signal_float64():
    sig = Signal(name="latitude", bit_length=64, data_type=SignalDataType.FLOAT64)
    assert sig.data_type == SignalDataType.FLOAT64


def test_positive_signal_with_text_table_single_values():
    sig = Signal(
        name="gear",
        bit_length=4,
        data_type=SignalDataType.UINT8,
        value_encoding=TextTable(
            entries=[
                TextEntry(value=0, label="Neutral"),
                TextEntry(value=1, label="First"),
                TextEntry(from_value=2, to_value=2, label="Second"),
            ],
        ),
    )
    assert isinstance(sig.value_encoding, TextTable)
    assert len(sig.value_encoding.entries) == 3


def test_positive_signal_with_range_text_table():
    sig = Signal(
        name="severity",
        bit_length=8,
        data_type=SignalDataType.UINT8,
        value_encoding=TextTable(
            entries=[
                TextEntry(from_value=0, to_value=9, label="Low"),
                TextEntry(from_value=10, to_value=99, label="Medium"),
                TextEntry(from_value=100, to_value=200, label="High"),
                TextEntry(from_value=255, to_value=255, label="Signal_Not_Available"),
            ],
        ),
    )
    assert isinstance(sig.value_encoding, TextTable)
    assert len(sig.value_encoding.entries) == 4


def test_positive_signal_with_range_text_table_signed():
    sig = Signal(
        name="signed_codes",
        bit_length=8,
        data_type=SignalDataType.INT8,
        value_encoding=TextTable(
            entries=[
                TextEntry(from_value=-128, to_value=-128, label="Invalid"),
                TextEntry(from_value=-127, to_value=-1, label="Negative_Range"),
                TextEntry(from_value=0, to_value=127, label="Valid"),
            ],
        ),
    )
    assert len(sig.value_encoding.entries) == 3


def test_positive_signal_text_table_mixed_terse_and_range():
    """Terse single values (using 'value' alias) and explicit ranges coexist in one table."""
    sig = Signal(
        name="mixed_terse_range",
        bit_length=8,
        data_type=SignalDataType.UINT8,
        value_encoding=TextTable(
            entries=[
                TextEntry(from_value=0, to_value=9, label="Low"),
                TextEntry(from_value=10, to_value=99, label="Medium"),
                TextEntry(value=255, label="Signal_Not_Available"),
            ],
        ),
    )
    assert len(sig.value_encoding.entries) == 3
    assert sig.value_encoding.entries[2].to_value == 255


def test_negative_text_table_terse_value_overlaps_range():
    """Overlap detection fires between a terse single value and a covering range."""
    with pytest.raises(ValidationError, match="overlap"):
        TextTable(
            entries=[
                TextEntry(from_value=0, to_value=9, label="Low"),
                TextEntry(value=5, label="Five"),
            ],
        )


def test_positive_signal_text_table_combined_with_linear():
    sig = Signal(
        name="VehicleSpeed",
        bit_length=16,
        data_type=SignalDataType.UINT16,
        factor=0.01,
        offset=0.0,
        lower_limit=0.0,
        upper_limit=655.35,
        unit="km/h",
        value_encoding=TextTable(
            entries=[
                TextEntry(from_value=65535, to_value=65535, label="Signal_Not_Available"),
            ],
        ),
    )
    assert sig.factor == 0.01
    assert isinstance(sig.value_encoding, TextTable)


def test_positive_signal_with_bitmask_flags():
    sig = Signal(
        name="PartialNetworkRelevance",
        bit_length=8,
        data_type=SignalDataType.UINT8,
        value_encoding=BitmaskFlags(
            flags=[
                BitmaskFlag(mask=0x01, label="MirrorLeft"),
                BitmaskFlag(mask=0x02, label="MirrorRight"),
                BitmaskFlag(mask=0x04, label="CabinLight"),
                BitmaskFlag(mask=0x08, label="EngineStatus"),
                BitmaskFlag(mask=0x10, label="TransmissionStatus"),
                BitmaskFlag(mask=0x20, label="VehicleDynamics"),
            ],
        ),
    )
    assert isinstance(sig.value_encoding, BitmaskFlags)
    assert len(sig.value_encoding.flags) == 6


def test_positive_signal_with_bitmask_flags_multi_bit_mask():
    """A single flag may span several bits (e.g. 0x03 = 'front mirrors')."""
    sig = Signal(
        name="GroupedFlags",
        bit_length=8,
        data_type=SignalDataType.UINT8,
        value_encoding=BitmaskFlags(
            flags=[
                BitmaskFlag(mask=0x03, label="FrontMirrors"),
                BitmaskFlag(mask=0x04, label="CabinLight"),
            ],
        ),
    )
    assert sig.value_encoding.flags[0].mask == 0x03


def test_positive_bitfield_state_terse_form():
    """BitfieldState with terse form (to_value defaults to from_value)."""
    state = BitfieldState(label="Test", from_value=5)
    assert state.from_value == 5
    assert state.to_value == 5


def test_positive_signal_with_bitfield_text_table():
    sig = Signal(
        name="States",
        bit_length=16,
        data_type=SignalDataType.UINT16,
        value_encoding=BitfieldTextTable(
            groups=[
                BitfieldGroup(
                    name="Problem",
                    mask=0xFF,
                    states=[
                        BitfieldState(label="ProblemNone", from_value=0x00),
                        BitfieldState(label="ProblemFailure", from_value=0x08, to_value=0x08),
                        BitfieldState(label="ProblemMajor", from_value=0x18),
                    ],
                ),
            ],
        ),
    )
    assert isinstance(sig.value_encoding, BitfieldTextTable)
    assert sig.value_encoding.groups[0].mask == 0xFF
    assert len(sig.value_encoding.groups[0].states) == 3


def test_positive_signal_with_bitfield_text_table_multiple_groups():
    sig = Signal(
        name="StatusWord",
        bit_length=16,
        data_type=SignalDataType.UINT16,
        value_encoding=BitfieldTextTable(
            groups=[
                BitfieldGroup(
                    name="Problem",
                    mask=0x00FF,
                    states=[
                        BitfieldState(label="ProblemNone", from_value=0x00, to_value=0x00),
                        BitfieldState(label="ProblemFailure", from_value=0x08, to_value=0x08),
                    ],
                ),
                BitfieldGroup(
                    name="Mode",
                    mask=0xFF00,
                    states=[
                        BitfieldState(label="ModeIdle", from_value=0x0000, to_value=0x0000),
                        BitfieldState(label="ModeActive", from_value=0x0100, to_value=0x0100),
                    ],
                ),
            ],
        ),
    )
    assert len(sig.value_encoding.groups) == 2


def test_positive_signal_with_negative_factor():
    sig = Signal(
        name="inverted",
        bit_length=8,
        data_type=SignalDataType.INT8,
        factor=-1.0,
    )
    assert sig.factor == -1.0


def test_positive_signal_limits_equal():
    sig = Signal(
        name="exact",
        bit_length=8,
        data_type=SignalDataType.UINT8,
        lower_limit=5.0,
        upper_limit=5.0,
    )
    assert sig.lower_limit == sig.upper_limit


def test_positive_signal_only_lower_limit():
    sig = Signal(
        name="lower_only",
        bit_length=8,
        data_type=SignalDataType.UINT8,
        lower_limit=0.0,
    )
    assert sig.upper_limit is None


def test_positive_signal_only_upper_limit():
    sig = Signal(
        name="upper_only",
        bit_length=8,
        data_type=SignalDataType.UINT8,
        upper_limit=100.0,
    )
    assert sig.lower_limit is None


@pytest.mark.parametrize(
    "data_type, bit_length, initial_value",
    [
        pytest.param(SignalDataType.UINT8, 8, 0, id="uint8_zero"),
        pytest.param(SignalDataType.UINT8, 8, 255, id="uint8_max"),
        pytest.param(SignalDataType.UINT8, 4, 15, id="uint8_4bit_max"),
        pytest.param(SignalDataType.INT8, 8, -128, id="int8_min"),
        pytest.param(SignalDataType.INT8, 8, 127, id="int8_max"),
        pytest.param(SignalDataType.INT16, 16, 0, id="int16_zero"),
        pytest.param(SignalDataType.UINT32, 32, 0, id="uint32_zero"),
    ],
)
def test_positive_signal_initial_value_integer(data_type, bit_length, initial_value):
    sig = Signal(
        name=f"iv_{data_type.value}_{initial_value}",
        bit_length=bit_length,
        data_type=data_type,
        initial_value=initial_value,
    )
    assert sig.initial_value == initial_value


def test_positive_signal_initial_value_float():
    sig = Signal(
        name="iv_float",
        bit_length=32,
        data_type=SignalDataType.FLOAT32,
        initial_value=3.14,
    )
    assert sig.initial_value == 3.14


def test_positive_signal_initial_value_int_for_float():
    sig = Signal(
        name="iv_float_int",
        bit_length=32,
        data_type=SignalDataType.FLOAT32,
        initial_value=0,
    )
    assert sig.initial_value == 0


def test_positive_signal_initial_value_char():
    sig = Signal(
        name="iv_char",
        bit_length=8,
        data_type=SignalDataType.CHAR,
        initial_value="A",
    )
    assert sig.initial_value == "A"


def test_positive_signal_initial_value_bytearray():
    sig = Signal(
        name="iv_bytes",
        bit_length=16,
        data_type=SignalDataType.BYTEARRAY,
        initial_value=b"\x00\xff",
    )
    assert sig.initial_value == b"\x00\xff"


def test_positive_signal_model_validate():
    data = {
        "name": "validated_sig",
        "bit_length": 8,
        "data_type": "uint8",
        "factor": 0.5,
        "offset": 10.0,
    }
    sig = Signal.model_validate(data)
    assert isinstance(sig, Signal)
    assert sig.factor == 0.5


def test_positive_signal_data_type_roundtrip():
    """Test that SignalDataType serializes to string and deserializes back to enum."""
    import random

    sig_original = Signal(
        name=f"orig-{random.random()}",
        bit_length=8,
        data_type=SignalDataType("uint8"),
        factor=2.0,
        offset=1.5,
        unit="km/h",
    )
    # Serialize
    data = sig_original.model_dump()
    assert data["data_type"] == "uint8"
    assert isinstance(data["data_type"], str)

    # Change name to avoid UniqueName registry conflict
    data["name"] = f"roundtrip-{random.random()}"

    # Deserialize - should convert string back to SignalDataType enum
    sig_roundtrip = Signal.model_validate(data)

    assert isinstance(sig_roundtrip.data_type, SignalDataType)
    assert sig_roundtrip.data_type == SignalDataType.UINT8
    assert sig_roundtrip.data_type.value == "uint8"

    # Verify all other fields match
    assert sig_roundtrip.bit_length == sig_original.bit_length
    assert sig_roundtrip.factor == sig_original.factor
    assert sig_roundtrip.offset == sig_original.offset
    assert sig_roundtrip.unit == sig_original.unit


# ---------------------------------------------------------------------------
# Signal — negative tests
# ---------------------------------------------------------------------------


def test_negative_signal_zero_factor():
    with pytest.raises(ValidationError):
        Signal(
            name="bad_factor",
            bit_length=8,
            data_type=SignalDataType.UINT8,
            factor=0,
        )


def test_negative_signal_bit_length_zero():
    with pytest.raises(ValidationError):
        Signal(name="zero_len", bit_length=0, data_type=SignalDataType.UINT8)


def test_negative_signal_bit_length_negative():
    with pytest.raises(ValidationError):
        Signal(name="neg_len", bit_length=-1, data_type=SignalDataType.UINT8)


@pytest.mark.parametrize(
    "data_type, bit_length",
    [
        pytest.param(SignalDataType.FLOAT32, 16, id="float32_16bit"),
        pytest.param(SignalDataType.FLOAT32, 64, id="float32_64bit"),
        pytest.param(SignalDataType.FLOAT64, 32, id="float64_32bit"),
        pytest.param(SignalDataType.FLOAT64, 16, id="float64_16bit"),
    ],
)
def test_negative_signal_float_wrong_bit_length(data_type, bit_length):
    with pytest.raises(ValidationError):
        Signal(
            name=f"bad_float_{bit_length}",
            bit_length=bit_length,
            data_type=data_type,
        )


@pytest.mark.parametrize(
    "data_type, bit_length",
    [
        pytest.param(SignalDataType.UINT8, 9, id="uint8_9bit"),
        pytest.param(SignalDataType.UINT16, 17, id="uint16_17bit"),
        pytest.param(SignalDataType.INT8, 9, id="int8_9bit"),
        pytest.param(SignalDataType.INT32, 33, id="int32_33bit"),
        pytest.param(SignalDataType.CHAR, 9, id="char_9bit"),
    ],
)
def test_negative_signal_exceeds_natural_width(data_type, bit_length):
    with pytest.raises(ValidationError):
        Signal(
            name=f"overflow_{data_type.value}",
            bit_length=bit_length,
            data_type=data_type,
        )


def test_negative_signal_limits_inverted():
    with pytest.raises(ValidationError):
        Signal(
            name="inverted_limits",
            bit_length=8,
            data_type=SignalDataType.UINT8,
            lower_limit=100.0,
            upper_limit=50.0,
        )


def test_negative_text_table_duplicate_value():
    with pytest.raises(ValidationError, match="overlap"):
        Signal(
            name="dup_val",
            bit_length=8,
            data_type=SignalDataType.UINT8,
            value_encoding=TextTable(
                entries=[
                    TextEntry(from_value=1, to_value=1, label="First"),
                    TextEntry(from_value=1, to_value=1, label="Also first"),
                ],
            ),
        )


def test_negative_text_table_duplicate_label():
    with pytest.raises(ValidationError, match="Duplicate label"):
        Signal(
            name="dup_label",
            bit_length=8,
            data_type=SignalDataType.UINT8,
            value_encoding=TextTable(
                entries=[
                    TextEntry(from_value=1, to_value=1, label="First"),
                    TextEntry(from_value=2, to_value=2, label="First"),
                ],
            ),
        )


def test_negative_range_text_table_overlapping_entries():
    with pytest.raises(ValidationError, match="overlap"):
        Signal(
            name="olap",
            bit_length=8,
            data_type=SignalDataType.UINT8,
            value_encoding=TextTable(
                entries=[
                    TextEntry(from_value=0, to_value=10, label="A"),
                    TextEntry(from_value=5, to_value=15, label="B"),
                ],
            ),
        )


def test_negative_range_text_table_duplicate_label():
    with pytest.raises(ValidationError, match="Duplicate label"):
        Signal(
            name="dup_range_label",
            bit_length=8,
            data_type=SignalDataType.UINT8,
            value_encoding=TextTable(
                entries=[
                    TextEntry(from_value=0, to_value=10, label="X"),
                    TextEntry(from_value=11, to_value=20, label="X"),
                ],
            ),
        )


def test_negative_range_text_entry_reversed_bounds():
    with pytest.raises(ValidationError, match="must not be less than"):
        TextEntry(from_value=10, to_value=5, label="bad")


@pytest.mark.parametrize(
    "data_type, bit_length, bad_value",
    [
        pytest.param(SignalDataType.UINT8, 4, 16, id="uint8_4bit_value_16"),
        pytest.param(SignalDataType.UINT8, 8, 256, id="uint8_value_256"),
        pytest.param(SignalDataType.INT8, 8, 128, id="int8_value_128"),
        pytest.param(SignalDataType.INT8, 8, -129, id="int8_value_neg129"),
    ],
)
def test_negative_text_table_out_of_range(data_type, bit_length, bad_value):
    with pytest.raises(ValidationError):
        Signal(
            name=f"vd_range_{data_type.value}",
            bit_length=bit_length,
            data_type=data_type,
            value_encoding=TextTable(
                entries=[TextEntry(from_value=bad_value, to_value=bad_value, label="Out")],
            ),
        )


@pytest.mark.parametrize(
    "data_type, bit_length, bad_from, bad_to",
    [
        pytest.param(SignalDataType.UINT8, 4, 16, 16, id="uint8_4bit_range_16"),
        pytest.param(SignalDataType.UINT8, 8, 250, 260, id="uint8_range_overflow"),
        pytest.param(SignalDataType.INT8, 8, -129, -1, id="int8_range_underflow"),
    ],
)
def test_negative_range_text_table_out_of_range(data_type, bit_length, bad_from, bad_to):
    with pytest.raises(ValidationError):
        Signal(
            name=f"rg_range_{data_type.value}",
            bit_length=bit_length,
            data_type=data_type,
            value_encoding=TextTable(
                entries=[TextEntry(from_value=bad_from, to_value=bad_to, label="Out")],
            ),
        )


@pytest.mark.parametrize(
    "data_type, bit_length",
    [
        pytest.param(SignalDataType.FLOAT32, 32, id="float32"),
        pytest.param(SignalDataType.FLOAT64, 64, id="float64"),
        pytest.param(SignalDataType.CHAR, 8, id="char"),
        pytest.param(SignalDataType.BYTEARRAY, 8, id="bytearray"),
    ],
)
def test_negative_value_encoding_unsupported_data_type(data_type, bit_length):
    with pytest.raises(ValidationError, match="not supported"):
        Signal(
            name="bad_dt",
            bit_length=bit_length,
            data_type=data_type,
            value_encoding=TextTable(
                entries=[TextEntry(from_value=0, to_value=0, label="X")],
            ),
        )


def test_negative_bitmask_flags_overlapping_masks():
    with pytest.raises(ValidationError, match="overlaps another flag"):
        BitmaskFlags(
            flags=[
                BitmaskFlag(mask=0x03, label="A"),
                BitmaskFlag(mask=0x06, label="B"),
            ],
        )


def test_negative_bitmask_flags_duplicate_label():
    with pytest.raises(ValidationError, match="duplicate flag label"):
        BitmaskFlags(
            flags=[
                BitmaskFlag(mask=0x01, label="Dup"),
                BitmaskFlag(mask=0x02, label="Dup"),
            ],
        )


def test_negative_bitmask_flags_zero_mask():
    with pytest.raises(ValidationError):
        BitmaskFlag(mask=0, label="ZeroMask")


def test_negative_bitmask_flags_mask_exceeds_bit_length():
    with pytest.raises(ValidationError, match="exceeds the representable range"):
        Signal(
            name="bm_overflow",
            bit_length=8,
            data_type=SignalDataType.UINT8,
            value_encoding=BitmaskFlags(
                flags=[BitmaskFlag(mask=0x100, label="TooBig")],
            ),
        )


def test_negative_bitfield_mask_exceeds_bit_length():
    with pytest.raises(ValidationError, match="exceeds the representable range"):
        Signal(
            name="mask_overflow",
            bit_length=8,
            data_type=SignalDataType.UINT8,
            value_encoding=BitfieldTextTable(
                groups=[
                    BitfieldGroup(
                        name="G",
                        mask=0x1FF,
                        states=[BitfieldState(label="S", from_value=0, to_value=0)],
                    ),
                ],
            ),
        )


def test_negative_bitfield_overlapping_group_masks():
    with pytest.raises(ValidationError, match="overlaps another group"):
        BitfieldTextTable(
            groups=[
                BitfieldGroup(
                    name="A",
                    mask=0xF0,
                    states=[BitfieldState(label="SA", from_value=0, to_value=0)],
                ),
                BitfieldGroup(
                    name="B",
                    mask=0x30,
                    states=[BitfieldState(label="SB", from_value=0, to_value=0)],
                ),
            ],
        )


def test_negative_bitfield_duplicate_group_name():
    with pytest.raises(ValidationError, match="duplicate group name"):
        BitfieldTextTable(
            groups=[
                BitfieldGroup(
                    name="G",
                    mask=0x0F,
                    states=[BitfieldState(label="A", from_value=0, to_value=0)],
                ),
                BitfieldGroup(
                    name="G",
                    mask=0xF0,
                    states=[BitfieldState(label="B", from_value=0, to_value=0)],
                ),
            ],
        )


def test_negative_bitfield_state_outside_mask():
    with pytest.raises(ValidationError, match="outside mask"):
        BitfieldGroup(
            name="G",
            mask=0x0F,
            states=[BitfieldState(label="OutOfMask", from_value=0x10, to_value=0x10)],
        )


def test_negative_bitfield_overlapping_states_within_group():
    with pytest.raises(ValidationError, match="overlap"):
        BitfieldGroup(
            name="G",
            mask=0xFF,
            states=[
                BitfieldState(label="A", from_value=0x08, to_value=0x18),
                BitfieldState(label="B", from_value=0x10, to_value=0x20),
            ],
        )


def test_negative_bitfield_duplicate_state_label():
    with pytest.raises(ValidationError, match="duplicate state label"):
        BitfieldGroup(
            name="G",
            mask=0xFF,
            states=[
                BitfieldState(label="Dup", from_value=0x01, to_value=0x01),
                BitfieldState(label="Dup", from_value=0x02, to_value=0x02),
            ],
        )


@pytest.mark.parametrize(
    "data_type, bit_length, bad_iv",
    [
        pytest.param(SignalDataType.UINT8, 8, "string_val", id="uint8_string"),
        pytest.param(SignalDataType.UINT8, 8, 3.14, id="uint8_float"),
        pytest.param(SignalDataType.INT8, 8, True, id="int8_bool"),
        pytest.param(SignalDataType.FLOAT32, 32, b"\x00", id="float32_bytes"),
        pytest.param(SignalDataType.CHAR, 8, 65, id="char_int"),
        pytest.param(SignalDataType.BYTEARRAY, 8, 0, id="bytearray_int"),
    ],
)
def test_negative_signal_initial_value_wrong_type(data_type, bit_length, bad_iv):
    with pytest.raises(ValidationError):
        Signal(
            name=f"bad_iv_{data_type.value}",
            bit_length=bit_length,
            data_type=data_type,
            initial_value=bad_iv,
        )


@pytest.mark.parametrize(
    "data_type, bit_length, bad_iv",
    [
        pytest.param(SignalDataType.UINT8, 8, 256, id="uint8_overflow"),
        pytest.param(SignalDataType.UINT8, 8, -1, id="uint8_negative"),
        pytest.param(SignalDataType.INT8, 8, 128, id="int8_overflow"),
        pytest.param(SignalDataType.INT8, 8, -129, id="int8_underflow"),
        pytest.param(SignalDataType.UINT8, 4, 16, id="uint8_4bit_overflow"),
    ],
)
def test_negative_signal_initial_value_out_of_range(data_type, bit_length, bad_iv):
    with pytest.raises(ValidationError):
        Signal(
            name=f"iv_range_{data_type.value}_{bad_iv}",
            bit_length=bit_length,
            data_type=data_type,
            initial_value=bad_iv,
        )


# ---------------------------------------------------------------------------
# InstancePlacement
# ---------------------------------------------------------------------------


def test_positive_instance_placement_defaults():
    ip = InstancePlacement()
    assert ip.bit_position is None
    assert ip.endianness == "LE"


@pytest.mark.parametrize(
    "endianness",
    [
        pytest.param("BE", id="BE"),
        pytest.param("LE", id="LE"),
    ],
)
def test_positive_instance_placement_endianness(endianness):
    ip = InstancePlacement(endianness=endianness, bit_position=0)
    assert ip.endianness == endianness


def test_negative_instance_placement_negative_bit_position():
    with pytest.raises(ValidationError):
        InstancePlacement(bit_position=-1)


# ---------------------------------------------------------------------------
# SignalInstance
# ---------------------------------------------------------------------------


def test_positive_signal_instance_with_bit_position(uint8_signal):
    si = SignalInstance(signal=uint8_signal, bit_position=0)
    assert si.bit_position == 0
    assert si.signal.name == "sig_uint8"


def test_positive_signal_instance_without_bit_position(uint8_signal):
    si = SignalInstance(signal=uint8_signal)
    assert si.bit_position is None


# ---------------------------------------------------------------------------
# SignalGroup
# ---------------------------------------------------------------------------


def test_positive_signal_group_single_signal(uint8_signal_instance):
    sg = SignalGroup(name="grp_single", signals=[uint8_signal_instance])
    assert len(sg.signals) == 1


def test_positive_signal_group_multiple_signals():
    s1 = Signal(name="grp_s1", bit_length=8, data_type=SignalDataType.UINT8)
    s2 = Signal(name="grp_s2", bit_length=16, data_type=SignalDataType.UINT16)
    sg = SignalGroup(
        name="grp_multi",
        signals=[
            SignalInstance(signal=s1, bit_position=0),
            SignalInstance(signal=s2, bit_position=8),
        ],
    )
    assert len(sg.signals) == 2


def test_positive_signal_group_with_description(uint8_signal_instance):
    sg = SignalGroup(
        name="grp_desc",
        signals=[uint8_signal_instance],
        description="Test group",
    )
    assert sg.description == "Test group"


def test_positive_signal_group_adjacent_no_overlap():
    """Signal instances whose ranges touch at the boundary are not overlapping."""
    s1 = Signal(name="grp_adj_s1", bit_length=4, data_type=SignalDataType.UINT8)
    s2 = Signal(name="grp_adj_s2", bit_length=4, data_type=SignalDataType.UINT8)
    sg = SignalGroup(
        name="grp_adj",
        signals=[
            SignalInstance(signal=s1, bit_position=0),
            SignalInstance(signal=s2, bit_position=4),
        ],
    )
    assert len(sg.signals) == 2


def test_positive_signal_group_unplaced_instance():
    """Signal instances without a bit_position are accepted and skipped by checks."""
    s = Signal(name="grp_unplaced_sig", bit_length=8, data_type=SignalDataType.UINT8)
    sg = SignalGroup(name="grp_unplaced", signals=[SignalInstance(signal=s)])
    assert len(sg.signals) == 1
    assert sg.signals[0].bit_position is None


def test_negative_signal_group_empty_signals():
    with pytest.raises(ValidationError):
        SignalGroup(name="grp_empty", signals=[])


def test_negative_signal_group_signals_overlap():
    """Two signal instances whose ranges intersect inside a group must be rejected."""
    s1 = Signal(name="grp_olap_s1", bit_length=8, data_type=SignalDataType.UINT8)
    s2 = Signal(name="grp_olap_s2", bit_length=8, data_type=SignalDataType.UINT8)
    with pytest.raises(ValidationError, match="overlap"):
        SignalGroup(
            name="grp_olap",
            signals=[
                SignalInstance(signal=s1, bit_position=0),
                SignalInstance(signal=s2, bit_position=4),
            ],
        )


def test_negative_signal_group_signals_identical_position():
    """Two signal instances at the same bit_position inside a group must overlap."""
    s1 = Signal(name="grp_same_s1", bit_length=8, data_type=SignalDataType.UINT8)
    s2 = Signal(name="grp_same_s2", bit_length=8, data_type=SignalDataType.UINT8)
    with pytest.raises(ValidationError, match="overlap"):
        SignalGroup(
            name="grp_same_pos",
            signals=[
                SignalInstance(signal=s1, bit_position=0),
                SignalInstance(signal=s2, bit_position=0),
            ],
        )


# ---------------------------------------------------------------------------
# SignalGroupInstance
# ---------------------------------------------------------------------------


def test_positive_signal_group_instance(uint8_signal_group):
    sgi = SignalGroupInstance(signal_group=uint8_signal_group, bit_position=0)
    assert sgi.bit_position == 0
    assert sgi.signal_group.name == "grp_uint8"


def test_positive_signal_group_instance_no_placement(uint8_signal_group):
    sgi = SignalGroupInstance(signal_group=uint8_signal_group)
    assert sgi.bit_position is None
