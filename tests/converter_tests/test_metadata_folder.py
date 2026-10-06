"""Tests that folder loaders ignore the ``.flync`` metadata folder (stored configs, reports)."""

import json

import pytest

from flync_converter.base import ConverterConfig
from flync_converter.base.converter_config import converter_config_file
from flync_converter.converters.helpers import content_files
from flync_converter.converters.json_converter import JsonConverter, load_json_files
from flync_converter.converters.yaml_converter import YamlConverter, load_yaml_files


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_content_files_skips_metadata_folder(tmp_path):
    _write(tmp_path / "model.yaml", "a: 1\n")
    _write(tmp_path / "nested" / "part.yaml", "b: 2\n")
    _write(tmp_path / ".flync" / "converters" / "yaml.yaml", "version: {}\n")
    _write(tmp_path / "nested" / ".flync" / "reports" / "yaml" / "config.yaml", "config_path: x\n")

    found = sorted(path.relative_to(tmp_path).as_posix() for path in content_files(tmp_path, "*.yaml"))

    assert found == ["model.yaml", "nested/part.yaml"]


def test_content_files_accepts_root_inside_a_metadata_folder(tmp_path):
    """Only folders below the root are checked, so a root under ``.flync`` still yields its files."""
    root = tmp_path / ".flync" / "data"
    _write(root / "model.yaml", "a: 1\n")

    assert [path.name for path in content_files(root, "*.yaml")] == ["model.yaml"]


def test_load_yaml_files_ignores_metadata_folder(tmp_path):
    _write(tmp_path / "model.yaml", "a: 1\n")
    ConverterConfig(config_path="unused").to_yaml_file(converter_config_file(tmp_path, "yaml"))

    assert load_yaml_files(tmp_path) == {"a": 1}


def test_load_json_files_ignores_metadata_folder(tmp_path):
    _write(tmp_path / "model.json", json.dumps({"a": 1}))
    _write(tmp_path / ".flync" / "reports" / "json" / "data.json", json.dumps({"b": 2}))

    assert load_json_files(tmp_path) == {"a": 1}


@pytest.mark.parametrize("converter_cls", [YamlConverter, JsonConverter])
def test_output_with_stored_config_reads_back(tmp_path, flync_object, converter_cls):
    """A converted folder decodes the same with the stored config and a report next to it."""
    converter = converter_cls(ConverterConfig(config_path=str(tmp_path)))
    converter.encode(flync_object)
    without_metadata = converter.decode()

    ConverterConfig(config_path=str(tmp_path), report_min_log_level="DEBUG").to_yaml_file(converter_config_file(tmp_path, converter.name))
    _write(tmp_path / ".flync" / "reports" / converter.name / "config.yaml", "config_path: x\n")
    _write(tmp_path / ".flync" / "reports" / converter.name / "data.json", json.dumps({"version": "x"}))

    assert converter.decode().model_dump() == without_metadata.model_dump()
