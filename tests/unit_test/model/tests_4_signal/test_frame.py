import pytest
from pydantic import ValidationError

from flync.model.flync_4_signal.frame import (
    CANFDFrame,
    CANFrame,
    FrameCyclicTiming,
    FrameEventTiming,
    FrameTransmissionTiming,
    J1939Frame,
    LINFrame,
)
from flync.model.flync_4_signal.pdu import PDUInstance
from tests.error_assertions import assert_single_error

_CAN_FD_VALID_LENGTHS = (0, 1, 2, 3, 4, 5, 6, 7, 8, 12, 16, 20, 24, 32, 48, 64)


def test_positive_frame_event_timing_defaults():
    t = FrameEventTiming()
    assert t.final_repetitions == 0
    assert t.repeating_time_range == 0.0
    assert isinstance(t, FrameEventTiming)


def test_positive_frame_event_timing_custom():
    t = FrameEventTiming(final_repetitions=3, repeating_time_range=0.01)
    assert t.final_repetitions == 3
    assert t.repeating_time_range == 0.01
    assert isinstance(t, FrameEventTiming)


def test_negative_frame_event_timing_negative_repetitions():
    with pytest.raises(ValidationError) as exc_info:
        FrameEventTiming(final_repetitions=-1)
    assert_single_error(exc_info, None, "greater than or equal to 0")


def test_negative_frame_event_timing_negative_repeating_time():
    with pytest.raises(ValidationError) as exc_info:
        FrameEventTiming(repeating_time_range=-0.01)
    assert_single_error(exc_info, None, "greater than or equal to 0")


def test_positive_frame_cyclic_timing():
    t = FrameCyclicTiming(cycle=0.01)
    assert t.cycle == 0.01
    assert isinstance(t, FrameCyclicTiming)


def test_positive_frame_cyclic_timing_large_cycle():
    t = FrameCyclicTiming(cycle=1.0)
    assert t.cycle == 1.0
    assert isinstance(t, FrameCyclicTiming)


def test_negative_frame_cyclic_timing_zero_cycle():
    with pytest.raises(ValidationError) as exc_info:
        FrameCyclicTiming(cycle=0)
    assert_single_error(exc_info, None, "greater than 0")


def test_negative_frame_cyclic_timing_negative_cycle():
    with pytest.raises(ValidationError) as exc_info:
        FrameCyclicTiming(cycle=-0.01)
    assert_single_error(exc_info, None, "greater than 0")


def test_positive_frame_transmission_timing_empty():
    t = FrameTransmissionTiming()
    assert t.cyclic_timings == []
    assert t.event_timings == []
    assert t.debounce_time is None
    assert isinstance(t, FrameTransmissionTiming)


def test_positive_frame_transmission_timing_cyclic_only():
    t = FrameTransmissionTiming(cyclic_timings=[FrameCyclicTiming(cycle=0.1)])
    assert len(t.cyclic_timings) == 1
    assert isinstance(t, FrameTransmissionTiming)


def test_positive_frame_transmission_timing_both():
    t = FrameTransmissionTiming(
        debounce_time=0.005,
        cyclic_timings=[FrameCyclicTiming(cycle=0.1)],
        event_timings=[FrameEventTiming(final_repetitions=2)],
    )
    assert t.debounce_time == 0.005
    assert len(t.event_timings) == 1
    assert isinstance(t, FrameTransmissionTiming)


def test_positive_can_frame_standard_id_min():
    frm = CANFrame(name="can_std_min", can_id=0, id_format="standard_11bit", length=8)
    assert frm.can_id == 0
    assert isinstance(frm, CANFrame)


def test_positive_can_frame_standard_id_max():
    frm = CANFrame(name="can_std_max", can_id=0x7FF, id_format="standard_11bit", length=8)
    assert frm.can_id == 0x7FF
    assert isinstance(frm, CANFrame)


