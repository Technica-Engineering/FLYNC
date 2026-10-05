"""Tests for flync_converter.base.converter_config — validation and on-disk persistence."""

import logging

import pytest
import yaml
from pydantic import ValidationError

from flync_converter.base.converter_config import ConverterConfig, converter_config_file, parse_log_level
from flync_converter.converters.dbc.dbc_config import DbcConverterConfig


@pytest.mark.parametrize(
    ("value", "expected"),
    [("DEBUG", logging.DEBUG), ("warning", logging.WARNING), (" error ", logging.ERROR), ("15", 15), (20, logging.INFO)],
)
def test_parse_log_level(value, expected):
    assert parse_log_level(value) == expected


@pytest.mark.parametrize("value", ["verbose", "", True])
def test_parse_log_level_rejects_unknown(value):
    with pytest.raises(ValueError):
        parse_log_level(value)


@pytest.mark.parametrize(("value", "stored"), [("debug", "DEBUG"), (10, "DEBUG"), ("40", "ERROR"), (15, "15")])
def test_report_min_log_level_is_stored_by_name(value, stored):
    config = ConverterConfig(config_path="out", report_min_log_level=value)
    assert config.report_min_log_level == stored
    assert config.report_level == parse_log_level(stored)


def test_report_min_log_level_rejects_unknown_level():
    with pytest.raises(ValidationError):
        ConverterConfig(config_path="out", report_min_log_level="verbose")


def test_report_enabled_rejects_unknown_value():
    with pytest.raises(ValidationError):
        ConverterConfig(config_path="out", report_enabled="enabled")


def test_defaults():
    config = ConverterConfig(config_path="out")
    assert config.report_enabled is True
    assert config.report_min_log_level == "INFO"
    assert config.persist_config is True


def test_config_is_frozen():
    config = ConverterConfig(config_path="out")
    with pytest.raises(ValidationError):
        config.report_enabled = False  # type: ignore[misc]


def test_unknown_field_is_rejected():
    with pytest.raises(ValidationError):
        ConverterConfig(config_path="out", report_enable=False)


def test_converter_config_file(tmp_path):
    assert converter_config_file(tmp_path, "flync") == tmp_path / ".flync" / "converters" / "flync.yaml"


def test_from_workspace_without_file_returns_defaults(tmp_path):
    config = ConverterConfig.from_workspace(tmp_path, "flync")
    assert config == ConverterConfig(config_path=str(tmp_path), version=config.version)


def test_round_trip(tmp_path):
    original = ConverterConfig(config_path="ignored", report_enabled=False, report_min_log_level="DEBUG")
    original.to_yaml_file(converter_config_file(tmp_path, "flync"))

    loaded = ConverterConfig.from_workspace(tmp_path, "flync")

    assert loaded.config_path == str(tmp_path)
    assert loaded.report_enabled is False
    assert loaded.report_min_log_level == "DEBUG"


def test_file_contains_only_non_defaults_and_version(tmp_path):
    path = converter_config_file(tmp_path, "flync")
    ConverterConfig(config_path=str(tmp_path), report_min_log_level="DEBUG").to_yaml_file(path)

    data = yaml.safe_load(path.read_text(encoding="utf-8"))

    assert set(data) == {"report_min_log_level", "version"}
    assert data["report_min_log_level"] == "DEBUG"


def test_subclass_fields_round_trip(tmp_path):
    DbcConverterConfig(config_path="ignored", baud_rate_default=250_000).to_yaml_file(converter_config_file(tmp_path, "dbc"))

    loaded = DbcConverterConfig.from_workspace(tmp_path, "dbc")

    assert loaded.baud_rate_default == 250_000


def test_file_setting_config_path_is_rejected(tmp_path):
    path = converter_config_file(tmp_path, "flync")
    path.parent.mkdir(parents=True)
    path.write_text("config_path: /elsewhere\n", encoding="utf-8")

    with pytest.raises(ValueError, match="config_path"):
        ConverterConfig.from_workspace(tmp_path, "flync")


def test_file_with_unknown_key_is_rejected(tmp_path):
    path = converter_config_file(tmp_path, "flync")
    path.parent.mkdir(parents=True)
    path.write_text("report_enable: false\n", encoding="utf-8")

    with pytest.raises(ValidationError):
        ConverterConfig.from_workspace(tmp_path, "flync")


def test_file_that_is_not_a_mapping_is_rejected(tmp_path):
    path = converter_config_file(tmp_path, "flync")
    path.parent.mkdir(parents=True)
    path.write_text("- a\n- b\n", encoding="utf-8")

    with pytest.raises(ValueError, match="mapping"):
        ConverterConfig.from_workspace(tmp_path, "flync")


def test_create_from_config_overrides_fields():
    base = ConverterConfig(config_path="out", report_min_log_level="DEBUG")
    updated = ConverterConfig.create_from_config(base, report_enabled=False)

    assert updated.report_enabled is False
    assert updated.report_min_log_level == "DEBUG"
