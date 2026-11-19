"""
Renders FLYNC validation results as rich tables on the console.

:func:`print_validation_result` is the entry point used by the CLI commands; it classifies the diagnostics
into warnings and errors (:func:`render_warnings`, :func:`render_errors`) and formats each entry with its
workspace-relative source location. :func:`sanitize_error_message` strips ANSI escapes from messages that
already carry markup.
"""

import re
from pathlib import Path
from typing import cast

from pydantic_core import ErrorDetails
from rich.table import Table

from flync.core.utils.exceptions_handling import is_semantic_validation_error
from flync.sdk.context.diagnostics_result import DiagnosticsResult, VariantSetDiagnosticsResult, WorkspaceState
from flync_cli.utils.console import console
from flync_cli.utils.styles import (
    STYLE_DETAILS,
    STYLE_ERROR_ID,
    STYLE_ERROR_MSG,
    STYLE_ERROR_TYPE,
    STYLE_LOCATION,
    STYLE_SOURCE,
    STYLE_WARNING_ID,
    STYLE_WARNING_MSG,
    STYLE_WARNING_TYPE,
    make_table,
)

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")
VARIANTS_CTX_KEY = "variants"
VALIDATION_ERRORS: dict = {}
ERRORS_HEADER = "\n[bold red]Errors:[/bold red]"


def sanitize_error_message(error_msg: str) -> str:
    """Remove ANSI escape sequences from error message."""
    return ANSI_ESCAPE_RE.sub("", error_msg)


def _make_details_cell(sub_errors: str) -> Table | str:
    """Build a nested table for the Details column, one row per sub-error."""
    if not sub_errors:
        return ""
    lines = [ln for ln in sub_errors.split("\n") if ln]
    nested = Table(show_header=False, show_edge=False, show_lines=True, padding=(0, 1))
    nested.add_column("detail", style=STYLE_DETAILS, overflow="fold")
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


def _classify_errors(errors_by_doc: dict) -> tuple[list, list]:
    """Split non-warning (doc_uri, err) pairs into (root_rows, subsequent_rows).

    The workspace loads documents in two structural roles:
    - ``.flync.yaml`` files   — validated against their own YAML content; any error
      here is a genuine problem in that file (root cause).
    - Directory documents     — usually assembled from child models that returned
      ``None`` when they failed (cascading errors), *but* a
      ``@model_validator`` on the directory-assembled type can also raise its
      own root-cause error (e.g. ``FLYNCChannelConfig.validate_pdu_refs``
      validating PDU references across the whole channels tree).

    ``doc_uri`` is the workspace-relative POSIX path produced by
    ``document_id_from_path``.  File documents always carry a ``.yaml`` suffix;
    directory documents have no suffix. User-raised semantic errors
    (``err_major`` / ``err_minor`` / ``err_fatal``) are treated as root causes
    on either kind of document.
    """

    root_rows: list[tuple[str, dict]] = []
    subsequent_rows: list[tuple[str, dict]] = []
    for doc_uri, errs in errors_by_doc.items():
        is_file_doc = bool(Path(doc_uri).suffix)
        for err in errs:
            if err.get("type") == "warning":
                continue
            if is_file_doc or is_semantic_validation_error(err):
                root_rows.append((doc_uri, err))
            else:
                subsequent_rows.append((doc_uri, err))
    return root_rows, subsequent_rows


def _make_error_table(show_variants: bool = False) -> Table:
    """Create a Rich Table for displaying validation errors with formatted columns."""
    table = make_table()
    table.add_column("#", justify="right")
    table.add_column("ID", style=STYLE_ERROR_ID, overflow="fold")
    table.add_column("Error Type", style=STYLE_ERROR_TYPE, overflow="fold")
    table.add_column("Message", style=STYLE_ERROR_MSG, overflow="fold")
    table.add_column("Location", style=STYLE_LOCATION, overflow="fold")
    table.add_column("Source", style=STYLE_SOURCE, overflow="fold")
    if show_variants:
        table.add_column("Variants", style=STYLE_LOCATION, overflow="fold")
    table.add_column("Details", style=STYLE_DETAILS, overflow="fold")
    return table


def _fill_error_table(table: Table, rows: list, start_idx: int, show_variants: bool = False) -> None:
    """Populate a Rich Table with error rows, adding them with sequential numbering."""
    for idx, (doc_uri, err) in enumerate(rows, start_idx):
        raw_ctx = err.get("ctx", {})
        cells = [
            str(idx),
            raw_ctx.get("error_id", ""),
            err.get("type", ""),
            sanitize_error_message(err.get("msg", "")),
            ".".join(str(p) for p in err.get("loc", [])),
            _format_source(doc_uri, raw_ctx),
        ]
        if show_variants:
            cells.append(raw_ctx.get(VARIANTS_CTX_KEY, ""))
        table.add_row(*cells, _make_details_cell(raw_ctx.get("sub_errors", "")))


