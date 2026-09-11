import pytest

from flync.core.datatypes.duration import parse_duration_ms, serialize_duration_ms


@pytest.mark.parametrize(
    "value, expected_ms",
    [
        pytest.param(50, 50, id="plain_int"),
        pytest.param("50ms", 50, id="ms_suffix"),
        pytest.param("5s", 5000, id="s_suffix"),
        pytest.param("50", 50, id="no_suffix"),
        pytest.param(" 50ms ", 50, id="surrounding_whitespace"),
        pytest.param("1.5s", 1500, id="fractional_seconds"),
        pytest.param("0.5ms", 0, id="fractional_ms_truncates"),
    ],
)
def test_parse_duration_ms(value, expected_ms):
    assert parse_duration_ms(value) == expected_ms


@pytest.mark.parametrize(
    "value, expected",
    [
        pytest.param(5000, "5000ms", id="value"),
        pytest.param(None, None, id="none_stays_none"),
    ],
)
def test_serialize_duration_ms(value, expected):
    assert serialize_duration_ms(value) == expected


@pytest.mark.parametrize("value", [50, "50ms", "5s"])
def test_parse_then_serialize_round_trips_to_milliseconds(value):
    parsed = parse_duration_ms(value)
    assert serialize_duration_ms(parsed) == f"{parsed}ms"
