"""Tests for the CLI commands using Click's CliRunner."""

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from flync_converter.base import ConverterConfig
from flync_converter.cli import cli


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def populated_registry():
    """Patch the registry with two fake converters."""
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


# ---------------------------------------------------------------------------
# list_converters
# ---------------------------------------------------------------------------


def test_list_converters_shows_registered(runner, populated_registry):
    result = runner.invoke(cli, ["list-converters"])
    assert result.exit_code == 0
    assert "json" in result.output
    assert "yaml" in result.output


def test_list_converters_empty_registry(runner):
    with patch("flync_converter.cli.commands.registry", {}):
        result = runner.invoke(cli, ["list-converters"])
    assert result.exit_code == 0
    assert "No converters registered" in result.output


# ---------------------------------------------------------------------------
# convert
# ---------------------------------------------------------------------------


def test_convert_same_format_skips(runner, populated_registry):
    result = runner.invoke(
        cli,
        [
            "convert",
            "-s",
            "input/path",
            "-o",
            "output/path",
            "-sf",
            "json",
            "-of",
            "json",
        ],
    )
    assert result.exit_code == 0
    assert "same" in result.output.lower()


def test_convert_calls_convert_func(runner, populated_registry):
    with patch("flync_converter.convert", return_value=None) as mock_func:
        result = runner.invoke(
            cli,
            [
                "convert",
                "-s",
                "input/path",
                "-o",
                "output/path",
                "-sf",
                "json",
                "-of",
                "yaml",
            ],
        )
    assert result.exit_code == 0
    mock_func.assert_called_once()
    assert mock_func.call_args.args[:4] == ("input/path", "output/path", "yaml", "json")


# ---------------------------------------------------------------------------
# convert_interactive
# ---------------------------------------------------------------------------


def test_convert_interactive_success(runner, populated_registry):
    """Simulate selecting json->yaml with minimal config input."""
    # input sequence: source format (1=json), config_path, dest format (2=yaml), config_path
    user_input = "1\n/src\n2\n/dst\n"
    with patch("flync_converter.cli.commands.Converter") as mock_converter_cls:
        mock_converter_cls.return_value.convert.return_value = None
        result = runner.invoke(cli, ["convert-interactive"], input=user_input)
    assert result.exit_code == 0
    assert "Conversion completed successfully" in result.output


def test_convert_interactive_conversion_error(runner, populated_registry):
    """Ensure conversion errors are reported gracefully."""
    user_input = "1\n/src\n2\n/dst\n"
    with patch("flync_converter.cli.commands.Converter") as mock_converter_cls:
        mock_converter_cls.return_value.convert.side_effect = RuntimeError("boom")
        result = runner.invoke(cli, ["convert-interactive"], input=user_input)
    assert result.exit_code == 0
    assert "boom" in result.output


# ---------------------------------------------------------------------------
# get_config_model (unit)
# ---------------------------------------------------------------------------


def test_get_config_model_returns_subclass():
    """Converter with a typed __init__ config param returns that subclass."""
    from flync_converter.base import ConverterConfig
    from flync_converter.utils import get_config_model

    class MyConfig(ConverterConfig):
        pass

    class MyConverter(MagicMock):
        def __init__(self, config: MyConfig = None):
            pass

    fake_registry = {"myconv": MyConverter()}
    with patch("flync_converter.utils.registry", fake_registry):
        result = get_config_model("myconv")
    assert result is MyConfig


def test_get_config_model_fallback_to_base():
    """Converter with no typed config falls back to ConverterConfig."""
    from flync_converter.base import ConverterConfig
    from flync_converter.utils import get_config_model

    fake_registry = {"plain": MagicMock(spec=[])}
    with patch("flync_converter.utils.registry", fake_registry):
        result = get_config_model("plain")
    assert result is ConverterConfig
