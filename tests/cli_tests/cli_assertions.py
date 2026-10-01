"""Exact CLI-error assertions, replacing ``exit_code != 0`` and bare ``pytest.raises(typer.Exit)``.

A weak ``exit_code != 0`` oracle also passes when the command crashes with an unrelated,
unhandled exception - Click's ``CliRunner`` turns any exception into a non-zero exit, so a crash
and an intentional ``typer.Exit(1)`` look identical to that assertion. These helpers tell them
apart and pin the message the command was supposed to print.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import pytest
import typer
from click.testing import Result

from tests.cli_tests.rich_output import plain


def _crashed(result: Result) -> bool:
    """A CliRunner result "crashed" if it raised anything other than the normal SystemExit control flow."""
    return result.exception is not None and not isinstance(result.exception, SystemExit)


def assert_cli_ok(result: Result) -> None:
    """Assert the command exited 0, re-raising its exception if it crashed instead of exiting cleanly."""
    if _crashed(result):
        raise result.exception
    assert result.exit_code == 0, f"expected exit code 0, got {result.exit_code}: {plain(result.output)}"


def assert_cli_error(result: Result, expected_code: int, message_fragment: str) -> None:
    """Assert the command failed with exactly *expected_code* and printed *message_fragment*."""
    assert not _crashed(result), f"command crashed instead of exiting cleanly: {result.exception!r}"
    assert result.exit_code == expected_code, f"expected exit code {expected_code}, got {result.exit_code}: {plain(result.output)}"
    reported = plain(result.output)
    assert message_fragment in reported, f"expected message fragment {message_fragment!r} in: {reported!r}"


@contextmanager
def assert_exits(expected_code: int) -> Iterator[None]:
    """Assert a direct ``_show_*``/helper call raises ``typer.Exit`` with exactly *expected_code*."""
    with pytest.raises(typer.Exit) as exc_info:
        yield
    assert exc_info.value.exit_code == expected_code, f"expected typer.Exit({expected_code}), got typer.Exit({exc_info.value.exit_code})"
