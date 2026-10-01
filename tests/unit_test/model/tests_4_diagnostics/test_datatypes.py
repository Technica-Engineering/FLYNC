import pytest
from pydantic import ValidationError

from flync.model.flync_4_diagnostics.uds.datatypes import DiagDataRecord, DiagField
from tests.error_assertions import assert_single_error


def field(**overrides):
    params = dict(name="f", type="uint8", bit_offset=0)
    params.update(overrides)
    return DiagField(**params)


@pytest.mark.parametrize(
    "diag_type,expected_width",
    [
        pytest.param("bool", 1, id="bool"),
        pytest.param("uint8", 8, id="uint8"),
        pytest.param("uint16", 16, id="uint16"),
        pytest.param("uint32", 32, id="uint32"),
        pytest.param("uint64", 64, id="uint64"),
        pytest.param("float32", 32, id="float32"),
        pytest.param("float64", 64, id="float64"),
    ],
)
def test_fixed_width_defaults_bit_length(diag_type, expected_width):
    f = field(type=diag_type)
    assert f.bit_length == expected_width


def test_fixed_width_accepts_matching_bit_length():
    f = field(type="uint16", bit_length=16)
    assert f.bit_length == 16


def test_fixed_width_rejects_mismatching_bit_length():
    with pytest.raises(ValidationError) as exc_info:
        field(type="uint16", bit_length=8)
    assert_single_error(exc_info, "FLYNC-DIA-MAJ-CONS-255", "bit_length 8 but the type is 16 bits wide")


@pytest.mark.parametrize("variable_type", ["ascii", "bytes"])
def test_variable_width_requires_bit_length(variable_type):
    with pytest.raises(ValidationError) as exc_info:
        field(type=variable_type)
    assert_single_error(exc_info, "FLYNC-DIA-MAJ-REQ-254", "must declare a bit_length")


def test_variable_width_accepts_given_bit_length():
    f = field(type="ascii", bit_length=40)
    assert f.bit_length == 40


def test_record_accepts_exactly_full_field():
    record = DiagDataRecord(byte_length=1, fields=[field(type="uint8", bit_offset=0)])
    assert record.byte_length == 1


def test_record_accepts_multiple_non_overlapping_fields():
    record = DiagDataRecord(
        byte_length=2,
        fields=[field(name="a", type="uint8", bit_offset=0), field(name="b", type="uint8", bit_offset=8)],
    )
    assert len(record.fields) == 2


def test_record_rejects_duplicate_field_names():
    fields = [field(name="a", type="uint8", bit_offset=0), field(name="a", type="uint8", bit_offset=8)]
    with pytest.raises(ValidationError) as exc_info:
        DiagDataRecord(byte_length=2, fields=fields)
    assert_single_error(exc_info, "FLYNC-DIA-MAJ-UNIQ-256", "Duplicate field name 'a'")


def test_record_rejects_field_exceeding_length():
    fields = [field(type="uint16", bit_offset=0)]
    with pytest.raises(ValidationError) as exc_info:
        DiagDataRecord(byte_length=1, fields=fields)
    assert_single_error(exc_info, "FLYNC-DIA-MAJ-VAL-257", "exceeds the record length (8 bits)")


def test_record_rejects_overlapping_fields():
    fields = [field(name="a", type="uint16", bit_offset=0), field(name="b", type="uint8", bit_offset=4)]
    with pytest.raises(ValidationError) as exc_info:
        DiagDataRecord(byte_length=2, fields=fields)
    assert_single_error(exc_info, "FLYNC-DIA-MAJ-CONS-258", "overlaps field 'a'")


def test_record_accepts_empty_field_list():
    record = DiagDataRecord(byte_length=4)
    assert record.fields == []
