"""Tests for the Textual TUI conversion preview and its toggle."""

from unittest.mock import MagicMock, patch

from flync_converter.base import ConverterConfig
from flync_converter.cli.dynamic import DST_PREFIX, SRC_PREFIX
from flync_converter.cli.preview import config_endpoint
from flync_converter.cli.tui.app import FlyncTUI
from flync_converter.conversion_request import ConversionOutput, ConversionRequest, ConversionSource


def _make_app():
    return FlyncTUI()


def test_tui_initializes_with_preview_enabled():
    app = _make_app()
    assert app._no_preview is False


def test_tui_toggle_preview_flips_state():
    app = _make_app()
    app.action_toggle_preview()
    assert app._no_preview is True
    app.action_toggle_preview()
    assert app._no_preview is False


@patch("textual.app.App.get_system_commands", lambda self, screen: iter(()))
def test_tui_get_system_commands_disable_when_shown():
    app = _make_app()
    screen = MagicMock()
    commands = list(app.get_system_commands(screen))
    assert any(c.title == "Preview conversion: Disable" for c in commands)


@patch("textual.app.App.get_system_commands", lambda self, screen: iter(()))
def test_tui_get_system_commands_enable_when_hidden():
    app = _make_app()
    app._no_preview = True
    screen = MagicMock()
    commands = list(app.get_system_commands(screen))
    assert any(c.title == "Preview conversion: Enable" for c in commands)


def _patch_app_queries(app, log, btn):
    def fake_query_one(selector, *args, **kwargs):
        if "run-log" in selector:
            return log
        return btn

    app.query_one = fake_query_one


def _cfg(path="/tmp/source"):
    return ConverterConfig(config_path=path)


def _request():
    source, output = _cfg("/tmp/source"), _cfg("/tmp/output")
    request = ConversionRequest(
        sources=[ConversionSource(path=source.config_path, converter_type="json", config=source)],
        outputs=[ConversionOutput(path=output.config_path, converter_type="yaml", config=output)],
    )
    return request, [config_endpoint("json", source, SRC_PREFIX)], [config_endpoint("yaml", output, DST_PREFIX)]


def test_tui_run_conversion_writes_preview_when_enabled():
    app = _make_app()
    log = MagicMock()
    btn = MagicMock()
    _patch_app_queries(app, log, btn)

    with (
        patch("flync_converter.cli.tui.app.Converter"),
        patch("flync_converter.cli.tui.app.threading.Thread.start") as mock_start,
    ):
        app._run_conversion(*_request())

    assert btn.disabled is True
    mock_start.assert_called_once()
    log.clear.assert_called_once()
    log.write_lines.assert_called_once()
    preview = "\n".join(log.write_lines.call_args.args[0])
    assert "Conversion preview" in preview
    assert "flync-converter convert" in preview


def test_tui_run_conversion_skips_preview_when_disabled():
    app = _make_app()
    app._no_preview = True
    log = MagicMock()
    btn = MagicMock()
    _patch_app_queries(app, log, btn)

    with (
        patch("flync_converter.cli.tui.app.Converter"),
        patch("flync_converter.cli.tui.app.threading.Thread.start") as mock_start,
    ):
        app._run_conversion(*_request())

    mock_start.assert_called_once()
    log.clear.assert_called_once()
    log.write_lines.assert_not_called()
    log.write_line.assert_called_once()
