"""TUI conversion flow: success, background execution, errors, and end-to-end scenarios."""

import time

from textual.widgets import Button, Log

from flync_converter.cli.tui.app import FlyncTUI
from flync_converter.cli.tui.widgets.converter_panel import ConverterPanel


def _make_converter_class(calls, *, sleep=0.0, error=None):
    class Fake:
        @staticmethod
        def convert_request(request):
            source = request.sources[0]
            destination = request.outputs[0]
            calls.append((source.converter_type, destination.converter_type, source.path, destination.path, request))
            if sleep:
                time.sleep(sleep)
            if error:
                raise RuntimeError(error)

    return Fake


def _install(monkeypatch, calls, *, sleep=0.0, error=None):
    monkeypatch.setattr(
        "flync_converter.cli.tui.app.Converter",
        _make_converter_class(calls, sleep=sleep, error=error),
    )


def _fill(app, src_cfg="/tmp/cfg-src", dst_cfg="/tmp/cfg-dst"):
    src = app.query_one("#source-panel-1", ConverterPanel)
    dst = app.query_one("#destination-panel-1", ConverterPanel)
    src.query_one("#field-source-panel-1-config_path").value = src_cfg
    dst.query_one("#field-destination-panel-1-config_path").value = dst_cfg


# ---------------------------------------------------------------------------
# TUI-P13  Valid conversion
class TestValidConversion:
    def test_conversion_succeeds_and_completed_logged(self, helpers, monkeypatch):
        calls = []
        _install(monkeypatch, calls)

        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                _fill(app)
                await pilot.pause()
                await pilot.click("#btn-convert")
                await helpers.wait_until(
                    lambda: "Conversion completed successfully." in helpers.log_text(app.query_one("#run-log")),
                    pilot,
                )
                assert len(calls) == 1
                assert calls[0][0] == "flync"
                assert calls[0][1] == "flync"

        helpers.run(_impl())


# ---------------------------------------------------------------------------
# TUI-P19  Background execution (button disabled then re-enabled)
class TestBackgroundExecution:
    def test_button_disabled_during_and_reenabled_after(self, helpers, monkeypatch):
        calls = []
        _install(monkeypatch, calls, sleep=0.8)

        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                _fill(app)
                await pilot.pause()
                btn = app.query_one("#btn-convert", Button)
                assert not btn.disabled
                await pilot.click("#btn-convert")
                assert await helpers.wait_until(lambda: btn.disabled is True, pilot)
                assert await helpers.wait_until(lambda: btn.disabled is False, pilot)
                assert len(calls) == 1

        helpers.run(_impl())


# ---------------------------------------------------------------------------
# TUI-P20  Return after conversion (fields preserved)
class TestStateAfterConversion:
    def test_fields_preserved_after_conversion(self, helpers, monkeypatch):
        calls = []
        _install(monkeypatch, calls)

        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                _fill(app, src_cfg="/tmp/keep-me")
                await pilot.pause()
                await pilot.click("#btn-convert")
                await helpers.wait_until(
                    lambda: "Conversion completed successfully." in helpers.log_text(app.query_one("#run-log")),
                    pilot,
                )
                src = app.query_one("#source-panel-1", ConverterPanel)
                assert src.read_config().config_path == "/tmp/keep-me"

        helpers.run(_impl())


# ---------------------------------------------------------------------------
# TUI-P23  Several consecutive conversions
class TestMultipleConversions:
    def test_sequential_conversions(self, helpers, monkeypatch):
        calls = []
        _install(monkeypatch, calls)

        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                _fill(app)
                await pilot.pause()
                btn = app.query_one("#btn-convert", Button)
                for i in range(3):
                    await pilot.pause()
                    btn.press()
                    await helpers.wait_until(lambda: len(calls) == i + 1, pilot)
                    await helpers.wait_until(lambda: btn.disabled is False, pilot)
                    await pilot.pause()
                assert len(calls) == 3

        helpers.run(_impl())


