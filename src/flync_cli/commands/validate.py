"""``flync validate`` command: loads a FLYNC workspace and reports validation errors."""

import sys
import time
from pathlib import Path

import typer
from typing_extensions import Annotated

from flync.sdk.context.diagnostics_result import DiagnosticsResult, WorkspaceState
from flync.sdk.helpers.debug_layers import run_debug
from flync.sdk.helpers.validation_helpers import validate_external_node, validate_workspace
from flync_cli.utils.console import console
from flync_cli.utils.error_table import print_validation_result
from flync_cli.utils.workspace import WorkspacePathArg, resolve_workspace_path

app = typer.Typer()


def _run_validate(path, node: str, config_name: str, verbose: bool) -> DiagnosticsResult:
    """
    Validate a FLYNC model at *path*, exiting non-zero unless it passed.

    The exit code is all a CI job sees. Warnings stay at zero: they are diagnostics, not failures.

    When *verbose* is set (and no *node* is given), the layered debug checks (folder structure, YAML syntax,
    schema, field values, system-wide) are run instead of the summary tables - the layers only cover a whole
    workspace, so *verbose* has no effect together with *node*.
    """

    resolved_path = resolve_workspace_path(path)

    console.print(f"-- Validating {config_name} ... --")
    start = time.monotonic()

    run_verbose = verbose
    if run_verbose and node:
        console.print("[dim]--verbose has no effect together with --node: the layered checks only cover the full workspace.[/dim]")
        run_verbose = False

    if run_verbose:
        result = run_debug(resolved_path)
    else:
        result = validate_external_node(node, resolved_path) if node else validate_workspace(resolved_path)
        print_validation_result(result)

    console.print(f">>> Elapsed time to load: {time.monotonic() - start:.2f}s")

    if result is None:
        console.print(f">>> Validation Result for {config_name}: [bold red] INVALID [/bold red] ")
        sys.exit(1)

    _print_migration_hint(resolved_path)

    if not result.passed:
        color = "bold red"
    elif result.state is WorkspaceState.WARNING:
        color = "bold yellow"
    else:
        color = "bold green"
    console.print(f">>> Validation Result for {config_name}: [{color}] {result.state.upper()} [/{color}] ")

    if not result.passed:
        sys.exit(1)

    return result


@app.command(help="Validate a FLYNC Model or parts of a Model.")
def validate(
    path: WorkspacePathArg = None,
    node: Annotated[
        str, typer.Option("--node", "-n", help="Node type name to validate via validate_external_node. Omit to validate the full workspace.")
    ] = "",
    config_name: Annotated[str, typer.Option("--config-name", "--config", "-c", help="Name of configuration.")] = "flync_config",
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Run the layered debug checks (folder structure, YAML syntax, schema, field values, system-wide) instead of "
            "the summary tables. Only applies when validating the full workspace (no --node).",
        ),
    ] = False,
) -> DiagnosticsResult:
    """Validate a FLYNC model at the given path, exiting non-zero unless it passed."""
    return _run_validate(path, node, config_name, verbose)


def _print_migration_hint(resolved_path: Path) -> None:
    """
    Suggest ``flync migrate`` when a workspace was created by an older FLYNC release.

    This is advisory only - it never changes the validation result or exit code.
    """
    try:
        from flync.core.version_migrators.engine import Migrator, WorkspaceMigrationState

        status = Migrator().plan(resolved_path)
    except Exception:  # pragma: no cover - a broken config must not break `validate`
        return

    if status.state is WorkspaceMigrationState.PENDING_MIGRATION:
        assert status.recorded is not None and status.current is not None
        console.print(
            f"[bold yellow]→ Workspace was created with FLYNC {status.recorded.version} "
            f"(installed: {status.current.version}). Run `flync migrate {resolved_path}` to update it.[/bold yellow]"
        )
