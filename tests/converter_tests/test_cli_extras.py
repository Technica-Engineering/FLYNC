"""Tests for flync_converter CLI modules: types, dynamic, group, interactive, commands."""

import enum
from typing import Optional, Union
from unittest.mock import MagicMock, call, patch

import click
import pytest
from click.testing import CliRunner

from flync_converter.base import ConverterConfig
from flync_converter.cli.dynamic import DynamicConverterCommand
from flync_converter.cli.group import _open_gui, _open_tui
from flync_converter.cli.types import _annotation_to_click_type, _EnumNameType

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _Color(enum.Enum):
    RED = 1
    GREEN = 2
    BLUE = 3


# ---------------------------------------------------------------------------
# _EnumNameType
# ---------------------------------------------------------------------------


class TestEnumNameType:
    def test_init_stores_enum_cls_and_name(self):
        t = _EnumNameType(_Color)
        assert t.enum_cls is _Color
        assert t.name == "_Color"

    def test_get_metavar_lists_members(self):
        t = _EnumNameType(_Color)
        assert t.get_metavar(None) == "[RED|GREEN|BLUE]"

    def test_get_metavar_with_ctx(self):
        t = _EnumNameType(_Color)
        assert t.get_metavar(None, ctx=None) == "[RED|GREEN|BLUE]"

    def test_convert_already_enum_returns_same(self):
        t = _EnumNameType(_Color)
        assert t.convert(_Color.RED, None, None) is _Color.RED

    def test_convert_valid_name(self):
        t = _EnumNameType(_Color)
        assert t.convert("GREEN", None, None) is _Color.GREEN

    def test_convert_invalid_name_fails(self):
        t = _EnumNameType(_Color)
        with pytest.raises(click.exceptions.BadParameter):
            t.convert("PURPLE", None, None)


# ---------------------------------------------------------------------------
# _annotation_to_click_type
# ---------------------------------------------------------------------------


class TestAnnotationToClickType:
    def test_plain_bool(self):
        assert _annotation_to_click_type(bool) is click.BOOL

    def test_plain_int(self):
        assert _annotation_to_click_type(int) is click.INT

    def test_plain_float(self):
        assert _annotation_to_click_type(float) is click.FLOAT

    def test_plain_str(self):
        assert _annotation_to_click_type(str) is click.STRING

    def test_plain_object_fallback(self):
        assert _annotation_to_click_type(object) is click.STRING

    def test_optional_int_unwraps(self):
        assert _annotation_to_click_type(Optional[int]) is click.INT

    def test_optional_float_unwraps(self):
        assert _annotation_to_click_type(Optional[float]) is click.FLOAT

    def test_optional_bool_unwraps(self):
        assert _annotation_to_click_type(Optional[bool]) is click.BOOL

    def test_enum_returns_enum_name_type(self):
        result = _annotation_to_click_type(_Color)
        assert isinstance(result, _EnumNameType)
        assert result.enum_cls is _Color

    def test_optional_enum_unwraps(self):
        result = _annotation_to_click_type(Optional[_Color])
        assert isinstance(result, _EnumNameType)

    def test_union_no_none_args_falls_back(self):
        result = _annotation_to_click_type(Union[int, str])
        assert result is click.INT

    def test_none_type_annotation_falls_back_to_string(self):
        result = _annotation_to_click_type(type(None))
        assert result is click.STRING


# ---------------------------------------------------------------------------
# DynamicConverterCommand._prescan_value
# ---------------------------------------------------------------------------


class TestPrescanValue:
    def _cmd(self):
        return DynamicConverterCommand("test", callback=lambda: None)

    def test_flag_space_form(self):
        cmd = self._cmd()
        assert cmd._prescan_value(["--source-format", "dbc", "--other"], "--source-format") == "dbc"

    def test_flag_equals_form(self):
        cmd = self._cmd()
        assert cmd._prescan_value(["--source-format=dbc"], "--source-format") == "dbc"

    def test_flag_at_end_returns_none(self):
        cmd = self._cmd()
        assert cmd._prescan_value(["--source-format"], "--source-format") is None

    def test_flag_not_present_returns_none(self):
        cmd = self._cmd()
        assert cmd._prescan_value(["--other", "val"], "--source-format") is None

    def test_multiple_flags_first_match_wins(self):
        cmd = self._cmd()
        result = cmd._prescan_value(["-sf", "json", "--source-format", "dbc"], "-sf", "--source-format")
        assert result == "json"

    def test_short_flag_space_form(self):
        cmd = self._cmd()
        assert cmd._prescan_value(["-sf", "json"], "-sf", "--source-format") == "json"


