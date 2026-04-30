"""Tests the fatal-error rejection of pre-0.11 single-file Controllers."""

import pytest
from pydantic import ValidationError

from flync.core.version_migrators.legacy_controller_check import (
    detect_legacy_controller_version,
    reject_legacy_controller,
)
from flync.model.flync_4_ecu.controller import Controller


def _legacy_payload(version: str = "0.10.0") -> dict:
    return {
        "name": "legacy_ctrl",
        "meta": {
            "type": "embedded",
            "author": "Dev",
            "compatible_flync_version": {
                "version_schema": "semver",
                "version": version,
            },
            "target_system": "every",
        },
        "interfaces": [
            {
                "name": "legacy_iface",
                "mac_address": "aa:bb:cc:dd:ee:ff",
                "virtual_interfaces": [],
            }
        ],
    }


def test_detect_returns_version_for_legacy_payload():
    assert detect_legacy_controller_version(_legacy_payload("0.9.0")) == "0.9.0"


def test_detect_returns_none_for_new_payload(embedded_metadata_entry):
    new_payload = {
        "name": "new_ctrl",
        "controller_metadata": embedded_metadata_entry,
        "ethernet_interfaces": [],
    }
    assert detect_legacy_controller_version(new_payload) is None


@pytest.mark.parametrize(
    "data",
    [None, "string", 42, [], {"meta": "not-a-dict"}, {"meta": {}}],
)
def test_detect_returns_none_for_unrelated_inputs(data):
    assert detect_legacy_controller_version(data) is None


def test_reject_legacy_controller_raises_fatal_error():
    with pytest.raises(Exception) as exc_info:
        reject_legacy_controller(_legacy_payload("0.10.0"))
    # err_fatal returns a PydanticCustomError whose type is "fatal"
    assert exc_info.value.type == "fatal"
    assert "0.10.0" in str(exc_info.value)


def test_reject_legacy_controller_is_noop_for_new_payload(
    embedded_metadata_entry,
):
    new_payload = {
        "name": "new_ctrl",
        "controller_metadata": embedded_metadata_entry,
        "ethernet_interfaces": [],
    }
    # must not raise
    reject_legacy_controller(new_payload)


def test_controller_model_validate_rejects_legacy_payload():
    with pytest.raises(ValidationError) as exc_info:
        Controller.model_validate(_legacy_payload("0.9.0"))
    errors = exc_info.value.errors()
    fatal_errors = [e for e in errors if e.get("type") == "fatal"]
    assert fatal_errors, f"expected a fatal error, got {errors}"
    msg = fatal_errors[0]["msg"]
    assert "0.9.0" in msg
    assert "0.11.0" in msg
    assert "0.10" in msg  # downgrade hint


def test_controller_model_validate_accepts_new_payload(
    embedded_metadata_entry, virtual_controller_interface
):
    Controller.model_validate(
        {
            "name": "new_ctrl",
            "controller_metadata": embedded_metadata_entry,
            "ethernet_interfaces": [
                {
                    "interface_config": {
                        "name": "iface",
                        "mac_address": "aa:bb:cc:dd:ee:ff",
                        "virtual_interfaces": [virtual_controller_interface],
                        "ptp_config": None,
                    }
                }
            ],
        }
    )
