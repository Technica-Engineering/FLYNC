"""
CLI script for validating a FLYNC workspace or a specific node type.

When run directly, accepts a path to a FLYNC configuration directory and validates it,
printing any errors as a Rich table and exiting with a non-zero status code on failure.
Use ``--node`` to validate a specific node type instead of the full workspace.
"""

import argparse
import re
import sys
import time
from pathlib import Path

from rich.console import Console
from rich.table import Table

from flync.sdk.context.diagnostics_result import DiagnosticsResult, WorkspaceState
from flync.sdk.helpers.validation_helpers import validate_external_node, validate_workspace

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")
ERRORS_HEADER = "\n[bold red]Errors:[/bold red]"
console = Console(force_terminal=True, legacy_windows=False)


def sanitize_error_message(error_msg: str) -> str:
    return ANSI_ESCAPE_RE.sub("", error_msg)


def _make_details_cell(sub_errors: str) -> Table | str:
    """Build a nested table for the Details column, one row per sub-error."""
    if not sub_errors:
        return ""
    lines = [ln for ln in sub_errors.split("\n") if ln]
    nested = Table(show_header=False, show_edge=False, show_lines=True, padding=(0, 1))
    nested.add_column("detail", style="magenta", overflow="fold")
    for i, line in enumerate(lines):
        nested.add_row(f"Error {i + 1}: {line}")
    return nested


def _format_source(doc_uri: str, raw_ctx: dict) -> str:
    """Workspace-relative path and line number for an error or warning.

    Both yaml_path (from ctx) and doc_uri are already workspace-relative
    (doc_uri = path.absolute().relative_to(workspace_root).as_posix()).
    """
    path = str(raw_ctx.get("yaml_path", "")) or doc_uri
    line = raw_ctx.get("line")
    return f"{path}:line {line}" if line is not None else path


def render_warnings(result: DiagnosticsResult) -> None:
    rows = [(doc_uri, err) for doc_uri, errs in result.errors.items() for err in errs if err.get("type") == "warning"]
    if not rows:
        return
    console.print("\n[bold yellow]Warnings:[/bold yellow]")
    table = Table(show_lines=True)
    table.add_column("#", justify="right")
    table.add_column("Warning Type", style="yellow", overflow="fold")
    table.add_column("Message", style="white", overflow="fold")
    table.add_column("Source", style="green", overflow="fold")
    for idx, (doc_uri, err) in enumerate(rows, 1):
        table.add_row(
            str(idx),
            err.get("type", ""),
            sanitize_error_message(err.get("msg", "")),
            _format_source(doc_uri, err.get("ctx", {})),
        )
    console.print(table)


def _classify_errors(errors_by_doc: dict) -> tuple[list, list]:
    """Split non-warning (doc_uri, err) pairs into (root_rows, subsequent_rows).

    The workspace loads documents in two structural roles:
    - ``.flync.yaml`` files   — validated against their own YAML content; any error
      here is a genuine problem in that file (root cause).
    - Directory documents     — assembled from child models that returned ``None``
      when they failed; errors here exist *only* because a child document failed
      (subsequent).

    ``doc_uri`` is the workspace-relative POSIX path produced by
    ``document_id_from_path``.  File documents always carry a ``.yaml`` suffix;
    directory documents have no suffix.
    """

    root_rows: list[tuple[str, dict]] = []
    subsequent_rows: list[tuple[str, dict]] = []
    for doc_uri, errs in errors_by_doc.items():
        is_file_doc = bool(Path(doc_uri).suffix)
        for err in errs:
            if err.get("type") == "warning":
                continue
            (root_rows if is_file_doc else subsequent_rows).append((doc_uri, err))
    return root_rows, subsequent_rows


def _make_error_table() -> Table:
    table = Table(show_lines=True)
    table.add_column("#", justify="right")
    table.add_column("Error Type", style="red", overflow="fold")
    table.add_column("Message", style="yellow", overflow="fold")
    table.add_column("Location", style="cyan", overflow="fold")
    table.add_column("Source", style="green", overflow="fold")
    table.add_column("Details", style="magenta", overflow="fold")
    return table


def _fill_error_table(table: Table, rows: list, start_idx: int) -> None:
    for idx, (doc_uri, err) in enumerate(rows, start_idx):
        raw_ctx = err.get("ctx", {})
        table.add_row(
            str(idx),
            err.get("type", ""),
            sanitize_error_message(err.get("msg", "")),
            ".".join(str(p) for p in err.get("loc", [])),
            _format_source(doc_uri, raw_ctx),
            _make_details_cell(raw_ctx.get("sub_errors", "")),
        )


def render_errors(result: DiagnosticsResult, only_root: bool = True) -> None:
    all_rows = [(doc_uri, err) for doc_uri, errs in result.errors.items() for err in errs if err.get("type") != "warning"]
    if result.state == WorkspaceState.BROKEN and not all_rows:
        console.print(ERRORS_HEADER)
        console.print("[red]  Workspace could not be loaded (BROKEN)[/red]")
        return
    if not all_rows:
        return

    root_rows, subsequent_rows = _classify_errors(result.errors)

    if root_rows:
        console.print(ERRORS_HEADER)
        table = _make_error_table()
        _fill_error_table(table, root_rows, 1)
        console.print(table)

    if not only_root and subsequent_rows:
        if root_rows:
            console.print("\n[bold yellow]Subsequent Errors[/bold yellow]" "[dim](likely caused by the root errors above — fix those first):[/dim]")
        else:
            console.print(ERRORS_HEADER)
        table = _make_error_table()
        _fill_error_table(table, subsequent_rows, len(root_rows) + 1)
        console.print(table)


parser = argparse.ArgumentParser(description="Validate a FLYNC workspace or a specific node.")
parser.add_argument("path", help="Path to the FLYNC configuration directory.")
parser.add_argument(
    "-n",
    "--name",
    default="flync_config",
    help="Name of FLYNC configuration.",
)
parser.add_argument(
    "--node",
    metavar="NODE",
    help="Node type name to validate via validate_external_node. Omit to validate the full workspace.",
)
parser.add_argument("-q", "--quiet", action="store_true", help="Only show final result of the validation.")
parser.add_argument("-a", "--all", action="store_false", help="Shows all results, including warnings, errors and subsequent errors.")
args = parser.parse_args()

path = Path(args.path)
flync_name = args.node or args.name

if not path.exists():
    print(f"Error: Path does not exist: {path}", file=sys.stderr)
    sys.exit(1)

console.print(f"Validating {flync_name} ...")
start = time.monotonic()

result = validate_external_node(args.node, path.resolve()) if args.node else validate_workspace(path.resolve())

console.print(f">>> Elapsed time to load: {time.monotonic() - start:.2f}s")

if not args.quiet:
    render_warnings(result)
    render_errors(result, args.all)

has_errors = any(err.get("type") != "warning" for errs in result.errors.values() for err in errs)
if result.state in (WorkspaceState.BROKEN, WorkspaceState.INVALID) or has_errors:
    console.print(f"[bold red]>> VALIDATION FAILED for {flync_name} <<[/bold red]")
    sys.exit(1)

console.print(f"[bold green]>> {flync_name} is properly configured! <<[/bold green]")
sys.exit(0)
