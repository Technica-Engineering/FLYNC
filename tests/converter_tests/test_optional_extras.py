"""Tests for the optional extras mechanism (flync[tui], flync[gui]).

Verifies that the _optional module correctly gates imports behind
``find_spec`` probes, and that missing extras produce actionable
ClickExceptions — never tracebacks.
"""

import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import click
import pytest
from click.testing import CliRunner

from flync_converter.cli._optional import _require, load_run_gui, load_run_tui
from flync_converter.cli.group import cli


class TestRequire:
    def test_passes_when_module_is_present(self):
        # ``click`` is always installed — _require should return None
        result = _require("click", "tui", "x")
        assert result is None

    def test_raises_click_exception_when_module_is_absent(self):
        with patch("flync_converter.cli._optional.find_spec", return_value=None):
            with pytest.raises(click.ClickException) as exc_info:
                _require("textual", "gui", "The desktop GUI")
            assert "flync[gui]" in str(exc_info.value.message)
            assert "textual" in str(exc_info.value.message)


class TestLoadRunTuiMissing:
    def test_raises_click_exception_with_install_hint(self):
        with patch("flync_converter.cli._optional.find_spec", return_value=None):
            with pytest.raises(click.ClickException) as exc_info:
                load_run_tui()
            assert "textual" in str(exc_info.value.message)
            assert "flync[tui]" in str(exc_info.value.message)


class TestLoadRunGuiMissing:
    def test_raises_click_exception_with_install_hint(self):
        with patch("flync_converter.cli._optional.find_spec", return_value=None):
            with pytest.raises(click.ClickException) as exc_info:
                load_run_gui()
            assert "PySide6" in str(exc_info.value.message)
            assert "flync[gui]" in str(exc_info.value.message)


class TestCliGuiSubcommandMissingExtra:
    def test_exit_code_1_and_install_hint(self):
        runner = CliRunner()
        with patch("flync_converter.cli._optional.find_spec", return_value=None):
            result = runner.invoke(cli, ["gui"])
        assert result.exit_code == 1
        assert "flync[gui]" in result.output


class TestLoadersWhenExtraPresent:
    """The probe passes, so the loader imports the front-end and returns its runner.

    The front-end packages themselves need textual/PySide6, which a core install
    does not have, so they are stubbed into ``sys.modules``.
    """

    def test_load_run_tui_returns_run_tui(self):
        stub = ModuleType("flync_converter.cli.tui")
        stub.run_tui = MagicMock()
        with patch("flync_converter.cli._optional.find_spec", return_value=object()):
            with patch.dict(sys.modules, {"flync_converter.cli.tui": stub}):
                assert load_run_tui() is stub.run_tui

    def test_load_run_gui_returns_run_gui(self):
        stub = ModuleType("flync_converter.cli.gui")
        stub.run_gui = MagicMock()
        with patch("flync_converter.cli._optional.find_spec", return_value=object()):
            with patch.dict(sys.modules, {"flync_converter.cli.gui": stub}):
                assert load_run_gui() is stub.run_gui


class TestRealImportErrorPropagates:
    """A broken optional module and a missing one are different failures (I3).

    ``find_spec`` reports the third-party dependency as present, so ``_require``
    passes; the ImportError then raised while importing the front-end package
    must escape as itself rather than be reported as a missing extra.
    """

    def test_import_error_inside_tui_is_not_swallowed(self):
        with patch("flync_converter.cli._optional.find_spec", return_value=object()):
            with patch.dict(sys.modules, {"flync_converter.cli.tui": None}):
                with pytest.raises(ImportError) as exc_info:
                    load_run_tui()
        assert not isinstance(exc_info.value, click.ClickException)

    def test_import_error_inside_gui_is_not_swallowed(self):
        with patch("flync_converter.cli._optional.find_spec", return_value=object()):
            with patch.dict(sys.modules, {"flync_converter.cli.gui": None}):
                with pytest.raises(ImportError) as exc_info:
                    load_run_gui()
        assert not isinstance(exc_info.value, click.ClickException)


class TestStandaloneEntryPoints:
    """``main_interactive`` / ``main_gui`` are called directly by the console
    scripts, outside any Click context, so they must render the ClickException
    themselves and exit 1 rather than let a traceback escape.
    """

    @pytest.mark.parametrize(
        ("entry_point", "extra"),
        [("main_interactive", "tui"), ("main_gui", "gui")],
    )
    def test_missing_extra_prints_hint_and_exits_1(self, entry_point, extra, capsys):
        import flync_converter.cli as cli_module

        with patch("flync_converter.cli._optional.find_spec", return_value=None):
            with pytest.raises(SystemExit) as exc_info:
                getattr(cli_module, entry_point)()

        assert exc_info.value.code == 1
        err = capsys.readouterr().err
        assert f"flync[{extra}]" in err
        assert "Traceback" not in err

    @pytest.mark.parametrize(
        ("entry_point", "loader"),
        [("main_interactive", "load_run_tui"), ("main_gui", "load_run_gui")],
    )
    def test_extra_present_runs_the_front_end(self, entry_point, loader):
        """With the extra installed the loader succeeds and its runner is invoked."""
        import flync_converter.cli as cli_module

        run = MagicMock()
        with patch(f"flync_converter.cli._optional.{loader}", return_value=run):
            getattr(cli_module, entry_point)()

        run.assert_called_once_with()

    def test_main_loads_plugins_before_dispatching(self):
        """``main`` is the plain CLI entry point — no extras involved."""
        import flync_converter.cli as cli_module

        with patch("flync_converter.registry.registry.load_plugins") as load_plugins:
            with patch.object(cli_module, "cli") as cli_group:
                cli_module.main()

        load_plugins.assert_called_once()
        cli_group.assert_called_once()


class TestCoreImportNeedsNoExtras:
    def test_core_imports_succeed(self):
        """import flync, import flync_converter, and the CLI group must
        work without any optional extras."""
        import flync  # noqa: F401
        import flync_converter  # noqa: F401
        from flync_converter.cli import cli  # noqa: F401, F811
