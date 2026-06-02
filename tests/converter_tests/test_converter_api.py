"""Tests for the top-level flync_converter API (Converter class and convert function)."""

from unittest.mock import MagicMock, patch

import pytest

from flync_converter import Converter, convert
from flync_converter.base import ConverterConfig


def _make_fake_registry(src_name="json", dst_name="yaml"):
    src_conv = MagicMock()
    src_conv.name = src_name
    decoded = MagicMock(name="decoded_model")
    src_conv.decode.return_value = decoded

    dst_conv = MagicMock()
    dst_conv.name = dst_name

    fake = {src_name: src_conv, dst_name: dst_conv}
    fake_reg = MagicMock()
    fake_reg.__getitem__.side_effect = fake.__getitem__
    fake_reg.pick.return_value = src_conv
    return fake_reg, src_conv, dst_conv, decoded


class TestConverterConvert:
    def test_same_source_and_dest_type_is_no_op(self):
        with patch("flync_converter.registry") as mock_reg:
            Converter.convert("s", "d", source_type="flync", destination_type="flync")
        mock_reg.__getitem__.assert_not_called()

    def test_normal_flow_calls_decode_then_encode(self):
        fake_reg, src_conv, dst_conv, decoded = _make_fake_registry()
        with patch("flync_converter.registry", fake_reg):
            Converter.convert("src/path", "dst/path", source_type="json", destination_type="yaml")
        src_conv.decode.assert_called_once()
        dst_conv.encode.assert_called_once_with(decoded)

    def test_auto_detects_source_type_via_pick(self):
        fake_reg, src_conv, dst_conv, decoded = _make_fake_registry()
        with patch("flync_converter.registry", fake_reg):
            Converter.convert("src/path", "dst/path", destination_type="yaml")
        fake_reg.pick.assert_called_once_with("src/path")
        src_conv.decode.assert_called_once()

    def test_source_config_set_on_converter(self):
        fake_reg, src_conv, dst_conv, _ = _make_fake_registry()
        src_cfg = ConverterConfig(config_path="/custom/src")
        with patch("flync_converter.registry", fake_reg):
            Converter.convert("src/path", "dst/path", source_type="json", destination_type="yaml", source_config=src_cfg)
        assert src_conv.config is src_cfg

    def test_destination_config_set_on_converter(self):
        fake_reg, src_conv, dst_conv, _ = _make_fake_registry()
        dst_cfg = ConverterConfig(config_path="/custom/dst")
        with patch("flync_converter.registry", fake_reg):
            Converter.convert("src/path", "dst/path", source_type="json", destination_type="yaml", destination_config=dst_cfg)
        assert dst_conv.config is dst_cfg

    def test_default_config_uses_path_string(self):
        fake_reg, src_conv, dst_conv, _ = _make_fake_registry()
        with patch("flync_converter.registry", fake_reg):
            Converter.convert("src/path", "dst/path", source_type="json", destination_type="yaml")
        assert src_conv.config.config_path == "src/path"
        assert dst_conv.config.config_path == "dst/path"


class TestConvertFunction:
    def test_delegates_to_converter(self):
        with patch("flync_converter.Converter.convert") as mock_convert:
            convert("src", "dst", destination_type="yaml", source_type="json")
        mock_convert.assert_called_once_with(
            "src",
            "dst",
            source_type="json",
            destination_type="yaml",
            source_config=None,
            destination_config=None,
        )

    def test_source_type_defaults_to_flync(self):
        with patch("flync_converter.Converter.convert") as mock_convert:
            convert("src", "dst", destination_type="yaml")
        call_kwargs = mock_convert.call_args[1]
        assert call_kwargs["source_type"] is "flync"
