import pytest
from pydantic import ValidationError

from flync.model.flync_4_signal.frame import (
    CANFDFrame,
    CANFrame,
    FrameCyclicTiming,
    FrameEventTiming,
    FrameTransmissionTiming,
    LINFrame,
    PDUReceiver,
    PDUSender,
)
from flync.model.flync_4_signal.pdu import PDUInstance

_CAN_FD_VALID_LENGTHS = (0, 1, 2, 3, 4, 5, 6, 7, 8, 12, 16, 20, 24, 32, 48, 64)


# ---------------------------------------------------------------------------
# FrameEventTiming
# ---------------------------------------------------------------------------


def test_positive_frame_event_timing_defaults():
    t = FrameEventTiming()
    assert t.final_repetitions == 0
    assert t.repeating_time_range == 0.0


def test_positive_frame_event_timing_custom():
    t = FrameEventTiming(final_repetitions=3, repeating_time_range=0.01)
    assert t.final_repetitions == 3
    assert t.repeating_time_range == 0.01


def test_negative_frame_event_timing_negative_repetitions():
    with pytest.raises(ValidationError):
        FrameEventTiming(final_repetitions=-1)


def test_negative_frame_event_timing_negative_repeating_time():
    with pytest.raises(ValidationError):
        FrameEventTiming(repeating_time_range=-0.01)


# ---------------------------------------------------------------------------
# FrameCyclicTiming
# ---------------------------------------------------------------------------


def test_positive_frame_cyclic_timing():
    t = FrameCyclicTiming(cycle=0.01)
    assert t.cycle == 0.01


def test_positive_frame_cyclic_timing_large_cycle():
    t = FrameCyclicTiming(cycle=1.0)
    assert t.cycle == 1.0


def test_negative_frame_cyclic_timing_zero_cycle():
    with pytest.raises(ValidationError):
        FrameCyclicTiming(cycle=0)


def test_negative_frame_cyclic_timing_negative_cycle():
    with pytest.raises(ValidationError):
        FrameCyclicTiming(cycle=-0.01)


# ---------------------------------------------------------------------------
# FrameTransmissionTiming
# ---------------------------------------------------------------------------


def test_positive_frame_transmission_timing_empty():
    t = FrameTransmissionTiming()
    assert t.cyclic_timings == []
    assert t.event_timings == []
    assert t.debounce_time is None


def test_positive_frame_transmission_timing_cyclic_only():
    t = FrameTransmissionTiming(cyclic_timings=[FrameCyclicTiming(cycle=0.1)])
    assert len(t.cyclic_timings) == 1


def test_positive_frame_transmission_timing_both():
    t = FrameTransmissionTiming(
        debounce_time=0.005,
        cyclic_timings=[FrameCyclicTiming(cycle=0.1)],
        event_timings=[FrameEventTiming(final_repetitions=2)],
    )
    assert t.debounce_time == 0.005
    assert len(t.event_timings) == 1


# ---------------------------------------------------------------------------
# CANFrame — positive tests
# ---------------------------------------------------------------------------


def test_positive_can_frame_standard_id_min():
    frm = CANFrame(name="can_std_min", can_id=0, id_format="standard_11bit", length=8)
    assert frm.can_id == 0


def test_positive_can_frame_standard_id_max():
    frm = CANFrame(name="can_std_max", can_id=0x7FF, id_format="standard_11bit", length=8)
    assert frm.can_id == 0x7FF


def test_positive_can_frame_extended_id():
    frm = CANFrame(name="can_ext", can_id=0x1FFFFFFF, id_format="extended_29bit", length=8)
    assert frm.id_format == "extended_29bit"


def test_positive_can_frame_rtr():
    frm = CANFrame(
        name="can_rtr",
        can_id=0x100,
        id_format="standard_11bit",
        length=0,
        is_remote_frame=True,
    )
    assert frm.is_remote_frame is True


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


def test_positive_can_frame_with_timing():
    frm = CANFrame(
        name="can_timed",
        can_id=0x200,
        id_format="standard_11bit",
        length=4,
        timing=FrameTransmissionTiming(cyclic_timings=[FrameCyclicTiming(cycle=0.01)]),
    )
    assert frm.timing is not None


def test_positive_can_frame_with_pdu():
    frm = CANFrame(
        name="can_pdu",
        can_id=0x300,
        id_format="standard_11bit",
        length=8,
        packed_pdus=[PDUInstance(pdu_ref="can_pdu_ref", bit_position=0)],
    )
    assert len(frm.packed_pdus) == 1


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


# ---------------------------------------------------------------------------
# CANFrame — negative tests
# ---------------------------------------------------------------------------


