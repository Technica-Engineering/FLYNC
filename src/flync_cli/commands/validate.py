"""``flync validate`` command: loads a FLYNC workspace and reports validation errors."""

import sys
import time
from pathlib import Path

import typer
from typing_extensions import Annotated

from flync.sdk.context.diagnostics_result import DiagnosticsResult, VariantSetDiagnosticsResult, WorkspaceState
from flync.sdk.helpers.debug_layers import run_debug
from flync.sdk.helpers.validation_helpers import validate_external_node, validate_variants, validate_workspace, workspace_has_variability
from flync_cli.utils.console import console, print_error
from flync_cli.utils.error_table import print_validation_result, print_variant_results
from flync_cli.utils.workspace import VariantOpt, WorkspacePathArg, resolve_workspace_path

app = typer.Typer()


def _plan_run(resolved_path: Path, node: str, verbose: bool, variant: str | None, all_variants: bool) -> tuple[bool, bool]:
    """
    Decide whether every variant is validated and whether the layered debug checks run.

    Returns ``(validate_all, run_verbose)``; a flag that has no effect in the chosen mode is reported and dropped.
    """

    run_verbose = verbose
    validate_all = all_variants or (variant is None and not node and workspace_has_variability(resolved_path))
    if validate_all and run_verbose:
        console.print("[dim]--verbose checks one variant at a time: pass --variant to run them; validating every variant instead.[/dim]")
        run_verbose = False
    return validate_all, run_verbose


def _result_color(result: DiagnosticsResult | VariantSetDiagnosticsResult) -> str:
    """Rich style of the final verdict line: red when failed, yellow when passed with warnings, green otherwise."""

    if not result.passed:
        return "bold red"
    if result.state is WorkspaceState.WARNING:
        return "bold yellow"
    return "bold green"


def _run_validate(
    path,
    node: str,
    config_name: str,
    verbose: bool,
    variant: str | None = None,
    all_variants: bool = False,
) -> DiagnosticsResult | VariantSetDiagnosticsResult:
    """
    Validate a FLYNC model at *path*, exiting non-zero unless it passed.

    The exit code is all a CI job sees. Warnings stay at zero: they are diagnostics, not failures.

    When *verbose* is set, the layered debug checks (folder structure, YAML syntax, schema, field values,
    system-wide) are run instead of the summary tables. Together with *node* the layers run against that node
    type as the root model, so a partial model rooted at *path* is debugged the same way.

    A workspace with a ``variability/`` folder is validated for every declared variant unless *variant* selects one (or *node*
    validates a single sub-node); *all_variants* forces the product-line validation.
    """

    resolved_path = resolve_workspace_path(path)
    if variant and all_variants:
        print_error("--variant and --all-variants cannot be combined.", "Use --variant for one variant, or --all-variants for every declared one.")
        raise typer.Exit(code=1)

    console.print(f"-- Validating {config_name} ... --")
    start = time.monotonic()

    validate_all, run_verbose = _plan_run(resolved_path, node, verbose, variant, all_variants)

    result: DiagnosticsResult | VariantSetDiagnosticsResult | None
    if validate_all:
        result = validate_variants(resolved_path)
        print_variant_results(result)
    elif run_verbose:
        result = run_debug(resolved_path, node, variant=variant)
    else:
        result = validate_external_node(node, resolved_path, variant=variant) if node else validate_workspace(resolved_path, variant=variant)
        print_validation_result(result)

    console.print(f">>> Elapsed time to load: {time.monotonic() - start:.2f}s")

    if result is None:
        console.print(f">>> Validation Result for {config_name}: [bold red] INVALID [/bold red] ")
        sys.exit(1)

    _print_migration_hint(resolved_path)

    color = _result_color(result)
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
            "the summary tables. Combine with --node to debug a partial model rooted at that node type.",
        ),
    ] = False,
    variant: VariantOpt = None,
    all_variants: Annotated[
        bool,
        typer.Option(
            "--all-variants",
            help="Validate every product variant of a workspace with a variability/ folder. This is the default for such a "
            "workspace unless --variant or --node is given.",
        ),
    ] = False,
) -> DiagnosticsResult | VariantSetDiagnosticsResult:
    """Validate a FLYNC model at the given path, exiting non-zero unless it passed."""
    return _run_validate(path, node, config_name, verbose, variant, all_variants)


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