# ---------------------------------------------------------------------------
# TUI-N13 / TUI-N14  Error during conversion
class TestConversionError:
    def test_conversion_failure_is_reported(self, helpers, monkeypatch):
        calls = []
        _install(monkeypatch, calls, error="broken-converter")

        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                _fill(app)
                await pilot.pause()
                await pilot.click("#btn-convert")
                await helpers.wait_until(
                    lambda: "Conversion failed: broken-converter" in helpers.log_text(app.query_one("#run-log")),
                    pilot,
                )

        helpers.run(_impl())

    def test_mid_conversion_error_reenables_button(self, helpers, monkeypatch):
        calls = []
        _install(monkeypatch, calls, sleep=0.2, error="late-crash")

        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                _fill(app)
                await pilot.pause()
                btn = app.query_one("#btn-convert", Button)
                await pilot.click("#btn-convert")
                await helpers.wait_until(lambda: btn.disabled is False, pilot)
                text = helpers.log_text(app.query_one("#run-log"))
                assert "Conversion failed: late-crash" in text

        helpers.run(_impl())


# ---------------------------------------------------------------------------
# TUI-N15  Double click on Convert
class TestDoubleClick:
    def test_double_click_runs_conversion_once(self, helpers, monkeypatch):
        calls = []
        _install(monkeypatch, calls, sleep=1.0)

        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                _fill(app)
                await pilot.pause()
                await pilot.click("#btn-convert")
                await pilot.pause()
                await pilot.click("#btn-convert")
                await pilot.pause()
                await helpers.wait_until(lambda: len(calls) == 1, pilot)
                assert calls[0][0] == "flync"

        helpers.run(_impl())


# ---------------------------------------------------------------------------
# TUI-N16  Modify during conversion
class TestModifyDuringConversion:
    def test_edit_field_while_converting(self, helpers, monkeypatch):
        calls = []
        _install(monkeypatch, calls, sleep=1.0)

        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                _fill(app, src_cfg="/tmp/orig")
                await pilot.pause()
                src = app.query_one("#source-panel-1", ConverterPanel)
                await pilot.click("#btn-convert")
                await pilot.pause()
                src.query_one("#field-source-panel-1-config_path").value = "/tmp/changed"
                await pilot.pause()
                await helpers.wait_until(lambda: len(calls) == 1, pilot)
                assert src.read_config().config_path == "/tmp/changed"

        helpers.run(_impl())


# ---------------------------------------------------------------------------
# TUI-N21  Close during conversion
class TestQuitDuringConversion:
    def test_quit_while_converting(self, helpers, monkeypatch):
        calls = []
        _install(monkeypatch, calls, sleep=1.5)

        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                _fill(app)
                await pilot.pause()
                await pilot.click("#btn-convert")
                await pilot.pause()
                await pilot.press("ctrl+q")
                await pilot.pause()
                assert app._closed

        helpers.run(_impl())


# ---------------------------------------------------------------------------
# TUI-R01..R13  Regression on the main flows
class TestRegression:
    def test_r01_happy_path(self, helpers, monkeypatch):
        calls = []
        _install(monkeypatch, calls)

        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                _fill(app)
                await pilot.pause()
                await pilot.click("#btn-convert")
                await helpers.wait_until(
                    lambda: "Conversion completed successfully." in helpers.log_text(app.query_one("#run-log")),
                    pilot,
                )
                assert len(calls) == 1

        helpers.run(_impl())

    def test_r02_button_state_cycle(self, helpers, monkeypatch):
        calls = []
        _install(monkeypatch, calls, sleep=0.5)

        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                _fill(app)
                await pilot.pause()
                btn = app.query_one("#btn-convert", Button)
                await pilot.click("#btn-convert")
                assert await helpers.wait_until(lambda: btn.disabled is True, pilot)
                assert await helpers.wait_until(lambda: btn.disabled is False, pilot)

        helpers.run(_impl())

    def test_r03_configured_conversion(self, helpers, monkeypatch):
        calls = []
        _install(monkeypatch, calls)

        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                src = app.query_one("#source-panel-1", ConverterPanel)
                dst = app.query_one("#destination-panel-1", ConverterPanel)
                await helpers.select_format(src, "json", pilot)
                await helpers.select_format(dst, "yaml", pilot)
                _fill(app)
                await pilot.pause()
                await pilot.click("#btn-convert")
                await helpers.wait_until(lambda: len(calls) == 1, pilot)
                assert calls[0][:2] == ("json", "yaml")

        helpers.run(_impl())

    def test_r04_multiple_conversions(self, helpers, monkeypatch):
        calls = []
        _install(monkeypatch, calls)

        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                _fill(app)
                await pilot.pause()
                btn = app.query_one("#btn-convert", Button)
                for i in range(2):
                    await pilot.pause()
                    btn.press()
                    await helpers.wait_until(lambda: len(calls) == i + 1, pilot)
                    await helpers.wait_until(lambda: btn.disabled is False, pilot)
                    await pilot.pause()
                assert len(calls) == 2

        helpers.run(_impl())

    def test_r05_error_reenables_button(self, helpers, monkeypatch):
        _install(monkeypatch, [], error="boom")

        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                _fill(app)
                await pilot.pause()
                btn = app.query_one("#btn-convert", Button)
                btn.press()
                log = app.query_one("#run-log")
                await helpers.wait_until(lambda: "Conversion failed: boom" in helpers.log_text(log) and not btn.disabled, pilot)
                assert "Conversion failed: boom" in helpers.log_text(log)
                assert btn.disabled is False

        helpers.run(_impl())


