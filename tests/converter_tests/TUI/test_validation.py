"""TUI validation behaviour: missing / invalid / unusual field inputs and robustness."""

import enum
import time

import pytest
from pydantic import Field, ValidationError
from textual.widgets import Input
from textual.widgets import Select as TextualSelect

from flync_converter.base import ConverterConfig
from flync_converter.cli.tui.app import FlyncTUI
from flync_converter.cli.tui.widgets.converter_panel import ConverterPanel


class RangedConfig(ConverterConfig):
    retries: int = Field(default=3, ge=1, le=10)


class Color(enum.Enum):
    RED = "red"
    GREEN = "green"


class EnumConfig(ConverterConfig):
    level: Color = Color.RED


def _raise_converter_class(error):
    class Fake:
        def convert(self, *a, **k):
            raise RuntimeError(error)

    return Fake


def _set(panel, name, value):
    panel.query_one(f"#field-{panel.id}-{name}", Input).value = value


# ---------------------------------------------------------------------------
# TUI-N01  Empty required field
class TestRequiredEmpty:
    def test_missing_required_field_raises(self, helpers):
        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                source = app.query_one("#source-panel", ConverterPanel)
                with pytest.raises(ValidationError):
                    source.read_config()

        helpers.run(_impl())


# ---------------------------------------------------------------------------
# TUI-N02  Invalid value for a field
# TUI-N03  Wrong type
class TestInvalidValues:
    def test_non_numeric_in_int_field(self, helpers):
        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                source = app.query_one("#source-panel", ConverterPanel)
                await helpers.select_format(source, "dbc", pilot)
                _set(source, "baud_rate_default", "abc")
                with pytest.raises(ValidationError):
                    source.read_config()

        helpers.run(_impl())

    def test_wrong_type_rejected(self, helpers):
        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                source = app.query_one("#source-panel", ConverterPanel)
                await helpers.select_format(source, "dbc", pilot)
                _set(source, "baud_rate_default", "not-an-int")
                with pytest.raises(ValidationError):
                    source.read_config()

        helpers.run(_impl())


# ---------------------------------------------------------------------------
# TUI-N04  Out-of-range value
class TestOutOfRange:
    def test_out_of_range_int(self, helpers):
        with helpers.register("n04range", RangedConfig) as name:

            async def _impl():
                app = FlyncTUI()
                async with app.run_test() as pilot:
                    await pilot.pause()
                    source = app.query_one("#source-panel", ConverterPanel)
                    await helpers.select_format(source, name, pilot)
                    _set(source, "retries", "99")
                    with pytest.raises(ValidationError):
                        source.read_config()

            helpers.run(_impl())


# ---------------------------------------------------------------------------
# TUI-N05  Invalid source config
# TUI-N06  Invalid destination config
class TestInvalidPanelConfig:
    def test_invalid_source_shows_error_and_skips(self, helpers, monkeypatch):
        calls = []
        monkeypatch.setattr("flync_converter.cli.tui.app.Converter", _raise_converter_class("boom"))

        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                source = app.query_one("#source-panel", ConverterPanel)
                await pilot.click("#btn-convert")
                await pilot.pause()
                err = source.query_one("#error")
                assert "config_path" in str(err.render())
                assert calls == []

        helpers.run(_impl())

    def test_invalid_destination_shows_error_and_skips(self, helpers, monkeypatch):
        calls = []
        monkeypatch.setattr("flync_converter.cli.tui.app.Converter", _raise_converter_class("boom"))

        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                source = app.query_one("#source-panel", ConverterPanel)
                helpers.set_config_path(source, "/tmp/only-source")
                dest = app.query_one("#dest-panel", ConverterPanel)
                await pilot.pause()
                await pilot.click("#btn-convert")
                await pilot.pause()
                err = dest.query_one("#error")
                assert "config_path" in str(err.render())
                assert calls == []

        helpers.run(_impl())


# ---------------------------------------------------------------------------
# TUI-N07  Source / destination incompatibility
class TestIncompatiblePair:
    def test_same_type_runs_without_crash(self, helpers):
        calls = []

        class Fake:
            def convert(self, *a, **k):
                calls.append(1)

        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr("flync_converter.cli.tui.app.Converter", Fake)

        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                helpers.set_config_path(app.query_one("#source-panel", ConverterPanel), "/tmp/a")
                helpers.set_config_path(app.query_one("#dest-panel", ConverterPanel), "/tmp/b")
                await pilot.pause()
                await pilot.click("#btn-convert")
                await helpers.wait_until(lambda: len(calls) == 1, pilot)
                assert calls == [1]

        helpers.run(_impl())


# ---------------------------------------------------------------------------
# TUI-N08  Nonexistent file
class TestMissingFile:
    def test_missing_file_reported_on_log(self, helpers, monkeypatch):
        monkeypatch.setattr(
            "flync_converter.cli.tui.app.Converter",
            _raise_converter_class("No such file"),
        )

        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                helpers.set_config_path(app.query_one("#source-panel", ConverterPanel), "/nonexistent/src")
                helpers.set_config_path(app.query_one("#dest-panel", ConverterPanel), "/nonexistent/dst")
                await pilot.pause()
                await pilot.click("#btn-convert")
                await helpers.wait_until(lambda: "Conversion failed" in helpers.log_text(app.query_one("#run-log")), pilot)

        helpers.run(_impl())