def test_negative_can_frame_standard_id_too_large():
    with pytest.raises(ValidationError):
        CANFrame(
            name="can_bad_std",
            can_id=0x800,
            id_format="standard_11bit",
            length=8,
        )


def test_negative_can_frame_extended_id_too_large():
    with pytest.raises(ValidationError):
        CANFrame(
            name="can_bad_ext",
            can_id=0x20000000,
            id_format="extended_29bit",
            length=8,
        )


def test_negative_can_frame_rtr_with_data():
    with pytest.raises(ValidationError):
        CANFrame(
            name="can_bad_rtr",
            can_id=0x100,
            id_format="standard_11bit",
            length=4,
            is_remote_frame=True,
        )


def test_negative_can_frame_length_too_large():
    with pytest.raises(ValidationError):
        CANFrame(name="can_len9", can_id=0x100, id_format="standard_11bit", length=9)


def test_negative_can_frame_negative_length():
    with pytest.raises(ValidationError):
        CANFrame(
            name="can_neg_len",
            can_id=0x100,
            id_format="standard_11bit",
            length=-1,
        )


def test_negative_can_frame_duplicate_pdu_bit_positions():
    with pytest.raises(ValidationError):
        CANFrame(
            name="can_dup_pdu",
            can_id=0x100,
            id_format="standard_11bit",
            length=8,
            packed_pdus=[
                PDUInstance(pdu_ref="p1", bit_position=0),
                PDUInstance(pdu_ref="p2", bit_position=0),
            ],
        )


# ---------------------------------------------------------------------------
# CANFDFrame — positive tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "length",
    [pytest.param(l, id=f"fd_len_{l}") for l in _CAN_FD_VALID_LENGTHS],
)
def test_positive_can_fd_frame_valid_lengths(length):
    frm = CANFDFrame(
        name=f"canfd_{length}",
        can_id=0x100,
        id_format="standard_11bit",
        length=length,
    )
    assert frm.length == length


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


def test_positive_can_fd_frame_no_brs():
    frm = CANFDFrame(
        name="canfd_no_brs",
        can_id=0x200,
        id_format="standard_11bit",
        length=8,
        bit_rate_switch=False,
    )
    assert frm.bit_rate_switch is False


def test_positive_can_fd_frame_extended_id():
    frm = CANFDFrame(
        name="canfd_ext",
        can_id=0x1FFFFFFF,
        id_format="extended_29bit",
        length=64,
    )
    assert frm.id_format == "extended_29bit"


def test_positive_can_fd_frame_with_esi():
    frm = CANFDFrame(
        name="canfd_esi",
        can_id=0x100,
        id_format="standard_11bit",
        length=8,
        error_state_indicator=True,
    )
    assert frm.error_state_indicator is True


def test_positive_can_fd_frame_model_validate():
    data = {
        "name": "canfd_mv",
        "can_id": 0x100,
        "id_format": "standard_11bit",
        "length": 8,
    }
    frm = CANFDFrame.model_validate(data)
    assert isinstance(frm, CANFDFrame)


# ---------------------------------------------------------------------------
# CANFDFrame — negative tests
# ---------------------------------------------------------------------------


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
    with pytest.raises(ValidationError):
        CANFDFrame(
            name=f"canfd_bad_{bad_length}",
            can_id=0x100,
            id_format="standard_11bit",
            length=bad_length,
        )


def test_negative_can_fd_frame_length_exceeds_max():
    with pytest.raises(ValidationError):
        CANFDFrame(
            name="canfd_65",
            can_id=0x100,
            id_format="standard_11bit",
            length=65,
        )


def test_negative_can_fd_frame_standard_id_too_large():
    with pytest.raises(ValidationError):
        CANFDFrame(
            name="canfd_bad_id",
            can_id=0x800,
            id_format="standard_11bit",
            length=8,
        )


def test_negative_can_fd_frame_duplicate_pdu_bit_positions():
    with pytest.raises(ValidationError):
        CANFDFrame(
            name="canfd_dup_pdu",
            can_id=0x100,
            id_format="standard_11bit",
            length=8,
            packed_pdus=[
                PDUInstance(pdu_ref="fd_p1", bit_position=0),
                PDUInstance(pdu_ref="fd_p2", bit_position=0),
            ],
        )


# ---------------------------------------------------------------------------
# LINFrame — positive tests
# ---------------------------------------------------------------------------


def test_positive_lin_frame_minimal():
    frm = LINFrame(name="lin_frm_min", lin_id=0x01, length=1)
    assert frm.type == "lin"
    assert frm.lin_id == 0x01
    assert frm.checksum_type == "enhanced"


