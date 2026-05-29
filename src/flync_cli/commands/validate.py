import sys
import time
from pathlib import Path

import typer
from rich.console import Console
from typing_extensions import Annotated

from flync.sdk.context.diagnostics_result import WorkspaceState
from flync.sdk.helpers.validation_helpers import validate_external_node, validate_workspace
from flync_cli.utils.error_table import print_validation_result

console = Console(force_terminal=True, legacy_windows=False)
app = typer.Typer()


@app.command(help="Validate a FLYNC Model or parts of a Model.")
def validate(
    path: Annotated[
        str,
        typer.Argument(
            help="Path to FLYNC config directory",
        ),
    ],
    node: Annotated[
        str, typer.Option("--node", "-n", help="Node type name to validate via validate_external_node. Omit to validate the full workspace.")
    ] = "",
    config_name: Annotated[str, typer.Option("--config", "-c", help="Name of configuration.")] = "flync_config",
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Only show final result of the validation.")] = False,
):
    """Validate a FLYNC model at the given path, optionally suppressing output."""

    resolved_path = Path(path).resolve()

    if not resolved_path.exists():
        print(f"Error: Path does not exist: {path}", file=sys.stderr)
        sys.exit(1)

    console.print(f"-- Validating {config_name} ... --")
    start = time.monotonic()

    result = validate_external_node(node, resolved_path) if node else validate_workspace(resolved_path)

    console.print(f">>> Elapsed time to load: {time.monotonic() - start:.2f}s")

    if not quiet:
        print_validation_result(result)

    has_errors = any(err.get("type") != "warning" for errs in result.errors.values() for err in errs)

    exit_err = False

    if (result.state is not WorkspaceState.VALID) and has_errors:
        exit_err = True
        color = "bold red"
    elif result.state is WorkspaceState.WARNING:
        color = "bold yellow"
    else:
        color = "bold green"
    console.print(f">>> Validation Result for {config_name}: [{color}] {result.state.upper()} [/{color}] ")
    return result if result.workspace else sys.exit(exit_err)
