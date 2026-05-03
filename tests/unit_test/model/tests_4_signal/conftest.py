import pytest

from flync.model.flync_4_signal.frame import (
    CANFrame,
    LINFrame,
)
from flync.model.flync_4_signal.pdu import PDUInstance, StandardPDU
from flync.model.flync_4_signal.signal import (
    Signal,
    SignalDataType,
    SignalGroup,
    SignalGroupInstance,
    SignalInstance,
)


@pytest.fixture
def uint8_signal():
    yield Signal(name="sig_uint8", bit_length=8, data_type=SignalDataType.UINT8)


@pytest.fixture
def uint16_signal():
    yield Signal(name="sig_uint16", bit_length=16, data_type=SignalDataType.UINT16)


@pytest.fixture
def uint8_signal_instance(uint8_signal):
    yield SignalInstance(signal=uint8_signal, bit_position=0)


@pytest.fixture
def uint16_signal_instance(uint16_signal):
    yield SignalInstance(signal=uint16_signal, bit_position=8)


@pytest.fixture
def uint8_signal_group(uint8_signal):
    yield SignalGroup(name="grp_uint8", signals=[uint8_signal])


@pytest.fixture
def uint8_signal_group_instance(uint8_signal_group):
    yield SignalGroupInstance(signal_group=uint8_signal_group, bit_position=0)


@pytest.fixture
def standard_pdu_8b():
    yield StandardPDU(name="pdu_8b", pdu_id=1, length=1)


@pytest.fixture
def standard_pdu_16b():
    yield StandardPDU(name="pdu_16b", pdu_id=2, length=2)


@pytest.fixture
def pdu_instance():
    yield PDUInstance(pdu_ref="pdu_8b", bit_position=0)


@pytest.fixture
def can_frame():
    yield CANFrame(
        name="can_frm",
        can_id=0x100,
        id_format="standard_11bit",
        length=8,
    )


@pytest.fixture
def lin_frame():
    yield LINFrame(
        name="lin_frm",
        lin_id=0x01,
        publisher_node="MasterNode",
        length=8,
    )
