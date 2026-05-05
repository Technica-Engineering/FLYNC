import pytest
from pydantic import ValidationError

from flync.model.flync_4_bus.can_bus import CANBus
from flync.model.flync_4_signal.frame import CANFDFrame, CANFrame

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_can_frame(
    name="frm",
    can_id=0x100,
    id_format="standard_11bit",
    length=8,
):
    return CANFrame(
        name=name,
        can_id=can_id,
        id_format=id_format,
        length=length,
    )


def _make_canfd_frame(name="fd_frm", can_id=0x100, id_format="standard_11bit", length=8):
    return CANFDFrame(name=name, can_id=can_id, id_format=id_format, length=length)


# ---------------------------------------------------------------------------
# CANBus — positive tests
# ---------------------------------------------------------------------------


def test_positive_can_bus_minimal():
    bus = CANBus(name="CAN_bus_1", baud_rate=500_000)
    assert bus.baud_rate == 500_000
    assert bus.fd_enabled is False
    assert bus.fd_baud_rate is None
    assert bus.frames == []


def test_positive_can_bus_with_description():
    bus = CANBus(name="CAN_bus_desc", baud_rate=250_000, description="Body CAN bus")
    assert bus.description == "Body CAN bus"


def test_positive_can_bus_with_version():
    bus = CANBus(name="CAN_bus_ver", baud_rate=500_000, version="1.0")
    assert bus.version == "1.0"


def test_positive_can_bus_empty_version():
    bus = CANBus(name="CAN_bus_empty_ver", baud_rate=500_000)
    assert bus.version == ""


@pytest.mark.parametrize(
    "baud_rate",
    [
        pytest.param(10_000, id="10k"),
        pytest.param(20_000, id="20k"),
        pytest.param(50_000, id="50k"),
        pytest.param(100_000, id="100k"),
        pytest.param(125_000, id="125k"),
        pytest.param(250_000, id="250k"),
        pytest.param(500_000, id="500k"),
        pytest.param(1_000_000, id="1M"),
    ],
)
def test_positive_can_bus_all_valid_baud_rates(baud_rate):
    bus = CANBus(name=f"CAN_br_{baud_rate}", baud_rate=baud_rate)
    assert bus.baud_rate == baud_rate


@pytest.mark.parametrize(
    "fd_baud_rate",
    [
        pytest.param(2_000_000, id="2M"),
        pytest.param(4_000_000, id="4M"),
        pytest.param(5_000_000, id="5M"),
        pytest.param(8_000_000, id="8M"),
    ],
)
def test_positive_can_bus_all_valid_fd_data_rates(fd_baud_rate):
    bus = CANBus(
        name=f"CAN_fd_{fd_baud_rate}",
        baud_rate=500_000,
        fd_enabled=True,
        fd_baud_rate=fd_baud_rate,
    )
    assert bus.fd_baud_rate == fd_baud_rate


def test_positive_can_bus_with_can_frame():
    frm = _make_can_frame("bus_frm_1")
    bus = CANBus(name="CAN_frm_bus", baud_rate=500_000, frames=[frm])
    assert len(bus.frames) == 1


def test_positive_can_bus_fd_with_canfd_frame():
    fd_frm = _make_canfd_frame("bus_fd_frm", length=64)
    bus = CANBus(
        name="CAN_fd_bus",
        baud_rate=500_000,
        fd_enabled=True,
        fd_baud_rate=2_000_000,
        frames=[fd_frm],
    )
    assert len(bus.frames) == 1


def test_positive_can_bus_model_validate():
    data = {"name": "CAN_mv_bus", "baud_rate": 250_000}
    bus = CANBus.model_validate(data)
    assert isinstance(bus, CANBus)


# ---------------------------------------------------------------------------
# CANBus — negative tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_baud",
    [
        pytest.param(9_600, id="9600"),
        pytest.param(300_000, id="300k"),
        pytest.param(0, id="zero"),
        pytest.param(2_000_000, id="2M_wrong_field"),
    ],
)
def test_negative_can_bus_invalid_baud_rate(bad_baud):
    with pytest.raises(ValidationError):
        CANBus(name=f"bad_br_{bad_baud}", baud_rate=bad_baud)


def test_negative_can_bus_fd_enabled_missing_fd_baud_rate():
    with pytest.raises(ValidationError):
        CANBus(name="CAN_fd_no_rate", baud_rate=500_000, fd_enabled=True)


def test_negative_can_bus_fd_baud_rate_without_fd_enabled():
    with pytest.raises(ValidationError):
        CANBus(
            name="CAN_rate_no_fd",
            baud_rate=500_000,
            fd_enabled=False,
            fd_baud_rate=2_000_000,
        )


@pytest.mark.parametrize(
    "bad_fd_rate",
    [
        pytest.param(1_000_000, id="1M"),
        pytest.param(3_000_000, id="3M"),
        pytest.param(6_000_000, id="6M"),
        pytest.param(10_000_000, id="10M"),
    ],
)
def test_negative_can_bus_invalid_fd_baud_rate(bad_fd_rate):
    with pytest.raises(ValidationError):
        CANBus(
            name=f"bad_fd_br_{bad_fd_rate}",
            baud_rate=500_000,
            fd_enabled=True,
            fd_baud_rate=bad_fd_rate,
        )


def test_negative_can_bus_canfd_frame_without_fd_enabled():
    fd_frm = _make_canfd_frame("bad_fd_frm")
    with pytest.raises(ValidationError):
        CANBus(
            name="CAN_no_fd_bus",
            baud_rate=500_000,
            fd_enabled=False,
            frames=[fd_frm],
        )


def test_negative_can_bus_duplicate_frame_names():
    frm = _make_can_frame("dup_frm_single", can_id=0x100)
    with pytest.raises(ValidationError):
        CANBus(name="CAN_dup_frm", baud_rate=500_000, frames=[frm, frm])


def test_negative_can_bus_duplicate_can_ids():
    frm1 = _make_can_frame("unique_frm_a", can_id=0x100, id_format="standard_11bit")
    frm2 = _make_can_frame("unique_frm_b", can_id=0x100, id_format="standard_11bit")
    with pytest.raises(ValidationError):
        CANBus(name="CAN_dup_ids", baud_rate=500_000, frames=[frm1, frm2])


def test_negative_can_bus_same_id_different_format_is_allowed():
    frm1 = _make_can_frame("id_std", can_id=0x100, id_format="standard_11bit")
    frm2 = _make_can_frame("id_ext", can_id=0x100, id_format="extended_29bit")
    bus = CANBus(name="CAN_mixed_fmt", baud_rate=500_000, frames=[frm1, frm2])
    assert len(bus.frames) == 2
