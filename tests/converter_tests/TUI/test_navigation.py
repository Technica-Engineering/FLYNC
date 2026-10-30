"""TUI keyboard navigation, quit behaviour, resize, and robustness under focus changes."""

import time

from textual.widgets import Button, Log

from flync_converter.cli.tui.app import FlyncTUI


def _fake_converter_class(calls, *, sleep=0.0, error=None):
    """Build a Converter class standing in for ``flync_converter.cli.tui.app.Converter``."""

    class Fake:
        @staticmethod
        def convert_request(request):
            calls.append((request.sources[0].converter_type, request.outputs[0].converter_type))
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
                for selector in ("#source-panel-1", "#destination-panel-1", "#run-log", "#btn-convert"):
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
                from flync_converter.cli.tui.widgets.converter_panel import ConverterPanel

                helpers.set_config_path(app.query_one("#source-panel-1", ConverterPanel), "/tmp/src")
                helpers.set_config_path(app.query_one("#destination-panel-1", ConverterPanel), "/tmp/dst")
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

                helpers.set_config_path(app.query_one("#source-panel-1", ConverterPanel), "/tmp/src")
                helpers.set_config_path(app.query_one("#destination-panel-1", ConverterPanel), "/tmp/dst")
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

                helpers.set_config_path(app.query_one("#source-panel-1", ConverterPanel), "/tmp/src")
                helpers.set_config_path(app.query_one("#destination-panel-1", ConverterPanel), "/tmp/dst")
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

                helpers.set_config_path(app.query_one("#source-panel-1", ConverterPanel), "/tmp/src")
                helpers.set_config_path(app.query_one("#destination-panel-1", ConverterPanel), "/tmp/dst")
                await pilot.pause()
                await pilot.click("#btn-convert")
                for _ in range(6):
                    await pilot.press("tab")
                    await pilot.pause()
                await helpers.wait_until(lambda: len(calls) == 1, pilot)
                assert app.is_running
                assert app.query_one("#run-log", Log) is not None

        helpers.run(_impl())


def test_add_remove_endpoints_and_renumber(helpers):
    """Add buttons insert panels above themselves and removal preserves one endpoint."""
    from textual.widgets import Button, Label

    from flync_converter.cli.tui.app import FlyncTUI
    from flync_converter.cli.tui.widgets import ConverterPanelList, RemoveAction

    async def _impl():
        app = FlyncTUI()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            sources = app.query_one("#source-panels", ConverterPanelList)
            assert len(sources.panels) == 1
            assert not sources.panels[0].query_one("#remove", RemoveAction).display

            await pilot.click("#add-source")
            await pilot.pause()
            assert len(sources.panels) == 2
            assert sources.panels[0].query_one("#remove", RemoveAction).display
            assert sources.children[-1].id == "add-source-row"
            add_button = sources.query_one("#add-source", Button)
            format_select = sources.panels[-1].query_one("#select")
            config_path = sources.panels[-1].query_one(".path-row")
            for _ in range(50):
                if config_path.outer_size.width:
                    break
                await pilot.pause(0.02)
            assert add_button.outer_size.width == format_select.outer_size.width
            assert format_select.outer_size.width == config_path.outer_size.width
            first_widths = (
                add_button.outer_size.width,
                format_select.outer_size.width,
                config_path.outer_size.width,
            )
            assert len(set(first_widths)) == 1

            assert await sources.remove_panel(sources.panels[0])
            await pilot.pause()
            assert len(sources.panels) == 1
            assert str(sources.panels[0].query_one(".panel-title", Label).render()) == "Source 1"
            assert not sources.panels[0].query_one("#remove", RemoveAction).display

    helpers.run(_impl())


def test_source_and_destination_columns_are_symmetric(helpers):
    """The base Source and Destination panels use equal dimensions."""
    from flync_converter.cli.tui.app import FlyncTUI
    from flync_converter.cli.tui.widgets import ConverterPanelList

    async def _impl():
        app = FlyncTUI()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            sources = app.query_one("#source-panels", ConverterPanelList)
            destinations = app.query_one("#destination-panels", ConverterPanelList)
            assert abs(sources.size.width - destinations.size.width) <= 1
            assert abs(sources.panels[0].size.width - destinations.panels[0].size.width) <= 1
            assert sources.panels[0].size.height == destinations.panels[0].size.height

    helpers.run(_impl())


def test_panel_collapse_hides_the_form_and_keeps_values(helpers):
    """A collapsed panel shows its format and path in the title row and keeps its field values."""
    from textual.widgets import Label

    from flync_converter.cli.tui.app import FlyncTUI
    from flync_converter.cli.tui.widgets import CollapseToggle, ConverterPanel

    async def _impl():
        app = FlyncTUI()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            source = app.query_one("#source-panel-1", ConverterPanel)
            helpers.set_config_path(source, "/tmp/in")
            expanded_height = source.size.height

            source.query_one("#collapse", CollapseToggle).focus()
            await pilot.press("enter")
            await pilot.pause()
            assert source.is_collapsed
            assert not source.query_one("#body").display
            assert str(source.query_one(".panel-summary", Label).render()) == "flync · /tmp/in"
            assert source.size.height < expanded_height
            source.show_error("boom")
            await pilot.pause()
            assert source.query_one("#error").display

            await pilot.click("#source-panel-1 #collapse")
            await pilot.pause()
            assert not source.is_collapsed
            assert str(source.query_one(".panel-summary", Label).render()) == ""
            assert str(source.read_config().config_path) == "/tmp/in"

    helpers.run(_impl())


def test_remove_action_removes_its_own_panel(helpers):
    """Activating Remove removes the panel that owns it and keeps the others."""
    from flync_converter.cli.tui.app import FlyncTUI
    from flync_converter.cli.tui.widgets import ConverterPanelList, RemoveAction

    async def _impl():
        app = FlyncTUI()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            destinations = app.query_one("#destination-panels", ConverterPanelList)
            await destinations.add_panel()
            await destinations.add_panel()
            await pilot.pause()

            destinations.panels[1].query_one("#remove", RemoveAction).activate()
            for _ in range(20):
                await pilot.pause()
                if len(destinations.panels) == 2:
                    break
            assert [panel.id for panel in destinations.panels] == ["destination-panel-1", "destination-panel-3"]

    helpers.run(_impl())


def test_convert_stays_disabled_while_a_conversion_runs(helpers):
    """Endpoint changes during a conversion do not re-enable Convert until it ends."""
    from textual.widgets import Button

    from flync_converter.cli.tui.app import FlyncTUI
    from flync_converter.cli.tui.widgets import ConverterPanelList

    async def _impl():
        app = FlyncTUI()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            button = app.query_one("#btn-convert", Button)
            assert not button.disabled

            app._converting = True
            await app.query_one("#source-panels", ConverterPanelList).add_panel()
            await pilot.pause()
            assert button.disabled

            app._conversion_finished()
            assert not button.disabled

    helpers.run(_impl())