def test_positive_lin_frame_max_id():
    frm = LINFrame(name="lin_frm_max_id", lin_id=0x3F, length=8)
    assert frm.lin_id == 0x3F


def test_positive_lin_frame_classic_checksum():
    frm = LINFrame(name="lin_frm_classic", lin_id=0x10, length=4, checksum_type="classic")
    assert frm.checksum_type == "classic"


def test_positive_lin_frame_with_timing():
    frm = LINFrame(
        name="lin_frm_timed",
        lin_id=0x05,
        length=8,
        timing=FrameTransmissionTiming(cyclic_timings=[FrameCyclicTiming(cycle=0.005)]),
    )
    assert frm.timing is not None


def test_positive_lin_frame_with_pdu():
    frm = LINFrame(
        name="lin_frm_pdu",
        lin_id=0x02,
        length=4,
        packed_pdus=[PDUInstance(pdu_ref="lin_pdu_1", bit_position=0)],
    )
    assert len(frm.packed_pdus) == 1


@pytest.mark.parametrize(
    "length",
    [pytest.param(i, id=f"lin_len_{i}") for i in range(1, 9)],
)
def test_positive_lin_frame_all_lengths(length):
    frm = LINFrame(name=f"lin_frm_{length}", lin_id=0x01, length=length)
    assert frm.length == length


def test_positive_lin_frame_model_validate():
    data = {"name": "lin_frm_mv", "lin_id": 0x10, "length": 4}
    frm = LINFrame.model_validate(data)
    assert isinstance(frm, LINFrame)


# ---------------------------------------------------------------------------
# LINFrame — negative tests
# ---------------------------------------------------------------------------


def test_negative_lin_frame_id_too_large():
    with pytest.raises(ValidationError):
        LINFrame(name="lin_bad_id", lin_id=0x40, length=4)


def test_negative_lin_frame_id_negative():
    with pytest.raises(ValidationError):
        LINFrame(name="lin_neg_id", lin_id=-1, length=4)


def test_negative_lin_frame_length_zero():
    with pytest.raises(ValidationError):
        LINFrame(name="lin_len0", lin_id=0x01, length=0)


def test_negative_lin_frame_length_too_large():
    with pytest.raises(ValidationError):
        LINFrame(name="lin_len9", lin_id=0x01, length=9)


def test_negative_lin_frame_duplicate_pdu_bit_positions():
    with pytest.raises(ValidationError):
        LINFrame(
            name="lin_dup_pdu",
            lin_id=0x01,
            length=8,
            packed_pdus=[
                PDUInstance(pdu_ref="lp1", bit_position=0),
                PDUInstance(pdu_ref="lp2", bit_position=0),
            ],
        )


# ---------------------------------------------------------------------------
# PDUSender
# ---------------------------------------------------------------------------


def test_positive_pdu_sender_basic():
    sender = PDUSender(pdu_ref="my_container_pdu")
    assert sender.deployment_type == "pdu_sender"
    assert sender.pdu_ref == "my_container_pdu"


def test_positive_pdu_sender_model_validate():
    data = {"deployment_type": "pdu_sender", "pdu_ref": "container_pdu_1"}
    sender = PDUSender.model_validate(data)
    assert isinstance(sender, PDUSender)


def test_positive_pdu_sender_default_type():
    sender = PDUSender(pdu_ref="pdu_x")
    assert sender.deployment_type == "pdu_sender"


def test_negative_pdu_sender_missing_pdu_ref():
    with pytest.raises(ValidationError):
        PDUSender.model_validate({"deployment_type": "pdu_sender"})


# ---------------------------------------------------------------------------
# PDUReceiver
# ---------------------------------------------------------------------------


def test_positive_pdu_receiver_basic():
    receiver = PDUReceiver(pdu_ref="my_container_pdu")
    assert receiver.deployment_type == "pdu_receiver"
    assert receiver.pdu_ref == "my_container_pdu"


def test_positive_pdu_receiver_model_validate():
    data = {"deployment_type": "pdu_receiver", "pdu_ref": "container_pdu_1"}
    receiver = PDUReceiver.model_validate(data)
    assert isinstance(receiver, PDUReceiver)


def test_positive_pdu_receiver_default_type():
    receiver = PDUReceiver(pdu_ref="pdu_x")
    assert receiver.deployment_type == "pdu_receiver"


def test_negative_pdu_receiver_missing_pdu_ref():
    with pytest.raises(ValidationError):
        PDUReceiver.model_validate({"deployment_type": "pdu_receiver"})
