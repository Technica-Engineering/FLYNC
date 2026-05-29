"""Tests for the validate CLI command and validate helper."""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

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
