"""TUI startup, layout, default formats, dynamic fields, and positive field tests."""

import enum

import pytest
from textual.widgets import Button, Input, Select

from flync_converter.base import ConverterConfig
from flync_converter.cli.tui.app import FlyncTUI
from flync_converter.cli.tui.widgets.converter_panel import ConverterPanel
from flync_converter.utils import get_config_model

# ---------- config models used only by the dynamic-field tests ----------


class Color(enum.Enum):
    RED = "red"
    GREEN = "green"


class RichConfig(ConverterConfig):
    """A config exposing every field kind the panel must render."""

    output_structure: str = "flat"
    encoding: str = "utf-8"
    indent: int = 2
    retries: int = 3
    flag: bool = False
    level: Color = Color.RED
    mode: Color = Color.GREEN
    name: str = ""


class ColorConfig(ConverterConfig):
    level: Color = Color.RED


class NoExtraConfig(ConverterConfig):
    """Only inherits the required config_path field."""


def _field_stats(panel):
    """Return (inputs, selects) present in the dynamically built fields area."""
    container = panel.query_one("#fields")
    inputs = 0
    selects = 0
    for child in container.children:
        if isinstance(child, Input):
            inputs += 1
        elif isinstance(child, Select):
            selects += 1
    return inputs, selects


def _field_names(panel):
    container = panel.query_one("#fields")
    return [getattr(c, "id", None) for c in container.children if isinstance(c, (Input, Select))]


# ---------------------------------------------------------------------------
# TUI-P01  TUI startup
# TUI-P02  Layout display
class TestStartupLayout:
    def test_app_launches(self, helpers):
        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                assert app.is_running

        helpers.run(_impl())

    def test_layout_widgets_are_present(self, helpers):
        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                for selector in (
                    "#panels",
                    "#source-panel",
                    "#dest-panel",
                    "#run-log",
                    "#btn-row",
                    "#log-level-select",
                    "#btn-convert",
                ):
                    assert app.query_one(selector) is not None

        helpers.run(_impl())


# ---------------------------------------------------------------------------
# TUI-P03  Default Source format
# TUI-P04  Default Destination format
class TestDefaultFormats:
    def test_source_defaults_to_flync(self, helpers):
        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                source = app.query_one("#source-panel", ConverterPanel)
                assert source.converter_type == "flync"

        helpers.run(_impl())

    def test_destination_defaults_to_flync(self, helpers):
        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                dest = app.query_one("#dest-panel", ConverterPanel)
                assert dest.converter_type == "flync"

        helpers.run(_impl())


# ---------------------------------------------------------------------------
# TUI-P05  Selecting a Source format
# TUI-P06  Selecting a Destination format
class TestFormatSelection:
    def test_select_source_format(self, helpers):
        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                source = app.query_one("#source-panel", ConverterPanel)
                await helpers.select_format(source, "dbc", pilot)
                assert source.converter_type == "dbc"

        helpers.run(_impl())

    def test_select_destination_format(self, helpers):
        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                dest = app.query_one("#dest-panel", ConverterPanel)
                await helpers.select_format(dest, "yaml", pilot)
                assert dest.converter_type == "yaml"

        helpers.run(_impl())