# ---------------------------------------------------------------------------
# TUI-N09  Empty path
class TestEmptyPath:
    def test_empty_path_is_required(self, helpers):
        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                source = app.query_one("#source-panel", ConverterPanel)
                _set(source, "config_path", "   ")
                with pytest.raises(ValidationError):
                    source.read_config()

        helpers.run(_impl())


# ---------------------------------------------------------------------------
# TUI-N10  Special characters in the path
class TestSpecialCharacters:
    def test_special_char_path_accepted(self, helpers):
        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                source = app.query_one("#source-panel", ConverterPanel)
                helpers.set_config_path(source, "C:/My Folder/file name(with)stuff.dbc")
                cfg = source.read_config()
                assert cfg.config_path == "C:/My Folder/file name(with)stuff.dbc"

        helpers.run(_impl())


# ---------------------------------------------------------------------------
# TUI-N11  Very long value
class TestVeryLong:
    def test_very_long_value_accepted(self, helpers):
        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                source = app.query_one("#source-panel", ConverterPanel)
                long_path = "/tmp/" + "x" * 5000
                helpers.set_config_path(source, long_path)
                cfg = source.read_config()
                assert cfg.config_path == long_path

        helpers.run(_impl())


# ---------------------------------------------------------------------------
# TUI-N12  Unicode value
class TestUnicode:
    def test_unicode_value_accepted(self, helpers):
        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                source = app.query_one("#source-panel", ConverterPanel)
                unicode_path = "/tmp/éàç-表-😀"
                helpers.set_config_path(source, unicode_path)
                cfg = source.read_config()
                assert cfg.config_path == unicode_path

        helpers.run(_impl())


# ---------------------------------------------------------------------------
# TUI-N16  Modify during conversion
class TestModifyDuringConversion:
    def test_modify_field_while_converting(self, helpers):
        calls = []

        class Slow:
            def convert(self, *a, **k):
                calls.append(1)
                time.sleep(1.0)

        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr("flync_converter.cli.tui.app.Converter", Slow)

        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                source = app.query_one("#source-panel", ConverterPanel)
                helpers.set_config_path(source, "/tmp/src")
                helpers.set_config_path(app.query_one("#dest-panel", ConverterPanel), "/tmp/dst")
                await pilot.pause()
                await pilot.click("#btn-convert")
                await pilot.pause()
                helpers.set_config_path(source, "/tmp/changed-mid")
                await pilot.pause()
                await helpers.wait_until(lambda: len(calls) == 1, pilot)
                assert source.read_config().config_path == "/tmp/changed-mid"

        helpers.run(_impl())


# ---------------------------------------------------------------------------
# TUI-N18  Misconfigured plugin
class TestPluginMisconfigured:
    def test_misconfigured_plugin_does_not_crash(self, helpers):
        with helpers.register("n18bad", object) as name:

            async def _impl():
                app = FlyncTUI()
                async with app.run_test() as pilot:
                    await pilot.pause()
                    source = app.query_one("#source-panel", ConverterPanel)
                    await helpers.select_format(source, name, pilot)
                    assert source.converter_type == name
                    assert app.query_one("#source-panel") is not None

            helpers.run(_impl())


# ---------------------------------------------------------------------------
# TUI-N19  Plugin without expected model
class TestPluginNoConfig:
    def test_plugin_without_config_falls_back(self, helpers):
        with helpers.register("n19plain", ConverterConfig) as name:

            async def _impl():
                app = FlyncTUI()
                async with app.run_test() as pilot:
                    await pilot.pause()
                    source = app.query_one("#source-panel", ConverterPanel)
                    await helpers.select_format(source, name, pilot)
                    helpers.set_config_path(source, "/tmp/x")
                    cfg = source.read_config()
                    assert isinstance(cfg, ConverterConfig)

            helpers.run(_impl())


# ---------------------------------------------------------------------------
# TUI-N24  Unknown format
class TestUnknownFormat:
    def test_unknown_format_is_not_registered(self, helpers):
        unknown = "not-a-registered-format"
        from flync_converter import registry as core_registry

        assert unknown not in core_registry.keys()

        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                source = app.query_one("#source-panel", ConverterPanel)
                assert app.query_one("#source-panel") is not None

        helpers.run(_impl())


# ---------------------------------------------------------------------------
# TUI-P11  Modifying a text field
# TUI-P12  Modifying an Enum
class TestPositiveModify:
    def test_modify_text_reflected_in_config(self, helpers):
        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                source = app.query_one("#source-panel", ConverterPanel)
                helpers.set_config_path(source, "/tmp/edited")
                assert source.read_config().config_path == "/tmp/edited"

        helpers.run(_impl())

    def test_modify_enum_reflected_in_config(self, helpers):
        with helpers.register("p12color", EnumConfig) as name:

            async def _impl():
                app = FlyncTUI()
                async with app.run_test() as pilot:
                    await pilot.pause()
                    source = app.query_one("#source-panel", ConverterPanel)
                    await helpers.select_format(source, name, pilot)
                    helpers.set_config_path(source, "/tmp/x")
                    en = source.query_one("#field-source-panel-level", TextualSelect)
                    en.value = Color.GREEN.value
                    assert source.read_config().level == Color.GREEN

            helpers.run(_impl())
