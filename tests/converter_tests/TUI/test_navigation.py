"""TUI keyboard navigation, quit behaviour, resize, and robustness under focus changes."""

import time

from textual.widgets import Button, Log

from flync_converter.cli.tui.app import FlyncTUI


def _fake_converter_class(calls, *, sleep=0.0, error=None):
    """Build a Converter class standing in for ``flync_converter.cli.tui.app.Converter``."""

    class Fake:
        def convert(
            self,
            source=None,
            destination=None,
            source_type=None,
            destination_type=None,
            source_config=None,
            destination_config=None,
        ):
            calls.append((source_type, destination_type))
            if sleep:
                time.sleep(sleep)
            if error:
                raise RuntimeError(error)

    return Fake


def _configure_app_converter(monkeypatch, calls, *, sleep=0.0, error=None):
    monkeypatch.setattr(
        "flync_converter.cli.tui.app.Converter",
        _fake_converter_class(calls, sleep=sleep, error=error),
    )


def _ready_panels(app):
    """Fill both panels with an acceptable config_path so conversion runs."""
    cfg_path = "/tmp/nav_source"
    dest_path = "/tmp/nav_dest"
    source = app.query_one("#source-panel")
    dest = app.query_one("#dest-panel")
    from flync_converter.cli.tui.widgets.converter_panel import ConverterPanel

    src = app.query_one("#source-panel", ConverterPanel)
    dst = app.query_one("#dest-panel", ConverterPanel)
    return src, dst, cfg_path, dest_path


# ---------------------------------------------------------------------------
# TUI-P21  Quit with Ctrl+Q
class TestQuit:
    def test_ctrl_q_quits(self, helpers):
        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("ctrl+q")
                await pilot.pause()
                assert app._closed

        helpers.run(_impl())


# ---------------------------------------------------------------------------
# TUI-P22  Resize
class TestResize:
    def test_resize_keeps_ui_consistent(self, helpers):
        async def _impl():
            app = FlyncTUI()
            async with app.run_test(size=(40, 12)) as pilot:
                await pilot.pause()
                await pilot.resize_terminal(80, 24)
                await pilot.pause()
                assert app.is_running
                for selector in ("#source-panel", "#dest-panel", "#run-log", "#btn-convert"):
                    assert app.query_one(selector) is not None

        helpers.run(_impl())


# ---------------------------------------------------------------------------
# TUI-P▶  Keyboard navigation (Tab / Shift+Tab)
class TestKeyboardNavigation:
    def test_tab_cycles_focus(self, helpers):
        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                all_ids = {w.id for w in app.query("Widget") if w.id}
                focused_ids = set()
                for _ in range(8):
                    await pilot.press("tab")
                    await pilot.pause()
                    assert app.focused is not None
                    assert app.focused.id in all_ids
                    focused_ids.add(app.focused.id)
                assert focused_ids
                assert "run-log" in focused_ids or "log-level-select" in focused_ids

        helpers.run(_impl())

    def test_focus_moves_to_log_and_level(self, helpers):
        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                app.query_one("#run-log", Log).focus()
                await pilot.pause()
                await pilot.press("tab")
                await pilot.pause()
                assert app.focused is not None
                assert app.focused.id != "run-log"

        helpers.run(_impl())


# ---------------------------------------------------------------------------
# TUI-P▶  Enter on active button
class TestEnterActivatesButton:
    def test_enter_on_focused_convert_runs_conversion(self, helpers, monkeypatch):
        calls = []
        _configure_app_converter(monkeypatch, calls)

        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                src = app.query_one("#source-panel")
                dst = app.query_one("#dest-panel")
                from flync_converter.cli.tui.widgets.converter_panel import ConverterPanel

                helpers.set_config_path(app.query_one("#source-panel", ConverterPanel), "/tmp/src")
                helpers.set_config_path(app.query_one("#dest-panel", ConverterPanel), "/tmp/dst")
                await pilot.pause()
                btn = app.query_one("#btn-convert", Button)
                btn.focus()
                await pilot.press("enter")
                await helpers.wait_until(lambda: len(calls) == 1, pilot)
                assert calls == [("flync", "flync")]

        helpers.run(_impl())


