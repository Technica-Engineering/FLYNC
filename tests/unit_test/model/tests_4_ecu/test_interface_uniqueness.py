"""Uniqueness validators for CAN/LIN interfaces and ``Controller.find_controller_interface``."""

import pytest
from pydantic import ValidationError

from flync.model.flync_4_ecu.can_interface import CANInterface
from flync.model.flync_4_ecu.lin_interface import LINMasterInterface, LINSlaveInterface
from tests.error_assertions import assert_single_error


def _can(**kwargs):
    return CANInterface(name="can0", bus_ref="bus", **kwargs)


def test_can_duplicate_sender_frames():
    ref = {"frame_ref": 1, "id_format": "standard_11bit"}
    with pytest.raises(ValidationError) as exc:
        _can(sender_frames=[ref, ref])
    assert_single_error(exc, "FLYNC-ECU-MAJ-UNIQ-434", "sender_frames")


def test_can_duplicate_receiver_frames():
    ref = {"frame_ref": 1, "id_format": "standard_11bit"}
    with pytest.raises(ValidationError) as exc:
        _can(receiver_frames=[ref, ref])
    assert_single_error(exc, "FLYNC-ECU-MAJ-UNIQ-434", "receiver_frames")


def test_can_same_id_different_format_is_allowed():
    _can(sender_frames=[{"frame_ref": 1, "id_format": "standard_11bit"}, {"frame_ref": 1, "id_format": "extended_29bit"}])


def test_lin_master_duplicate_sender_frames():
    ref = {"frame_ref": 3}
    with pytest.raises(ValidationError) as exc:
        LINMasterInterface(name="m", bus_ref="lin", lin_protocol="2.1", p2_min=1.0, st_min=1.0, sender_frames=[ref, ref])
    assert_single_error(exc, "FLYNC-ECU-MAJ-UNIQ-435", "sender_frames")


def test_lin_slave_duplicate_receiver_frames():
    ref = {"frame_ref": 3}
    with pytest.raises(ValidationError) as exc:
        LINSlaveInterface(name="s", bus_ref="lin", lin_protocol="2.1", configured_nad=1, initial_nad=1, receiver_frames=[ref, ref])
    assert_single_error(exc, "FLYNC-ECU-MAJ-UNIQ-435", "receiver_frames")