def test_positive_can_frame_extended_id():
    frm = CANFrame(name="can_ext", can_id=0x1FFFFFFF, id_format="extended_29bit", length=8)
    assert frm.id_format == "extended_29bit"
    assert isinstance(frm, CANFrame)


def test_positive_can_frame_rtr():
    frm = CANFrame(
        name="can_rtr",
        can_id=0x100,
        id_format="standard_11bit",
        length=0,
        is_remote_frame=True,
    )
    assert frm.is_remote_frame is True
    assert isinstance(frm, CANFrame)


@pytest.mark.parametrize(
    "length",
    [pytest.param(i, id=f"len_{i}") for i in range(9)],
)
def test_positive_can_frame_all_lengths(length):
    frm = CANFrame(
        name=f"can_len_{length}",
        can_id=0x100,
        id_format="standard_11bit",
        length=length,
    )
    assert frm.length == length
    assert isinstance(frm, CANFrame)


def test_positive_can_frame_with_timing():
    frm = CANFrame(
        name="can_timed",
        can_id=0x200,
        id_format="standard_11bit",
        length=4,
        timing=FrameTransmissionTiming(cyclic_timings=[FrameCyclicTiming(cycle=0.01)]),
    )
    assert frm.timing is not None
    assert isinstance(frm, CANFrame)


def test_positive_can_frame_with_pdu():
    frm = CANFrame(
        name="can_pdu",
        can_id=0x300,
        id_format="standard_11bit",
        length=8,
        packed_pdus=[PDUInstance(pdu_ref="can_pdu_ref", bit_position=0)],
    )
    assert len(frm.packed_pdus) == 1
    assert isinstance(frm, CANFrame)


def test_positive_can_frame_model_validate():
    data = {
        "name": "can_mv",
        "can_id": 0x100,
        "id_format": "standard_11bit",
        "length": 4,
    }
    frm = CANFrame.model_validate(data)
    assert isinstance(frm, CANFrame)
    assert frm.type == "can"


def test_negative_can_frame_standard_id_too_large():
    with pytest.raises(ValidationError) as exc_info:
        CANFrame(
            name="can_bad_std",
            can_id=0x800,
            id_format="standard_11bit",
            length=8,
        )
    assert_single_error(exc_info, "FLYNC-SIG-MIN-VAL-106", "out of range")


def test_negative_can_frame_negative_id():
    with pytest.raises(ValidationError) as exc_info:
        CANFrame(
            name="can_neg_id",
            can_id=-1,
            id_format="standard_11bit",
            length=8,
        )
    assert_single_error(exc_info, "FLYNC-SIG-MIN-VAL-106", "out of range")


def test_negative_can_frame_invalid_id_format():
    with pytest.raises(ValidationError) as exc_info:
        CANFrame(
            name="can_bad_format",
            can_id=0x100,
            id_format="standard_29bit",
            length=8,
        )
    assert_single_error(exc_info, None, "standard_11bit")


def test_negative_can_frame_extended_id_too_large():
    with pytest.raises(ValidationError) as exc_info:
        CANFrame(
            name="can_bad_ext",
            can_id=0x20000000,
            id_format="extended_29bit",
            length=8,
        )
    assert_single_error(exc_info, "FLYNC-SIG-MIN-VAL-106", "out of range")


def test_negative_can_frame_rtr_with_data():
    with pytest.raises(ValidationError) as exc_info:
        CANFrame(
            name="can_bad_rtr",
            can_id=0x100,
            id_format="standard_11bit",
            length=4,
            is_remote_frame=True,
        )
    assert_single_error(exc_info, "FLYNC-SIG-MIN-CONS-103", "is_remote_frame=True requires length=0")


def test_negative_can_frame_length_too_large():
    with pytest.raises(ValidationError) as exc_info:
        CANFrame(name="can_len9", can_id=0x100, id_format="standard_11bit", length=9)
    assert_single_error(exc_info, None, "less than or equal to 8")


