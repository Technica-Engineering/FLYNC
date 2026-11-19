"""``flync variants`` command group: inspect, check, and export the product variants of a 150 % workspace."""

from pathlib import Path
from typing import Iterator, Optional

import typer
from rich.markup import escape
from typing_extensions import Annotated

from flync.model.flync_4_variability import (
    Condition,
    ConditionSyntaxError,
    Variability,
    VariantContext,
    VariantDefinition,
    compile_condition,
)
from flync.sdk.context.diagnostics_result import DiagnosticsResult, WorkspaceState
from flync.sdk.helpers.generation_helpers import export_variant
from flync.sdk.helpers.validation_helpers import validate_workspace, workspace_has_variability
from flync.sdk.helpers.variant_helpers import compare_workspace_variants, trace_workspace_features
from flync.sdk.workspace.flync_workspace import FLYNCWorkspace, VariantWorkspaceWriteError, WorkspaceConfiguration
from flync_cli.utils.console import console, print_error
from flync_cli.utils.error_table import print_validation_result
from flync_cli.utils.styles import STYLE_SOURCE, STYLE_VARIANT, make_table
from flync_cli.utils.workspace import WorkspacePathArg, resolve_workspace_path

app = typer.Typer(help="Inspect, check, and export the product variants of a workspace with a variability/ folder.")

VariantArg = Annotated[str, typer.Argument(help="Name of the product variant.")]

_VARIABILITY_ERROR_PREFIX = "FLYNC-VAR-"


def _load_variability(path: Optional[str]) -> tuple[Path, Variability]:
    """Resolve the workspace path and load its variability model, or exit 1 with a message."""

    resolved = resolve_workspace_path(path)
    if not workspace_has_variability(resolved):
        print_error(
            f"{escape(str(resolved))} has no variability/ folder, so it describes a single architecture.",
            "The variants commands need a workspace with a variability/ folder.",
        )
        raise typer.Exit(code=1)
    workspace = FLYNCWorkspace.safe_load_workspace(
        "variants",
        resolved / "variability",
        workspace_config=WorkspaceConfiguration(root_model=Variability, map_objects=False),
    )
    if not isinstance(workspace.flync_model, Variability):
        print_error("The variability model could not be loaded.", "Fix the findings below in variability/ first.")
        print_validation_result(DiagnosticsResult(state=WorkspaceState.INVALID, errors={k: v for k, v in workspace.documents_diags.items() if v}))
        raise typer.Exit(code=1)
    return resolved, workspace.flync_model


def _declared_features_hint(variability: Variability) -> str:
    """The hint under an error about a feature name: the features the feature model declares."""

    return f"Declared features: {escape(', '.join(feature.name for feature in variability.features()))}."


def _format_value(value: object) -> str:
    """Render a feature value for the table: booleans as colored yes/no."""

    if value is True:
        return "[green]yes[/green]"
    if value is False:
        return "[dim]no[/dim]"
    return str(value)


DEFAULT_LIST_LIMIT = 50
"""Rows ``flync variants list`` shows unless ``--limit`` says otherwise; a product line can declare millions of variants."""

_NAMES_IN_MESSAGES = 10
"""Variant names an error message lists before it abbreviates the rest."""


def _compile_filter(variability: Variability, where: str) -> Condition:
    """Compile a ``--where`` condition and check it against the feature model, or exit 1 with the reason."""

    try:
        condition = compile_condition(where)
    except ConditionSyntaxError as exc:
        print_error(f"Invalid --where condition '{escape(where)}': {escape(exc.reason)}.", _declared_features_hint(variability))
        raise typer.Exit(code=1) from None
    problems = variability.symbol_table().problems(condition)
    if problems:
        print_error(f"Invalid --where condition '{escape(where)}': {escape('; '.join(problems))}.", _declared_features_hint(variability))
        raise typer.Exit(code=1)
    return condition


def _check_features(variability: Variability, features: list[str]) -> None:
    """Exit 1 with a message when a ``--feature`` names no declared feature."""

    unknown = [name for name in features if variability.feature_model.feature(name) is None]
    if unknown:
        print_error(f"Unknown feature {escape(', '.join(map(repr, unknown)))}.", _declared_features_hint(variability))
        raise typer.Exit(code=1)


