"""
CLI script for validating a FLYNC workspace.

When run directly, accepts a path to a FLYNC configuration directory and
validates it, printing any errors as a Rich table and exiting with a non-zero
status code on failure.
"""

import argparse
import re
import sys
from pathlib import Path

from pydantic import ValidationError
from pydantic_core import ErrorDetails
from rich.console import Console
from rich.table import Table

from flync.sdk.workspace.flync_workspace import FLYNCWorkspace

PROJECT_BASE = Path(__file__).resolve().parent.parent
VALIDATION_ERRORS: dict = {}
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")
console = Console(force_terminal=True, legacy_windows=False)


def _make_details_cell(sub_errors: str) -> Table | str:
    """Build a nested table for the Details column.

    Each newline-separated sub-error gets its own row, separated by a
    horizontal rule, matching the visual pattern:

        Error 1: abc not good
        ─────────────────────
        Error 2: DEF not good
    """
    if not sub_errors:
        return ""
    lines = [ln for ln in sub_errors.split("\n") if ln]
    nested = Table(
        show_header=False,
        show_edge=False,
        show_lines=True,
        padding=(0, 1),
    )
    nested.add_column("detail", style="magenta", overflow="fold")
    for i, line in enumerate(lines):
        nested.add_row(f"Error {i + 1}: {line}")
    return nested


def sanitize_error_message(error_msg: str) -> str:
    """Strip ANSI escape codes from an error message string.

    Args:
        error_msg (str): The raw error message, potentially containing ANSI
            colour sequences.

    Returns:
        str: The message with all ANSI escape codes removed.
    """
    return ANSI_ESCAPE_RE.sub("", error_msg)


def __add_pydantic_errors_to_report(
    pydantic_validation_errors: list[ErrorDetails],
    error_list: list,
):
    """Append formatted rows for Pydantic errors to a report list.

    Each error is flattened into a ``[type, message, location, context]``
    row and appended to ``error_list`` in place.

    Args:
        pydantic_validation_errors (list[ErrorDetails]): Pydantic error detail
            dicts as returned by ``ValidationError.errors()``.
        error_list (list): The mutable list to append formatted rows to.
    """
    for err in pydantic_validation_errors:
        location = ".".join(str(p) for p in err.get("loc", []))
        err_type = err.get("type", "")
        msg = err.get("msg", "")
        raw_ctx = err.get("ctx", {})
        sub_errors = raw_ctx.get("sub_errors", "")
        ctx = ", ".join(
            f"{k}={v}" for k, v in raw_ctx.items() if k != "sub_errors"
        )
        error_list.append([err_type, msg, location, ctx, sub_errors])


def add_errors_to_report(
    errors_report,
    config_name: str,
    exc: Exception,
):
    """Record an exception as formatted error rows in a report dictionary.

    Handles both :class:`pydantic.ValidationError` (expanded field-by-field)
    and generic exceptions (treated as a single row).

    Args:
        errors_report (dict): Mapping of config names to lists of error rows.
            Updated in place.
        config_name (str): Key under which the errors are stored.
        exc (Exception): The exception to record.

    Returns:
        dict: The updated ``errors_report`` mapping.
    """
    errs: list = []

    if isinstance(exc, ValidationError):
        pydantic_validation_errors = exc.errors()
        __add_pydantic_errors_to_report(pydantic_validation_errors, errs)
    else:
        # Generic exception handling
        location = ""
        err_type = type(exc).__name__
        msg = sanitize_error_message(str(exc))
        ctx = ""
        errs.append([err_type, msg, location, ctx, ""])

    errors_report[config_name] = errs
    return errors_report


def render_validation_errors(errors: dict) -> None:
    """Display FLYNC project validation errors as a Rich table."""
    for config_name, errs in errors.items():
        console.print(f"\n[bold red]Errors for {config_name}:[/bold red]")
        table = Table(show_lines=True)
        table.add_column("Num.", justify="right")
        table.add_column("Error Type", style="red", overflow="fold")
        table.add_column("Message", style="yellow", overflow="fold")
        table.add_column("Location", style="cyan", overflow="fold")
        table.add_column("Context", style="green", overflow="fold")
        table.add_column("Details", style="magenta", overflow="fold")
        for idx, error_row in enumerate(errs, 1):
            *main_cols, sub = error_row
            table.add_row(str(idx), *main_cols, _make_details_cell(sub))
        console.print(table)


parser = argparse.ArgumentParser(
    description="Script to validate a FLYNC workspace."
)
parser.add_argument("path", help="Absolute path to FLYNC configuration.")
parser.add_argument(
    "-n",
    "--name",
    default="flync_config",
    help="Name of FLYNC configuration.",
)
args = parser.parse_args()

path = Path(args.path)
flync_name = args.name

if not path.exists():
    print(f"Error: Path does not exist: {path}", file=sys.stderr)
    sys.exit(1)


console.print(f"Validating {flync_name} ...")
loaded_ws = None
VALIDATION_WARNINGS: dict = {}
VALIDATION_SOFT_ERRORS: dict = {}
try:
    loaded_ws = FLYNCWorkspace.load_workspace(flync_name, path.resolve())
except Exception as e:
    console.print(
        "[bold red]VALIDATION FAILED:"
        f" Validation of {flync_name} failed![/bold red]"
    )
    if isinstance(e, ValidationError):
        all_errs = e.errors()
        warn_rows = [x for x in all_errs if x.get("type") == "warning"]
        err_rows = [x for x in all_errs if x.get("type") != "warning"]
        if warn_rows:
            VALIDATION_WARNINGS[flync_name] = []
            __add_pydantic_errors_to_report(
                warn_rows, VALIDATION_WARNINGS[flync_name]
            )
        if err_rows:
            err_list: list = []
            __add_pydantic_errors_to_report(err_rows, err_list)
            VALIDATION_ERRORS[flync_name] = err_list
    else:
        VALIDATION_ERRORS = add_errors_to_report(
            VALIDATION_ERRORS, flync_name, e
        )
if loaded_ws and loaded_ws.load_errors:
    actual_warnings = [
        e for e in loaded_ws.load_errors if e.get("type") == "warning"
    ]
    soft_errors = [
        e for e in loaded_ws.load_errors if e.get("type") != "warning"
    ]
    if actual_warnings:
        VALIDATION_WARNINGS[flync_name] = []
        __add_pydantic_errors_to_report(
            actual_warnings, VALIDATION_WARNINGS[flync_name]
        )
    if soft_errors:
        VALIDATION_SOFT_ERRORS[flync_name] = []
        __add_pydantic_errors_to_report(
            soft_errors, VALIDATION_SOFT_ERRORS[flync_name]
        )

for config_name, warnings in VALIDATION_WARNINGS.items():
    console.print(f"\n[bold yellow]Warnings for {config_name}:[/bold yellow]")
    table = Table(show_lines=True)
    table.add_column("Num.", justify="right")
    table.add_column("Warning Type", style="yellow", overflow="fold")
    table.add_column("Message", style="white", overflow="fold")
    for idx, warning_row in enumerate(warnings, 1):
        table.add_row(str(idx), warning_row[0], warning_row[1])
    console.print(table)

render_validation_errors(VALIDATION_SOFT_ERRORS)
render_validation_errors(VALIDATION_ERRORS)
if len(VALIDATION_ERRORS) == 0:
    console.print(
        f"[bold green]>> {flync_name} is properly configured! <<[/bold green]"
    )
    sys.exit(0)
else:
    sys.exit(1)
