import pytest
from pydantic import ValidationError

from flync.model.flync_4_bus.lin_bus import (
    LINBus,
    LINMasterNode,
    LINScheduleEntry,
    LINScheduleTable,
    LINSlaveNode,
)
from flync.model.flync_4_signal.frame import LINFrame

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_master(name="Master", protocol="2.2A", p2_min=5.0, st_min=0.0):
    return LINMasterNode(name=name, lin_protocol=protocol, p2_min=p2_min, st_min=st_min)


def _make_slave(name="Slave1", protocol="2.2A", configured_nad=0x01, initial_nad=0x01):
    return LINSlaveNode(
        name=name,
        lin_protocol=protocol,
        configured_nad=configured_nad,
        initial_nad=initial_nad,
    )


def _make_lin_frame(name="lin_frm", lin_id=0x01, publisher_node="Master", length=4):
    return LINFrame(name=name, lin_id=lin_id, publisher_node=publisher_node, length=length)


# ---------------------------------------------------------------------------
# LINMasterNode — positive tests
# ---------------------------------------------------------------------------


def test_positive_lin_master_node_basic():
    node = _make_master()
    assert node.node_type == "master"
    assert node.name == "Master"
    assert node.lin_protocol == "2.2A"


def test_positive_lin_master_node_with_description():
    node = LINMasterNode(
        name="MasterDesc",
        lin_protocol="2.1",
        p2_min=5.0,
        st_min=0.0,
        description="Main master node",
    )
    assert node.description == "Main master node"


@pytest.mark.parametrize(
    "protocol",
    [
        pytest.param("1.3", id="LIN_1.3"),
        pytest.param("2.0", id="LIN_2.0"),
        pytest.param("2.1", id="LIN_2.1"),
        pytest.param("2.2A", id="LIN_2.2A"),
    ],
)
def test_positive_lin_master_node_all_protocols(protocol):
    node = LINMasterNode(
        name=f"Master_{protocol.replace('.', '_')}",
        lin_protocol=protocol,
        p2_min=5.0,
        st_min=0.0,
    )
    assert node.lin_protocol == protocol


def test_positive_lin_master_node_model_validate():
    data = {
        "node_type": "master",
        "name": "MasterMV",
        "lin_protocol": "2.2A",
        "p2_min": 10.0,
        "st_min": 1.0,
    }
    node = LINMasterNode.model_validate(data)
    assert isinstance(node, LINMasterNode)


# ---------------------------------------------------------------------------
# LINMasterNode — negative tests
# ---------------------------------------------------------------------------


def test_negative_lin_master_node_invalid_protocol():
    with pytest.raises(ValidationError):
        LINMasterNode(name="BadMaster", lin_protocol="3.0", p2_min=5.0, st_min=0.0)


# ---------------------------------------------------------------------------
# LINSlaveNode — positive tests
# ---------------------------------------------------------------------------


def test_positive_lin_slave_node_basic():
    node = _make_slave()
    assert node.node_type == "slave"
    assert node.name == "Slave1"
    assert node.configured_nad == 0x01


def test_positive_lin_slave_node_nad_boundaries():
    node_min = LINSlaveNode(
        name="SlaveMin",
        lin_protocol="2.2A",
        configured_nad=0x00,
        initial_nad=0x00,
    )
    node_max = LINSlaveNode(
        name="SlaveMax",
        lin_protocol="2.2A",
        configured_nad=0xFF,
        initial_nad=0xFF,
    )
    assert node_min.configured_nad == 0
    assert node_max.initial_nad == 0xFF


def test_positive_lin_slave_node_with_product_id():
    node = LINSlaveNode(
        name="SlaveProd",
        lin_protocol="2.1",
        configured_nad=0x10,
        initial_nad=0x10,
        product_id="0x7FFF_0001_01",
    )
    assert node.product_id == "0x7FFF_0001_01"


def test_positive_lin_slave_node_with_response_error():
    node = LINSlaveNode(
        name="SlaveErr",
        lin_protocol="2.2A",
        configured_nad=0x02,
        initial_nad=0x02,
        response_error="response_error_signal",
    )
    assert node.response_error == "response_error_signal"


@pytest.mark.parametrize(
    "protocol",
    [
        pytest.param("1.3", id="LIN_1.3"),
        pytest.param("2.0", id="LIN_2.0"),
        pytest.param("2.1", id="LIN_2.1"),
        pytest.param("2.2A", id="LIN_2.2A"),
    ],
)
def test_positive_lin_slave_node_all_protocols(protocol):
    node = LINSlaveNode(
        name=f"Slave_{protocol.replace('.', '_')}",
        lin_protocol=protocol,
        configured_nad=0x05,
        initial_nad=0x05,
    )
    assert node.lin_protocol == protocol


