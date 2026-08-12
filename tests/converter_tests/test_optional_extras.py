"""Tests for the optional extras mechanism (flync[tui], flync[gui]).

Verifies that the _optional module correctly gates imports behind
``find_spec`` probes, and that missing extras produce actionable
ClickExceptions — never tracebacks.
"""

import sys
from unittest.mock import patch

import click
import pytest
from click.testing import CliRunner

from flync_converter.cli._optional import _require, load_run_gui, load_run_tui
from flync_converter.cli.group import cli

# ---------------------------------------------------------------------------
# _require
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# load_run_tui / load_run_gui — missing extra
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# CLI gui subcommand — missing extra
# ---------------------------------------------------------------------------


class TestCliGuiSubcommandMissingExtra:
    def test_exit_code_1_and_install_hint(self):
        runner = CliRunner()
        with patch("flync_converter.cli._optional.find_spec", return_value=None):
            result = runner.invoke(cli, ["gui"])
        assert result.exit_code == 1
        assert "flync[gui]" in result.output


# ---------------------------------------------------------------------------
# Real ImportError propagation (I3)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Core import smoke test (I1)
# ---------------------------------------------------------------------------


class TestCoreImportNeedsNoExtras:
    def test_core_imports_succeed(self):
        """import flync, import flync_converter, and the CLI group must
        work without any optional extras."""
        import flync  # noqa: F401
        import flync_converter  # noqa: F401
        from flync_converter.cli import cli  # noqa: F401, F811
