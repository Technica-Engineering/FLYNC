"""Tests for the ``flync filetree`` command."""

import pytest
from typer.testing import CliRunner

import flync.sdk.helpers.debug as debug
from flync_cli.commands.filetree import app
from tests.cli_tests.cli_assertions import assert_cli_error, assert_cli_ok

runner = CliRunner()


@pytest.fixture(autouse=True)
def _exports_dir(tmp_path, monkeypatch):
    """Redirect ``print_flync_structure``/``print_field_subtree``'s output away from the repo's real ``exports/`` dir."""
    exports = tmp_path / "exports"
    monkeypatch.setattr(debug, "_EXPORTS_DIR", exports)
    return exports


class TestFiletreeCommand:
    def test_default_renders_the_full_model(self, _exports_dir):
        result = runner.invoke(app, [])
        assert_cli_ok(result)
        assert (_exports_dir / "FLYNCModel_structure.txt").exists()

    def test_named_class_renders_that_subtree(self, _exports_dir):
        result = runner.invoke(app, ["--class", "ecu"])
        assert_cli_ok(result)
        assert (_exports_dir / "ECU_structure.txt").exists()

    def test_named_field_renders_a_leaf_subtree(self, _exports_dir):
        result = runner.invoke(app, ["--class", "ports"])
        assert_cli_ok(result)
        assert (_exports_dir / "ports_structure.txt").exists()

    def test_unknown_class_exits_nonzero(self):
        result = runner.invoke(app, ["--class", "bogus"])
        assert_cli_error(result, 1, "Unknown class 'bogus'")
