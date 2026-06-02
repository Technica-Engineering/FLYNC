"""Util to call validate in several commands."""

import sys
from pathlib import Path

from rich.console import Console

from flync_cli.commands.validate import validate

console = Console(force_terminal=True)


def run_validation(path):
    """Run validation by calling the CLI command `flync validate`. Return with error if there is validation errors present."""
    resolved_path = Path(path).resolve()
    result = validate(path=str(resolved_path), quiet=True)
    loaded_ws = result.workspace
    has_errors = any(err.get("type") != "warning" for errs in result.errors.values() for err in errs)
    if has_errors:
        console.print("⚠️ [bold red] Validate your model first with `flync validate`.[/bold red]")
        sys.exit(1)
    else:
        return loaded_ws
