"""Tests for the validate CLI command."""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from flync.sdk.context.diagnostics_result import DiagnosticsResult, WorkspaceState
from flync.sdk.helpers.generation_helpers import dump_flync_workspace
from flync_cli.commands.validate import app
from tests.cli_tests.cli_assertions import assert_cli_error, assert_cli_ok, assert_exits
from tests.model_builders import make_model

runner = CliRunner()


def _diagnostic(kind):
    """One diagnostic. ``ErrorDetails`` needs ``loc`` and ``input``; only ``type`` decides pass or fail."""

    return {"type": kind, "msg": f"a {kind}", "loc": (), "input": None}


ERROR = _diagnostic("major")
WARNING = _diagnostic("warning")


def _result(state, diagnostics=()):
    """A result without a workspace, which is all the command needs to pick an exit code."""

    return DiagnosticsResult(state=state, errors={"doc.yaml": list(diagnostics)} if diagnostics else {})


class TestValidateExitCode:
    """
    The exit code is the only thing a CI job sees, so errors have to reach it.

    The command used to compute the exit condition and then drop it, so every invocation exited 0 and the CI gate could not fail.
    """

    @staticmethod
    def _invoke(tmp_path, result, extra_args=()):
        with patch("flync_cli.commands.validate.validate_workspace", return_value=result):
            return runner.invoke(app, [str(tmp_path), *extra_args])

    @pytest.mark.parametrize(
        "state, diagnostics",
        [
            (WorkspaceState.VALID, ()),
            (WorkspaceState.WARNING, (WARNING,)),
        ],
        ids=["clean", "warnings_only"],
    )
    def test_exits_zero_without_errors(self, tmp_path, state, diagnostics):
        """Warnings are diagnostics, not failures: an example may warn and still be a good example."""

        assert_cli_ok(self._invoke(tmp_path, _result(state, diagnostics)))

    @pytest.mark.parametrize(
        "diagnostics",
        [
            (ERROR,),
            (WARNING, ERROR),
        ],
        ids=["errors_only", "errors_among_warnings"],
    )
    def test_exits_non_zero_on_errors(self, tmp_path, diagnostics):
        assert_cli_error(self._invoke(tmp_path, _result(WorkspaceState.INVALID, diagnostics)), 1, "INVALID")

    @pytest.mark.parametrize("state", [WorkspaceState.BROKEN, WorkspaceState.EMPTY], ids=["broken", "empty"])
    def test_exits_non_zero_when_nothing_loaded(self, tmp_path, state):
        """A workspace that never loaded carries no diagnostics at all, so the diagnostics alone would read as a pass."""

        assert_cli_error(self._invoke(tmp_path, _result(state)), 1, state.upper())

    def test_node_validation_uses_the_same_exit_rule(self, tmp_path):
        """``--node`` reaches the same tail by a different route, so it needs the same guarantee."""

        with patch("flync_cli.commands.validate.validate_external_node", return_value=_result(WorkspaceState.INVALID, (ERROR,))):
            outcome = runner.invoke(app, [str(tmp_path), "--node", "ECU"])
        assert_cli_error(outcome, 1, "INVALID")

    def test_missing_path_exits_non_zero(self, tmp_path):
        assert_cli_error(runner.invoke(app, [str(tmp_path / "does_not_exist")]), 1, "Path does not exist")

    def test_missing_path_and_no_stored_config_exits_non_zero(self):
        with patch("flync_cli.utils.workspace.get_stored_workspace_path", return_value=None):
            result = runner.invoke(app, [])
        assert_cli_error(result, 1, "No path given and no workspace configured")

    def test_quiet_flag_no_longer_exists(self, tmp_path):
        """``--quiet`` was removed: --verbose now covers the detailed-diagnostics use case."""

        with patch("flync_cli.commands.validate.validate_workspace", return_value=_result(WorkspaceState.VALID)):
            result = runner.invoke(app, [str(tmp_path), "--quiet"])
        assert_cli_error(result, 2, "No such option: --quiet")


class TestValidateVerbose:
    def test_verbose_runs_the_layered_debug_checks(self, tmp_path):
        with patch("flync_cli.commands.validate.run_debug", return_value=_result(WorkspaceState.VALID)) as mock_run_debug:
            result = runner.invoke(app, [str(tmp_path), "--verbose"])
        assert_cli_ok(result)
        mock_run_debug.assert_called_once()

    def test_verbose_exits_nonzero_when_debug_stopped_before_loading(self, tmp_path):
        """``run_debug`` returns ``None`` when it stops at layer 1 or 2, before any DiagnosticsResult exists."""

        with patch("flync_cli.commands.validate.run_debug", return_value=None):
            result = runner.invoke(app, [str(tmp_path), "--verbose"])
        assert_cli_error(result, 1, "INVALID")

    def test_verbose_is_ignored_together_with_node(self, tmp_path):
        """The layered checks only cover a whole workspace, so --verbose has no effect together with --node."""

        with (
            patch("flync_cli.commands.validate.run_debug") as mock_run_debug,
            patch("flync_cli.commands.validate.validate_external_node", return_value=_result(WorkspaceState.VALID)),
        ):
            result = runner.invoke(app, [str(tmp_path), "--node", "ECU", "--verbose"])
        assert_cli_ok(result)
        mock_run_debug.assert_not_called()


class TestLoadWorkspace:
    """
    The path that ``info`` and ``generate-system-uml`` take: resolve the path, validate the workspace there.

    Exercises the case ``validate`` never sees at the CLI level: a result that passed and still carries no workspace,
    which the callers would otherwise dereference straight away.
    """

    @staticmethod
    def _run(tmp_path, result):
        from flync_cli.utils.workspace import load_workspace

        with patch("flync_cli.utils.workspace.validate_workspace", return_value=result):
            return load_workspace(str(tmp_path))

    def test_returns_the_workspace_when_validation_passes(self, tmp_path):
        result = _result(WorkspaceState.VALID)
        result.workspace = MagicMock()
        assert self._run(tmp_path, result) is result.workspace

    def test_exits_when_no_workspace_came_back(self, tmp_path):
        result = _result(WorkspaceState.VALID)
        with assert_exits(1):
            self._run(tmp_path, result)


class TestValidateGeneratedWorkspace:
    """
    End-to-end run of ``flync validate`` against a purpose-built on-disk workspace.

    Dumping a real, minimal ``FLYNCModel`` (see ``tests/model_builders.py``) exercises the full
    load/validate pipeline without depending on the bundled ``examples/flync_example`` workspace,
    whose content can change for reasons unrelated to these tests.
    """

    def test_verbose_reports_the_layers(self, tmp_path):
        # Rich's number highlighter splits "Layer 1" across styled spans, so match the layer title text
        # instead of the digit.
        workspace = tmp_path / "ws"
        dump_flync_workspace(make_model(), workspace, "test_ws")

        result = runner.invoke(app, [str(workspace), "--verbose"])

        assert_cli_ok(result)
        assert "Folder & File Structure" in result.output
        assert "System-Wide Validation" in result.output

    def test_stray_file_is_tolerated_and_validates(self, tmp_path):
        """An unrecognized extra file must never turn a passing workspace into a failure."""

        workspace = tmp_path / "ws"
        dump_flync_workspace(make_model(), workspace, "test_ws")
        (workspace / "ecus" / "readme.md").write_text("extra file")

        result = runner.invoke(app, [str(workspace)])

        assert_cli_ok(result)
