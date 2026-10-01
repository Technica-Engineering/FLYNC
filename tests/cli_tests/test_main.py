"""Tests for the ``flync`` root callback (``--version``)."""

from importlib import metadata

from typer.testing import CliRunner

from flync_cli.main import app
from tests.cli_tests.cli_assertions import assert_cli_ok

runner = CliRunner()


class TestVersionFlag:
    def test_prints_the_installed_version(self):
        result = runner.invoke(app, ["--version"])
        assert_cli_ok(result)
        assert f"Version: {metadata.version('flync')}" in result.output

    def test_is_ignored_when_a_subcommand_is_given(self):
        """``--version`` only short-circuits when invoked without a subcommand."""

        result = runner.invoke(app, ["--version", "errors", "get-next-number"])
        assert_cli_ok(result)
        assert "Version:" not in result.output
