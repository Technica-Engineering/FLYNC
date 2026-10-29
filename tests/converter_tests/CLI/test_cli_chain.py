"""Tests for the chained ``convert source ... destination ...`` form and the deprecated flat form."""

import enum
import logging
import shlex
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from flync_converter.base import ConverterConfig
from flync_converter.cli import cli
from flync_converter.cli.dynamic import DST_PREFIX, SRC_PREFIX
from flync_converter.cli.preview import build_command_line, config_endpoint
from flync_converter.model_merger import OnConflict


class _IndentConfig(ConverterConfig):
    indent: int = 2


class _ShadowingConfig(ConverterConfig):
    format: str = "x"


class _Mode(enum.Enum):
    FAST = "fast"
    SAFE = "safe"


class _RichConfig(ConverterConfig):
    mode: _Mode = _Mode.FAST
    strict: bool = False
    indent: int = 2
    label: str | None = None


def _mock_converter(name, config_class):
    """Return a converter stand-in whose class annotates ``config`` with ``config_class``."""
    converter_class = type(f"_{name}Converter", (), {"__annotations__": {"config": config_class}, "name": name})
    return converter_class()


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture(autouse=True)
def populated_registry():
    fake_registry = {
        "flync": _mock_converter("flync", ConverterConfig),
        "json": _mock_converter("json", ConverterConfig),
        "yaml": _mock_converter("yaml", _IndentConfig),
        "shadow": _mock_converter("shadow", _ShadowingConfig),
        "rich": _mock_converter("rich", _RichConfig),
    }
    with (
        patch("flync_converter.cli.commands.registry", fake_registry),
        patch("flync_converter.utils.registry", fake_registry),
    ):
        yield fake_registry


def _invoke(runner, *args):
    with patch("flync_converter.convert_request") as convert_request:
        result = runner.invoke(cli, ["convert", *args])
    request = convert_request.call_args.args[0] if convert_request.called else None
    return result, request


def _endpoints(endpoints):
    return [(str(endpoint.path), endpoint.converter_type) for endpoint in endpoints]


def test_one_to_one_builds_a_request(runner):
    result, request = _invoke(runner, "source", "-p", "in", "-f", "flync", "destination", "-p", "out.json", "-f", "json")
    assert result.exit_code == 0, result.output
    assert _endpoints(request.sources) == [("in", "flync")]
    assert _endpoints(request.outputs) == [("out.json", "json")]
    assert request.on_conflict is OnConflict.FIRST
    assert request.fail_fast is False


def test_many_to_many_keeps_order_and_conversion_options(runner):
    result, request = _invoke(
        runner,
        "--on-conflict",
        "error",
        "--fail-fast",
        "source",
        "--path",
        "first",
        "--format",
        "flync",
        "source",
        "-p",
        "second",
        "-f",
        "yaml",
        "destination",
        "-p",
        "one.json",
        "-f",
        "json",
        "destination",
        "-p",
        "two.yaml",
        "-f",
        "yaml",
    )
    assert result.exit_code == 0, result.output
    assert _endpoints(request.sources) == [("first", "flync"), ("second", "yaml")]
    assert _endpoints(request.outputs) == [("one.json", "json"), ("two.yaml", "yaml")]
    assert request.on_conflict is OnConflict.ERROR
    assert request.fail_fast is True


def test_format_options_apply_to_their_own_occurrence(runner):
    result, request = _invoke(
        runner,
        "source",
        "-p",
        "a",
        "-f",
        "yaml",
        "--indent",
        "4",
        "source",
        "-p",
        "b",
        "-f",
        "yaml",
        "destination",
        "-p",
        "out.json",
        "-f",
        "json",
    )
    assert result.exit_code == 0, result.output
    assert [source.config.indent for source in request.sources] == [4, 2]


def test_format_options_do_not_leak_into_the_next_occurrence(runner):
    result, request = _invoke(
        runner, "source", "-p", "a", "-f", "yaml", "--indent", "4", "destination", "-p", "out.json", "-f", "json", "--indent", "4"
    )
    assert result.exit_code == 2
    assert "No such option '--indent'" in result.output
    assert request is None


