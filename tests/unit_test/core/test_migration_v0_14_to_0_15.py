"""Tests for the 0.14 → 0.15 workspace migration."""

import copy

import pytest

from flync.core.version_migrators._base import MigrationRegistry, migration_registry
from flync.core.version_migrators.engine import MigrationEngine
from flync.core.version_migrators.migrations.v0_14_to_0_15 import Migration0_15
from flync.model.flync_4_ecu.can_interface import CANInterface
from flync.model.flync_4_metadata.metadata import BaseVersion

V = lambda v: BaseVersion(version_schema="pep440", version=v)  # noqa: E731

BUS_URI = "communication/channels/can/body_can.flync.yaml"
IFACE_URI = "ecus/ecu1/controllers/c1/can_interfaces/body_can_interface.flync.yaml"


def can_bus(name: str, *frames: tuple[int, str]) -> dict:
    """A CAN bus document declaring one classical frame per ``(can_id, id_format)``."""
    return {
        "name": name,
        "baud_rate": 500000,
        "frames": [{"name": f"F_{fmt}_{can_id:x}", "type": "can", "length": 8, "can_id": can_id, "id_format": fmt} for can_id, fmt in frames],
    }


def migrate(documents: dict, recorded: str = "0.14.0") -> dict:
    """Migrate ``documents``, asserting a second run changes nothing."""
    registry = MigrationRegistry.new()
    registry.register(Migration0_15())
    engine = MigrationEngine(registry=registry)
    _, working, _ = engine.apply(documents, V(recorded), V("0.15.0"))
    _, again, changed = engine.apply(copy.deepcopy(working), V(recorded), V("0.15.0"))
    assert again == working and not changed
    return working


def test_registered_in_default_registry():
    assert migration_registry.get("v0_14_to_0_15").target_version == "0.15.0"


@pytest.mark.parametrize(
    "buses, ref, expected",
    [
        pytest.param([can_bus("BodyCAN", (0x510, "standard_11bit"))], {"bus_ref": "BodyCAN", "frame_ref": 0x510}, "standard_11bit", id="standard"),
        pytest.param(
            [can_bus("BodyCAN", (0x100, "extended_29bit"))], {"bus_ref": "BodyCAN", "frame_ref": 0x100}, "extended_29bit", id="extended-low-id"
        ),
        pytest.param(
            [can_bus("BodyCAN", (0x100, "standard_11bit"), (0x100, "extended_29bit"))],
            {"bus_ref": "BodyCAN", "frame_ref": 0x100},
            "extended_29bit",
            id="duplicate-id-last-wins",
        ),
        pytest.param(
            [can_bus("BodyCAN", (0x100, "standard_11bit")), can_bus("OtherCAN", (0x100, "extended_29bit"))],
            {"bus_ref": "OtherCAN", "frame_ref": 0x100},
            "extended_29bit",
            id="ref-own-bus",
        ),
        pytest.param([can_bus("BodyCAN")], {"bus_ref": "BodyCAN", "frame_ref": 0x7FF}, "standard_11bit", id="dangling-standard-range"),
        pytest.param([can_bus("BodyCAN")], {"bus_ref": "BodyCAN", "frame_ref": 0x800}, "extended_29bit", id="dangling-extended-range"),
        pytest.param([can_bus("BodyCAN", (0x100, "standard_11bit"))], {"frame_ref": 0x100}, "standard_11bit", id="no-bus-ref-uses-interface"),
        pytest.param([can_bus("BodyCAN")], {"frame_ref": 0x100, "id_format": "extended_29bit"}, "extended_29bit", id="already-migrated"),
    ],
)
def test_can_frame_refs_drop_bus_ref_and_gain_id_format(buses, ref, expected):
    documents = {f"communication/channels/can/{bus['name']}.flync.yaml": bus for bus in buses}
    documents[IFACE_URI] = {"bus_ref": "BodyCAN", "sender_frames": [dict(ref)], "receiver_frames": [dict(ref)]}

    interface = migrate(documents)[IFACE_URI]

    assert interface["sender_frames"] == interface["receiver_frames"] == [{"frame_ref": ref["frame_ref"], "id_format": expected}]
    CANInterface.model_validate({"name": "body_can_interface", **interface})


def test_can_frame_refs_of_inline_interface():
    controller = {
        "name": "c1",
        "can_interfaces": [{"name": "i", "bus_ref": "BodyCAN", "sender_frames": [{"bus_ref": "BodyCAN", "frame_ref": 0x510}]}],
    }
    documents = {BUS_URI: can_bus("BodyCAN", (0x510, "standard_11bit")), "ecus/ecu1/controllers/c1/controller.flync.yaml": controller}

    migrated = migrate(documents)["ecus/ecu1/controllers/c1/controller.flync.yaml"]

    assert migrated["can_interfaces"][0]["sender_frames"] == [{"frame_ref": 0x510, "id_format": "standard_11bit"}]


def test_lin_frame_refs_untouched():
    lin_uri = "ecus/ecu1/controllers/c1/lin_interfaces/body_lin_interface.flync.yaml"
    documents = {lin_uri: {"bus_ref": "BodyLIN", "sender_frames": [{"bus_ref": "BodyLIN", "frame_ref": 0x10}]}}

    assert migrate(documents) == documents
