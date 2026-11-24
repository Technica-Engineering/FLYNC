"""Tests for the dynamically generated converter CLI config arguments (preview support)."""

import enum

import click
import pytest
from pydantic import BaseModel, Field

from flync_converter.cli.dynamic import DynamicConverterCommand, serialize_option_value
from flync_converter.cli.types import _annotation_to_click_type, _json_kind, _JsonParamType, field_default, format_default, parse_field_input


class _Mode(enum.Enum):
    FAST = "fast"
    SAFE = "safe"


def test_serialize_option_value_enum_uses_member_name():
    assert serialize_option_value(_Mode.SAFE) == "SAFE"


def test_serialize_option_value_plain_value_uses_str():
    assert serialize_option_value("AUTOSAR 4.3") == "AUTOSAR 4.3"


def test_serialize_option_value_bool_uses_str():
    assert serialize_option_value(True) == "True"


def _build_command(*options):
    command = DynamicConverterCommand("convert")
    command.params.extend(options)
    return command


def test_build_config_arguments_single_value():
    command = _build_command(click.Option(["--dst-name"], default="x"))
    ctx = click.Context(command)
    ctx.params = {"dst_name": "x"}
    assert command.build_config_arguments(ctx, command._DST_PREFIX) == [
        "--name",
        "x",
    ]


def test_build_config_arguments_multiple_option():
    command = _build_command(click.Option(["--dst-tags"], multiple=True))
    ctx = click.Context(command)
    ctx.params = {"dst_tags": ["a", "b"]}
    assert command.build_config_arguments(ctx, command._DST_PREFIX) == [
        "--tags",
        "a",
        "--tags",
        "b",
    ]


def test_build_config_arguments_skips_none_and_other_prefix():
    command = _build_command(
        click.Option(["--dst-name"], default="x"),
        click.Option(["--src-name"], default="s"),
    )
    ctx = click.Context(command)
    ctx.params = {"dst_name": None, "src_name": "s"}
    assert command.build_config_arguments(ctx, command._DST_PREFIX) == []


def test_serialize_option_value_path_uses_full_path():
    from pathlib import PurePosixPath

    assert serialize_option_value(PurePosixPath("out/dir")) == "out/dir"


def test_serialize_option_value_mapping_uses_json():
    assert serialize_option_value({"AR": {"out": "a.arxml"}}) == '{"AR": {"out": "a.arxml"}}'


def test_serialize_option_value_sequence_uses_json():
    assert serialize_option_value(["a", "b"]) == '["a", "b"]'


def test_annotation_to_click_type_maps_containers_to_json():
    mapping_type = _annotation_to_click_type(dict[str, list[str]])
    assert isinstance(mapping_type, _JsonParamType)
    assert mapping_type.kind == "object"
    assert _annotation_to_click_type(list[str]).kind == "array"


def test_annotation_to_click_type_unwraps_optional():
    assert _annotation_to_click_type(str | None) is click.STRING


def test_json_kind_unwraps_optional_containers():
    from typing import Optional

    assert _json_kind(Optional[dict[str, str]]) == "object"
    assert _json_kind(dict[str, str] | None) == "object"
    assert _json_kind(Optional[list[str]]) == "array"
    assert _json_kind(list[str] | None) == "array"
    assert _json_kind(str | None) is None


def test_json_kind_ignores_scalars_and_unhandled_annotations():
    from typing import Literal

    assert _json_kind(int) is None
    assert _json_kind(Literal["a"]) is None


def test_format_default_encodes_containers_as_json():
    assert format_default({"Frame": "Frames"}) == '{"Frame": "Frames"}'
    assert format_default(["a", "b"]) == '["a", "b"]'
    assert format_default(2) == "2"
    assert format_default(None) is None


def test_format_default_uses_enum_member_name():
    assert format_default(_Mode.SAFE) == "SAFE"


def test_field_default_evaluates_factory_and_maps_undefined_to_none():
    class _Config(BaseModel):
        required: int
        items: list[str] = Field(default_factory=list)

    assert field_default(_Config.model_fields["required"]) is None
    assert field_default(_Config.model_fields["items"]) == []


def test_field_default_falls_back_when_factory_kwarg_is_unsupported():
    class _LegacyField:
        def is_required(self):
            return False

        def get_default(self, *, call_default_factory=False):
            if call_default_factory:
                raise TypeError("call_default_factory is not supported")
            return "fallback"

    assert field_default(_LegacyField()) == "fallback"


def test_parse_field_input_parses_structured_json():
    assert parse_field_input("package_paths", '{"Frame": "Frames"}', dict[str, str]) == {"Frame": "Frames"}
    assert parse_field_input("sender_ecus", "[]", list[str]) == []


def test_parse_field_input_casts_scalars():
    assert parse_field_input("retries", "3", int) == 3


def test_parse_field_input_rejects_invalid_json_with_field_name():
    with pytest.raises(ValueError, match="^package_paths: invalid JSON"):
        parse_field_input("package_paths", "{not json", dict[str, str])


def test_make_option_evaluates_default_factory():
    class _Config(BaseModel):
        package_paths: dict[str, list[str]] = Field(default_factory=dict)

    option = DynamicConverterCommand._make_option("flync", "dst_", "package_paths", _Config.model_fields["package_paths"])
    assert isinstance(option.type, _JsonParamType)
    assert option.default is None
    assert option.show_default == "{}"


def test_json_param_type_metavar_reflects_kind():
    assert _JsonParamType("object").get_metavar(None) == "{...}"
    assert _JsonParamType("array").get_metavar(None) == "[...]"
    assert _JsonParamType().get_metavar(None) == "JSON"


def test_json_option_passes_through_non_string_values():
    param_type = _JsonParamType("object")
    assert param_type.convert(None, None, None) is None
    assert param_type.convert({"AR": "a"}, None, None) == {"AR": "a"}


@pytest.mark.parametrize(
    ("kind", "value", "message"),
    [
        pytest.param("object", "[]", "expected a JSON object", id="object-rejects-array"),
        pytest.param("array", "{}", "expected a JSON array", id="array-rejects-object"),
    ],
)
def test_json_option_rejects_mismatched_kind(kind, value, message):
    param_type = _JsonParamType(kind)
    with pytest.raises(click.BadParameter, match=message):
        param_type.convert(value, None, None)


def test_json_option_accepts_object_and_treats_empty_as_unset():
    param_type = _JsonParamType("object")
    assert param_type.convert('{"AR": {"out": "a.arxml"}}', None, None) == {"AR": {"out": "a.arxml"}}
    assert param_type.convert("", None, None) is None


def test_json_option_rejects_invalid_json():
    param_type = _JsonParamType("object")
    with pytest.raises(click.BadParameter):
        param_type.convert("{", None, None)