def render_warnings(result: DiagnosticsResult, show_variants: bool = False) -> None:
    """Display all warnings from validation result in a formatted table."""
    rows = [(doc_uri, err) for doc_uri, errs in result.errors.items() for err in errs if err.get("type") == "warning"]
    if not rows:
        return
    console.print("\n[bold yellow]Warnings:[/bold yellow]")
    table = make_table()
    table.add_column("#", justify="right")
    table.add_column("ID", style=STYLE_WARNING_ID, overflow="fold")
    table.add_column("Warning Type", style=STYLE_WARNING_TYPE, overflow="fold")
    table.add_column("Message", style=STYLE_WARNING_MSG, overflow="fold")
    table.add_column("Source", style=STYLE_SOURCE, overflow="fold")
    if show_variants:
        table.add_column("Variants", style=STYLE_LOCATION, overflow="fold")
    for idx, (doc_uri, err) in enumerate(rows, 1):
        raw_ctx = err.get("ctx", {})
        cells = [
            str(idx),
            raw_ctx.get("error_id", ""),
            err.get("type", ""),
            sanitize_error_message(err.get("msg", "")),
            _format_source(doc_uri, raw_ctx),
        ]
        if show_variants:
            cells.append(raw_ctx.get(VARIANTS_CTX_KEY, ""))
        table.add_row(*cells)
    console.print(table)


def render_errors(result: DiagnosticsResult, verbose: bool = True, show_variants: bool = False) -> None:
    """Display validation errors in formatted tables, separated by root and subsequent causes."""
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
        table = _make_error_table(show_variants)
        _fill_error_table(table, root_rows, 1, show_variants)
        console.print(table)

    if verbose and subsequent_rows:
        if root_rows:
            console.print("\n[bold yellow]Subsequent Errors[/bold yellow] [dim](likely caused by the root errors above — fix those first):[/dim]")
        else:
            console.print(ERRORS_HEADER)
        table = _make_error_table(show_variants)
        _fill_error_table(table, subsequent_rows, len(root_rows) + 1, show_variants)
        console.print(table)


def print_validation_result(result: DiagnosticsResult) -> None:
    """Display validation results (warnings and errors) from diagnostics."""
    if result.variant:
        console.print(f"[dim]Resolved for variant[/dim] [bold]{result.variant}[/bold]")
    render_warnings(result)
    render_errors(result)


def _finding_key(doc_uri: str, err: ErrorDetails) -> tuple:
    """Identify the same finding across variants: list indices shift between variants, source lines do not."""
    ctx = err.get("ctx") or {}
    line = ctx.get("line")
    where = (line, ctx.get("col")) if line is not None else tuple(err.get("loc", ()))
    return doc_uri, where, err.get("type"), ctx.get("error_id"), err.get("msg")


def merge_variant_findings(result: VariantSetDiagnosticsResult) -> dict[str, list[ErrorDetails]]:
    """
    Merge the findings of every variant, each reported once with the variants it occurs in.

    Returns:
        dict[str, list[ErrorDetails]]: Findings per document; each carries ``ctx["variants"]`` - ``"all"`` or a comma-separated list.
    """

    merged: dict[tuple, tuple[str, ErrorDetails, list[str]]] = {}
    for name, variant_result in result.variants.items():
        for doc_uri, errs in variant_result.errors.items():
            for err in errs:
                key = _finding_key(doc_uri, err)
                if key not in merged:
                    merged[key] = (doc_uri, err, [])
                merged[key][2].append(name)
    by_doc: dict[str, list[ErrorDetails]] = {}
    for doc_uri, err, names in merged.values():
        ctx = dict(err.get("ctx") or {})
        ctx[VARIANTS_CTX_KEY] = "all" if len(names) == len(result.variants) else ", ".join(names)
        finding = cast(ErrorDetails, {**err, "ctx": ctx})
        by_doc.setdefault(doc_uri, []).append(finding)
    return by_doc


def print_variant_results(result: VariantSetDiagnosticsResult) -> None:
    """Display the validation of every product variant: a summary per variant, then each finding once with its variants."""
    if result.errors:
        console.print("[bold red]The variability model could not be loaded, so no variant was validated.[/bold red]")
        print_validation_result(DiagnosticsResult(state=result.state, errors=result.errors))
        return
    table = make_table()
    table.add_column("Variant", style=STYLE_SOURCE, overflow="fold")
    table.add_column("State", overflow="fold")
    table.add_column("Errors", justify="right")
    table.add_column("Warnings", justify="right")
    for name, variant_result in result.variants.items():
        findings = [err for errs in variant_result.errors.values() for err in errs]
        warnings = sum(1 for err in findings if err.get("type") == "warning")
        if not variant_result.passed:
            state_style = "red"
        elif warnings:
            state_style = "yellow"
        else:
            state_style = "green"
        table.add_row(name or "-", f"[{state_style}]{variant_result.state.upper()}[/{state_style}]", str(len(findings) - warnings), str(warnings))
    console.print("\n[bold]Variants:[/bold]")
    console.print(table)
    combined = DiagnosticsResult(state=result.state, errors=merge_variant_findings(result))
    render_warnings(combined, show_variants=True)
    render_errors(combined, show_variants=True)
