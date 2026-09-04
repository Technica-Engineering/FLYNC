"""``flync errors`` — helper commands for the error catalog."""

import typer
from rich.table import Table

from flync_cli.utils.console import console
from flync_cli.utils.errors import (
    CATALOG_PATH,
    CatalogReport,
    next_error_number,
    render_catalog,
    scan_error_calls,
    validate_catalog,
)

app = typer.Typer(help="Inspect and maintain the FLYNC error catalog.")

_ALL_ERRORS_KINDS = {
    "unnumbered",
    "invalid_category",
    "uncategorised",
    "duplicate_numbers",
    "missing_from_catalog",
    "orphaned_in_catalog",
}
_GENERATE_BLOCKING_KINDS = {
    "unnumbered",
    "duplicate_numbers",
    "invalid_category",
}


def _drift_rows(report: CatalogReport) -> dict[str, list[tuple[str, str]]]:
    """Pre-compute ``(issue label, detail)`` rows for every drift kind."""
    return {
        "unnumbered": [("unnumbered", f"{r.file}:{r.lineno} ({r.location})") for r in report.unnumbered],
        "invalid_category": [("invalid category", f"{r.bad_category!r} at {r.file}:{r.lineno} ({r.location})") for r in report.invalid_category],
        "uncategorised": [("uncategorised", f"{r.error_id} — {r.file}:{r.lineno}") for r in report.uncategorised],
        "duplicate_numbers": [
            ("duplicate number", f"{number}: " + ", ".join(f"{r.file}:{r.lineno}" for r in rs)) for number, rs in report.duplicate_numbers.items()
        ],
        "missing_from_catalog": [("missing from catalog", e) for e in report.missing_from_catalog],
        "orphaned_in_catalog": [("orphaned in catalog", e) for e in report.orphaned_in_catalog],
    }


def _drift_table(report: CatalogReport, kinds: set[str] | None = None) -> Table:
    """Render a table of the requested catalog drift issues (default: all kinds)."""
    rows = _drift_rows(report)
    if kinds is None:
        kinds = _ALL_ERRORS_KINDS
    table = Table(show_lines=True, title="Catalog drift")
    table.add_column("Issue", style="red")
    table.add_column("Detail", style="yellow", overflow="fold")
    for kind in kinds:
        for label, detail in rows.get(kind, []):
            table.add_row(label, detail)
    return table


@app.command(name="get-next-number", help="Print the next free globally-unique error number.")
def get_next_number():
    """Print the next free error number (highest assigned + 1, never reused)."""
    console.print(next_error_number(scan_error_calls()))


@app.command(name="validate-catalog", help="Check that the catalog matches the code (source of truth).")
def validate():
    """Report drift between the code and the committed ``error_catalog.rst``."""
    records = scan_error_calls()
    text = CATALOG_PATH.read_text(encoding="utf-8") if CATALOG_PATH.exists() else None
    report = validate_catalog(records, text)

    if report.ok:
        console.print(f"[green]Catalog is in sync with {len(records)} error call sites.[/green]")
        return

    console.print(_drift_table(report))
    raise typer.Exit(code=1)


@app.command(name="generate-catalog", help="(Re)generate docs/source/error_catalog.rst from the code.")
def generate():
    """Write ``error_catalog.rst`` from the current source; requires all call sites numbered."""
    records = scan_error_calls()
    report = validate_catalog(records, None)
    if report.unnumbered or report.duplicate_numbers or report.invalid_category:
        console.print("[red]Cannot generate: fix the drift listed below first, then re-run.[/red]")
        console.print(_drift_table(report, kinds=_GENERATE_BLOCKING_KINDS))
        raise typer.Exit(code=1)

    CATALOG_PATH.write_text(render_catalog(records), encoding="utf-8")
    console.print(f"[green]Wrote {len(records)} entries to {CATALOG_PATH}.[/green]")