# ---------------------------------------------------------------------------
# E2E positive: startup → format selection → validation → successful conversion
class TestE2EPositive:
    def test_full_flow(self, helpers, monkeypatch):
        calls = []
        _install(monkeypatch, calls)

        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                # 1. Startup: layout present, default formats flync/flync.
                src = app.query_one("#source-panel-1", ConverterPanel)
                dst = app.query_one("#destination-panel-1", ConverterPanel)
                assert src.converter_type == "flync"
                assert dst.converter_type == "flync"
                # 2. Selecting other formats.
                await helpers.select_format(src, "json", pilot)
                await helpers.select_format(dst, "yaml", pilot)
                # 3. Filling in the fields (generated Pydantic representations).
                _fill(app)
                await pilot.pause()
                # 4. Conversion.
                await pilot.click("#btn-convert")
                await helpers.wait_until(
                    lambda: "Conversion completed successfully." in helpers.log_text(app.query_one("#run-log")),
                    pilot,
                )
                assert calls[0][:2] == ("json", "yaml")
                # 5. UI still responsive.
                assert app.is_running
                assert app.query_one("#run-log", Log) is not None

        helpers.run(_impl())


# ---------------------------------------------------------------------------
# E2E negative: validation fails, no conversion launched, no crash
class TestE2ENegative:
    def test_invalid_input_blocked(self, helpers, monkeypatch):
        calls = []
        _install(monkeypatch, calls)

        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                # Leaves the fields empty (config_path required).
                await pilot.click("#btn-convert")
                await pilot.pause()
                src = app.query_one("#source-panel-1", ConverterPanel)
                err = src.query_one("#error")
                assert "config_path" in str(err.render())
                assert calls == []
                assert app.is_running

        helpers.run(_impl())


def test_many_to_many_request_preserves_endpoint_order(helpers, monkeypatch):
    """Every configured endpoint is passed once and in visible order."""
    from unittest.mock import patch

    from flync_converter.cli.tui.widgets import ConverterPanelList

    captured = []
    monkeypatch.setattr("flync_converter.cli.tui.app.Converter.convert_request", lambda request: captured.append(request))

    async def _impl():
        app = FlyncTUI()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            sources = app.query_one("#source-panels", ConverterPanelList)
            destinations = app.query_one("#destination-panels", ConverterPanelList)
            await sources.add_panel()
            await destinations.add_panel()
            await pilot.pause()

            for index, panel in enumerate(sources.panels, start=1):
                panel.query_one(f"#field-{panel.id}-config_path").value = f"/tmp/source-{index}"
            for index, panel in enumerate(destinations.panels, start=1):
                panel.query_one(f"#field-{panel.id}-config_path").value = f"/tmp/output-{index}"

            with patch.object(app, "_no_preview", True):
                await pilot.click("#btn-convert")
            assert await helpers.wait_until(lambda: len(captured) == 1, pilot)
            request = captured[0]
            assert [str(item.path) for item in request.sources] == ["/tmp/source-1", "/tmp/source-2"]
            assert [str(item.path) for item in request.outputs] == ["/tmp/output-1", "/tmp/output-2"]

    helpers.run(_impl())
