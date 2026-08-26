"""Tests for the validate CLI command and validate helper."""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from flync.sdk.context.diagnostics_result import DiagnosticsResult, WorkspaceState
from flync_cli.commands.validate import app, validate

runner = CliRunner()


@pytest.mark.skip(reason="Mock will create broken workspace. Tests false positive.")
class TestValidateAll:
    def test_returns_workspace_on_success(self, tmp_path):
        ws = MagicMock()
        with patch("flync_cli.commands.validate.FLYNCWorkspace.load_workspace", return_value=ws):
            result = validate(tmp_path, quiet=True)
        assert result is ws

    def test_returns_none_on_exception_when_quiet(self, tmp_path):
        with patch(
            "flync_cli.commands.validate.FLYNCWorkspace.load_workspace",
            side_effect=ValueError("bad config"),
        ):
            result = validate(tmp_path, quiet=True)
        assert result is None

    def test_raises_system_exit_on_exception_when_loud(self, tmp_path):
        with patch(
            "flync_cli.commands.validate.FLYNCWorkspace.load_workspace",
            side_effect=ValueError("bad config"),
        ):
            with pytest.raises(SystemExit):
                validate(tmp_path, quiet=False)

    def test_success_does_not_raise(self, tmp_path):
        ws = MagicMock()
        with patch("flync_cli.commands.validate.FLYNCWorkspace.load_workspace", return_value=ws):
            validate(tmp_path, quiet=False)


@pytest.mark.skip(reason="Mock will create broken workspace. Tests false positive.")
class TestValidateCommand:
    def test_all_level_exits_zero(self, tmp_path):
        ws = MagicMock()
        with patch("flync_cli.commands.validate.FLYNCWorkspace.load_workspace", return_value=ws):
            result = runner.invoke(app, ["All", str(tmp_path)])
        assert result.exit_code == 0

    def test_all_level_prints_configured_message(self, tmp_path):
        ws = MagicMock()
        with patch("flync_cli.commands.validate.FLYNCWorkspace.load_workspace", return_value=ws):
            result = runner.invoke(app, ["All", str(tmp_path)])
        assert "properly configured" in result.output

    def test_ecus_level_not_yet_implemented(self, tmp_path):
        result = runner.invoke(app, ["Ecus", str(tmp_path)])
        assert result.exit_code == 0
        assert "Not yet" in result.output

    def test_file_level_not_yet_implemented(self, tmp_path):
        result = runner.invoke(app, ["File", str(tmp_path)])
        assert result.exit_code == 0
        assert "Not yet" in result.output

    def test_topology_level_not_yet_implemented(self, tmp_path):
        result = runner.invoke(app, ["Topology", str(tmp_path)])
        assert result.exit_code == 0
        assert "Not yet" in result.output

    def test_metadata_level_not_yet_implemented(self, tmp_path):
        result = runner.invoke(app, ["Metadata", str(tmp_path)])
        assert result.exit_code == 0
        assert "Not yet" in result.output

    def test_general_level_not_yet_implemented(self, tmp_path):
        result = runner.invoke(app, ["General", str(tmp_path)])
        assert result.exit_code == 0
        assert "Not yet" in result.output

    def test_invalid_level_is_rejected(self, tmp_path):
        result = runner.invoke(app, ["NotALevel", str(tmp_path)])
        assert result.exit_code != 0


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
        with pytest.raises(SystemExit) as exc_info:
            self._run(tmp_path, _result(WorkspaceState.INVALID, (ERROR,)))
        assert exc_info.value.code == 1
        assert "flync validate" in capsys.readouterr().out

    def test_exits_when_no_workspace_came_back(self, tmp_path):
        with pytest.raises(SystemExit) as exc_info:
            self._run(tmp_path, _result(WorkspaceState.VALID))
        assert exc_info.value.code == 1
