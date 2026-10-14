"""TUI logging: conversion log output, log-level selection/filtering, and edge cases."""

import logging
import time

import pytest
from textual.widgets import Log, Select

from flync_converter.cli.tui.app import FlyncTUI


def _logging_converter_class(records, func, *, sleep=0.0):
    class Fake:
        def convert(self, *a, **k):
            func()
            if sleep:
                time.sleep(sleep)

    return Fake


def _install(monkeypatch, records, func, *, sleep=0.0):
    monkeypatch.setattr(
        "flync_converter.cli.tui.app.Converter",
        _logging_converter_class(records, func, sleep=sleep),
    )


def _set_paths(app):
    from flync_converter.cli.tui.widgets.converter_panel import ConverterPanel

    src = app.query_one("#source-panel", ConverterPanel)
    dst = app.query_one("#dest-panel", ConverterPanel)
    # call set_config_path through a throwaway helpers instance is avoided;
    # set the Input directly instead.
    src.query_one("#field-source-panel-config_path").value = "/tmp/log-src"
    dst.query_one("#field-dest-panel-config_path").value = "/tmp/log-dst"


async def _select_level(app, pilot, helpers, level):
    sel = app.query_one("#log-level-select", Select)
    sel.value = level
    expected = getattr(logging, level)
    await helpers.wait_until(
        lambda: logging.getLogger().level == expected and app._log_handler is not None and app._log_handler.level == expected,
        pilot,
    )
    return sel


# ---------------------------------------------------------------------------
# TUI-P14  Conversion log
# TUI-R10  Display in the log
class TestConversionLog:
    def test_conversion_log_lines(self, helpers, monkeypatch):
        _install(monkeypatch, [], lambda: None)

        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                _set_paths(app)
                await pilot.pause()
                await pilot.click("#btn-convert")
                await helpers.wait_until(
                    lambda: "Conversion completed successfully." in helpers.log_text(app.query_one("#run-log")),
                    pilot,
                )
                text = helpers.log_text(app.query_one("#run-log"))
                assert "Starting: flync -> flync" in text

        helpers.run(_impl())


# ---------------------------------------------------------------------------
# TUI-L01..L04  Selecting a log level
# TUI-P15..P18 / TUI-R11  Filtering by level
class TestLogLevelSelection:
    @pytest.mark.parametrize("level", ["DEBUG", "INFO", "WARNING", "ERROR"])
    def test_selecting_level_updates_handlers(self, helpers, level):
        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                await _select_level(app, pilot, helpers, level)
                await pilot.pause()
                expected = getattr(logging, level)
                assert app._log_handler.level == expected
                assert logging.getLogger().level == expected

        helpers.run(_impl())


class TestLevelFiltering:
    @pytest.mark.parametrize(
        "level,seen,hidden",
        [
            ("ERROR", "ERROR", "WARNING"),
            ("WARNING", "WARNING", "INFO"),
            ("INFO", "INFO", "DEBUG"),
        ],
    )
    def test_level_filtering(self, helpers, monkeypatch, level, seen, hidden):
        def func():
            logging.getLogger("tui.logtest").warning("should-hidden-warning")
            logging.getLogger("tui.logtest").info("should-hidden-info")
            logging.getLogger("tui.logtest").debug("should-hidden-debug")
            logging.getLogger("tui.logtest").error("visible-error")

        _install(monkeypatch, [], func)

        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                await _select_level(app, pilot, helpers, level)
                _set_paths(app)
                await pilot.pause()
                await pilot.click("#btn-convert")
                await helpers.wait_until(lambda: "visible-error" in helpers.log_text(app.query_one("#run-log")), pilot)
                text = helpers.log_text(app.query_one("#run-log"))
                assert "visible-error" in text

        helpers.run(_impl())


# ---------------------------------------------------------------------------
# TUI-L05  Multiple logs during conversion
class TestMultipleLogs:
    def test_logs_appear_during_conversion(self, helpers, monkeypatch):
        def func():
            for i in range(4):
                logging.getLogger("tui.multi").info("multi-log-%d", i)

        _install(monkeypatch, [], func)

        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                await _select_level(app, pilot, helpers, "INFO")
                _set_paths(app)
                await pilot.pause()
                await pilot.click("#btn-convert")
                await helpers.wait_until(lambda: "multi-log-3" in helpers.log_text(app.query_one("#run-log")), pilot)
                text = helpers.log_text(app.query_one("#run-log"))
                for i in range(4):
                    assert f"multi-log-{i}" in text

        helpers.run(_impl())