@app.command(
    name="list",
    help=(
        "List the product variants, one row per variant: name, inheritance, and description. "
        f"Shows the first {DEFAULT_LIST_LIMIT} by default; filter with --where and add feature columns with --feature."
    ),
)
def list_variants(
    path: WorkspacePathArg = None,
    where: Annotated[
        Optional[str],
        typer.Option("--where", "-w", help="Only list the variants in which this variant condition holds, e.g. 'architecture == zonal'."),
    ] = None,
    features: Annotated[
        Optional[list[str]],
        typer.Option("--feature", "-f", help="Add a column with the value of this feature. Repeat it for several features."),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", "-n", min=0, help=f"Show at most this many variants (default {DEFAULT_LIST_LIMIT}); 0 shows all of them."),
    ] = DEFAULT_LIST_LIMIT,
):
    """List the product variants, one row per variant, filtered and limited."""
    _, variability = _load_variability(path)
    columns = features or []
    _check_features(variability, columns)
    condition = _compile_filter(variability, where) if where is not None else None
    rows, matching = _list_rows(variability, condition, columns, limit)
    if rows:
        table = make_table()
        table.add_column("Variant", style=STYLE_VARIANT, overflow="fold")
        table.add_column("Extends", style=STYLE_SOURCE)
        table.add_column("Description", overflow="fold")
        for name in columns:
            table.add_column(name)
        for row in rows:
            table.add_row(*row)
        console.print(table)
    console.print(_list_summary(len(rows), matching, len(variability.variants or []), filtered=condition is not None))


def _matching_variants(
    variability: Variability, condition: Optional[Condition], with_context: bool
) -> Iterator[tuple[VariantDefinition, Optional[VariantContext]]]:
    """Yield the declared variants in which ``condition`` holds (every variant without one), with their context if asked for."""

    for variant in variability.variants or []:
        # contexts are only built where something needs them: with millions of variants this is most of the cost
        context = variability.context(variant.name) if with_context or condition is not None else None
        if condition is None or (context is not None and context.holds(condition)):
            yield variant, context


def _list_rows(variability: Variability, condition: Optional[Condition], columns: list[str], limit: int) -> tuple[list[list[str]], int]:
    """The rows of ``flync variants list`` (at most ``limit`` of them, all for ``0``) and the number of matching variants."""

    default = variability.feature_model.default_variant
    rows: list[list[str]] = []
    matching = 0
    for variant, context in _matching_variants(variability, condition, with_context=bool(columns)):
        matching += 1
        if limit and len(rows) >= limit:
            if condition is None:
                # without a filter every remaining variant matches; no need to visit them
                return rows, len(variability.variants or [])
            continue
        marker = " (default)" if variant.name == default else ""
        values = [_format_value(context.assignment.get(name, "-")) for name in columns] if context is not None else []
        rows.append([f"{variant.name}{marker}", variant.extends or "-", variant.description or "", *values])
    return rows, matching


def _list_summary(shown: int, matching: int, declared: int, filtered: bool) -> str:
    """The footer of ``flync variants list``: how many variants are shown out of how many."""

    if filtered and not matching:
        return f">>> No variant matches the condition ({declared:,} declared)."
    if filtered:
        text = f">>> {shown:,} of {matching:,} matching variants shown ({declared:,} declared)"
    else:
        text = f">>> {shown:,} of {declared:,} variants shown"
    if shown < matching:
        text += "; use --limit to see more, or --where to narrow the list"
    return text + "."


def _require_variant(variability: Variability, variant: str) -> None:
    """Exit 1 with a message when ``variant`` is not declared."""

    if variability.variant(variant) is None:
        names = variability.variant_names()
        listed = ", ".join(names[:_NAMES_IN_MESSAGES])
        if len(names) > _NAMES_IN_MESSAGES:
            listed += f", ... ({len(names):,} in total; see 'flync variants list')"
        print_error(f"Unknown variant '{escape(variant)}'.", f"Available variants: {escape(listed)}.")
        raise typer.Exit(code=1)


@app.command(
    name="show",
    help="Show one variant: its description, inheritance, every feature value with where it comes from, and active qualifiers.",
)
def show_variant(variant: VariantArg, path: WorkspacePathArg = None):
    """Show one variant: its description, inheritance, feature values with their source, and active qualifiers."""
    _, variability = _load_variability(path)
    _require_variant(variability, variant)
    definition = variability.variant(variant)
    assert definition is not None
    context = variability.context(variant)
    console.print(f"[bold]{variant}[/bold]" + (f" - {definition.description}" if definition.description else ""))
    if definition.extends:
        console.print(f"[dim]extends[/dim] {definition.extends}")
    table = make_table()
    table.add_column("Feature", style=STYLE_SOURCE)
    table.add_column("Value", style=STYLE_VARIANT)
    table.add_column("Source")
    table.add_column("Type")
    for feature in variability.features():
        source = context.sources.get(feature.name)
        table.add_row(
            feature.name,
            _format_value(context.assignment.get(feature.name, "-")),
            source.value if source is not None else "-",
            feature.feature_type.value,
        )
    console.print(table)
    qualifiers = [name for name in variability.feature_model.qualifiers if context.is_enabled(name)]
    console.print(f"[dim]active qualifiers:[/dim] {', '.join(qualifiers) or 'none'}")


def _presence_text(present: bool) -> str:
    """Describe whether an element is part of a variant."""

    return "present" if present else "absent"


