"""Tests for the validate CLI command and validate helper."""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from flync.sdk.context.diagnostics_result import DiagnosticsResult, WorkspaceState
from flync_cli.commands.validate import app

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
            return runner.invoke(app, [str(tmp_path), "--quiet", *extra_args])

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

        assert self._invoke(tmp_path, _result(state, diagnostics)).exit_code == 0

    @pytest.mark.parametrize(
        "diagnostics",
        [
            (ERROR,),
            (WARNING, ERROR),
        ],
        ids=["errors_only", "errors_among_warnings"],
    )
    def test_exits_non_zero_on_errors(self, tmp_path, diagnostics):
        assert self._invoke(tmp_path, _result(WorkspaceState.INVALID, diagnostics)).exit_code != 0

    @pytest.mark.parametrize("state", [WorkspaceState.BROKEN, WorkspaceState.EMPTY], ids=["broken", "empty"])
    def test_exits_non_zero_when_nothing_loaded(self, tmp_path, state):
        """A workspace that never loaded carries no diagnostics at all, so the diagnostics alone would read as a pass."""

        assert self._invoke(tmp_path, _result(state)).exit_code != 0

    def test_node_validation_uses_the_same_exit_rule(self, tmp_path):
        """``--node`` reaches the same tail by a different route, so it needs the same guarantee."""

        with patch("flync_cli.commands.validate.validate_external_node", return_value=_result(WorkspaceState.INVALID, (ERROR,))):
            outcome = runner.invoke(app, [str(tmp_path), "--node", "ECU", "--quiet"])
        assert outcome.exit_code != 0

    def test_missing_path_exits_non_zero(self, tmp_path):
        assert runner.invoke(app, [str(tmp_path / "does_not_exist")]).exit_code != 0


class TestRunValidation:
    """
    The path that ``info``, ``vlan_info``, ``service_info`` and ``generate_system_uml`` take.

    ``validate`` already exits on a failed model, so what is left here is the case it does not cover: a result that passed and still
    carries no workspace, which the callers would dereference straight away.
    """

    @staticmethod
    def _run(tmp_path, result):
        from flync_cli.utils.run_validation import run_validation

        with patch("flync_cli.commands.validate.validate_workspace", return_value=result):
            return run_validation(str(tmp_path))

    def test_returns_the_workspace_when_validation_passes(self, tmp_path):
        result = _result(WorkspaceState.VALID)
        result.workspace = MagicMock()
        assert self._run(tmp_path, result) is result.workspace

    def test_exits_on_errors_with_guidance(self, tmp_path, capsys):
        result = _result(WorkspaceState.INVALID, (ERROR,))
        with pytest.raises(SystemExit) as exc_info:
            self._run(tmp_path, result)
        assert exc_info.value.code == 1
        assert "flync validate" in capsys.readouterr().out

    def test_exits_when_no_workspace_came_back(self, tmp_path):
        result = _result(WorkspaceState.VALID)
        with pytest.raises(SystemExit) as exc_info:
            self._run(tmp_path, result)
        assert exc_info.value.code == 1


class TestValidateExampleWorkspace:
    """
    End-to-end run of ``flync validate`` against the bundled clean example workspace.

    The example is free of diagnostics, so it validates to ``VALID`` and exits 0.
    """

    def test_example_passes_validation(self, example_workspace_path):
        result = runner.invoke(app, [str(example_workspace_path)])
        assert result.exit_code == 0
        assert "VALID" in result.output

    def test_quiet_still_reports_the_outcome(self, example_workspace_path):
        result = runner.invoke(app, [str(example_workspace_path), "--quiet"])
        assert result.exit_code == 0
        assert "Validation Result" in result.output

    def test_stray_file_is_tolerated_and_validates(self, example_workspace_path, tmp_path):
        """An unrecognized extra file must never turn a passing workspace into a failure."""

        import shutil

        workspace = tmp_path / "with_stray_file"
        shutil.copytree(example_workspace_path, workspace)
        (workspace / "ecus" / "readme.md").write_text("extra file")

        result = runner.invoke(app, [str(workspace)])

        assert result.exit_code == 0
        assert "VALID" in result.output