# ---------------------------------------------------------------------------
# DynamicConverterCommand._inject_config_params
# ---------------------------------------------------------------------------


class TestInjectConfigParams:
    def _cmd(self):
        return DynamicConverterCommand("test", callback=lambda: None)

    def test_injects_non_path_fields(self):
        class MyConfig(ConverterConfig):
            extra_field: Optional[str] = None

        cmd = self._cmd()
        with patch("flync_converter.cli.dynamic.get_config_model", return_value=MyConfig):
            cmd._inject_config_params("myconv", "dst_")

        param_names = [p.name for p in cmd.params]
        assert "dst_extra_field" in param_names

    def test_skips_config_path(self):
        cmd = self._cmd()
        with patch("flync_converter.cli.dynamic.get_config_model", return_value=ConverterConfig):
            cmd._inject_config_params("myconv", "dst_")

        param_names = [p.name for p in cmd.params]
        assert "dst_config_path" not in param_names

    def test_no_duplicate_injection(self):
        class MyConfig(ConverterConfig):
            extra_field: Optional[str] = None

        cmd = self._cmd()
        with patch("flync_converter.cli.dynamic.get_config_model", return_value=MyConfig):
            cmd._inject_config_params("myconv", "dst_")
            cmd._inject_config_params("myconv", "dst_")

        count = sum(1 for p in cmd.params if p.name == "dst_extra_field")
        assert count == 1

    def test_exception_silently_suppressed(self):
        cmd = self._cmd()
        with patch("flync_converter.cli.dynamic.get_config_model", side_effect=RuntimeError("boom")):
            cmd._inject_config_params("broken", "src_")
        # no exception raised

    def test_no_model_fields_skips(self):
        cmd = self._cmd()
        with patch("flync_converter.cli.dynamic.get_config_model", return_value=object):
            cmd._inject_config_params("plain", "src_")
        # nothing injected — no crash


# ---------------------------------------------------------------------------
# DynamicConverterCommand.parse_args
# ---------------------------------------------------------------------------


class TestParseArgs:
    def test_parse_args_injects_for_src_and_dst(self):
        injected = []

        @click.command(cls=DynamicConverterCommand)
        @click.option("-sf", "--source-format", default=None)
        @click.option("-of", "--output-format", default="flync")
        def _cmd(source_format, output_format):
            pass

        with patch.object(DynamicConverterCommand, "_inject_config_params", side_effect=lambda *a: injected.append(a)):
            runner = CliRunner()
            runner.invoke(_cmd, ["-sf", "dbc", "-of", "json"])

        keys = [a[0] for a in injected]
        assert "dbc" in keys
        assert "json" in keys

    def test_parse_args_no_source_format(self):
        injected = []

        @click.command(cls=DynamicConverterCommand)
        @click.option("-sf", "--source-format", default=None)
        @click.option("-of", "--output-format", default="flync")
        def _cmd(source_format, output_format):
            pass

        with patch.object(DynamicConverterCommand, "_inject_config_params", side_effect=lambda *a: injected.append(a)):
            runner = CliRunner()
            runner.invoke(_cmd, ["-of", "json"])

        keys = [a[0] for a in injected]
        assert "dbc" not in keys
        assert "json" in keys


# ---------------------------------------------------------------------------
# group._open_tui / _open_gui
# ---------------------------------------------------------------------------


class TestOpenTui:
    def test_resilient_parsing_no_op(self):
        ctx = MagicMock()
        ctx.resilient_parsing = True
        _open_tui(ctx, None, True)
        ctx.exit.assert_not_called()

    def test_value_false_no_op(self):
        ctx = MagicMock()
        ctx.resilient_parsing = False
        _open_tui(ctx, None, False)
        ctx.exit.assert_not_called()

    def test_value_true_runs_tui_and_exits(self):
        import sys

        ctx = MagicMock()
        ctx.resilient_parsing = False
        mock_tui_mod = MagicMock()
        with patch.dict(sys.modules, {"flync_converter.cli.tui": mock_tui_mod}):
            _open_tui(ctx, None, True)
        mock_tui_mod.run_tui.assert_called_once()
        ctx.exit.assert_called_once()