@app.command(name="trace", help="Trace features to the workspace elements they decide.")
def trace(
    feature: Annotated[Optional[str], typer.Option("--feature", "-f", help="Only trace this feature.")] = None,
    path: WorkspacePathArg = None,
):
    """Trace features to the variation points that refer to them."""
    resolved, variability = _load_variability(path)
    if feature is not None and variability.feature_model.feature(feature) is None:
        print_error(f"Unknown feature '{escape(feature)}'.", _declared_features_hint(variability))
        raise typer.Exit(code=1)
    traced = trace_workspace_features(resolved, variability)
    table = make_table()
    table.add_column("Feature", style=STYLE_SOURCE)
    table.add_column("Category")
    table.add_column("Workspace elements", overflow="fold")
    for name, points in traced.items():
        if feature is not None and name != feature:
            continue
        declared = variability.feature_model.feature(name)
        category = declared.category.value if declared is not None and declared.category is not None else "-"
        elements = "\n".join(point.describe() for point in points) or "-"
        table.add_row(name, category, elements)
    console.print(table)


@app.command(name="diff", help="Compare two variants: the feature values and the workspace elements that differ.")
def diff(
    left: Annotated[str, typer.Argument(help="Name of the first variant.")],
    right: Annotated[str, typer.Argument(help="Name of the second variant.")],
    path: WorkspacePathArg = None,
):
    """Compare two variants feature by feature and element by element."""
    resolved, variability = _load_variability(path)
    _require_variant(variability, left)
    _require_variant(variability, right)
    comparison = compare_workspace_variants(resolved, variability, left, right)
    if comparison.identical:
        console.print(f"Variants [bold]{left}[/bold] and [bold]{right}[/bold] resolve identically.")
        return
    features = make_table()
    features.add_column("Feature", style=STYLE_SOURCE)
    features.add_column(left, style=STYLE_VARIANT)
    features.add_column(right, style=STYLE_VARIANT)
    for name, left_value, right_value in comparison.features:
        features.add_row(
            name, _format_value(left_value if left_value is not None else "-"), _format_value(right_value if right_value is not None else "-")
        )
    console.print(features)
    elements = make_table()
    elements.add_column("Workspace element", style=STYLE_SOURCE, overflow="fold")
    elements.add_column(left, style=STYLE_VARIANT)
    elements.add_column(right, style=STYLE_VARIANT)
    for point, left_outcome, right_outcome in comparison.elements:
        elements.add_row(point.describe(), _presence_text(left_outcome), _presence_text(right_outcome))
    console.print(elements)
    console.print(f">>> {len(comparison.features)} features and {len(comparison.elements)} workspace elements differ.")


@app.command(name="check", help="Check the variability model and every variation point of the workspace, for all variants at once.")
def check_variants(path: WorkspacePathArg = None):
    """Check the variability model and every variation point of the workspace."""
    resolved, variability = _load_variability(path)
    result = validate_workspace(resolved, variant=variability.variant_names()[0])
    findings = {
        doc: [err for err in errs if str((err.get("ctx") or {}).get("error_id", "")).startswith(_VARIABILITY_ERROR_PREFIX)]
        for doc, errs in result.errors.items()
    }
    findings = {doc: errs for doc, errs in findings.items() if errs}
    print_validation_result(DiagnosticsResult(state=result.state, errors=findings))
    failed = any(err.get("type") != "warning" for errs in findings.values() for err in errs)
    console.print(
        f">>> {len(variability.variant_names())} variants, {len(variability.features())} features: "
        + ("[bold red]INVALID[/bold red]" if failed else "[bold green]VALID[/bold green]")
    )
    if failed:
        raise typer.Exit(code=1)


@app.command(name="export", help="Write one resolved variant as a plain workspace without variability, for downstream tools.")
def export(
    variant: VariantArg,
    output: Annotated[Path, typer.Option("--out", "-o", help="Folder to write the variant workspace to.")],
    path: WorkspacePathArg = None,
):
    """Write one resolved variant as a plain workspace without variability."""
    resolved = resolve_workspace_path(path)
    result = validate_workspace(resolved, variant=variant)
    if result.model is None:
        print_validation_result(result)
        print_error(f"Variant '{escape(variant)}' could not be resolved, so nothing was exported.", "See the findings above.")
        raise typer.Exit(code=1)
    if not result.passed:
        print_validation_result(result)
        console.print("[yellow]The variant has validation errors; exporting what could be loaded.[/yellow]")
    try:
        export_variant(result.model, output.resolve(), workspace_name=variant)  # type: ignore[arg-type]
    except VariantWorkspaceWriteError as exc:
        print_error(escape(str(exc)))
        raise typer.Exit(code=1) from None
    console.print(f"[green]Exported variant[/green] [bold]{variant}[/bold] [green]to[/green] {output.resolve()}")