def test_negative_can_frame_negative_length():
    with pytest.raises(ValidationError) as exc_info:
        CANFrame(
            name="can_neg_len",
            can_id=0x100,
            id_format="standard_11bit",
            length=-1,
        )
    assert_single_error(exc_info, None, "greater than or equal to 0")


def test_negative_can_frame_duplicate_pdu_bit_positions():
    packed_pdus = [PDUInstance(pdu_ref="p1", bit_position=0), PDUInstance(pdu_ref="p2", bit_position=0)]

    with pytest.raises(ValidationError) as exc_info:
        CANFrame(name="can_dup_pdu", can_id=0x100, id_format="standard_11bit", length=8, packed_pdus=packed_pdus)
    assert_single_error(exc_info, "FLYNC-SIG-MIN-UNIQ-105", "share bit_position")


@pytest.mark.parametrize(
    "length",
    [pytest.param(length, id=f"fd_len_{length}") for length in _CAN_FD_VALID_LENGTHS],
)
def test_positive_can_fd_frame_valid_lengths(length):
    frm = CANFDFrame(
        name=f"canfd_{length}",
        can_id=0x100,
        id_format="standard_11bit",
        length=length,
    )
    assert frm.length == length
    assert isinstance(frm, CANFDFrame)


def test_positive_can_fd_frame_with_brs():
    frm = CANFDFrame(
        name="canfd_brs",
        can_id=0x200,
        id_format="standard_11bit",
        length=64,
        bit_rate_switch=True,
    )
    assert frm.bit_rate_switch is True
    assert frm.type == "can_fd"
    assert isinstance(frm, CANFDFrame)


def test_positive_can_fd_frame_no_brs():
    frm = CANFDFrame(
        name="canfd_no_brs",
        can_id=0x200,
        id_format="standard_11bit",
        length=8,
        bit_rate_switch=False,
    )
    assert frm.bit_rate_switch is False
    assert isinstance(frm, CANFDFrame)


def test_positive_can_fd_frame_extended_id():
    frm = CANFDFrame(
        name="canfd_ext",
        can_id=0x1FFFFFFF,
        id_format="extended_29bit",
        length=64,
    )
    assert frm.id_format == "extended_29bit"
    assert isinstance(frm, CANFDFrame)


def test_positive_can_fd_frame_with_esi():
    frm = CANFDFrame(
        name="canfd_esi",
        can_id=0x100,
        id_format="standard_11bit",
        length=8,
        error_state_indicator=True,
    )
    assert frm.error_state_indicator is True
    assert isinstance(frm, CANFDFrame)


def test_positive_can_fd_frame_model_validate():
    data = {
        "name": "canfd_mv",
        "can_id": 0x100,
        "id_format": "standard_11bit",
        "length": 8,
    }
    frm = CANFDFrame.model_validate(data)
    assert isinstance(frm, CANFDFrame)


@pytest.mark.parametrize(
    "bad_length",
    [
        pytest.param(9, id="len_9"),
        pytest.param(10, id="len_10"),
        pytest.param(11, id="len_11"),
        pytest.param(13, id="len_13"),
        pytest.param(15, id="len_15"),
        pytest.param(33, id="len_33"),
    ],
)
def test_negative_can_fd_frame_invalid_length(bad_length):
    with pytest.raises(ValidationError) as exc_info:
        CANFDFrame(
            name=f"canfd_bad_{bad_length}",
            can_id=0x100,
            id_format="standard_11bit",
            length=bad_length,
        )
    assert_single_error(exc_info, "FLYNC-SIG-MIN-VAL-104", "not a valid CAN FD payload size")


def test_negative_can_fd_frame_length_exceeds_max():
    with pytest.raises(ValidationError) as exc_info:
        CANFDFrame(
            name="canfd_65",
            can_id=0x100,
            id_format="standard_11bit",
            length=65,
        )
    assert_single_error(exc_info, None, "less than or equal to 64")


