"""Tests for the ``flync migrate`` CLI command."""

import re
from unittest.mock import patch

from typer.testing import CliRunner

from flync.core.version_migrators.engine import ApplicationResult
from flync.core.version_migrators.engine import WorkspaceMigrationState as State
from flync.model.flync_4_metadata.metadata import BaseVersion
from flync_cli.commands.migrate import app

runner = CliRunner()

V = lambda v: BaseVersion(version_schema="pep440", version=v)  # noqa: E731

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def _out(result) -> str:
    """Strip ANSI color codes the force_terminal Rich console always emits."""
    return _ANSI.sub("", result.output)


class _FakeMigration:
    unique_id = "m1"
    target_version = "0.10.0"
    description = "Move the thing."


def _status(state, **kwargs):
    from flync.core.version_migrators.engine import MigrationEngine

    base = MigrationEngine().evaluate(None, V("0.12.0"))
    base.state = state
    base.recorded = kwargs.get("recorded")
    base.current = kwargs.get("current", V("0.12.0"))
    base.pending = kwargs.get("pending", [])
    base.requires_stamp = kwargs.get("requires_stamp", False)
    return base


def _run(path, *args):
    return runner.invoke(app, [str(path), *args])


class TestMigrateCLI:
    def test_missing_path_exits_nonzero(self, tmp_path):
        assert _run(tmp_path / "nope").exit_code == 1

    def test_no_version_prints_stamp_hint(self, tmp_path):
        with patch("flync_cli.commands.migrate.Migrator.plan", return_value=_status(State.NO_VERSION)):
            result = _run(tmp_path)
        assert result.exit_code == 1
        assert "--init" in _out(result)

    def test_newer_prints_warning_and_exits_zero(self, tmp_path):
        status = _status(State.NEWER, recorded=V("0.13.0"))
        with patch("flync_cli.commands.migrate.Migrator.plan", return_value=status):
            result = _run(tmp_path)
        assert result.exit_code == 0
        assert "newer than the installed" in _out(result)

    def test_unsupported_old_prints_error(self, tmp_path):
        status = _status(State.UNSUPPORTED_OLD, recorded=V("0.1.0"))
        with patch("flync_cli.commands.migrate.Migrator.plan", return_value=status):
            result = _run(tmp_path)
        assert result.exit_code == 1
        assert "lowest supported" in _out(result)

    def test_dry_run_lists_plan_without_applying(self, tmp_path):
        status = _status(State.PENDING_MIGRATION, recorded=V("0.9.0"), pending=[_FakeMigration()])
        with patch("flync_cli.commands.migrate.Migrator.plan", return_value=status) as plan, patch("flync_cli.commands.migrate.Migrator.run") as run:
            result = _run(tmp_path, "--dry-run")
        assert result.exit_code == 0
        assert "m1" in _out(result)
        plan.assert_called_once()
        run.assert_not_called()

    def test_apply_runs_and_reports(self, tmp_path):
        status = _status(State.PENDING_MIGRATION, recorded=V("0.9.0"), pending=[_FakeMigration()])
        app_result = ApplicationResult(applied=["m1"], changed_uris=["x.flync.yaml"], message="Applied 1 migration(s).")
        with (
            patch("flync_cli.commands.migrate.Migrator.plan", return_value=status),
            patch("flync_cli.commands.migrate.Migrator.run", return_value=app_result) as run,
        ):
            result = _run(tmp_path)
        assert result.exit_code == 0
        run.assert_called_once()
        assert "Applied 1 migration" in _out(result)

    def test_init_stamps(self, tmp_path):
        with patch("flync_cli.commands.migrate.Migrator.stamp") as stamp:
            result = _run(tmp_path, "--init")
        assert result.exit_code == 0
        stamp.assert_called_once()
        assert "Stamped" in _out(result)
