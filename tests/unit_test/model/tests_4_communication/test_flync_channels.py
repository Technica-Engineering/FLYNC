import pytest
from pydantic import ValidationError

from flync.model.flync_4_communication.flync_channels import (
    FLYNCChannelConfig,
)


def _make_pdu(name: str, length: int) -> dict:
    return {"name": name, "type": "standard", "length": length}


def _make_can_bus(name: str, frames: list) -> dict:
    return {
        "name": name,
        "baud_rate": 500_000,
        "fd_enabled": True,
        "fd_baud_rate": 2_000_000,
        "frames": frames,
    }


def _make_can_fd_frame(name: str, length: int, packed_pdus: list, can_id: int = 1) -> dict:
    return {
        "name": name,
        "type": "can_fd",
        "length": length,
        "can_id": can_id,
        "id_format": "standard_11bit",
        "packed_pdus": packed_pdus,
    }


def _make_lin_bus(name: str, frames: list) -> dict:
    return {
        "name": name,
        "lin_protocol_version": "2.2A",
        "lin_language_version": "2.2A",
        "baud_rate": 19_200,
        "frames": frames,
    }


def _make_lin_frame(name: str, length: int, packed_pdus: list, lin_id: int = 1) -> dict:
    return {
        "name": name,
        "type": "lin",
        "length": length,
        "lin_id": lin_id,
        "checksum_type": "enhanced",
        "packed_pdus": packed_pdus,
    }


# ---------------------------------------------------------------------------
# CAN frame — packed PDU overlap / overflow
# ---------------------------------------------------------------------------


def test_positive_can_frame_packed_pdus_no_overlap():
    cfg = {
        "pdus": [_make_pdu("P1", 4), _make_pdu("P2", 4)],
        "can_buses": [
            _make_can_bus(
                "B1",
                frames=[
                    _make_can_fd_frame(
                        "F1",
                        length=64,
                        packed_pdus=[
                            {"pdu_ref": "P1", "bit_position": 0},
                            {"pdu_ref": "P2", "bit_position": 32},
                        ],
                    ),
                ],
            )
        ],
    }
    assert FLYNCChannelConfig.model_validate(cfg)


def test_negative_can_frame_packed_pdus_overlap():
    cfg = {
        "pdus": [_make_pdu("P1", 4)],
        "can_buses": [
            _make_can_bus(
                "B1",
                frames=[
                    _make_can_fd_frame(
                        "F1",
                        length=64,
                        packed_pdus=[
                            {"pdu_ref": "P1", "bit_position": 0},
                            {"pdu_ref": "P1", "bit_position": 16},
                        ],
                    ),
                ],
            )
        ],
    }
    with pytest.raises(ValidationError, match="overlap"):
        FLYNCChannelConfig.model_validate(cfg)


def test_negative_can_frame_packed_pdu_overflows_frame():
    cfg = {
        "pdus": [_make_pdu("P1", 8)],
        "can_buses": [
            _make_can_bus(
                "B1",
                frames=[
                    _make_can_fd_frame(
                        "F1",
                        length=8,
                        packed_pdus=[{"pdu_ref": "P1", "bit_position": 8}],
                    ),
                ],
            )
        ],
    }
    with pytest.raises(ValidationError, match="overflows"):
        FLYNCChannelConfig.model_validate(cfg)


def test_positive_can_frame_packed_pdu_unplaced_skipped():
    cfg = {
        "pdus": [_make_pdu("P1", 4), _make_pdu("P2", 4)],
        "can_buses": [
            _make_can_bus(
                "B1",
                frames=[
                    _make_can_fd_frame(
                        "F1",
                        length=64,
                        packed_pdus=[
                            {"pdu_ref": "P1"},
                            {"pdu_ref": "P2", "bit_position": 0},
                        ],
                    ),
                ],
            )
        ],
    }
    assert FLYNCChannelConfig.model_validate(cfg)


# ---------------------------------------------------------------------------
# LIN frame — packed PDU overlap / overflow / unknown ref
# ---------------------------------------------------------------------------


def test_positive_lin_frame_packed_pdus_no_overlap():
    cfg = {
        "pdus": [_make_pdu("P1", 2)],
        "lin_buses": [
            _make_lin_bus(
                "L1",
                frames=[
                    _make_lin_frame(
                        "LF1",
                        length=2,
                        packed_pdus=[{"pdu_ref": "P1", "bit_position": 0}],
                    ),
                ],
            )
        ],
    }
    assert FLYNCChannelConfig.model_validate(cfg)


def test_negative_lin_frame_packed_pdus_overlap():
    cfg = {
        "pdus": [_make_pdu("P1", 2), _make_pdu("P2", 2)],
        "lin_buses": [
            _make_lin_bus(
                "L1",
                frames=[
                    _make_lin_frame(
                        "LF1",
                        length=4,
                        packed_pdus=[
                            {"pdu_ref": "P1", "bit_position": 0},
                            {"pdu_ref": "P2", "bit_position": 8},
                        ],
                    ),
                ],
            )
        ],
    }
    with pytest.raises(ValidationError, match="overlap"):
        FLYNCChannelConfig.model_validate(cfg)


def test_negative_lin_frame_unknown_pdu_ref():
    cfg = {
        "pdus": [_make_pdu("P1", 2)],
        "lin_buses": [
            _make_lin_bus(
                "L1",
                frames=[
                    _make_lin_frame(
                        "LF1",
                        length=2,
                        packed_pdus=[{"pdu_ref": "Unknown", "bit_position": 0}],
                    ),
                ],
            )
        ],
    }
    with pytest.raises(ValidationError, match="LINBus 'L1' references unknown PDU"):
        FLYNCChannelConfig.model_validate(cfg)


def test_negative_can_frame_unknown_pdu_ref():
    cfg = {
        "pdus": [_make_pdu("P1", 2)],
        "can_buses": [
            _make_can_bus(
                "B1",
                frames=[
                    _make_can_fd_frame(
                        "F1",
                        length=8,
                        packed_pdus=[{"pdu_ref": "Unknown", "bit_position": 0}],
                    ),
                ],
            )
        ],
    }
    with pytest.raises(ValidationError, match="CANBus 'B1' references unknown PDU"):
        FLYNCChannelConfig.model_validate(cfg)
