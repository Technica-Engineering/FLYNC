"""Util to call validate in several commands."""

import sys
from pathlib import Path

from rich.console import Console

from flync_cli.commands.validate import validate

console = Console(force_terminal=True)


def run_validation(path):
    """
    Validate the workspace at *path* and hand it to a command that needs one.

    ``validate`` exits non-zero itself when the model does not pass, so the only case left here is a result that passed and still carries
    no workspace: the callers dereference it straight away.
    """

    result = validate(path=str(Path(path).resolve()), quiet=True)

    if result.workspace is None:
        console.print("⚠️ [bold red] Validate your model first with `flync validate`.[/bold red]")
        sys.exit(1)

    return result.workspace