def test_negative_can_fd_frame_standard_id_too_large():
    with pytest.raises(ValidationError) as exc_info:
        CANFDFrame(
            name="canfd_bad_id",
            can_id=0x800,
            id_format="standard_11bit",
            length=8,
        )
    assert_single_error(exc_info, "FLYNC-SIG-MIN-VAL-106", "out of range")


def test_negative_can_fd_frame_negative_id():
    with pytest.raises(ValidationError) as exc_info:
        CANFDFrame(
            name="canfd_neg_id",
            can_id=-1,
            id_format="standard_11bit",
            length=8,
        )
    assert_single_error(exc_info, "FLYNC-SIG-MIN-VAL-106", "out of range")


def test_negative_can_fd_frame_duplicate_pdu_bit_positions():
    packed_pdus = [PDUInstance(pdu_ref="fd_p1", bit_position=0), PDUInstance(pdu_ref="fd_p2", bit_position=0)]

    with pytest.raises(ValidationError) as exc_info:
        CANFDFrame(name="canfd_dup_pdu", can_id=0x100, id_format="standard_11bit", length=8, packed_pdus=packed_pdus)
    assert_single_error(exc_info, "FLYNC-SIG-MIN-UNIQ-105", "share bit_position")


def test_positive_lin_frame_minimal():
    frm = LINFrame(name="lin_frm_min", lin_id=0x01, length=1)
    assert frm.type == "lin"
    assert frm.lin_id == 0x01
    assert frm.checksum_type == "enhanced"
    assert isinstance(frm, LINFrame)


def test_positive_lin_frame_max_id():
    frm = LINFrame(name="lin_frm_max_id", lin_id=0x3F, length=8)
    assert frm.lin_id == 0x3F
    assert isinstance(frm, LINFrame)


def test_positive_lin_frame_classic_checksum():
    frm = LINFrame(name="lin_frm_classic", lin_id=0x10, length=4, checksum_type="classic")
    assert frm.checksum_type == "classic"
    assert isinstance(frm, LINFrame)


def test_positive_lin_frame_with_timing():
    frm = LINFrame(
        name="lin_frm_timed",
        lin_id=0x05,
        length=8,
        timing=FrameTransmissionTiming(cyclic_timings=[FrameCyclicTiming(cycle=0.005)]),
    )
    assert frm.timing is not None
    assert isinstance(frm, LINFrame)


def test_positive_lin_frame_with_pdu():
    frm = LINFrame(
        name="lin_frm_pdu",
        lin_id=0x02,
        length=4,
        packed_pdus=[PDUInstance(pdu_ref="lin_pdu_1", bit_position=0)],
    )
    assert len(frm.packed_pdus) == 1
    assert isinstance(frm, LINFrame)


@pytest.mark.parametrize(
    "length",
    [pytest.param(i, id=f"lin_len_{i}") for i in range(1, 9)],
)
def test_positive_lin_frame_all_lengths(length):
    frm = LINFrame(name=f"lin_frm_{length}", lin_id=0x01, length=length)
    assert frm.length == length
    assert isinstance(frm, LINFrame)


def test_positive_lin_frame_model_validate():
    data = {"name": "lin_frm_mv", "lin_id": 0x10, "length": 4}
    frm = LINFrame.model_validate(data)
    assert isinstance(frm, LINFrame)


def test_negative_lin_frame_id_too_large():
    with pytest.raises(ValidationError) as exc_info:
        LINFrame(name="lin_bad_id", lin_id=0x40, length=4)
    assert_single_error(exc_info, None, "less than or equal to 63")


def test_negative_lin_frame_id_negative():
    with pytest.raises(ValidationError) as exc_info:
        LINFrame(name="lin_neg_id", lin_id=-1, length=4)
    assert_single_error(exc_info, None, "greater than or equal to 0")


def test_negative_lin_frame_length_zero():
    with pytest.raises(ValidationError) as exc_info:
        LINFrame(name="lin_len0", lin_id=0x01, length=0)
    assert_single_error(exc_info, None, "greater than or equal to 1")


