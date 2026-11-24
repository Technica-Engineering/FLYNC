"""Tests for the conversion preview and the --no-preview flag."""

import enum
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from flync_converter.base import ConverterConfig
from flync_converter.cli import cli
from flync_converter.cli.dynamic import DST_PREFIX, SRC_PREFIX
from flync_converter.cli.preview import (
    ConversionEndpoint,
    build_command_line,
    config_endpoint,
    conversion_summary,
    join_command,
    render_preview,
)


class _OutputType(enum.Enum):
    CLASSIC = "classic"
    COMPACT = "compact"


class _SampleConfig(ConverterConfig):
    output_type: _OutputType = _OutputType.CLASSIC
    indent: int = 2
    tags: list[str] = []


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def populated_registry():
    mock_json = MagicMock()
    mock_json.name = "json"
    mock_json.__doc__ = "JSON converter."
    mock_json.__class__.__init__.__annotations__ = {"config": ConverterConfig}

    mock_yaml = MagicMock()
    mock_yaml.name = "yaml"
    mock_yaml.__doc__ = "YAML converter."
    mock_yaml.__class__.__init__.__annotations__ = {"config": ConverterConfig}

    fake_registry = {"json": mock_json, "yaml": mock_yaml}
    with (
        patch("flync_converter.cli.commands.registry", fake_registry),
        patch("flync_converter.cli.interactive.registry", fake_registry),
        patch("flync_converter.utils.registry", fake_registry),
    ):
        yield fake_registry


def _convert(runner, *args):
    with patch("flync_converter.convert", return_value=None):
        return runner.invoke(cli, list(args))


_CONVERT_ARGS = ("-s", "input/path", "-o", "output/path", "-sf", "json", "-of", "yaml")


# ---------------------------------------------------------------------------
# Command line


def test_build_command_line_single_endpoints():
    sources = [ConversionEndpoint("flync", "workspace/", {"indent": 2}, ["--indent", "2"])]
    destinations = [ConversionEndpoint("yaml", "out/", {"output_type": "CLASSIC"}, ["--output-type", "CLASSIC"])]
    assert build_command_line(sources, destinations, posix=True) == (
        "flync-converter convert source -p workspace/ -f flync --indent 2 destination -p out/ -f yaml --output-type CLASSIC"
    )


def test_build_command_line_multiple_endpoints():
    sources = [ConversionEndpoint("flync", "a/"), ConversionEndpoint("dbc", "b.dbc")]
    destinations = [ConversionEndpoint("yaml", "out/")]
    assert build_command_line(sources, destinations, posix=True) == (
        "flync-converter convert source -p a/ -f flync source -p b.dbc -f dbc destination -p out/ -f yaml"
    )


def test_join_command_posix_quoting():
    assert join_command(["x", "C:/my docs/in"], posix=True) == "x 'C:/my docs/in'"


def test_join_command_windows_quoting():
    assert join_command(["x", r"C:\my docs\in", r"C:\out"], posix=False) == r'x "C:\my docs\in" C:\out'


# ---------------------------------------------------------------------------
# Endpoints built from a configuration


def test_config_endpoint_default_config_has_no_options():
    endpoint = config_endpoint("flync", ConverterConfig(config_path="ws"), SRC_PREFIX)
    assert endpoint == ConversionEndpoint("flync", "ws")


def test_config_endpoint_keeps_only_offered_non_default_fields():
    config = ConverterConfig(config_path="ws", persist_config=False)

    assert config_endpoint("flync", config, SRC_PREFIX).arguments == []
    destination = config_endpoint("flync", config, DST_PREFIX)
    assert destination.options == {"persist_config": False}
    assert destination.arguments == ["--persist-config", "False"]


def test_config_endpoint_serializes_enum_by_name():
    endpoint = config_endpoint("yaml", _SampleConfig(config_path="out", output_type=_OutputType.COMPACT, indent=4), DST_PREFIX)
    assert endpoint.arguments == ["--output-type", "COMPACT", "--indent", "4"]


def test_config_endpoint_passes_non_scalar_values_as_json():
    endpoint = config_endpoint("yaml", _SampleConfig(config_path="out", tags=["a"]), DST_PREFIX)
    assert endpoint.options == {"tags": ["a"]}
    assert endpoint.arguments == ["--tags", '["a"]']


# ---------------------------------------------------------------------------
# Preview text


def test_render_preview_lists_options_under_their_endpoint():
    sources = [ConversionEndpoint("flync", "workspace/", {"indent": 2}, ["--indent", "2"])]
    destinations = [ConversionEndpoint("yaml", "out/", {"output_type": _OutputType.CLASSIC}, ["--output-type", "CLASSIC"])]
    assert render_preview(sources, destinations, posix=True).splitlines() == [
        "Conversion preview",
        "------------------",
        "- Source            : flync -> workspace/",
        "- Source option     : indent = 2",
        "- Destination       : yaml -> out/",
        "- Destination option: output_type = CLASSIC",
        "- Command           : flync-converter convert source -p workspace/ -f flync --indent 2 destination -p out/ -f yaml --output-type CLASSIC",
    ]


def test_render_preview_numbers_multiple_endpoints():
    text = render_preview([ConversionEndpoint("flync", "a/"), ConversionEndpoint("dbc", "b.dbc")], [ConversionEndpoint("yaml", "out/")])
    assert "- Source 1          : flync -> a/" in text
    assert "- Source 2          : dbc -> b.dbc" in text
    assert "- Destination       : yaml -> out/" in text


def test_conversion_summary():
    sources = [ConversionEndpoint("flync", "a/"), ConversionEndpoint("dbc", "b.dbc")]
    assert conversion_summary(sources, [ConversionEndpoint("yaml", "out/")]) == "Converting a/ (flync), b.dbc (dbc) -> out/ (yaml)"


# ---------------------------------------------------------------------------
# convert command


def test_convert_shows_preview(runner, populated_registry):
    result = _convert(runner, "convert", *_CONVERT_ARGS)
    assert result.exit_code == 0
    assert "Conversion preview" in result.output
    assert "- Source            : json -> input/path" in result.output
    assert "flync-converter convert source -p input/path -f json destination -p output/path -f yaml" in result.output
    assert "Converting input/path (json) -> output/path (yaml)" in result.output


def test_convert_preview_includes_given_options(runner, populated_registry):
    result = _convert(runner, "convert", *_CONVERT_ARGS, "--dst-persist-config", "false")
    assert result.exit_code == 0
    assert "- Destination option: persist_config = False" in result.output
    assert "destination -p output/path -f yaml --persist-config False" in result.output


def test_convert_preview_includes_config_files(runner, populated_registry, tmp_path):
    config_file = tmp_path / "dst.yaml"
    config_file.write_text("{}\n")
    result = _convert(runner, "convert", *_CONVERT_ARGS, "--dst-config", str(config_file))
    assert result.exit_code == 0
    assert join_command(["destination", "-p", "output/path", "-f", "yaml", "--config", str(config_file)]) in result.output


@pytest.mark.parametrize(
    "args",
    [("--no-preview", "convert", *_CONVERT_ARGS), ("convert", "--no-preview", *_CONVERT_ARGS)],
    ids=["main-command", "subcommand"],
)
def test_convert_no_preview_suppresses_preview(runner, populated_registry, args):
    result = _convert(runner, *args)
    assert result.exit_code == 0
    assert "Conversion preview" not in result.output
    assert "flync-converter convert" not in result.output
    assert "Converting input/path (json) -> output/path (yaml)" in result.output