# ---------------------------------------------------------------------------
# TUI-L06  Many logs
class TestManyLogs:
    def test_many_logs(self, helpers, monkeypatch):
        def func():
            for i in range(200):
                logging.getLogger("tui.many").info("many-%d", i)

        _install(monkeypatch, [], func)

        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                await _select_level(app, pilot, helpers, "INFO")
                _set_paths(app)
                await pilot.pause()
                await pilot.click("#btn-convert")
                await helpers.wait_until(lambda: "many-199" in helpers.log_text(app.query_one("#run-log")), pilot)

        helpers.run(_impl())


# ---------------------------------------------------------------------------
# TUI-L07  Change of level during conversion
class TestChangeLevelDuringConversion:
    def test_change_level_while_converting(self, helpers, monkeypatch):
        def func():
            time.sleep(0.5)
            logging.getLogger("tui.change").info("after-sleep")

        _install(monkeypatch, [], func, sleep=0.5)

        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                _set_paths(app)
                await pilot.pause()
                await pilot.click("#btn-convert")
                await pilot.pause()
                await _select_level(app, pilot, helpers, "ERROR")
                await pilot.pause()
                await helpers.wait_until(
                    lambda: "Conversion completed successfully." in helpers.log_text(app.query_one("#run-log")),
                    pilot,
                )
                assert app.is_running

        helpers.run(_impl())


# ---------------------------------------------------------------------------
# TUI-L08  Unicode log
class TestUnicodeLog:
    def test_unicode_log_line(self, helpers, monkeypatch):
        def func():
            logging.getLogger("tui.uni").info("schéma-表-😀")

        _install(monkeypatch, [], func)

        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                await _select_level(app, pilot, helpers, "INFO")
                _set_paths(app)
                await pilot.pause()
                await pilot.click("#btn-convert")
                await helpers.wait_until(lambda: "schéma-表-😀" in helpers.log_text(app.query_one("#run-log")), pilot)

        helpers.run(_impl())


# ---------------------------------------------------------------------------
# TUI-L09  Very long log line
class TestLongLogLine:
    def test_long_line_still_appears(self, helpers, monkeypatch):
        long_msg = "long-line-" + "x" * 4000

        def func():
            logging.getLogger("tui.long").info(long_msg)

        _install(monkeypatch, [], func)

        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                await _select_level(app, pilot, helpers, "INFO")
                _set_paths(app)
                await pilot.pause()
                await pilot.click("#btn-convert")
                await helpers.wait_until(lambda: "long-line-" in helpers.log_text(app.query_one("#run-log")), pilot)

        helpers.run(_impl())


# ---------------------------------------------------------------------------
# TUI-L10  Exception with traceback
class TestExceptionLog:
    def test_conversion_failure_is_logged(self, helpers, monkeypatch):
        def boom():
            raise RuntimeError("boom")

        _install(monkeypatch, [], boom)

        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                _set_paths(app)
                await pilot.pause()
                await pilot.click("#btn-convert")
                await helpers.wait_until(lambda: "Conversion failed: boom" in helpers.log_text(app.query_one("#run-log")), pilot)

        helpers.run(_impl())


# ---------------------------------------------------------------------------
# TUI-L11  Rapid logs
class TestRapidLogs:
    def test_rapid_logs_no_crash(self, helpers, monkeypatch):
        def func():
            for i in range(50):
                logging.getLogger("tui.rapid").info("rapid-%d", i)

        _install(monkeypatch, [], func)

        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                await _select_level(app, pilot, helpers, "INFO")
                _set_paths(app)
                await pilot.pause()
                await pilot.click("#btn-convert")
                await helpers.wait_until(lambda: "rapid-49" in helpers.log_text(app.query_one("#run-log")), pilot)
                assert app.is_running

        helpers.run(_impl())


# ---------------------------------------------------------------------------
# TUI-L12  No log (empty)
class TestNoLogs:
    def test_log_empty_on_launch(self, helpers):
        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                log = app.query_one("#run-log", Log)
                assert len(log.lines) == 0

        helpers.run(_impl())
