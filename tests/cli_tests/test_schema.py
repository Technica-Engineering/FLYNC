"""Tests for the ``flync schema`` command."""

import json

from typer.testing import CliRunner

from flync_cli.commands.schema import app
from flync_cli.main import app as main_app
from tests.cli_tests.cli_assertions import assert_cli_error, assert_cli_ok

runner = CliRunner()


class TestSchemaCommand:
    def test_writes_one_file_per_model(self, tmp_path):
        result = runner.invoke(app, [str(tmp_path)])
        assert_cli_ok(result)
        root = json.loads((tmp_path / "FLYNCModel.schema.json").read_text(encoding="utf-8"))
        assert "$defs" not in root
        assert (tmp_path / "ECU.schema.json").exists()
        assert "root schema: FLYNCModel.schema.json" in result.output

    def test_suffix_and_base_uri(self, tmp_path):
        result = runner.invoke(app, [str(tmp_path), "--suffix", ".json", "--base-uri", "https://example.com/schemas"])
        assert_cli_ok(result)
        root = json.loads((tmp_path / "FLYNCModel.json").read_text(encoding="utf-8"))
        assert root["$id"] == "https://example.com/schemas/FLYNCModel.json"

    def test_serialization_mode(self, tmp_path):
        result = runner.invoke(app, [str(tmp_path), "--mode", "serialization"])
        assert_cli_ok(result)
        assert (tmp_path / "FLYNCModel.schema.json").exists()

    def test_unknown_mode_exits_with_usage_error(self, tmp_path):
        result = runner.invoke(app, [str(tmp_path), "--mode", "bogus"])
        assert_cli_error(result, 2, "Invalid value for '--mode'")

    def test_registered_on_main_app(self, tmp_path):
        result = runner.invoke(main_app, ["schema", str(tmp_path)])
        assert_cli_ok(result)
        assert (tmp_path / "FLYNCModel.schema.json").exists()