def test_negative_lin_frame_length_too_large():
    with pytest.raises(ValidationError) as exc_info:
        LINFrame(name="lin_len9", lin_id=0x01, length=9)
    assert_single_error(exc_info, None, "less than or equal to 8")


def test_negative_lin_frame_duplicate_pdu_bit_positions():
    packed_pdus = [PDUInstance(pdu_ref="lp1", bit_position=0), PDUInstance(pdu_ref="lp2", bit_position=0)]

    with pytest.raises(ValidationError) as exc_info:
        LINFrame(name="lin_dup_pdu", lin_id=0x01, length=8, packed_pdus=packed_pdus)
    assert_single_error(exc_info, "FLYNC-SIG-MIN-UNIQ-105", "share bit_position")


def _make_j1939_frame(
    name="j1939_frm",
    pdu_format=240,
    pdu_specific=4,
    destination_type="global",
    length=8,
    packed_pdus=None,
):
    return J1939Frame(
        name=name,
        priority=3,
        pdu_format=pdu_format,
        pdu_specific=pdu_specific,
        data_page=0,
        extended_data_page=0,
        destination_type=destination_type,
        length=length,
        packed_pdus=packed_pdus or [],
    )


def test_positive_j1939_frame_minimal():
    frm = _make_j1939_frame()
    assert frm.priority == 3
    assert frm.pdu_format == 240
    assert frm.pdu_specific == 4
    assert frm.destination_type == "global"
    assert frm.length == 8


def test_positive_j1939_frame_global_edge():
    frm = _make_j1939_frame(pdu_format=240, destination_type="global")
    assert frm.destination_type == "global"


def test_positive_j1939_frame_specific_edge():
    frm = _make_j1939_frame(pdu_format=239, pdu_specific=0x1F, destination_type="specific")
    assert frm.destination_type == "specific"


def test_positive_j1939_frame_zero_pdus_allowed():
    frm = _make_j1939_frame()
    assert frm.packed_pdus == []


def test_positive_j1939_frame_with_pdu():
    frm = J1939Frame(
        name="j1939_pdu",
        priority=3,
        pdu_format=240,
        pdu_specific=4,
        data_page=0,
        extended_data_page=0,
        destination_type="global",
        length=8,
        packed_pdus=[PDUInstance(pdu_ref="pdu_nm", bit_position=0)],
    )
    assert len(frm.packed_pdus) == 1


def test_positive_j1939_frame_zero_pdus_allowed():
    frm = _make_j1939_frame()
    assert frm.packed_pdus == []


def test_negative_j1939_frame_zero_length_rejected():
    """J1939 data frames always carry 8 bytes; length < 8 is rejected (TP isn't modelled)."""
    with pytest.raises(ValidationError) as exc_info:
        _make_j1939_frame(length=0)
    assert_single_error(exc_info, None, "Input should be 8")


def test_negative_j1939_frame_multiple_pdus_rejected():
    with pytest.raises(ValidationError) as exc_info:
        _make_j1939_frame(
            packed_pdus=[
                PDUInstance(pdu_ref="pdu_nm_1", bit_position=0),
                PDUInstance(pdu_ref="pdu_nm_2", bit_position=1),
            ]
        )
    assert_single_error(exc_info, "FLYNC-SIG-MAJ-CONS-370", "carries exactly one Parameter Group")


def test_positive_j1939_frame_model_validate():
    data = {
        "name": "j1939_mv",
        "priority": 3,
        "pdu_format": 240,
        "pdu_specific": 4,
        "data_page": 0,
        "extended_data_page": 0,
        "destination_type": "global",
        "length": 8,
    }
    frm = J1939Frame.model_validate(data)
    assert isinstance(frm, J1939Frame)


@pytest.mark.parametrize(
    "pdu_format,destination_type",
    [
        pytest.param(0, "specific", id="pf_0_specific"),
        pytest.param(239, "specific", id="pf_239_specific"),
        pytest.param(240, "global", id="pf_240_global"),
        pytest.param(255, "global", id="pf_255_global"),
    ],
)
def test_positive_j1939_frame_pdu_format_destination_type(pdu_format, destination_type):
    frm = _make_j1939_frame(pdu_format=pdu_format, destination_type=destination_type)
    assert frm.pdu_format == pdu_format


