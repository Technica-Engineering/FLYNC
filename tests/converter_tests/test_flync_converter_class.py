"""Tests for flync_converter.converters.flync_converter — FLYNCConverter class."""

import logging
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from flync.model import FLYNCModel
from flync_converter.base import ConverterConfig
from flync_converter.converters.flync_converter import FLYNCConverter

MODULE = "flync_converter.converters.flync_converter"

WARNING = {"type": "warning", "loc": ("ecus", 0, "name"), "msg": "name is odd", "ctx": {"error_id": "FLYNC-ECU-WARN-VAL-001"}, "input": None}
MAJOR = {"type": "major", "loc": (), "msg": "broken reference", "ctx": {"error_id": "FLYNC-ECU-MAJ-REF-002"}, "input": None}

_DEFAULT_MODEL = object()


def _workspace(diags=None, model=_DEFAULT_MODEL):
    """Return a fake workspace with the given diagnostics and model (a FLYNCModel stand-in by default)."""
    workspace = MagicMock()
    workspace.documents_diags = diags or {}
    workspace.flync_model = MagicMock(spec=FLYNCModel) if model is _DEFAULT_MODEL else model
    return workspace


class TestFLYNCConverterEncode:
    def test_raises_valueerror_when_config_is_none(self):
        """Test that encode raises ValueError when config is None."""
        converter = FLYNCConverter()
        converter.config = None
        fake_model = MagicMock()

        with pytest.raises(ValueError, match="config must be set before encoding"):
            converter.encode(fake_model)

    def test_writes_workspace_from_model_at_config_path(self):
        """Test that encode builds the workspace from the model and writes it."""
        converter = FLYNCConverter()
        converter.config = ConverterConfig(config_path="/tmp/test_workspace")
        fake_model = MagicMock()

        with patch(f"{MODULE}.FLYNCWorkspace.load_model") as mock_load_model:
            converter.encode(fake_model)
            mock_load_model.assert_called_once_with(fake_model, "converted workspace", "/tmp/test_workspace")
            mock_load_model.return_value.generate_configs.assert_called_once_with()

    def test_encode_logs_workspace_diagnostics(self, caplog):
        """Test that encode logs the diagnostics of the written workspace."""
        converter = FLYNCConverter()
        converter.config = ConverterConfig(config_path="/tmp/test_workspace")

        with patch(f"{MODULE}.FLYNCWorkspace.load_model") as mock_load_model, caplog.at_level(logging.INFO, logger=MODULE):
            mock_load_model.return_value = _workspace(diags={"doc.flync.yaml": [WARNING]})
            converter.encode(MagicMock())

        assert "FLYNC-ECU-WARN-VAL-001" in caplog.text


class TestFLYNCConverterDecode:
    def test_raises_valueerror_when_config_is_none(self):
        """Test that decode raises ValueError when config is None."""
        converter = FLYNCConverter()
        converter.config = None

        with pytest.raises(ValueError, match="config must be set before decoding"):
            converter.decode()

    def test_loads_workspace_from_config_path(self):
        """Test that decode loads the workspace at the configured path and returns its model."""
        converter = FLYNCConverter()
        converter.config = ConverterConfig(config_path="/tmp/test_workspace")
        mock_workspace = _workspace()

        with patch(f"{MODULE}.FLYNCWorkspace.safe_load_workspace", return_value=mock_workspace) as mock_load:
            result = converter.decode()

        mock_load.assert_called_once_with("converted_workspace", "/tmp/test_workspace")
        assert result is mock_workspace.flync_model

    def test_decode_logs_workspace_diagnostics(self, caplog):
        """Test that warnings are logged at WARNING and errors at ERROR, with a summary line."""
        converter = FLYNCConverter()
        converter.config = ConverterConfig(config_path="/workspace/path")
        mock_workspace = _workspace(diags={"a.flync.yaml": [WARNING], "b.flync.yaml": [MAJOR]})

        with patch(f"{MODULE}.FLYNCWorkspace.safe_load_workspace", return_value=mock_workspace), caplog.at_level(logging.INFO, logger=MODULE):
            converter.decode()

        levels = {record.getMessage(): record.levelno for record in caplog.records}
        assert levels["a.flync.yaml: FLYNC-ECU-WARN-VAL-001 at ecus.0.name: name is odd"] == logging.WARNING
        assert levels["b.flync.yaml: FLYNC-ECU-MAJ-REF-002 at <root>: broken reference"] == logging.ERROR
        assert levels["Workspace diagnostics: 2 finding(s)"] == logging.INFO

    def test_decode_logs_diagnostics_before_raising_when_no_model(self, caplog):
        """Test that diagnostics are logged even when the workspace produces no model."""
        converter = FLYNCConverter()
        converter.config = ConverterConfig(config_path="/workspace/path")
        mock_workspace = _workspace(diags={"b.flync.yaml": [MAJOR]}, model=None)
        mock_workspace.load_errors = []

        with (
            patch(f"{MODULE}.FLYNCWorkspace.safe_load_workspace", return_value=mock_workspace),
            caplog.at_level(logging.INFO, logger=MODULE),
            pytest.raises(ValidationError),
        ):
            converter.decode()

        assert "FLYNC-ECU-MAJ-REF-002" in caplog.text

    def test_pydantic_errors_without_id_use_their_type(self, caplog):
        """Test that a plain Pydantic error is identified by its type."""
        converter = FLYNCConverter()
        converter.config = ConverterConfig(config_path="/workspace/path")
        missing = {"type": "missing", "loc": ("ecus", 0, "name"), "msg": "Field required", "input": None}

        with (
            patch(f"{MODULE}.FLYNCWorkspace.safe_load_workspace", return_value=_workspace(diags={"c.flync.yaml": [missing]})),
            caplog.at_level(logging.INFO, logger=MODULE),
        ):
            converter.decode()

        assert "c.flync.yaml: missing at ecus.0.name: Field required" in caplog.text


class TestFLYNCConverterBasics:
    def test_converter_name_is_flync(self):
        """Test that converter name is 'flync'."""
        assert FLYNCConverter.name == "flync"

    def test_can_decode_returns_true(self):
        """Test that can_decode returns True."""
        converter = FLYNCConverter()
        assert converter.can_decode() is True

    def test_converter_inherits_from_base_converter(self):
        """Test that FLYNCConverter is a BaseConverter."""
        from flync_converter.base.base_converter import BaseConverter

        assert issubclass(FLYNCConverter, BaseConverter)

    def test_converter_reports_sdk_loggers(self):
        """Test that the FLYNC SDK loggers are part of the conversion log."""
        assert FLYNCConverter.report_loggers == ("flync_converter.converters.flync_converter", "flync.sdk")

    def test_converter_has_config_attribute(self):
        """Test that converter has config attribute."""
        converter = FLYNCConverter()
        assert hasattr(converter, "config")
