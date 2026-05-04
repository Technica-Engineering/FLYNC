import pytest
from pydantic import ValidationError

from flync.model.flync_4_signal.signal import (
    InstancePlacement,
    Signal,
    SignalDataType,
    SignalGroup,
    SignalGroupInstance,
    SignalInstance,
    ValueDescription,
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
# ValueDescription
# ---------------------------------------------------------------------------


def test_positive_value_description_basic():
    vd = ValueDescription(value=0, description="Off")
    assert vd.value == 0
    assert vd.description == "Off"


def test_positive_value_description_negative_value():
    vd = ValueDescription(value=-1, description="Error")
    assert vd.value == -1


def test_positive_value_description_model_validate():
    vd = ValueDescription.model_validate({"value": 3, "description": "Active"})
    assert isinstance(vd, ValueDescription)


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


def test_positive_signal_with_value_descriptions():
    sig = Signal(
        name="gear",
        bit_length=4,
        data_type=SignalDataType.UINT8,
        value_descriptions=[
            ValueDescription(value=0, description="Neutral"),
            ValueDescription(value=1, description="First"),
            ValueDescription(value=2, description="Second"),
        ],
    )
    assert len(sig.value_descriptions) == 3


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


def test_negative_signal_duplicate_value_descriptions():
    with pytest.raises(ValidationError):
        Signal(
            name="dup_vd",
            bit_length=8,
            data_type=SignalDataType.UINT8,
            value_descriptions=[
                ValueDescription(value=1, description="First"),
                ValueDescription(value=1, description="Also first"),
            ],
        )


@pytest.mark.parametrize(
    "data_type, bit_length, bad_value",
    [
        pytest.param(SignalDataType.UINT8, 4, 16, id="uint8_4bit_value_16"),
        pytest.param(SignalDataType.UINT8, 8, 256, id="uint8_value_256"),
        pytest.param(SignalDataType.INT8, 8, 128, id="int8_value_128"),
        pytest.param(SignalDataType.INT8, 8, -129, id="int8_value_neg129"),
    ],
)
def test_negative_signal_value_description_out_of_range(data_type, bit_length, bad_value):
    with pytest.raises(ValidationError):
        Signal(
            name=f"vd_range_{data_type.value}",
            bit_length=bit_length,
            data_type=data_type,
            value_descriptions=[ValueDescription(value=bad_value, description="Out")],
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
    assert ip.subscriber_nodes == []


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


def test_positive_instance_placement_with_subscribers():
    ip = InstancePlacement(subscriber_nodes=["NodeA", "NodeB"], bit_position=0)
    assert len(ip.subscriber_nodes) == 2


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


def test_positive_signal_instance_with_subscribers(uint8_signal):
    si = SignalInstance(signal=uint8_signal, bit_position=0, subscriber_nodes=["ECU_A"])
    assert si.subscriber_nodes == ["ECU_A"]


def test_positive_signal_instance_BE(uint8_signal):
    si = SignalInstance(signal=uint8_signal, bit_position=0, endianness="BE")
    assert si.endianness == "BE"


# ---------------------------------------------------------------------------
# SignalGroup
# ---------------------------------------------------------------------------


def test_positive_signal_group_single_signal(uint8_signal):
    sg = SignalGroup(name="grp_single", signals=[uint8_signal])
    assert len(sg.signals) == 1


def test_positive_signal_group_multiple_signals():
    s1 = Signal(name="grp_s1", bit_length=8, data_type=SignalDataType.UINT8)
    s2 = Signal(name="grp_s2", bit_length=16, data_type=SignalDataType.UINT16)
    sg = SignalGroup(name="grp_multi", signals=[s1, s2])
    assert len(sg.signals) == 2


def test_positive_signal_group_with_description(uint8_signal):
    sg = SignalGroup(name="grp_desc", signals=[uint8_signal], description="Test group")
    assert sg.description == "Test group"


def test_negative_signal_group_empty_signals():
    with pytest.raises(ValidationError):
        SignalGroup(name="grp_empty", signals=[])


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