class TestOpenGui:
    def test_resilient_parsing_no_op(self):
        ctx = MagicMock()
        ctx.resilient_parsing = True
        _open_gui(ctx, None, True)
        ctx.exit.assert_not_called()

    def test_value_false_no_op(self):
        ctx = MagicMock()
        ctx.resilient_parsing = False
        _open_gui(ctx, None, False)
        ctx.exit.assert_not_called()

    def test_value_true_runs_gui_and_exits(self):
        import sys

        ctx = MagicMock()
        ctx.resilient_parsing = False
        mock_gui_mod = MagicMock()
        with patch.dict(sys.modules, {"flync_converter.cli.gui": mock_gui_mod}):
            _open_gui(ctx, None, True)
        mock_gui_mod.run_gui.assert_called_once()
        ctx.exit.assert_called_once()


# ---------------------------------------------------------------------------
# interactive.select_converter
# ---------------------------------------------------------------------------


class TestSelectConverter:
    def test_numeric_choice_returns_converter_name(self):
        from flync_converter.cli.interactive import select_converter

        with (
            patch("flync_converter.cli.interactive.registry", {"dbc": MagicMock(), "json": MagicMock()}),
            patch("flync_converter.cli.interactive.Prompt.ask", return_value="1"),
            patch("flync_converter.cli.interactive.console"),
        ):
            result = select_converter("source")
        assert result == "dbc"

    def test_name_choice_returned_directly(self):
        from flync_converter.cli.interactive import select_converter

        with (
            patch("flync_converter.cli.interactive.registry", {"dbc": MagicMock(), "json": MagicMock()}),
            patch("flync_converter.cli.interactive.Prompt.ask", return_value="json"),
            patch("flync_converter.cli.interactive.console"),
        ):
            result = select_converter("destination")
        assert result == "json"


# ---------------------------------------------------------------------------
# interactive.interactive_configure_converter
# ---------------------------------------------------------------------------


class TestInteractiveConfigureConverter:
    def test_pydantic_path_returns_config(self):
        from flync_converter.cli.interactive import interactive_configure_converter

        class MyCfg(ConverterConfig):
            pass

        with (
            patch("flync_converter.cli.interactive.get_config_model", return_value=MyCfg),
            patch("flync_converter.cli.interactive.Prompt.ask", return_value="/tmp/x"),
            patch("flync_converter.cli.interactive.console"),
        ):
            result = interactive_configure_converter("myconv", "source")
        assert isinstance(result, MyCfg)

    def test_non_pydantic_fallback_returns_converter_config(self):
        from flync_converter.cli.interactive import interactive_configure_converter

        mock_cfg_cls = MagicMock(return_value=MagicMock(spec=ConverterConfig))

        with (
            patch("flync_converter.cli.interactive.get_config_model", return_value=object),
            patch("flync_converter.cli.interactive.Prompt.ask", return_value="/tmp/x"),
            patch("flync_converter.cli.interactive.ConverterConfig", mock_cfg_cls),
            patch("flync_converter.cli.interactive.console"),
        ):
            result = interactive_configure_converter("plain", "source")
        # common_fields: input_path, output_path, path all populated
        mock_cfg_cls.assert_called_once_with(input_path="/tmp/x", output_path="/tmp/x", path="/tmp/x")

    def test_pydantic_with_default_displays_default(self):
        from flync_converter.cli.interactive import interactive_configure_converter

        class MyCfg(ConverterConfig):
            extra: Optional[str] = "default_val"

        asked_labels = []

        def _fake_ask(label, default=None):
            asked_labels.append(label)
            # always return something non-empty so required fields are populated
            return default if default is not None else "/tmp/path"

        with (
            patch("flync_converter.cli.interactive.get_config_model", return_value=MyCfg),
            patch("flync_converter.cli.interactive.Prompt.ask", side_effect=_fake_ask),
            patch("flync_converter.cli.interactive.console"),
        ):
            interactive_configure_converter("myconv", "source")

        assert any("default_val" in lbl for lbl in asked_labels)

    def test_non_pydantic_skips_empty_fields(self):
        from flync_converter.cli.interactive import interactive_configure_converter

        mock_cfg_cls = MagicMock(return_value=MagicMock(spec=ConverterConfig))
        responses = iter(["", "", ""])

        with (
            patch("flync_converter.cli.interactive.get_config_model", return_value=object),
            patch("flync_converter.cli.interactive.Prompt.ask", side_effect=responses),
            patch("flync_converter.cli.interactive.ConverterConfig", mock_cfg_cls),
            patch("flync_converter.cli.interactive.console"),
        ):
            result = interactive_configure_converter("plain", "source")
        # called with no kwargs since all prompts returned empty
        mock_cfg_cls.assert_called_once_with()


