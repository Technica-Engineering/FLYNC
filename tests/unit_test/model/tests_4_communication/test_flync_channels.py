import pytest
from pydantic import ValidationError

from flync.model.flync_4_communication.flync_channels import (
    FLYNCChannelConfig,
)
from tests.error_assertions import assert_single_error


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


def test_positive_ethernet_pdu_container_known_pdu_refs():
    cfg = {
        "pdus": [_make_pdu("P1", 2)],
        "ethernet_pdu_containers": [
            {
                "name": "C1",
                "length": 8,
                "pdu_id": 1,
                "header": {"id_length_bits": 8, "length_field_bits": 8},
                "contained_pdus": [
                    {"header_id": 1, "pdu_ref": "P1"},
                    {"header_id": 2, "pdu_ref": "P1"},
                ],
            }
        ],
    }
    assert FLYNCChannelConfig.model_validate(cfg)


def test_negative_ethernet_pdu_container_unknown_pdu_ref():
    cfg = {
        "pdus": [_make_pdu("P1", 2)],
        "ethernet_pdu_containers": [
            {
                "name": "C1",
                "length": 8,
                "pdu_id": 1,
                "header": {"id_length_bits": 8, "length_field_bits": 8},
                "contained_pdus": [{"header_id": 1, "pdu_ref": "Unknown"}],
            }
        ],
    }
    with pytest.raises(ValidationError) as exc_info:
        FLYNCChannelConfig.model_validate(cfg)
    assert_single_error(exc_info, "FLYNC-CMN-MAJ-REF-236", "ContainerPDU 'C1' references unknown PDU")


def _make_multiplexed_pdu(name: str, static_group_ref=None, mux_group_refs=None) -> dict:
    """Build a multiplexed PDU dict. ``static_group`` is emitted as a list of PDU instances."""
    return {
        "name": name,
        "type": "multiplexed",
        "length": 8,
        "selector_signal": {"signal": {"name": "mp_sel", "bit_length": 4, "data_type": "uint8"}},
        "static_group": [{"pdu_ref": static_group_ref}] if static_group_ref else None,
        "mux_groups": [{"selector_value": idx, "pdu": {"pdu_ref": ref}} for idx, ref in enumerate(mux_group_refs or [])],
    }


def test_positive_multiplexed_pdu_known_pdu_refs():
    cfg = {
        "pdus": [
            _make_pdu("P1", 2),
            _make_pdu("P2", 2),
            _make_multiplexed_pdu("MP1", static_group_ref="P1", mux_group_refs=["P2"]),
        ],
    }
    assert FLYNCChannelConfig.model_validate(cfg)


def test_positive_multiplexed_pdu_static_group_single_mapping():
    # static_group used to be a single PDU instance; the unwrapped mapping is still accepted.
    mp = _make_multiplexed_pdu("MP1", static_group_ref="P1", mux_group_refs=["P2"])
    mp["static_group"] = {"pdu_ref": "P1"}
    cfg = {"pdus": [_make_pdu("P1", 2), _make_pdu("P2", 2), mp]}
    config = FLYNCChannelConfig.model_validate(cfg)
    assert [inst.pdu_ref for inst in config.pdus[2].static_group] == ["P1"]


def test_negative_multiplexed_pdu_static_group_unknown_pdu_ref():
    cfg = {
        "pdus": [
            _make_pdu("P1", 2),
            _make_multiplexed_pdu("MP1", static_group_ref="Unknown", mux_group_refs=["P1"]),
        ],
    }
    with pytest.raises(ValidationError) as exc_info:
        FLYNCChannelConfig.model_validate(cfg)
    assert_single_error(exc_info, "FLYNC-CMN-MAJ-REF-237", "MultiplexedPDU 'MP1' references unknown PDU")


def test_negative_multiplexed_pdu_unknown_pdu_ref():
    cfg = {
        "pdus": [
            {
                "name": "MP1",
                "type": "multiplexed",
                "length": 8,
                "selector_signal": {"signal": {"name": "mp_sel", "bit_length": 4, "data_type": "uint8"}},
                "mux_groups": [{"selector_value": 0, "pdu": {"pdu_ref": "Unknown"}}],
            }
        ],
    }
    with pytest.raises(ValidationError) as exc_info:
        FLYNCChannelConfig.model_validate(cfg)
    assert_single_error(exc_info, "FLYNC-CMN-MAJ-REF-237", "MultiplexedPDU 'MP1' references unknown PDU")


# ---------------------------------------------------------------------------
# MultiplexedPDU placements
#
# Each referenced PDU occupies [bit_position, bit_position + referenced_pdu.length * 8) — the signals
# inside it are irrelevant, exactly as for PDU placements in a frame. Statics must be disjoint from each
# other and from the selector; mux groups are runtime alternatives and may share bits with one another.
# ---------------------------------------------------------------------------


