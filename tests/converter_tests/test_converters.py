import json
import os
from typing import Type

import pytest
import yaml

from flync.core.base_models.base_model import FLYNCBaseModel
from flync.model import FLYNCModel  # type: ignore[import-untyped]
from flync_converter import BaseConverter, ConverterConfig, FLYNCConverter, JsonConverter, YamlConverter

from .test_helpers import GENERATED_TEST_OUTPUT_DIR

_MULTICAST_REASON = (
    "FLYNCModel.validate_multicast_paths mutates switch VLAN multicast lists "
    "during validation; multicast_groups (the source data) is excluded from "
    "model_dump (Field(exclude=True)) and only partially restored during "
    "model_validate because SOME/IP deployment validators need ECU registry "
    "entries that don't exist yet when general config is validated. Result: "
    "decoded multicast data differs from the original. Requires FLYNC SDK fix."
)

converters = [
    pytest.param(
        "json_converter",
        JsonConverter,
        marks=pytest.mark.xfail(reason=_MULTICAST_REASON, strict=False),
    ),
    pytest.param(
        "yaml_converter",
        YamlConverter,
        marks=pytest.mark.xfail(reason=_MULTICAST_REASON, strict=False),
    ),
    pytest.param(
        "flync_converter",
        FLYNCConverter,
        marks=pytest.mark.xfail(
            reason=(
                "dump_flync_workspace serializes IPv4Address routing entries as "
                "raw integers; FLYNCWorkspace.load_workspace then fails with a "
                "'default_gateway' ValidationError which partially registers "
                "SwitchPorts, causing duplicate-name errors on subsequent loads. "
                "Requires FLYNC SDK fix."
            ),
            strict=False,
        ),
    ),
]


def eq_patch(self, other):
    if not isinstance(other, type(self)):
        return False
    return self.model_dump() == other.model_dump()


@pytest.mark.skip(reason="Investigating shelve caching deadlock on pipeline")
@pytest.mark.parametrize("converter_name, converter_class", converters)
def test_roudtrip(
    monkeypatch,
    flync_object,
    converter_name,
    converter_class: Type[BaseConverter],
):
    # mock eq to ignore the recursion until it's fixed in core
    monkeypatch.setattr(FLYNCBaseModel, "__eq__", eq_patch)
    output_path = os.path.join(GENERATED_TEST_OUTPUT_DIR, converter_name)
    converter = converter_class(ConverterConfig(config_path=output_path))
    converter.encode(flync_object)
    roundtrip_obj = converter.decode()
    assert roundtrip_obj == flync_object


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
