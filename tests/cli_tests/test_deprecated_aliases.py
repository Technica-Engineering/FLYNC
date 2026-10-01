"""Tests for the hidden, deprecated top-level command aliases in ``main.py``.

Each alias only has to warn and delegate with the right arguments - the report logic itself is
covered by ``test_info.py`` / ``test_validate.py`` / ``test_model_views.py``, so the underlying
``_show_*`` functions are mocked here.
"""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from flync_cli.main import app

runner = CliRunner()


class TestDisplayVlanInfoAlias:
    def test_delegates_to_info_vlans(self, tmp_path):
        ws = MagicMock()
        with (
            patch("flync_cli.main.load_workspace", return_value=ws) as mock_load,
            patch("flync_cli.main._show_vlans") as mock_show,
        ):
            result = runner.invoke(app, ["display-vlan-info", "10", str(tmp_path), "--ecu-name", "ECU1"])

        assert result.exit_code == 0
        mock_load.assert_called_once_with(str(tmp_path))
        mock_show.assert_called_once_with(ws.flync_model, "ECU1", 10)
        assert "deprecated" in result.output.lower()
        assert "info vlans" in result.output


class TestDisplayServiceInfoAlias:
    def test_resolves_name_then_delegates_to_info_instances(self, tmp_path):
        ws = MagicMock()
        with (
            patch("flync_cli.main.load_workspace", return_value=ws),
            patch("flync_cli.main._resolve_service_by_name", return_value=(0x0101, 1)) as mock_resolve,
            patch("flync_cli.main._show_instances") as mock_show,
        ):
            result = runner.invoke(app, ["display-service-info", "MyService", str(tmp_path)])

        assert result.exit_code == 0
        mock_resolve.assert_called_once_with(ws.flync_model, "MyService")
        mock_show.assert_called_once_with(ws.flync_model, 0x0101, 1)
        assert "info instances" in result.output


class TestDisplayRepoStructureAlias:
    def test_delegates_to_filetree(self):
        with patch("flync_cli.main._show_filetree") as mock_show:
            result = runner.invoke(app, ["display-repo-structure", "--class", "ecu"])

        assert result.exit_code == 0
        mock_show.assert_called_once_with("ecu")
        assert "filetree" in result.output


class TestDebugAlias:
    def test_delegates_to_validate_verbose(self, tmp_path):
        with patch("flync_cli.main._run_validate") as mock_run_validate:
            result = runner.invoke(app, ["debug", str(tmp_path)])

        assert result.exit_code == 0
        mock_run_validate.assert_called_once_with(str(tmp_path), "", "flync_config", True)
        assert "validate --verbose" in result.output


class TestAliasesAreHidden:
    def test_not_listed_in_help(self):
        result = runner.invoke(app, ["--help"])
        for name in ("display-vlan-info", "display-service-info", "display-repo-structure", "debug"):
            assert name not in result.output
