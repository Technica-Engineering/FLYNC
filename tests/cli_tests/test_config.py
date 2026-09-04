"""Tests for the ``flync config`` command group.

Every test monkeypatches ``CONFIG_DIR``/``CONFIG_FILE`` to a ``tmp_path`` location so the real
``~/.config/FLYNC/cli.json`` on the machine running these tests is never touched.
"""

import pytest
import typer
from typer.testing import CliRunner

from flync_cli.commands.config import app
from flync_cli.utils import workspace as workspace_module

runner = CliRunner()


def _isolate(monkeypatch, tmp_path):
    config_dir = tmp_path / "config"
    config_file = config_dir / "cli.json"
    monkeypatch.setattr(workspace_module, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(workspace_module, "CONFIG_FILE", config_file)
    return config_file


class TestConfigSet:
    def test_stores_an_existing_directory(self, monkeypatch, tmp_path):
        _isolate(monkeypatch, tmp_path)
        workspace_dir = tmp_path / "workspace"
        workspace_dir.mkdir()

        result = runner.invoke(app, ["set", str(workspace_dir)])

        assert result.exit_code == 0
        assert workspace_module.get_stored_workspace_path() == str(workspace_dir.resolve())

    def test_rejects_a_path_that_is_not_a_directory(self, monkeypatch, tmp_path):
        _isolate(monkeypatch, tmp_path)
        not_a_dir = tmp_path / "file.txt"
        not_a_dir.write_text("x")

        result = runner.invoke(app, ["set", str(not_a_dir)])

        assert result.exit_code != 0
        assert workspace_module.get_stored_workspace_path() is None


class TestConfigShow:
    def test_reports_nothing_stored(self, monkeypatch, tmp_path):
        _isolate(monkeypatch, tmp_path)
        result = runner.invoke(app, ["show"])
        assert result.exit_code == 0
        assert "No workspace path is stored" in result.output

    def test_reports_the_stored_path(self, monkeypatch, tmp_path):
        _isolate(monkeypatch, tmp_path)
        workspace_dir = tmp_path / "workspace"
        workspace_dir.mkdir()
        workspace_module.set_stored_workspace_path(str(workspace_dir))

        result = runner.invoke(app, ["show"])

        # Rich's path highlighter splits a printed path across ANSI-styled spans, so match only the
        # basename rather than the full path string.
        assert result.exit_code == 0
        assert workspace_dir.name in result.output
        assert "no longer exists" not in result.output

    def test_flags_a_stored_path_that_no_longer_exists(self, monkeypatch, tmp_path):
        _isolate(monkeypatch, tmp_path)
        gone = tmp_path / "gone"
        workspace_module.set_stored_workspace_path(str(gone))

        result = runner.invoke(app, ["show"])

        assert result.exit_code == 0
        assert "no longer exists" in result.output


class TestConfigClear:
    def test_clears_the_stored_path(self, monkeypatch, tmp_path):
        _isolate(monkeypatch, tmp_path)
        workspace_dir = tmp_path / "workspace"
        workspace_dir.mkdir()
        workspace_module.set_stored_workspace_path(str(workspace_dir))

        result = runner.invoke(app, ["clear"])

        assert result.exit_code == 0
        assert workspace_module.get_stored_workspace_path() is None

    def test_clearing_when_nothing_is_stored_does_not_error(self, monkeypatch, tmp_path):
        _isolate(monkeypatch, tmp_path)
        result = runner.invoke(app, ["clear"])
        assert result.exit_code == 0


class TestResolveWorkspacePath:
    """``resolve_workspace_path`` backs every command's optional ``path`` argument."""

    def test_explicit_path_wins_over_the_stored_one(self, monkeypatch, tmp_path):
        _isolate(monkeypatch, tmp_path)
        stored = tmp_path / "stored"
        stored.mkdir()
        explicit = tmp_path / "explicit"
        explicit.mkdir()
        workspace_module.set_stored_workspace_path(str(stored))

        resolved = workspace_module.resolve_workspace_path(str(explicit))

        assert resolved == explicit.resolve()

    def test_falls_back_to_the_stored_path_when_omitted(self, monkeypatch, tmp_path):
        _isolate(monkeypatch, tmp_path)
        stored = tmp_path / "stored"
        stored.mkdir()
        workspace_module.set_stored_workspace_path(str(stored))

        resolved = workspace_module.resolve_workspace_path(None)

        assert resolved == stored.resolve()

    def test_exits_when_neither_is_available(self, monkeypatch, tmp_path):
        _isolate(monkeypatch, tmp_path)
        with pytest.raises(typer.Exit):
            workspace_module.resolve_workspace_path(None)
