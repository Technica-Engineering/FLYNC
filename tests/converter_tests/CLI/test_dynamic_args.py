"""Tests for the dynamically generated converter CLI config arguments (preview support)."""

import enum

import click

from flync_converter.cli.dynamic import DynamicConverterCommand, serialize_option_value


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
        "--dst-name",
        "x",
    ]


def test_build_config_arguments_multiple_option():
    command = _build_command(click.Option(["--dst-tags"], multiple=True))
    ctx = click.Context(command)
    ctx.params = {"dst_tags": ["a", "b"]}
    assert command.build_config_arguments(ctx, command._DST_PREFIX) == [
        "--dst-tags",
        "a",
        "--dst-tags",
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