# ---------------------------------------------------------------------------
# TUI-P07  Dynamic field changes
# TUI-P08  Required field
# TUI-P09  Optional field
# TUI-P10  Enum field
# TUI-P11  Modifying a text field
# TUI-P12  Modifying an Enum
class TestDynamicFields:
    def test_fields_change_with_format(self, helpers):
        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                source = app.query_one("#source-panel", ConverterPanel)
                flync_fields = _field_names(source)
                await helpers.select_format(source, "dbc", pilot)
                dbc_fields = _field_names(source)
                assert flync_fields != dbc_fields
                assert "field-source-panel-baud_rate_default" in dbc_fields

        helpers.run(_impl())

    def test_required_field_placeholder(self, helpers):
        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                source = app.query_one("#source-panel", ConverterPanel)
                inp = source.query_one("#field-source-panel-config_path", Input)
                assert inp.placeholder == "required"

        helpers.run(_impl())

    def test_optional_field_shows_default(self, helpers):
        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                source = app.query_one("#source-panel", ConverterPanel)
                await helpers.select_format(source, "dbc", pilot)
                baud = source.query_one("#field-source-panel-baud_rate_default", Input)
                assert baud.value == "500000"

        helpers.run(_impl())

    def test_enum_field_renders_as_select(self, helpers):
        with helpers.register("p10color", ColorConfig) as name:

            async def _impl():
                app = FlyncTUI()
                async with app.run_test() as pilot:
                    await pilot.pause()
                    source = app.query_one("#source-panel", ConverterPanel)
                    await helpers.select_format(source, name, pilot)
                    inputs, selects = _field_stats(source)
                    assert selects >= 1

            helpers.run(_impl())

    def test_modify_text_field(self, helpers):
        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                source = app.query_one("#source-panel", ConverterPanel)
                helpers.set_config_path(source, "/tmp/custom")
                cfg = source.read_config()
                assert cfg.config_path == "/tmp/custom"

        helpers.run(_impl())

    def test_modify_enum_field(self, helpers):
        with helpers.register("p12color", ColorConfig) as name:

            async def _impl():
                app = FlyncTUI()
                async with app.run_test() as pilot:
                    await pilot.pause()
                    source = app.query_one("#source-panel", ConverterPanel)
                    await helpers.select_format(source, name, pilot)
                    helpers.set_config_path(source, "/tmp/x")
                    enum_sel = source.query_one("#field-source-panel-level", Select)
                    enum_sel.value = Color.GREEN.value
                    cfg = source.read_config()
                    assert cfg.level == Color.GREEN

            helpers.run(_impl())


# ---------------------------------------------------------------------------
# TUI-P24  Additional dynamic fields
class TestExtraDynamicFields:
    def test_rich_config_renders_all_field_kinds(self, helpers):
        with helpers.register("p24rich", RichConfig) as name:

            async def _impl():
                app = FlyncTUI()
                async with app.run_test() as pilot:
                    await pilot.pause()
                    source = app.query_one("#source-panel", ConverterPanel)
                    await helpers.select_format(source, name, pilot)
                    inputs, selects = _field_stats(source)
                    # config_path + output_structure + encoding + indent + retries + flag + name
                    assert inputs >= 7
                    # level + mode
                    assert selects >= 2

            helpers.run(_impl())


# ---------------------------------------------------------------------------
# TUI-D01  Model with required fields only
class TestDRequiredOnly:
    def test_required_only(self, helpers):
        with helpers.register("d01req", NoExtraConfig) as name:

            async def _impl():
                app = FlyncTUI()
                async with app.run_test() as pilot:
                    await pilot.pause()
                    source = app.query_one("#source-panel", ConverterPanel)
                    await helpers.select_format(source, name, pilot)
                    inputs, selects = _field_stats(source)
                    assert inputs == 1
                    assert selects == 0

            helpers.run(_impl())


# ---------------------------------------------------------------------------
# TUI-D02  Model with optional fields
# TUI-D03  str field
# TUI-D04  int field
# TUI-D05  bool field
# TUI-D06  Enum field
# TUI-D07  Multiple Enums
# TUI-D08  Model without fields
class TestDFieldKinds:
    def test_optional_fields_present(self, helpers):
        with helpers.register("d02opt", RichConfig) as name:

            async def _impl():
                app = FlyncTUI()
                async with app.run_test() as pilot:
                    await pilot.pause()
                    source = app.query_one("#source-panel", ConverterPanel)
                    await helpers.select_format(source, name, pilot)
                    inputs, selects = _field_stats(source)
                    assert inputs > 1

            helpers.run(_impl())

    def test_str_int_bool_enum_fields(self, helpers):
        with helpers.register("d03rich", RichConfig) as name:

            async def _impl():
                app = FlyncTUI()
                async with app.run_test() as pilot:
                    await pilot.pause()
                    source = app.query_one("#source-panel", ConverterPanel)
                    await helpers.select_format(source, name, pilot)
                    # str
                    assert isinstance(source.query_one("#field-source-panel-name", Input), Input)
                    # int (default 2)
                    assert source.query_one("#field-source-panel-indent", Input).value == "2"
                    # bool (default False)
                    assert source.query_one("#field-source-panel-flag", Input).value == "False"
                    # enum -> Select
                    assert isinstance(source.query_one("#field-source-panel-level", Select), Select)

            helpers.run(_impl())

    def test_multiple_enums(self, helpers):
        with helpers.register("d07multienum", RichConfig) as name:

            async def _impl():
                app = FlyncTUI()
                async with app.run_test() as pilot:
                    await pilot.pause()
                    source = app.query_one("#source-panel", ConverterPanel)
                    await helpers.select_format(source, name, pilot)
                    assert isinstance(source.query_one("#field-source-panel-level", Select), Select)
                    assert isinstance(source.query_one("#field-source-panel-mode", Select), Select)

            helpers.run(_impl())

    def test_model_without_extra_fields(self, helpers):
        with helpers.register("d08none", NoExtraConfig) as name:

            async def _impl():
                app = FlyncTUI()
                async with app.run_test() as pilot:
                    await pilot.pause()
                    source = app.query_one("#source-panel", ConverterPanel)
                    await helpers.select_format(source, name, pilot)
                    inputs, selects = _field_stats(source)
                    assert inputs == 1
                    assert selects == 0

            helpers.run(_impl())


