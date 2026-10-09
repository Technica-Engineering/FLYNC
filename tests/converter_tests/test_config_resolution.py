"""Tests for converter configuration resolution in Converter.convert (FLYNC-1432).

Each side's configuration comes from what is passed for it: nothing (the
configuration stored in that side's workspace, or the defaults), the path of a
configuration file (used instead of the stored one), or a configuration object
(its set fields layered over the stored configuration).
"""

from unittest.mock import MagicMock, patch

import pytest

from flync_converter import Converter, ConverterConfig
from flync_converter.base.converter_config import converter_config_file
from flync_converter.converters.dbc import DbcConverterConfig
from flync_converter.converters.dbc.converter import DbcConverter


def _fake_registry(source_name="dbc", destination_name="yaml"):
    src_conv = MagicMock()
    src_conv.name = source_name
    src_conv.report_loggers = ()
    dst_conv = MagicMock()
    dst_conv.name = destination_name
    dst_conv.report_loggers = ()
    fake = {source_name: src_conv, destination_name: dst_conv}
    fake_reg = MagicMock()
    fake_reg.__getitem__.side_effect = fake.__getitem__
    return fake_reg, src_conv, dst_conv


def _convert(tmp_path, config_model=DbcConverterConfig, **kwargs):
    """Run a dbc -> yaml conversion with fake converters and return them."""
    fake_reg, src_conv, dst_conv = _fake_registry()
    with patch("flync_converter.registry", fake_reg), patch("flync_converter.get_config_model", return_value=config_model):
        Converter.convert(str(tmp_path / "src"), str(tmp_path / "dst"), source_type="dbc", destination_type="yaml", **kwargs)
    return src_conv, dst_conv


def _store(workspace, name, config):
    config.to_yaml_file(converter_config_file(workspace, name))


def _store_file(path, config):
    config.to_yaml_file(path)


@pytest.fixture
def explicit_file(tmp_path):
    path = tmp_path / "shared-dbc.yaml"
    _store_file(path, DbcConverterConfig(config_path="unused", baud_rate_default=125_000, fd_baud_rate_default=1_000_000))
    return path


# region source side


def test_source_defaults_without_stored_config(tmp_path):
    src_conv, _ = _convert(tmp_path)

    assert isinstance(src_conv.config, DbcConverterConfig)
    assert src_conv.config.config_path == str(tmp_path / "src")
    assert src_conv.config.baud_rate_default == 500_000


def test_source_uses_config_stored_in_source_workspace(tmp_path):
    _store(tmp_path / "src", "dbc", DbcConverterConfig(config_path="unused", baud_rate_default=250_000))

    src_conv, _ = _convert(tmp_path)

    assert src_conv.config.baud_rate_default == 250_000
    assert src_conv.config.config_path == str(tmp_path / "src")


def test_stored_config_is_keyed_by_converter_name(tmp_path):
    _store(tmp_path / "src", "other", DbcConverterConfig(config_path="unused", baud_rate_default=250_000))

    src_conv, _ = _convert(tmp_path)

    assert src_conv.config.baud_rate_default == 500_000


def test_source_explicit_fields_override_stored_config(tmp_path):
    _store(tmp_path / "src", "dbc", DbcConverterConfig(config_path="unused", baud_rate_default=250_000, fd_baud_rate_default=1_000_000))

    src_conv, _ = _convert(tmp_path, source_config=DbcConverterConfig(config_path=str(tmp_path / "src"), baud_rate_default=1_000_000))

    # Set explicitly: wins over the file.
    assert src_conv.config.baud_rate_default == 1_000_000
    # Not set explicitly: taken from the file, not from the field default.
    assert src_conv.config.fd_baud_rate_default == 1_000_000


def test_source_that_is_a_file_has_no_stored_config(tmp_path):
    source_file = tmp_path / "bus.dbc"
    source_file.write_text("", encoding="utf-8")
    fake_reg, src_conv, _ = _fake_registry()

    with patch("flync_converter.registry", fake_reg), patch("flync_converter.get_config_model", return_value=DbcConverterConfig):
        Converter.convert(str(source_file), str(tmp_path / "dst"), source_type="dbc", destination_type="yaml")

    assert src_conv.config.config_path == str(source_file)
    assert src_conv.config.baud_rate_default == 500_000


def test_source_config_is_not_written(tmp_path):
    _convert(tmp_path)
    assert not converter_config_file(tmp_path / "src", "dbc").exists()


# endregion
# region configuration files


def test_source_file_replaces_stored_config(tmp_path, explicit_file):
    _store(tmp_path / "src", "dbc", DbcConverterConfig(config_path="unused", baud_rate_default=250_000))

    src_conv, _ = _convert(tmp_path, source_config=explicit_file)

    assert isinstance(src_conv.config, DbcConverterConfig)
    assert src_conv.config.baud_rate_default == 125_000
    assert src_conv.config.config_path == str(tmp_path / "src")


def test_source_file_given_as_string(tmp_path, explicit_file):
    src_conv, _ = _convert(tmp_path, source_config=str(explicit_file))

    assert src_conv.config.baud_rate_default == 125_000


def test_destination_file_is_used_and_persisted(tmp_path):
    shared = tmp_path / "shared-yaml.yaml"
    _store_file(shared, ConverterConfig(config_path="unused", report_min_log_level="DEBUG"))

    _, dst_conv = _convert(tmp_path, config_model=ConverterConfig, destination_config=shared)

    assert dst_conv.config.report_min_log_level == "DEBUG"
    assert dst_conv.config.config_path == str(tmp_path / "dst")
    stored = ConverterConfig.from_workspace(tmp_path / "dst", "yaml")
    assert stored.report_min_log_level == "DEBUG"


def test_file_setting_config_path_is_rejected(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("config_path: /elsewhere\n", encoding="utf-8")

    with pytest.raises(ValueError, match="config_path"):
        _convert(tmp_path, source_config=bad)


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        _convert(tmp_path, source_config=tmp_path / "nope.yaml")


# endregion
# region real DBC converter


_BUS_DBC = """\
VERSION "1.0"

NS_ :

BS_:

BU_: ECU1

BO_ 256 SpeedMsg: 8 ECU1
 SG_ Speed : 0|16@1+ (0.1,0) [0|6553.5] "km/h" Vector__XXX
"""


def test_stored_source_config_reaches_the_dbc_decoder(tmp_path):
    source = tmp_path / "src"
    source.mkdir()
    (source / "Bus.dbc").write_text(_BUS_DBC, encoding="utf-8")
    _store(source, "dbc", DbcConverterConfig(config_path="unused", baud_rate_default=250_000))

    dst_conv = MagicMock()
    dst_conv.name = "yaml"
    dst_conv.report_loggers = ()
    fake = {"dbc": DbcConverter(), "yaml": dst_conv}
    fake_reg = MagicMock()
    fake_reg.__getitem__.side_effect = fake.__getitem__

    with patch("flync_converter.registry", fake_reg), patch("flync_converter.get_config_model", return_value=DbcConverterConfig):
        Converter.convert(str(source), str(tmp_path / "dst"), source_type="dbc", destination_type="yaml")

    model = dst_conv.encode.call_args.args[0]
    assert [bus.baud_rate for bus in model.communication.channels.can_buses] == [250_000]


# endregion
