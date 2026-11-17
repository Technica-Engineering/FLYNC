"""Tests for the 0.15 -> 0.16 migration."""

import copy
import logging

import pytest

from flync.core.version_migrators._base import MigrationRegistry, migration_registry
from flync.core.version_migrators.engine import MigrationEngine
from flync.core.version_migrators.migrations.v0_15_to_0_16 import Migration016
from flync.model.flync_4_ecu.can_interface import CANInterface
from flync.model.flync_4_metadata.metadata import BaseVersion

V = lambda v: BaseVersion(version_schema="pep440", version=v)  # noqa: E731

BUS_URI = "communication/channels/can/j1939_can.flync.yaml"
IFACE_URI = "ecus/ecu1/controllers/c1/can_interfaces/j1939_can_interface.flync.yaml"


def j1939_frame(name: str, pdu_format: int, pdu_specific: int, data_page: int = 0) -> dict:
    return {
        "name": name,
        "type": "j1939",
        "priority": 6,
        "pdu_format": pdu_format,
        "pdu_specific": pdu_specific,
        "data_page": data_page,
        "extended_data_page": 0,
        "destination_type": "global" if pdu_format >= 240 else "specific",
    }


BUS = {
    "name": "J1939BusCAN",
    "baud_rate": 250000,
    "frames": [
        j1939_frame("Frame_EBC1", 0xF0, 0x01),
        j1939_frame("Frame_PropA", 0xEF, 0x21),
    ],
}


def migrate(documents: dict) -> dict:
    """Migrate ``documents`` from 0.15, asserting a second run changes nothing."""
    registry = MigrationRegistry.new()
    registry.register(Migration016())
    engine = MigrationEngine(registry=registry)
    _, working, _ = engine.apply(documents, V("0.15.1"), V("0.16.0"))
    _, again, changed = engine.apply(copy.deepcopy(working), V("0.15.1"), V("0.16.0"))
    assert again == working
    assert not changed
    return working


def interface(*refs: dict) -> dict:
    return {"bus_ref": "J1939BusCAN", "j1939_name": 1, "j1939_sender_frames": [dict(ref) for ref in refs]}


def test_registered_in_default_registry():
    assert migration_registry.get("v0_15_to_0_16").target_version == "0.16.0"


@pytest.mark.parametrize(
    "ref, expected",
    [
        pytest.param({"pgn": 0xF001}, {"frame_ref": "Frame_EBC1"}, id="pdu2"),
        pytest.param({"pgn": 0xEF00}, {"frame_ref": "Frame_PropA"}, id="pdu1-destination-not-in-pgn"),
        pytest.param({"frame_ref": "Frame_EBC1"}, {"frame_ref": "Frame_EBC1"}, id="already-migrated"),
    ],
)
def test_pgn_reference_becomes_the_frame_name(ref, expected):
    migrated = migrate({BUS_URI: copy.deepcopy(BUS), IFACE_URI: interface(ref)})[IFACE_URI]

    assert migrated["j1939_sender_frames"] == [expected]
    CANInterface.model_validate({"name": "j1939_can_interface", **migrated})


@pytest.mark.parametrize(
    "pgn, message",
    [
        pytest.param(0x1234, "no J1939 frame has PGN 0x1234", id="unknown"),
        pytest.param(0xF001, "several J1939 frames share PGN 0xf001", id="shared"),
    ],
)
def test_unresolvable_pgn_is_left_unchanged(caplog, pgn, message):
    bus = copy.deepcopy(BUS)
    bus["frames"].append(j1939_frame("Frame_EBC1_Copy", 0xF0, 0x01))
    with caplog.at_level(logging.WARNING):
        migrated = migrate({BUS_URI: bus, IFACE_URI: interface({"pgn": pgn})})[IFACE_URI]

    assert migrated["j1939_sender_frames"] == [{"pgn": pgn}]
    assert message in caplog.text


def test_pgn_is_resolved_on_the_interface_bus():
    other = copy.deepcopy(BUS)
    other["name"] = "OtherCAN"
    other["frames"] = [j1939_frame("Other_EBC1", 0xF0, 0x01)]
    documents = {
        BUS_URI: copy.deepcopy(BUS),
        "communication/channels/can/other_can.flync.yaml": other,
        IFACE_URI: interface({"pgn": 0xF001}),
    }

    assert migrate(documents)[IFACE_URI]["j1939_sender_frames"] == [{"frame_ref": "Frame_EBC1"}]
