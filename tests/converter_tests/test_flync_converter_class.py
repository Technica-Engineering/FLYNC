"""Tests for flync_converter.converters.flync_converter — FLYNCConverter class."""

from unittest.mock import MagicMock, patch

import pytest

from flync_converter.base import ConverterConfig
from flync_converter.converters.flync_converter import FLYNCConverter


class TestFLYNCConverterEncode:
    def test_raises_valueerror_when_config_is_none(self):
        """Test that encode raises ValueError when config is None."""
        converter = FLYNCConverter()
        converter.config = None
        fake_model = MagicMock()

        with pytest.raises(ValueError, match="config must be set before encoding"):
            converter.encode(fake_model)

    def test_calls_dump_flync_workspace_with_config_path(self):
        """Test that encode calls dump_flync_workspace with correct path."""
        converter = FLYNCConverter()
        converter.config = ConverterConfig(config_path="/tmp/test_workspace")
        fake_model = MagicMock()

        with patch("flync_converter.converters.flync_converter.dump_flync_workspace") as mock_dump:
            converter.encode(fake_model)
            mock_dump.assert_called_once_with(fake_model, "/tmp/test_workspace", "converted workspace")

    def test_encode_with_valid_config(self):
        """Test successful encode operation."""
        converter = FLYNCConverter()
        converter.config = ConverterConfig(config_path="/output/workspace")
        fake_model = MagicMock()

        with patch("flync_converter.converters.flync_converter.dump_flync_workspace"):
            # Should not raise
            converter.encode(fake_model)

    def test_encode_passes_workspace_name(self):
        """Test that encode passes 'converted workspace' as the workspace name."""
        converter = FLYNCConverter()
        converter.config = ConverterConfig(config_path="/tmp/path")
        fake_model = MagicMock()

        with patch("flync_converter.converters.flync_converter.dump_flync_workspace") as mock_dump:
            converter.encode(fake_model)
            call_args = mock_dump.call_args
            assert call_args[0][2] == "converted workspace"


class TestFLYNCConverterDecode:
    def test_raises_valueerror_when_config_is_none(self):
        """Test that decode raises ValueError when config is None."""
        converter = FLYNCConverter()
        converter.config = None

        with pytest.raises(ValueError, match="config must be set before decoding"):
            converter.decode()

    def test_calls_load_workspace_with_config_path(self):
        """Test that decode calls FLYNCWorkspace.load_workspace."""
        converter = FLYNCConverter()
        converter.config = ConverterConfig(config_path="/tmp/test_workspace")

        mock_workspace = MagicMock()
        mock_workspace.flync_model = MagicMock()

        with patch("flync_converter.converters.flync_converter.FLYNCWorkspace.load_workspace") as mock_load:
            mock_load.return_value = mock_workspace
            result = converter.decode()
            mock_load.assert_called_once_with("converted_workspace", "/tmp/test_workspace")
            assert result == mock_workspace.flync_model

    def test_decode_returns_flync_model(self):
        """Test that decode returns the flync_model from loaded workspace."""
        converter = FLYNCConverter()
        converter.config = ConverterConfig(config_path="/input/workspace")

        expected_model = MagicMock()
        mock_workspace = MagicMock()
        mock_workspace.flync_model = expected_model

        with patch("flync_converter.converters.flync_converter.FLYNCWorkspace.load_workspace") as mock_load:
            mock_load.return_value = mock_workspace
            result = converter.decode()
            assert result is expected_model

    def test_decode_with_valid_config(self):
        """Test successful decode operation."""
        converter = FLYNCConverter()
        converter.config = ConverterConfig(config_path="/workspace/path")

        mock_workspace = MagicMock()
        mock_workspace.flync_model = MagicMock(name="test_model")

        with patch("flync_converter.converters.flync_converter.FLYNCWorkspace.load_workspace") as mock_load:
            mock_load.return_value = mock_workspace
            result = converter.decode()
            assert result is not None


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

    def test_converter_has_config_attribute(self):
        """Test that converter has config attribute."""
        converter = FLYNCConverter()
        assert hasattr(converter, "config")