# ---------------------------------------------------------------------------
# TUI-N21  Close during conversion
class TestQuitDuringConversion:
    def test_close_during_conversion(self, helpers, monkeypatch):
        calls = []
        _configure_app_converter(monkeypatch, calls, sleep=2.0)

        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                from flync_converter.cli.tui.widgets.converter_panel import ConverterPanel

                helpers.set_config_path(app.query_one("#source-panel", ConverterPanel), "/tmp/src")
                helpers.set_config_path(app.query_one("#dest-panel", ConverterPanel), "/tmp/dst")
                await pilot.pause()
                await pilot.click("#btn-convert")
                await pilot.pause()
                await pilot.press("ctrl+q")
                await pilot.pause()
                assert app._closed

        helpers.run(_impl())


# ---------------------------------------------------------------------------
# TUI-N22  Ctrl+C does not crash
class TestCtrlC:
    def test_ctrl_c_does_not_crash(self, helpers):
        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("ctrl+c")
                await pilot.pause()
                assert app.is_running
                assert app.query_one("#run-log", Log) is not None

        helpers.run(_impl())


# ---------------------------------------------------------------------------
# TUI-N23  Unexpected key / input
# TUI-N28  Unknown shortcut
# TUI-N29  Unexpected combination
class TestUnexpectedInput:
    def test_unexpected_input_is_ignored(self, helpers):
        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("ctrl+p")
                await pilot.pause()
                assert app.is_running

        helpers.run(_impl())

    def test_unknown_shortcut(self, helpers):
        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("ctrl+k")
                await pilot.pause()
                assert app.is_running

        helpers.run(_impl())

    def test_unexpected_combo(self, helpers):
        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("shift+ctrl+q")
                await pilot.pause()
                assert app.is_running

        helpers.run(_impl())


# ---------------------------------------------------------------------------
# TUI-N25  Double Enter
class TestDoubleEnter:
    def test_double_enter_not_crashing(self, helpers):
        # Full double-activation coverage lives in test_conversion.TestDoubleClick.
        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("enter", "enter")
                await pilot.pause()
                assert app.is_running

        helpers.run(_impl())


# ---------------------------------------------------------------------------
# TUI-N26  Escape without a menu
# TUI-N27  Ctrl+Q during conversion
class TestEscapeAndQuit:
    def test_escape_without_menu(self, helpers):
        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("escape")
                await pilot.pause()
                assert app.is_running
                assert app.screen is not None

        helpers.run(_impl())

    def test_ctrl_q_during_conversion(self, helpers, monkeypatch):
        calls = []
        _configure_app_converter(monkeypatch, calls, sleep=2.0)

        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                from flync_converter.cli.tui.widgets.converter_panel import ConverterPanel

                helpers.set_config_path(app.query_one("#source-panel", ConverterPanel), "/tmp/src")
                helpers.set_config_path(app.query_one("#dest-panel", ConverterPanel), "/tmp/dst")
                await pilot.pause()
                await pilot.click("#btn-convert")
                await pilot.pause()
                await pilot.press("ctrl+q")
                await pilot.pause()
                assert app._closed

        helpers.run(_impl())


# ---------------------------------------------------------------------------
# TUI-N30  Navigation during conversion
class TestNavigateDuringConversion:
    def test_navigate_while_converting(self, helpers, monkeypatch):
        calls = []
        _configure_app_converter(monkeypatch, calls, sleep=1.5)

        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                from flync_converter.cli.tui.widgets.converter_panel import ConverterPanel

                helpers.set_config_path(app.query_one("#source-panel", ConverterPanel), "/tmp/src")
                helpers.set_config_path(app.query_one("#dest-panel", ConverterPanel), "/tmp/dst")
                await pilot.pause()
                await pilot.click("#btn-convert")
                for _ in range(6):
                    await pilot.press("tab")
                    await pilot.pause()
                await helpers.wait_until(lambda: len(calls) == 1, pilot)
                assert app.is_running
                assert app.query_one("#run-log", Log) is not None

        helpers.run(_impl())