def test_equals_syntax_before_the_next_subcommand(runner):
    result, request = _invoke(runner, "source", "-p", "a", "--format=flync", "destination", "--path=out.json", "--format=json")
    assert result.exit_code == 0, result.output
    assert _endpoints(request.sources) == [("a", "flync")]
    assert _endpoints(request.outputs) == [("out.json", "json")]


def test_config_file_is_passed_per_endpoint(runner, tmp_path):
    config_file = tmp_path / "src.yaml"
    config_file.write_text("{}\n")
    result, request = _invoke(runner, "source", "-p", "a", "-f", "flync", "--config", str(config_file), "destination", "-p", "o", "-f", "json")
    assert result.exit_code == 0, result.output
    assert request.sources[0].config == str(config_file)
    assert isinstance(request.outputs[0].config, ConverterConfig)


def test_preview_prints_the_subcommand_form(runner):
    result, _ = _invoke(runner, "source", "-p", "a", "-f", "yaml", "--indent", "4", "destination", "-p", "out.json", "-f", "json")
    assert result.exit_code == 0, result.output
    assert "- Source option     : indent = 4" in result.output
    assert "flync-converter convert source -p a -f yaml --indent 4 destination -p out.json -f json" in result.output
    assert "Converting a (yaml) -> out.json (json)" in result.output


def test_format_is_required(runner):
    result, request = _invoke(runner, "source", "-p", "a", "destination", "-p", "out.json", "-f", "json")
    assert result.exit_code == 2
    assert "Missing option '-f' / '--format'" in result.output
    assert request is None


def test_source_after_destination_is_rejected(runner):
    result, request = _invoke(runner, "source", "-p", "a", "-f", "flync", "destination", "-p", "o", "-f", "json", "source", "-p", "b", "-f", "flync")
    assert result.exit_code == 2
    assert "Sources must come before destinations" in result.output
    assert request is None


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (("source", "-p", "a", "-f", "flync"), "At least one destination is required"),
        (("destination", "-p", "o", "-f", "json"), "At least one source is required"),
    ],
    ids=["no-destination", "no-source"],
)
def test_both_sides_are_required(runner, args, message):
    result, request = _invoke(runner, *args)
    assert result.exit_code == 2
    assert message in result.output
    assert request is None


def test_invalid_request_is_a_usage_error(runner):
    result, request = _invoke(runner, "source", "-p", "a", "-f", "flync", "destination", "-p", "a/out", "-f", "json")
    assert result.exit_code == 2
    assert "a conversion cannot write where it reads" in result.output
    assert "Traceback" not in result.output
    assert request is None


def test_bare_convert_prints_help(runner):
    result, request = _invoke(runner)
    assert result.exit_code == 2
    assert "source ... destination ..." in result.output
    assert request is None


def test_field_shadowing_a_subcommand_option_is_not_offered(runner, caplog):
    with caplog.at_level(logging.WARNING, logger="flync_converter.cli.dynamic"):
        result, request = _invoke(runner, "source", "-p", "a", "-f", "shadow", "destination", "-p", "o", "-f", "json")
    assert result.exit_code == 0, result.output
    assert request.sources[0].converter_type == "shadow"
    assert "Config field 'format' shadows the --format option" in caplog.text


def test_flat_form_still_converts_and_warns(runner):
    with patch("flync_converter.convert") as legacy_convert:
        result = runner.invoke(cli, ["convert", "-s", "in", "-o", "out", "-sf", "flync", "-of", "json", "--no-preview"])
    assert result.exit_code == 0, result.output
    assert "the flat -s/-o form of convert is deprecated" in result.output
    legacy_convert.assert_called_once()


def test_flat_form_mixed_with_subcommands_is_rejected(runner):
    result, request = _invoke(runner, "-s", "in", "-sf", "flync", "destination", "-p", "o", "-f", "json")
    assert result.exit_code == 2
    assert "-s, -sf cannot be combined with source/destination subcommands" in result.output
    assert request is None


def test_flat_option_inside_a_subcommand_is_rejected(runner):
    result, request = _invoke(runner, "source", "-p", "a", "-f", "flync", "-o", "o")
    assert result.exit_code == 2
    assert "No such option '-o'" in result.output
    assert request is None


