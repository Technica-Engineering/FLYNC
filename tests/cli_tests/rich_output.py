"""Deterministic capture of Rich console output for CLI report assertions.

Every ``flync info`` (and similar) report prints through one shared ``Console`` instance that
each command module imports by value (``from flync_cli.utils.console import console``) - so it
must be patched on the *importing* module, not on ``flync_cli.utils.console`` itself.

``capture()`` swaps that name for a recording console with a pinned width, so tests get exact
table rows back instead of loose substrings that Rich's highlighters can fragment across ANSI
spans, or that column truncation can cut short at a narrower terminal width (both verified: see
the plan this module implements).
"""

from __future__ import annotations

import re
from contextlib import contextmanager
from dataclasses import dataclass
from types import ModuleType
from typing import Iterator

from rich.console import Console

from flync_cli.utils.error_table import sanitize_error_message

#: Wide enough that no report column in this suite truncates; matches the old COLUMNS=200 hack
#: this module replaces, but pinned explicitly per capture instead of via a global env var.
DEFAULT_WIDTH = 200


@dataclass
class Captured:
    """The plain-text render of everything printed during a :func:`capture` block."""

    text: str

    @property
    def rows(self) -> list[list[str]]:
        """Return the rows of the single table in :attr:`text`.

        Raises ``AssertionError`` if the output contains zero or more than one table - use
        :meth:`tables` for reports that print more than one (e.g. ``vlans``, ``sockets``).
        """
        found = self.tables
        assert len(found) == 1, f"expected exactly one table, found {len(found)}"
        return found[0]

    @property
    def tables(self) -> list[list[list[str]]]:
        """Return every box-drawn table in :attr:`text` as a list of tables, each a list of rows of cells."""
        return _parse_tables(self.text)

    @property
    def plain(self) -> str:
        """Return :attr:`text` with ANSI escapes stripped and whitespace collapsed, for non-table messages."""
        return plain(self.text)


@contextmanager
def capture(*modules: ModuleType, width: int = DEFAULT_WIDTH) -> Iterator[Captured]:
    """Redirect ``console`` on every module in *modules* to one shared recording console.

    Each command module imports ``console`` by value, and some errors are raised from a
    different module than the one printing the report (e.g. ``flync_cli.utils.model_views``'s
    ``require_ecu`` prints its own message, independent of ``flync_cli.commands.info``'s table) -
    pass every module whose output the test needs to see.

    Usage::

        with capture(info) as out:
            info._show_ip(model, None)
        assert out.rows[1] == ["ECU1", "CTRL0", "ETH0", "vi10", "10", "10.0.20.5/24"]
    """
    originals = [module.console for module in modules]
    recorder = Console(record=True, width=width, no_color=True, force_terminal=False)
    for module in modules:
        module.console = recorder
    captured = Captured(text="")
    try:
        yield captured
    finally:
        captured.text = recorder.export_text()
        for module, original in zip(modules, originals):
            module.console = original


def plain(text: str) -> str:
    """Strip ANSI escapes and collapse whitespace, so a fragmented/wrapped message matches a plain substring."""
    return re.sub(r"\s+", " ", sanitize_error_message(text)).strip()


def _parse_tables(text: str) -> list[list[list[str]]]:
    """Split Rich box-drawn tables out of *text* into ``[[row, ...], ...]`` per table."""
    tables: list[list[list[str]]] = []
    current: list[list[str]] = []
    in_table = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("┌"):
            in_table = True
            current = []
        elif stripped.startswith("└"):
            in_table = False
            tables.append(current)
        elif in_table and stripped.startswith("│"):
            cells = [cell.strip() for cell in stripped.strip("│").split("│")]
            current.append(cells)
        # separator rows ("├...┤") carry no data and are skipped
    return tables