# ---------------------------------------------------------------------------
# LINSlaveNode — negative tests
# ---------------------------------------------------------------------------


def test_negative_lin_slave_node_configured_nad_too_large():
    with pytest.raises(ValidationError):
        LINSlaveNode(
            name="BadSlave",
            lin_protocol="2.2A",
            configured_nad=0x100,
            initial_nad=0x01,
        )


def test_negative_lin_slave_node_initial_nad_too_large():
    with pytest.raises(ValidationError):
        LINSlaveNode(
            name="BadSlave2",
            lin_protocol="2.2A",
            configured_nad=0x01,
            initial_nad=0x100,
        )


def test_negative_lin_slave_node_configured_nad_negative():
    with pytest.raises(ValidationError):
        LINSlaveNode(
            name="BadSlave3",
            lin_protocol="2.2A",
            configured_nad=-1,
            initial_nad=0x01,
        )


def test_negative_lin_slave_node_invalid_protocol():
    with pytest.raises(ValidationError):
        LINSlaveNode(
            name="BadProtoSlave",
            lin_protocol="4.0",
            configured_nad=0x01,
            initial_nad=0x01,
        )


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


def test_positive_lin_bus_single_master_only():
    bus = LINBus(
        name="LIN_bus_1",
        lin_protocol_version="2.2A",
        lin_language_version="2.2A",
        baud_rate=19_200,
        nodes=[_make_master()],
    )
    assert bus.name == "LIN_bus_1"


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
        nodes=[_make_master(name=f"M_{baud_rate}")],
    )
    assert bus.baud_rate == baud_rate


def test_positive_lin_bus_with_master_and_slaves():
    bus = LINBus(
        name="LIN_bus_2",
        lin_protocol_version="2.2A",
        lin_language_version="2.2A",
        baud_rate=19_200,
        nodes=[
            _make_master("MasterMain"),
            _make_slave("SlaveA", configured_nad=0x01, initial_nad=0x01),
            _make_slave("SlaveB", configured_nad=0x02, initial_nad=0x02),
        ],
    )
    assert len(bus.nodes) == 3


def test_positive_lin_bus_with_frames():
    frm = _make_lin_frame("bus_lin_frm_1")
    bus = LINBus(
        name="LIN_bus_3",
        lin_protocol_version="2.2A",
        lin_language_version="2.2A",
        baud_rate=19_200,
        nodes=[_make_master("M3")],
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
        nodes=[_make_master("M4")],
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
        nodes=[_make_master("M_mixed", protocol="2.1")],
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
        nodes=[_make_master("M_ch")],
    )
    assert bus.channel_name == "LIN_1"


def test_positive_lin_bus_model_validate():
    data = {
        "name": "LIN_mv_bus",
        "lin_protocol_version": "2.2A",
        "lin_language_version": "2.2A",
        "baud_rate": 19_200,
        "nodes": [
            {
                "node_type": "master",
                "name": "MV_Master",
                "lin_protocol": "2.2A",
                "p2_min": 5.0,
                "st_min": 0.0,
            }
        ],
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
            nodes=[_make_master(name=f"Mbad_{bad_baud}")],
        )


def test_negative_lin_bus_no_master():
    with pytest.raises(ValidationError):
        LINBus(
            name="LIN_no_master",
            lin_protocol_version="2.2A",
            lin_language_version="2.2A",
            baud_rate=19_200,
            nodes=[_make_slave("SlaveOnly")],
        )


def test_negative_lin_bus_no_nodes():
    with pytest.raises(ValidationError):
        LINBus(
            name="LIN_empty",
            lin_protocol_version="2.2A",
            lin_language_version="2.2A",
            baud_rate=19_200,
            nodes=[],
        )


def test_negative_lin_bus_multiple_masters():
    with pytest.raises(ValidationError):
        LINBus(
            name="LIN_two_masters",
            lin_protocol_version="2.2A",
            lin_language_version="2.2A",
            baud_rate=19_200,
            nodes=[
                _make_master("MasterA"),
                _make_master("MasterB"),
            ],
        )


def test_negative_lin_bus_duplicate_node_names():
    with pytest.raises(ValidationError):
        LINBus(
            name="LIN_dup_nodes",
            lin_protocol_version="2.2A",
            lin_language_version="2.2A",
            baud_rate=19_200,
            nodes=[
                _make_master("DupNode"),
                _make_slave("DupNode"),
            ],
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
            nodes=[_make_master("MBadRef")],
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
            nodes=[_make_master("MPartial")],
            frames=[frm],
            schedule_tables=[table],
        )