# ---------------------------------------------------------------------------
# TUI-D09  output_structure present
# TUI-D10  encoding present
# TUI-D11  indent present
class TestD9D10D11NamedFields:
    def test_named_fields_rendered(self, helpers):
        with helpers.register("d910rich", RichConfig) as name:

            async def _impl():
                app = FlyncTUI()
                async with app.run_test() as pilot:
                    await pilot.pause()
                    source = app.query_one("#source-panel", ConverterPanel)
                    await helpers.select_format(source, name, pilot)
                    assert source.query_one("#field-source-panel-output_structure", Input).value == "flat"
                    assert source.query_one("#field-source-panel-encoding", Input).value == "utf-8"
                    assert source.query_one("#field-source-panel-indent", Input).value == "2"

            helpers.run(_impl())


# ---------------------------------------------------------------------------
# TUI-D12  Format modification
# TUI-D13  Transition Format A → B → A
class TestDFormatSwitching:
    def test_switch_format_rebuilds_fields(self, helpers):
        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                source = app.query_one("#source-panel", ConverterPanel)
                a = _field_names(source)  # flync
                await helpers.select_format(source, "dbc", pilot)
                b = _field_names(source)
                assert a != b

        helpers.run(_impl())

    def test_a_to_b_to_a(self, helpers):
        async def _impl():
            app = FlyncTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                source = app.query_one("#source-panel", ConverterPanel)
                fields_a = _field_names(source)  # flync
                await helpers.select_format(source, "dbc", pilot)
                await helpers.select_format(source, "flync", pilot)
                fields_a_again = _field_names(source)
                assert fields_a == fields_a_again

        helpers.run(_impl())


# ---------------------------------------------------------------------------
# TUI-N17  Format not selected
class TestNoSelection:
    def test_read_config_raises_without_selection(self):
        panel = ConverterPanel("Source")
        with pytest.raises(RuntimeError, match="No converter type selected"):
            panel.read_config()


# ---------------------------------------------------------------------------
# TUI-N18  Misconfigured plugin
class TestPluginMisconfigured:
    def test_misconfigured_falls_back_to_base_fields(self, helpers):
        # config_model not recognisable -> get_config_model falls back to ConverterConfig.
        with helpers.register("n18bad", object) as name:

            async def _impl():
                app = FlyncTUI()
                async with app.run_test() as pilot:
                    await pilot.pause()
                    source = app.query_one("#source-panel", ConverterPanel)
                    await helpers.select_format(source, name, pilot)
                    inputs, selects = _field_stats(source)
                    assert inputs >= 1  # config_path still rendered, no crash

            helpers.run(_impl())


# ---------------------------------------------------------------------------
# TUI-N19  Plugin without expected model
class TestPluginNoConfig:
    def test_no_config_plugin_falls_back(self, helpers):
        with helpers.register("n19plain", ConverterConfig) as name:

            async def _impl():
                app = FlyncTUI()
                async with app.run_test() as pilot:
                    await pilot.pause()
                    source = app.query_one("#source-panel", ConverterPanel)
                    await helpers.select_format(source, name, pilot)
                    inputs, selects = _field_stats(source)
                    assert inputs >= 1

            helpers.run(_impl())


# ---------------------------------------------------------------------------
# TUI-N24  Unknown format
class TestUnknownFormat:
    def test_get_config_model_unknown_returns_base(self):
        assert get_config_model("definitely_not_a_converter") is ConverterConfig


# ---------------------------------------------------------------------------
# TUI-N20  Very small terminal
class TestSmallTerminal:
    def test_app_runs_on_small_terminal(self, helpers):
        async def _impl():
            app = FlyncTUI()
            async with app.run_test(size=(30, 8)) as pilot:
                await pilot.pause()
                assert app.query_one("#btn-convert", Button) is not None
                assert app.is_running

        helpers.run(_impl())