@pytest.mark.parametrize("subcommand", ["source", "destination"])
def test_unknown_format_is_rejected_with_the_registered_ones(runner, subcommand):
    args = {"source": ("source", "-p", "a", "-f", "dbcc", "destination", "-p", "o", "-f", "json")}
    args["destination"] = ("source", "-p", "a", "-f", "flync", "destination", "-p", "o", "-f", "dbcc")
    result, request = _invoke(runner, *args[subcommand])
    assert result.exit_code == 2
    assert "'dbcc' is not a registered converter. Registered: flync, json, rich, shadow, yaml." in result.output
    assert request is None


def test_dry_run_prints_the_preview_and_converts_nothing(runner):
    result, request = _invoke(
        runner, "--dry-run", "--no-preview", "source", "-p", "a", "-f", "yaml", "--indent", "4", "destination", "-p", "o", "-f", "json"
    )
    assert result.exit_code == 0, result.output
    assert "flync-converter convert source -p a -f yaml --indent 4 destination -p o -f json" in result.output
    assert "Dry run: the conversion is valid. Nothing was read or written." in result.output
    assert "Converting" not in result.output
    assert request is None


def test_dry_run_still_validates_the_request(runner):
    result, request = _invoke(runner, "--dry-run", "source", "-p", "a", "-f", "flync", "destination", "-p", "a/out", "-f", "json")
    assert result.exit_code == 2
    assert "a conversion cannot write where it reads" in result.output
    assert request is None


def test_dry_run_rejects_an_invalid_config_file(runner, tmp_path):
    config_file = tmp_path / "src.yaml"
    config_file.write_text("no_such_field: 1\n")
    result, request = _invoke(
        runner, "--dry-run", "source", "-p", "a", "-f", "yaml", "--config", str(config_file), "destination", "-p", "o", "-f", "json"
    )
    assert result.exit_code == 2
    assert f"--config {config_file} of source a" in result.output
    assert request is None


def test_dry_run_is_not_offered_for_the_flat_form(runner):
    result, request = _invoke(runner, "--dry-run", "-s", "in", "-o", "out", "-sf", "flync", "-of", "json")
    assert result.exit_code == 2
    assert "--dry-run needs source/destination subcommands" in result.output
    assert request is None


@pytest.mark.parametrize("prefix", [SRC_PREFIX, DST_PREFIX], ids=["source", "destination"])
def test_tui_and_gui_preview_command_reparses_to_the_same_config(runner, prefix):
    """The command the TUI and GUI print for a configuration runs that same configuration."""
    config = _RichConfig(config_path="my dir/rich", mode=_Mode.SAFE, strict=True, indent=4, label="a b")
    endpoint = config_endpoint("rich", config, prefix)
    other = config_endpoint("json", ConverterConfig(config_path="other"), DST_PREFIX if prefix == SRC_PREFIX else SRC_PREFIX)
    sources, destinations = ([endpoint], [other]) if prefix == SRC_PREFIX else ([other], [endpoint])

    command_line = build_command_line(sources, destinations, posix=True)
    result, request = _invoke(runner, *shlex.split(command_line)[2:])

    assert result.exit_code == 0, result.output
    parsed = (request.sources if prefix == SRC_PREFIX else request.outputs)[0].config
    assert parsed == config


def test_cli_preview_command_reruns_the_same_request(runner, tmp_path):
    """The command printed by the preview, including --config, builds the request it was printed for."""
    config_file = tmp_path / "rich config.yaml"
    config_file.write_text("indent: 8\n")
    args = (
        "source",
        "-p",
        "my dir/a",
        "-f",
        "rich",
        "--config",
        str(config_file),
        "--mode",
        "SAFE",
        "--strict",
        "true",
        "source",
        "-p",
        "b",
        "-f",
        "yaml",
        "destination",
        "-p",
        "out dir",
        "-f",
        "json",
    )
    with patch("flync_converter.cli.preview.os", SimpleNamespace(name="posix")):
        first, first_request = _invoke(runner, *args)
    assert first.exit_code == 0, first.output
    command_line = next(line for line in first.output.splitlines() if line.startswith("- Command")).split(": ", 1)[1]

    second, second_request = _invoke(runner, *shlex.split(command_line)[2:])

    assert second.exit_code == 0, second.output
    assert second_request == first_request
