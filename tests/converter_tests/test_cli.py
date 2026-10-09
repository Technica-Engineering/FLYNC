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


def test_convert_interactive_success(runner, populated_registry):
    """Simulate selecting json->yaml with minimal config input."""
    # input sequence: source format (1=json), config_path, dest format (2=yaml), config_path,
    # then the defaults for report_enabled, report_min_log_level and persist_config
    user_input = "1\n/src\n2\n/dst\n\n\n\n"
    with patch("flync_converter.cli.commands.Converter") as mock_converter_cls:
        mock_converter_cls.return_value.convert.return_value = None
        result = runner.invoke(cli, ["convert-interactive"], input=user_input)
    assert result.exit_code == 0
    assert "Conversion completed successfully" in result.output


def test_convert_interactive_conversion_error(runner, populated_registry):
    """Ensure conversion errors are reported gracefully."""
    user_input = "1\n/src\n2\n/dst\n\n\n\n"
    with patch("flync_converter.cli.commands.Converter") as mock_converter_cls:
        mock_converter_cls.return_value.convert.side_effect = RuntimeError("boom")
        result = runner.invoke(cli, ["convert-interactive"], input=user_input)
    assert result.exit_code == 0
    assert "boom" in result.output


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


def _dbc_registry():
    """Registry with a converter whose config carries a defaulted numeric field."""

    class DbcCfg(ConverterConfig):
        baud_rate_default: int = 500_000

    class _DbcConverter:
        name = "dbc"
        __doc__ = "DBC converter."

        def __init__(self, config: DbcCfg = None):
            pass

    return {"dbc": _DbcConverter(), "yaml": MagicMock(name="yaml")}


def _invoke_convert(runner, args):
    reg = _dbc_registry()
    with (
        patch("flync_converter.cli.commands.registry", reg),
        patch("flync_converter.cli.interactive.registry", reg),
        patch("flync_converter.utils.registry", reg),
        patch("flync_converter.convert") as mock_convert,
    ):
        result = runner.invoke(cli, ["convert", *args])
    return result, mock_convert


_DBC_TO_YAML = ["-s", "in", "-o", "out", "-sf", "dbc", "-of", "yaml"]


def test_convert_without_src_field_flags_sets_only_config_path(runner):
    """Options left unset must not count as explicit values, so stored or file configs still apply."""
    result, mock_convert = _invoke_convert(runner, _DBC_TO_YAML)

    assert result.exit_code == 0, result.output
    config = mock_convert.call_args.kwargs["source_config"]
    assert config.model_fields_set == {"config_path"}


def test_convert_with_src_field_flag_sets_that_field(runner):
    result, mock_convert = _invoke_convert(runner, [*_DBC_TO_YAML, "--src-baud-rate-default", "1000000"])

    assert result.exit_code == 0, result.output
    config = mock_convert.call_args.kwargs["source_config"]
    assert config.baud_rate_default == 1_000_000
    assert config.model_fields_set == {"config_path", "baud_rate_default"}


def test_convert_passes_config_file_alone_as_path(runner, tmp_path):
    """A file without per-field options is passed on as a path, replacing the stored configuration."""
    src_cfg = tmp_path / "src-dbc.yaml"
    dst_cfg = tmp_path / "dst-yaml.yaml"
    src_cfg.write_text("baud_rate_default: 123\n", encoding="utf-8")
    dst_cfg.write_text("report_min_log_level: DEBUG\n", encoding="utf-8")

    result, mock_convert = _invoke_convert(runner, [*_DBC_TO_YAML, "--src-config", str(src_cfg), "--dst-config", str(dst_cfg)])

    assert result.exit_code == 0, result.output
    assert mock_convert.call_args.kwargs["source_config"] == str(src_cfg)
    assert mock_convert.call_args.kwargs["destination_config"] == str(dst_cfg)


def test_convert_applies_field_options_over_config_file(runner, tmp_path):
    src_cfg = tmp_path / "src-dbc.yaml"
    src_cfg.write_text("baud_rate_default: 123\nreport_min_log_level: DEBUG\n", encoding="utf-8")

    result, mock_convert = _invoke_convert(runner, [*_DBC_TO_YAML, "--src-config", str(src_cfg), "--src-baud-rate-default", "1000000"])

    assert result.exit_code == 0, result.output
    config = mock_convert.call_args.kwargs["source_config"]
    assert config.config_path == "in"
    # From the option, over the file.
    assert config.baud_rate_default == 1_000_000
    # From the file.
    assert config.report_min_log_level == "DEBUG"


def test_convert_rejects_missing_config_file(runner, tmp_path):
    result, _ = _invoke_convert(runner, [*_DBC_TO_YAML, "--src-config", str(tmp_path / "nope.yaml")])

    assert result.exit_code != 0
    assert "--src-config" in result.output
