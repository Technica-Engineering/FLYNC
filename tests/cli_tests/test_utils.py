"""Tests for flync_cli utility modules."""

import re

from pydantic import BaseModel, ValidationError

from flync_cli.utils.error_table import sanitize_error_message
from flync_cli.utils.mapping import get_mapping


class TestGetMapping:
    def test_returns_dict(self):
        result = get_mapping()
        assert isinstance(result, dict)

    def test_contains_expected_keys(self):
        result = get_mapping()
        assert "ecu_port_to_switch_port" in result
        assert "switch_port_to_controller_interface" in result

    def test_values_are_tuples_of_two(self):
        for key, val in get_mapping().items():
            assert isinstance(val, tuple)
            assert len(val) == 2


class TestSanitizeErrorMessage:
    def test_strips_ansi_sequences(self):
        raw = "\x1b[31mError\x1b[0m"
        assert sanitize_error_message(raw) == "Error"

    def test_plain_string_unchanged(self):
        assert sanitize_error_message("plain error") == "plain error"

    def test_empty_string(self):
        assert sanitize_error_message("") == ""
