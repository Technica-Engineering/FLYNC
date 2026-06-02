"""Tests for user-friendly MAC address validation error messages."""

import pytest
from pydantic import ValidationError

from flync.core.datatypes.macaddress import FLYNCMacAddress, MACAddressEntry
from flync.core.validators.address_validators import before_validate_mac_address
from flync.model.flync_4_ecu.controller import ComputeNodes, ControllerInterface
from flync.model.flync_4_ecu.mac_multicast_endpoint import MACMulticastEndpoint

# --- before_validate_mac_address unit tests ---


def test_before_validator_passes_valid_colon_mac():
    assert before_validate_mac_address("aa:bb:cc:dd:ee:ff") == "aa:bb:cc:dd:ee:ff"


def test_before_validator_passes_valid_dash_mac():
    assert before_validate_mac_address("aa-bb-cc-dd-ee-ff") == "aa-bb-cc-dd-ee-ff"


def test_before_validator_rejects_integer_with_friendly_message():
    with pytest.raises(ValueError, match="MAC address must be a string"):
        before_validate_mac_address(1122334455)


def test_before_validator_rejects_no_separator_string_with_friendly_message():
    with pytest.raises(ValueError, match="missing separators"):
        before_validate_mac_address("aabbccddeeff")


def test_before_validator_no_separator_error_includes_formatted_hint():
    with pytest.raises(ValueError, match="aa:bb:cc:dd:ee:ff"):
        before_validate_mac_address("aabbccddeeff")


def test_before_validator_passes_non_mac_string_to_pydantic():
    # Strings that are not 12-hex-char patterns should pass through
    # (pydantic_extra_types handles the final rejection)
    result = before_validate_mac_address("not-a-mac")
    assert result == "not-a-mac"


# --- Integration tests: FLYNCMacAddress in pydantic models ---


def test_mac_address_entry_rejects_integer_with_validation_error():
    with pytest.raises(ValidationError, match="MAC address must be a string"):
        MACAddressEntry(address=1122334455)


def test_mac_address_entry_rejects_no_separator_string_with_validation_error():
    with pytest.raises(ValidationError, match="missing separators"):
        MACAddressEntry(address="aabbccddeeff")


def test_mac_address_entry_accepts_valid_mac():
    entry = MACAddressEntry(address="aa:bb:cc:dd:ee:ff")
    assert entry.address == "aa:bb:cc:dd:ee:ff"


def test_controller_interface_mac_rejects_integer():
    with pytest.raises(ValidationError, match="MAC address must be a string"):
        ComputeNodes(name="test", mac_address=1122334455)


def test_controller_interface_mac_rejects_no_separator():
    with pytest.raises(ValidationError, match="missing separators"):
        ComputeNodes(name="test", mac_address="aabbccddeeff")


def test_mac_multicast_endpoint_rejects_integer_mac():
    with pytest.raises(ValidationError, match="MAC address must be a string"):
        MACMulticastEndpoint(
            name="ep",
            mac_address=1122334455,
            protocol="avtp",
        )


def test_mac_multicast_endpoint_rejects_no_separator_mac():
    with pytest.raises(ValidationError, match="missing separators"):
        MACMulticastEndpoint(
            name="ep",
            mac_address="91e0f0000001",
            protocol="avtp",
        )


def test_mac_multicast_endpoint_tx_rejects_no_separator():
    with pytest.raises(ValidationError, match="missing separators"):
        MACMulticastEndpoint(
            name="ep",
            mac_address="91:e0:f0:00:00:01",
            protocol="avtp",
            multicast_tx=["91e0f0000001"],
        )