def _make_placed_multiplexed_pdu(length=8, selector_bit=0, static=(), mux=()) -> dict:
    return {
        "name": "MP1",
        "type": "multiplexed",
        "length": length,
        "selector_signal": {"signal": {"name": "mp_sel", "bit_length": 4, "data_type": "uint8"}, "bit_position": selector_bit},
        "static_group": [{"pdu_ref": ref, "bit_position": bit} for ref, bit in static] or None,
        "mux_groups": [{"selector_value": idx, "pdu": {"pdu_ref": ref, "bit_position": bit}} for idx, (ref, bit) in enumerate(mux)],
    }


def test_positive_multiplexed_pdu_placements_clear_of_selector():
    cfg = {
        "pdus": [
            _make_pdu("P1", 1),
            _make_pdu("P2", 2),
            _make_placed_multiplexed_pdu(static=[("P1", 8)], mux=[("P2", 16)]),
        ],
    }
    assert FLYNCChannelConfig.model_validate(cfg)


def test_positive_multiplexed_pdu_mux_groups_may_share_bits():
    # Two alternatives selected by different selector values are expected to occupy the same bits.
    cfg = {
        "pdus": [
            _make_pdu("P1", 2),
            _make_pdu("P2", 2),
            _make_placed_multiplexed_pdu(mux=[("P1", 8), ("P2", 8)]),
        ],
    }
    assert FLYNCChannelConfig.model_validate(cfg)


def test_negative_multiplexed_pdu_static_overlaps_selector():
    # P1 is 1 byte at bit 0 -> [0, 8), which covers the 4-bit selector at [0, 4).
    cfg = {
        "pdus": [
            _make_pdu("P1", 1),
            _make_pdu("P2", 2),
            _make_placed_multiplexed_pdu(static=[("P1", 0)], mux=[("P2", 16)]),
        ],
    }
    with pytest.raises(ValidationError) as exc_info:
        FLYNCChannelConfig.model_validate(cfg)
    assert_single_error(exc_info, "FLYNC-CMN-MIN-CONS-030", "MultiplexedPDU 'MP1'")


def test_negative_multiplexed_pdu_statics_overlap_each_other():
    cfg = {
        "pdus": [
            _make_pdu("P1", 2),
            _make_pdu("P2", 2),
            _make_placed_multiplexed_pdu(static=[("P1", 8), ("P1", 16)], mux=[("P2", 40)]),
        ],
    }
    with pytest.raises(ValidationError) as exc_info:
        FLYNCChannelConfig.model_validate(cfg)
    assert_single_error(exc_info, "FLYNC-CMN-MIN-CONS-030", "MultiplexedPDU 'MP1'")


def test_negative_multiplexed_pdu_mux_overlaps_static():
    cfg = {
        "pdus": [
            _make_pdu("P1", 2),
            _make_pdu("P2", 2),
            _make_placed_multiplexed_pdu(static=[("P1", 8)], mux=[("P2", 16)]),
        ],
    }
    cfg["pdus"][2]["mux_groups"][0]["pdu"]["bit_position"] = 8
    with pytest.raises(ValidationError) as exc_info:
        FLYNCChannelConfig.model_validate(cfg)
    assert_single_error(exc_info, "FLYNC-CMN-MIN-CONS-030", "MultiplexedPDU 'MP1'")


def test_negative_multiplexed_pdu_mux_overlaps_selector():
    cfg = {
        "pdus": [
            _make_pdu("P1", 2),
            _make_placed_multiplexed_pdu(mux=[("P1", 0)]),
        ],
    }
    with pytest.raises(ValidationError) as exc_info:
        FLYNCChannelConfig.model_validate(cfg)
    assert_single_error(exc_info, "FLYNC-CMN-MIN-CONS-030", "MultiplexedPDU 'MP1'")


def test_negative_multiplexed_pdu_placement_exceeds_length():
    # A 2-byte PDU placed at bit 56 ends at bit 72, past the multiplexed PDU's 8 byte (64 bit) length.
    cfg = {
        "pdus": [
            _make_pdu("P1", 2),
            _make_placed_multiplexed_pdu(mux=[("P1", 56)]),
        ],
    }
    with pytest.raises(ValidationError) as exc_info:
        FLYNCChannelConfig.model_validate(cfg)
    assert_single_error(exc_info, "FLYNC-CMN-MIN-VAL-029", "MultiplexedPDU 'MP1'")


def test_positive_multiplexed_pdu_unplaced_instances_skipped():
    # An unplaced selector or PDU instance cannot be range-checked and is skipped here.
    cfg = {
        "pdus": [
            _make_pdu("P1", 2),
            _make_pdu("P2", 2),
            {
                **_make_placed_multiplexed_pdu(static=[("P1", 0)], mux=[("P2", 0)]),
                "selector_signal": {"signal": {"name": "mp_sel", "bit_length": 4, "data_type": "uint8"}},
            },
        ],
    }
    cfg["pdus"][2]["static_group"][0].pop("bit_position")
    cfg["pdus"][2]["mux_groups"][0]["pdu"].pop("bit_position")
    assert FLYNCChannelConfig.model_validate(cfg)
