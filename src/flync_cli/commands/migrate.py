"""
``flync migrate`` — bring a FLYNC workspace up to the installed FLYNC schema.

Detects the version gap between the workspace's recorded version and the installed FLYNC release and
applies the registered schema migrations in order, recording them in ``.flync/migrations/history.yaml``.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table
from typing_extensions import Annotated

from flync.core.version_migrators.engine import Migrator
from flync.core.version_migrators.engine import WorkspaceMigrationState as State

console = Console(force_terminal=True, legacy_windows=False)
app = typer.Typer(help="Migrate a FLYNC workspace to the installed FLYNC schema.")


def _print_plan(migrator: Migrator, path: Path) -> State | None:
    """Print the migration status/plan for ``path`` and return its state."""
    try:
        status = migrator.plan(path)
    except Exception as exc:  # pragma: no cover - defensive
        console.print(f"[bold red]Could not read migration status: {exc}[/bold red]")
        return None

    # NO_VERSION is the only state without a recorded stamp; handle it first so the
    # narrowing assert below never runs on a ``None`` recorded version.
    if status.state is State.NO_VERSION:
        console.print(
            "[bold yellow]Workspace has no recorded FLYNC version[/bold yellow]\n"
            f"`.flync/config.yaml` at {path} is missing or has no `version` entry, so FLYNC treats the workspace as "
            "already in the installed schema.\n"
            f"Run `flync migrate --init {path}` to record the current version (no data is changed)."
        )
        return status.state

    assert status.recorded is not None
    if status.state is State.NEWER:
        console.print(
            f"[bold yellow]Workspace was created by FLYNC {status.recorded.version}, newer than the installed "
            f"{status.current.version}.[/bold yellow]\nRefusing to migrate a workspace from a newer FLYNC."
        )
    elif status.state is State.UNSUPPORTED_OLD:
        console.print(
            f"[bold red]Workspace records FLYNC {status.recorded.version}, older than the lowest supported "
            f"{status.lowest_supported}.[/bold red]\nThere is no migration path; re-create or re-import the workspace."
        )
    elif status.state is State.PENDING_MIGRATION:
        table = Table(title=f"Migrations to apply: {status.recorded.version} → {status.current.version}", show_lines=True)
        table.add_column("Migration", style="cyan")
        table.add_column("Target", style="green")
        table.add_column("Description", overflow="fold")
        for migration in status.pending:
            table.add_row(migration.unique_id, migration.target_version, migration.description)
        console.print(table)
        console.print(f"\nRun `flync migrate {path}` to apply {len(status.pending)} migration(s).")
    elif status.requires_stamp:
        console.print(
            f"[green]Workspace is up to date, but its version stamp ({status.recorded.version}) lags the installed "
            f"{status.current.version}.[/green]\nRun `flync migrate {path}` to advance the stamp."
        )
    else:
        console.print(f"[green]Workspace is up to date (FLYNC {status.current.version}).[/green]")
    return status.state


@app.command(help="Migrate a FLYNC workspace to the installed FLYNC schema.")
def migrate(
    path: Annotated[str, typer.Argument(help="Path to the FLYNC workspace directory.")],
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", "--plan", help="Show what would run without changing anything."),
    ] = False,
    init: Annotated[
        bool,
        typer.Option("--init", help="Only stamp the workspace with the current FLYNC version (no transforms)."),
    ] = False,
):
    """
    Apply pending migrations to the workspace at ``path``.

    Without flags, applies pending migrations in order and records them in
    ``.flync/migrations/history.yaml``. ``--dry-run`` only prints the plan; ``--init`` only stamps a
    baseline version without touching the workspace content.

    Exit codes: 0 on success or plan-only, 1 when an unsupported/error state prevents migration.
    """
    resolved = Path(path).resolve()
    if not resolved.exists():
        console.print(f"[bold red]Path does not exist: {path}[/bold red]")
        raise typer.Exit(code=1)

    migrator = Migrator()

    if init:
        try:
            migrator.stamp(resolved)
        except Exception as exc:  # pragma: no cover - defensive
            console.print(f"[bold red]Could not stamp the workspace: {exc}[/bold red]")
            raise typer.Exit(code=1)
        console.print(f"[green]Stamped {resolved} with the current FLYNC version.[/green]")
        raise typer.Exit(code=0)

    state = _print_plan(migrator, resolved)

    if dry_run:
        raise typer.Exit(code=0 if state is not State.UNSUPPORTED_OLD else 1)
    if state in (State.NO_VERSION, State.NEWER, State.UNSUPPORTED_OLD):
        raise typer.Exit(code=0 if state is State.NEWER else 1)

    try:
        result = migrator.run(resolved)
    except RuntimeError as exc:
        console.print(f"[bold red]{exc}[/bold red]")
        raise typer.Exit(code=1)

    console.print(f"[bold green]{result.message}[/bold green]")
    for uri in result.changed_uris:
        console.print(f"  [cyan]updated[/cyan] {uri}")
    if result.changed_uris:
        console.print("Recorded in .flync/migrations/history.yaml.")
    raise typer.Exit(code=0)


if __name__ == "__main__":
    app()
