import pytest
from pydantic import ValidationError

from flync.model.flync_4_bus.lin_bus import (
    LINBus,
    LINScheduleEntry,
    LINScheduleTable,
)
from flync.model.flync_4_signal.frame import LINFrame

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_lin_frame(name="lin_frm", lin_id=0x01, length=4):
    return LINFrame(name=name, lin_id=lin_id, length=length)


# ---------------------------------------------------------------------------
# LINScheduleEntry — positive tests
# ---------------------------------------------------------------------------


def test_positive_lin_schedule_entry_basic():
    entry = LINScheduleEntry(frame_name="frm_A", period=10.0)
    assert entry.frame_name == "frm_A"
    assert entry.period == 10.0


def test_positive_lin_schedule_entry_small_period():
    entry = LINScheduleEntry(frame_name="frm_B", period=0.001)
    assert entry.period == 0.001


def test_positive_lin_schedule_entry_model_validate():
    data = {"frame_name": "frm_C", "period": 20.0}
    entry = LINScheduleEntry.model_validate(data)
    assert isinstance(entry, LINScheduleEntry)


# ---------------------------------------------------------------------------
# LINScheduleEntry — negative tests
# ---------------------------------------------------------------------------


def test_negative_lin_schedule_entry_zero_period():
    with pytest.raises(ValidationError):
        LINScheduleEntry(frame_name="frm_bad", period=0.0)


def test_negative_lin_schedule_entry_negative_period():
    with pytest.raises(ValidationError):
        LINScheduleEntry(frame_name="frm_neg", period=-10.0)


# ---------------------------------------------------------------------------
# LINScheduleTable — positive tests
# ---------------------------------------------------------------------------


def test_positive_lin_schedule_table_empty():
    table = LINScheduleTable(name="sched_empty")
    assert table.entries == []


def test_positive_lin_schedule_table_with_entries():
    table = LINScheduleTable(
        name="sched_full",
        entries=[
            LINScheduleEntry(frame_name="frm_1", period=10.0),
            LINScheduleEntry(frame_name="frm_2", period=20.0),
        ],
    )
    assert len(table.entries) == 2


def test_positive_lin_schedule_table_with_description():
    table = LINScheduleTable(name="sched_desc", description="Main schedule", entries=[])
    assert table.description == "Main schedule"


# ---------------------------------------------------------------------------
# LINBus — positive tests
# ---------------------------------------------------------------------------


def test_positive_lin_bus_minimal():
    bus = LINBus(
        name="LIN_bus_1",
        lin_protocol_version="2.2A",
        lin_language_version="2.2A",
        baud_rate=19_200,
    )
    assert bus.name == "LIN_bus_1"
    assert bus.frames == []
    assert bus.schedule_tables == []


def test_positive_lin_bus_with_description():
    bus = LINBus(
        name="LIN_bus_desc",
        lin_protocol_version="2.2A",
        lin_language_version="2.2A",
        baud_rate=19_200,
        description="Body LIN bus",
    )
    assert bus.description == "Body LIN bus"


@pytest.mark.parametrize(
    "baud_rate",
    [
        pytest.param(1_200, id="1200"),
        pytest.param(2_400, id="2400"),
        pytest.param(4_800, id="4800"),
        pytest.param(9_600, id="9600"),
        pytest.param(10_400, id="10400"),
        pytest.param(19_200, id="19200"),
    ],
)
def test_positive_lin_bus_all_valid_baud_rates(baud_rate):
    bus = LINBus(
        name=f"LIN_br_{baud_rate}",
        lin_protocol_version="2.2A",
        lin_language_version="2.2A",
        baud_rate=baud_rate,
    )
    assert bus.baud_rate == baud_rate


def test_positive_lin_bus_with_frames():
    frm = _make_lin_frame("bus_lin_frm_1")
    bus = LINBus(
        name="LIN_bus_3",
        lin_protocol_version="2.2A",
        lin_language_version="2.2A",
        baud_rate=19_200,
        frames=[frm],
    )
    assert len(bus.frames) == 1


def test_positive_lin_bus_with_schedule_table():
    frm = _make_lin_frame("bus_lin_frm_2")
    table = LINScheduleTable(
        name="main_sched",
        entries=[LINScheduleEntry(frame_name="bus_lin_frm_2", period=10.0)],
    )
    bus = LINBus(
        name="LIN_bus_4",
        lin_protocol_version="2.2A",
        lin_language_version="2.2A",
        baud_rate=9_600,
        frames=[frm],
        schedule_tables=[table],
    )
    assert len(bus.schedule_tables) == 1


def test_positive_lin_bus_different_protocol_versions():
    bus = LINBus(
        name="LIN_bus_mixed",
        lin_protocol_version="2.1",
        lin_language_version="2.2A",
        baud_rate=19_200,
    )
    assert bus.lin_protocol_version == "2.1"
    assert bus.lin_language_version == "2.2A"


def test_positive_lin_bus_with_channel_name():
    bus = LINBus(
        name="LIN_ch_bus",
        lin_protocol_version="2.2A",
        lin_language_version="2.2A",
        baud_rate=19_200,
        channel_name="LIN_1",
    )
    assert bus.channel_name == "LIN_1"


def test_positive_lin_bus_model_validate():
    data = {
        "name": "LIN_mv_bus",
        "lin_protocol_version": "2.2A",
        "lin_language_version": "2.2A",
        "baud_rate": 19_200,
    }
    bus = LINBus.model_validate(data)
    assert isinstance(bus, LINBus)


# ---------------------------------------------------------------------------
# LINBus — negative tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_baud",
    [
        pytest.param(500, id="500"),
        pytest.param(3_600, id="3600"),
        pytest.param(9_000, id="9000"),
        pytest.param(115_200, id="115200"),
    ],
)
def test_negative_lin_bus_invalid_baud_rate(bad_baud):
    with pytest.raises(ValidationError):
        LINBus(
            name=f"LIN_bad_br_{bad_baud}",
            lin_protocol_version="2.2A",
            lin_language_version="2.2A",
            baud_rate=bad_baud,
        )


def test_negative_lin_bus_schedule_references_unknown_frame():
    table = LINScheduleTable(
        name="bad_sched",
        entries=[LINScheduleEntry(frame_name="nonexistent_frame", period=10.0)],
    )
    with pytest.raises(ValidationError):
        LINBus(
            name="LIN_bad_ref",
            lin_protocol_version="2.2A",
            lin_language_version="2.2A",
            baud_rate=19_200,
            schedule_tables=[table],
        )


def test_negative_lin_bus_schedule_references_unknown_frame_with_existing():
    frm = _make_lin_frame("known_frm", lin_id=0x10)
    table = LINScheduleTable(
        name="partial_sched",
        entries=[
            LINScheduleEntry(frame_name="known_frm", period=10.0),
            LINScheduleEntry(frame_name="missing_frm", period=10.0),
        ],
    )
    with pytest.raises(ValidationError):
        LINBus(
            name="LIN_partial_ref",
            lin_protocol_version="2.2A",
            lin_language_version="2.2A",
            baud_rate=19_200,
            frames=[frm],
            schedule_tables=[table],
        )