@pytest.mark.parametrize(
    "pdu_format,destination_type,error_id",
    [
        pytest.param(0, "global", "FLYNC-SIG-MIN-CONS-348", id="pf_0_global"),
        pytest.param(239, "global", "FLYNC-SIG-MIN-CONS-348", id="pf_239_global"),
        pytest.param(240, "specific", "FLYNC-SIG-MIN-CONS-347", id="pf_240_specific"),
        pytest.param(255, "specific", "FLYNC-SIG-MIN-CONS-347", id="pf_255_specific"),
    ],
)
def test_negative_j1939_frame_pdu_format_destination_type_mismatch(pdu_format, destination_type, error_id):
    with pytest.raises(ValidationError) as exc_info:
        _make_j1939_frame(pdu_format=pdu_format, destination_type=destination_type)
    assert_single_error(exc_info, error_id, "destination_type")


@pytest.mark.parametrize(
    "pdu_format,pdu_specific,destination_type",
    [
        pytest.param(0, 254, "specific", id="pdu1_specific_da254"),
        pytest.param(238, 255, "global", id="pdu1_global_address_claim"),
        pytest.param(240, 1, "global", id="pdu2_global"),
        pytest.param(255, 0, "global", id="pdu2_global_ge0"),
    ],
)
def test_positive_j1939_frame_destination_matches_da(pdu_format, pdu_specific, destination_type):
    frm = _make_j1939_frame(pdu_format=pdu_format, pdu_specific=pdu_specific, destination_type=destination_type)
    assert frm.destination_type == destination_type


@pytest.mark.parametrize(
    "pdu_format,pdu_specific,destination_type,error_id",
    [
        pytest.param(238, 255, "specific", "FLYNC-SIG-MIN-CONS-348", id="pdu1_specific_but_da255"),
        pytest.param(238, 254, "global", "FLYNC-SIG-MIN-CONS-348", id="pdu1_global_but_da254"),
    ],
)
def test_negative_j1939_frame_destination_mismatches_da(pdu_format, pdu_specific, destination_type, error_id):
    with pytest.raises(ValidationError) as exc_info:
        _make_j1939_frame(pdu_format=pdu_format, pdu_specific=pdu_specific, destination_type=destination_type)
    assert_single_error(exc_info, error_id, "destination_type")


@pytest.mark.parametrize(
    "field,value,msg",
    [
        pytest.param("priority", -1, "greater than or equal to 0", id="priority_neg"),
        pytest.param("priority", 8, "less than or equal to 7", id="priority_hi"),
        pytest.param("pdu_format", -1, "greater than or equal to 0", id="pf_neg"),
        pytest.param("pdu_format", 256, "less than or equal to 255", id="pf_hi"),
        pytest.param("pdu_specific", -1, "greater than or equal to 0", id="ps_neg"),
        pytest.param("pdu_specific", 256, "less than or equal to 255", id="ps_hi"),
        pytest.param("data_page", 2, "less than or equal to 1", id="dp_hi"),
        pytest.param("extended_data_page", 2, "less than or equal to 1", id="edp_hi"),
    ],
)
def test_negative_j1939_frame_out_of_range(field, value, msg):
    kwargs = dict(
        name="j1939_rng", priority=3, pdu_format=240, pdu_specific=4, data_page=0, extended_data_page=0, destination_type="global", length=8
    )
    kwargs[field] = value
    with pytest.raises(ValidationError) as exc_info:
        J1939Frame(**kwargs)
    assert_single_error(exc_info, None, msg)


def test_negative_j1939_frame_invalid_destination_type():
    with pytest.raises(ValidationError) as exc_info:
        _make_j1939_frame(destination_type="bogus")
    assert_single_error(exc_info, None, "'global' or 'specific'")
