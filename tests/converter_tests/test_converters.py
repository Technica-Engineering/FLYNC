import json
from typing import Type

import pytest
import yaml

from flync.core.base_models.base_model import FLYNCBaseModel
from flync.model import FLYNCModel  # type: ignore[import-untyped]
from flync_converter import BaseConverter, ConverterConfig, FLYNCConverter, JsonConverter, YamlConverter

converters = [
    pytest.param(
        "json_converter",
        JsonConverter,
    ),
    pytest.param(
        "yaml_converter",
        YamlConverter,
    ),
    pytest.param(
        "flync_converter",
        FLYNCConverter,
    ),
]


def eq_patch(self, other):
    if not isinstance(other, type(self)):
        return False
    return self.model_dump() == other.model_dump()

def test_json_encode(flync_object, tmp_path):
    converter = JsonConverter(ConverterConfig(config_path=str(tmp_path)))
    converter.encode(flync_object)

    json_files = list(tmp_path.rglob("*.json"))
    assert json_files, "encode produced no JSON files"
    for f in json_files:
        assert f.stat().st_size > 0, f"{f.name} is empty"
        data = json.loads(f.read_text(encoding="utf-8"))
        assert isinstance(data, dict), f"{f.name} is not a JSON object"


def test_json_decode(flync_object, tmp_path):
    converter = JsonConverter(ConverterConfig(config_path=str(tmp_path)))
    converter.encode(flync_object)

    result = converter.decode()

    assert result is not None, "decode returned None"
    assert isinstance(result, FLYNCModel)
    assert len(result.ecus) > 0, "decoded model has no ECUs"


def test_yaml_encode(flync_object, tmp_path):
    converter = YamlConverter(ConverterConfig(config_path=str(tmp_path)))
    converter.encode(flync_object)

    yaml_files = list(tmp_path.rglob("*.yaml"))
    assert yaml_files, "encode produced no YAML files"
    for f in yaml_files:
        assert f.stat().st_size > 0, f"{f.name} is empty"
        data = yaml.safe_load(f.read_text(encoding="utf-8"))
        assert isinstance(data, dict), f"{f.name} is not a YAML mapping"


def test_yaml_decode(flync_object, tmp_path):
    converter = YamlConverter(ConverterConfig(config_path=str(tmp_path)))
    converter.encode(flync_object)

    result = converter.decode()

    assert result is not None, "decode returned None"
    assert isinstance(result, FLYNCModel)
    assert len(result.ecus) > 0, "decoded model has no ECUs"
