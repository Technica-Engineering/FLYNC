"""``flync errors`` — helper commands for the error catalogue."""

import typer
from rich.console import Console
from rich.table import Table

from flync_cli.utils.errors import (
    CATALOGUE_PATH,
    next_error_number,
    render_catalogue,
    scan_error_calls,
    validate_catalogue,
)

app = typer.Typer(help="Inspect and maintain the FLYNC error catalogue.")
console = Console(force_terminal=True)


@app.command(name="get-next-number", help="Print the next free globally-unique error number.")
def get_next_number():
    """Print the next free error number (highest assigned + 1, never reused)."""
    console.print(next_error_number(scan_error_calls()))


@app.command(name="validate-catalogue", help="Check that the catalogue matches the code (source of truth).")
def validate():
    """Report drift between the code and the committed ``error_catalogue.rst``."""
    records = scan_error_calls()
    text = CATALOGUE_PATH.read_text(encoding="utf-8") if CATALOGUE_PATH.exists() else None
    report = validate_catalogue(records, text)

    if report.ok:
        console.print(f"[green]Catalogue is in sync with {len(records)} error call sites.[/green]")
        return

    table = Table(show_lines=True, title="Catalogue drift")
    table.add_column("Issue", style="red")
    table.add_column("Detail", style="yellow", overflow="fold")
    for r in report.unnumbered:
        table.add_row("unnumbered", f"{r.file}:{r.lineno} ({r.location})")
    for r in report.invalid_category:
        table.add_row("invalid category", f"{r.bad_category!r} at {r.file}:{r.lineno} ({r.location})")
    for r in report.uncategorised:
        table.add_row("uncategorised", f"{r.error_id} — {r.file}:{r.lineno}")
    for number, rs in report.duplicate_numbers.items():
        table.add_row("duplicate number", f"{number}: " + ", ".join(f"{r.file}:{r.lineno}" for r in rs))
    for error_id in report.missing_from_catalogue:
        table.add_row("missing from catalogue", error_id)
    for error_id in report.orphaned_in_catalogue:
        table.add_row("orphaned in catalogue", error_id)
    console.print(table)
    raise typer.Exit(code=1)


@app.command(name="generate-catalogue", help="(Re)generate docs/source/error_catalogue.rst from the code.")
def generate():
    """Write ``error_catalogue.rst`` from the current source; requires all call sites numbered."""
    records = scan_error_calls()
    report = validate_catalogue(records, None)
    if report.unnumbered or report.duplicate_numbers or report.invalid_category:
        console.print("[red]Cannot generate: fix unnumbered / duplicate / invalid-category call sites first (see validate-catalogue).[/red]")
        raise typer.Exit(code=1)

    CATALOGUE_PATH.write_text(render_catalogue(records), encoding="utf-8")
    console.print(f"[green]Wrote {len(records)} entries to {CATALOGUE_PATH}.[/green]")