# ---------------------------------------------------------------------------
# commands.list_converters
# ---------------------------------------------------------------------------


class TestListConverters:
    def test_no_converters_prints_warning(self):
        from flync_converter.cli.commands import list_converters

        runner = CliRunner()
        with patch("flync_converter.cli.commands.registry", {}):
            result = runner.invoke(list_converters, [])
        assert result.exit_code == 0

    def test_with_converters_lists_them(self):
        from flync_converter.cli.commands import list_converters

        fake_conv = MagicMock()
        fake_conv.__doc__ = "A test converter"

        runner = CliRunner()
        with patch("flync_converter.cli.commands.registry", {"myconv": fake_conv}):
            result = runner.invoke(list_converters, [])
        assert result.exit_code == 0

    def test_description_exception_uses_fallback(self):
        from flync_converter.cli.commands import list_converters

        fake_reg = MagicMock()
        fake_reg.keys.return_value = ["broken"]
        fake_reg.__getitem__ = MagicMock(side_effect=RuntimeError("nope"))

        runner = CliRunner()
        with patch("flync_converter.cli.commands.registry", fake_reg):
            result = runner.invoke(list_converters, [])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# commands.tui / gui
# ---------------------------------------------------------------------------


class TestTuiGuiCommands:
    def test_tui_command_calls_run_tui(self):
        import sys

        from flync_converter.cli.commands import tui

        mock_tui_mod = MagicMock()
        runner = CliRunner()
        with patch.dict(sys.modules, {"flync_converter.cli.tui": mock_tui_mod}):
            result = runner.invoke(tui, [])
        mock_tui_mod.run_tui.assert_called_once()
        assert result.exit_code == 0

    def test_gui_command_calls_run_gui(self):
        import sys

        from flync_converter.cli.commands import gui

        mock_gui_mod = MagicMock()
        runner = CliRunner()
        with patch.dict(sys.modules, {"flync_converter.cli.gui": mock_gui_mod}):
            result = runner.invoke(gui, [])
        mock_gui_mod.run_gui.assert_called_once()
        assert result.exit_code == 0

    def test_gui_import_error_raises_click_exception(self):
        import sys

        from flync_converter.cli.commands import gui

        runner = CliRunner()
        with patch.dict(sys.modules, {"flync_converter.cli.gui": None}):
            result = runner.invoke(gui, [])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# commands.convert — auto-detect and same-format paths
# ---------------------------------------------------------------------------


class TestConvertCommand:
    def test_same_format_exits_early(self):
        from flync_converter.cli.commands import convert

        runner = CliRunner()
        with patch("flync_converter.cli.commands.registry"):
            result = runner.invoke(convert, ["-s", "/src", "-o", "/dst", "-sf", "flync", "-of", "flync"])
        assert result.exit_code == 0
        assert "No conversion needed" in result.output

    def test_source_defaults_to_flync_same_as_output(self):
        import sys

        from flync_converter.cli.commands import convert

        fake_registry = MagicMock()
        mock_flync_mod = MagicMock()

        runner = CliRunner()
        with (
            patch("flync_converter.cli.commands.registry", fake_registry),
            patch("flync_converter.cli.commands.get_config_model", return_value=ConverterConfig),
            patch.dict(sys.modules, {"flync_converter": mock_flync_mod}),
        ):
            result = runner.invoke(convert, ["-s", "/src", "-o", "/dst", "-of", "flync"])
        assert "Source and output formats are the same" in result.output
        assert result.exit_code == 0
