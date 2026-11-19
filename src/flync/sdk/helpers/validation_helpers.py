"""
Validation helper functions for the FLYNC SDK.

Provides high-level functions to validate FLYNC workspaces and individual nodes, returning structured
:class:`~flync.sdk.context.diagnostics_result.DiagnosticsResult` objects that capture the validation state, errors, and loaded model.
"""

import faulthandler
import logging
from pathlib import Path

from pydantic_core import (
    ErrorDetails,
    InitErrorDetails,
    PydanticCustomError,
    ValidationError,
)

from flync.model import FLYNCBaseModel, FLYNCModel
from flync.model.flync_4_variability.resolution import VARIABILITY_FOLDER
from flync.sdk.context.diagnostics_result import (
    DiagnosticsResult,
    VariantSetDiagnosticsResult,
    WorkspaceState,
    worst_state,
)
from flync.sdk.workspace.flync_workspace import (
    FLYNCWorkspace,
    WorkspaceConfiguration,
    _resolve_workspace_config,
)
from flync.sdk.workspace.ids import ObjectId

from .nodes_helpers import type_from_input

logger = logging.getLogger(__name__)

faulthandler.enable()


def workspace_has_variability(workspace_path: str | Path) -> bool:
    """
    Return whether a workspace is a 150 % workspace, i.e. has a ``variability/`` folder.

    Args:
        workspace_path (str | Path): Path to the workspace directory.

    Returns:
        bool: ``True`` when the workspace declares product variants.
    """

    return (Path(workspace_path) / VARIABILITY_FOLDER).is_dir()


def validate_workspace(
    workspace_path: str | Path,
    workspace_config: WorkspaceConfiguration | None = None,
    variant: str | None = None,
) -> DiagnosticsResult:
    """
    Validate an entire FLYNC workspace rooted at the default ``FLYNCModel``.

    Args:
        workspace_path (str | Path): Path to the workspace directory.
        workspace_config (WorkspaceConfiguration | None): Optional workspace configuration. Uses defaults if ``None``.
        variant (str | None): Product variant to resolve a workspace with a ``variability/`` folder for; ``None`` uses the
        feature model's ``default_variant``. See :func:`validate_variants` to validate every variant.

    Returns:
        DiagnosticsResult: The validation outcome including state, errors, and the loaded model.
    """

    return validate_external_node(FLYNCModel, workspace_path, workspace_config, variant=variant)


def _collect_diagnostics(ws: FLYNCWorkspace) -> tuple[WorkspaceState, dict[str, list[ErrorDetails]]]:
    """Return the validation state of a loaded workspace and its documents that have findings."""

    state = WorkspaceState.VALID
    errors: dict[str, list[ErrorDetails]] = {}
    for doc_url, doc_errors in ws.documents_diags.items():
        if doc_errors:
            errors[doc_url] = list(doc_errors)
            state = WorkspaceState.WARNING
    if ws.flync_model is None:
        state = WorkspaceState.INVALID
    return state, errors


def validate_external_node(
    node: str | type[FLYNCBaseModel],
    node_path: Path | str,
    workspace_config: WorkspaceConfiguration | None = None,
    variant: str | None = None,
) -> DiagnosticsResult:
    """
    Validate a specific FLYNC node type at a given filesystem path.

    Loads the node using a fresh workspace configured with ``node`` as the root model, then inspects per-document errors to determine the overall
    :class:`~flync.sdk.context.diagnostics_result.WorkspaceState`.

    Args:
        node (str | type[FLYNCBaseModel]): The model class to validate, or its string name.
        node_path (Path | str): Path to the directory containing the node's FLYNC configuration files.
        workspace_config (WorkspaceConfiguration | None): Optional workspace configuration. \
            If ``None``, the ``.flync/config.yaml`` of ``node_path`` is used, else the defaults. \
            The ``root_model`` field is always overwritten with ``node``.
        variant (str | None): Product variant to resolve for. A sub-node (e.g. one ECU folder) is resolved with the
        variability of its enclosing workspace. ``None`` uses the feature model's ``default_variant``.

    Returns:
        DiagnosticsResult: Validation outcome with state, per-document errors, the loaded model, and the workspace instance.
    """

    node = type_from_input(node)
    state = WorkspaceState.EMPTY
    errors: dict[str, list[ErrorDetails]] = {}
    model = None
    ws = None
    node_path = Path(node_path)
    try:
        if workspace_config is None and node_path.is_dir():
            # A workspace folder is validated with its own configuration, as when it is loaded.
            workspace_config = _resolve_workspace_config(node_path, None)
        if workspace_config:
            workspace_config = WorkspaceConfiguration.create_from_config(workspace_config, root_model=node)
        else:
            workspace_config = WorkspaceConfiguration(root_model=node)
    except Exception as ex:
        logger.exception("Encountered issue while validating node %s: %s", node_path, ex)
        return DiagnosticsResult(state=WorkspaceState.BROKEN, errors=errors, model=model, workspace=ws)
    if node_path.is_dir() and not any(p.is_file() and "".join(p.suffixes) in workspace_config.allowed_extensions for p in node_path.rglob("*")):
        return DiagnosticsResult(state=WorkspaceState.EMPTY, errors=errors, model=model, workspace=ws)
    try:
        ws = FLYNCWorkspace.safe_load_workspace(
            "validation_workspace",
            node_path,
            workspace_config=workspace_config,
            variant=variant,
        )
        model = ws.flync_model
        # only add documents that have problems
        state, errors = _collect_diagnostics(ws)
    except Exception as ex:
        state = WorkspaceState.BROKEN
        logger.exception("Encountered issue while validating node %s: %s", node_path, ex)
        error = InitErrorDetails(
            type=PydanticCustomError(
                "unhandled_exception",
                "unhandled exception caught: {ex}",
                {"ex": str(ex)},
            ),
            ctx={"ex": str(ex)},
            input=node_path.name,
        )
        try:
            raise ValidationError.from_exception_data(title="node validation", line_errors=[error])
        except ValidationError as validation_error:
            errors[str(node_path)] = validation_error.errors()
    active = ws.active_variant.name if ws is not None and ws.active_variant is not None else None
    return DiagnosticsResult(state=state, errors=errors, model=model, workspace=ws, variant=active)


def validate_variants(
    workspace_path: str | Path,
    workspace_config: WorkspaceConfiguration | None = None,
    variants: list[str] | None = None,
    keep_models: bool = False,
) -> VariantSetDiagnosticsResult:
    """
    Validate every product variant of a 150 % workspace.

    The documents are parsed once; the workspace is then resolved and fully validated for one variant after the other. Every
    rule of the model therefore applies per variant: a finding is reported for exactly the variants it occurs in.

    Args:
        workspace_path (str | Path): Path to the workspace directory.
        workspace_config (WorkspaceConfiguration | None): Optional workspace configuration. Object mapping is always disabled.
        variants (list[str] | None): The variants to validate; ``None`` validates every declared variant.
        keep_models (bool): Keep the resolved model of each variant in its result. Off by default, since a product line can
        hold many variants.

    Returns:
        VariantSetDiagnosticsResult: The result per variant. A workspace without variability is validated once, under the
        variant name ``""``.
    """

    workspace_path = Path(workspace_path)
    if not workspace_has_variability(workspace_path):
        single = validate_workspace(workspace_path, workspace_config)
        return VariantSetDiagnosticsResult(state=single.state, variants={"": single}, errors={})

    if workspace_config:
        config = WorkspaceConfiguration.create_from_config(workspace_config, root_model=FLYNCModel, map_objects=False)
    else:
        config = WorkspaceConfiguration(root_model=FLYNCModel, map_objects=False)
    try:
        ws = FLYNCWorkspace.safe_load_workspace("variant_validation", workspace_path, workspace_config=config)
    except Exception as ex:
        logger.exception("Encountered issue while validating the variants of %s: %s", workspace_path, ex)
        return VariantSetDiagnosticsResult(state=WorkspaceState.BROKEN, variants={}, errors={})
    return _validate_loaded_variants(ws, variants if variants is not None else ws.variants, keep_models, workspace_path)


def _validate_loaded_variants(ws: FLYNCWorkspace, names: list[str], keep_models: bool, workspace_path: Path) -> VariantSetDiagnosticsResult:
    """Validate the variants ``names`` of a loaded workspace one after the other; a broken variability model fails them all."""

    if ws.variability is None:
        # the variability model itself is broken, so no variant can be resolved
        _, errors = _collect_diagnostics(ws)
        return VariantSetDiagnosticsResult(state=WorkspaceState.INVALID, variants={}, errors=errors)
    results: dict[str, DiagnosticsResult] = {}
    for name in names:
        try:
            if ws.active_variant is None or ws.active_variant.name != name or ws.flync_model is None:
                ws.select_variant(name)
            state, errors = _collect_diagnostics(ws)
            model = ws.flync_model if keep_models else None
            results[name] = DiagnosticsResult(state=state, errors=errors, model=model, workspace=None, variant=name)
        except Exception as ex:
            logger.exception("Encountered issue while validating variant %s of %s: %s", name, workspace_path, ex)
            results[name] = DiagnosticsResult(state=WorkspaceState.BROKEN, errors={}, variant=name)
    return VariantSetDiagnosticsResult(state=worst_state([result.state for result in results.values()]), variants=results, errors={})


def validate_node(
    ws_path: Path | str,
    node_path: str = "",
    workspace_config: WorkspaceConfiguration | None = None,
) -> DiagnosticsResult:
    """
    Validate a single node within an already-loaded workspace.

    First validates the full workspace, then checks that the node at ``node_path`` exists and extracts its model. If the node is missing, a
    fatal validation error is recorded.

    Args:
        ws_path (Path | str): Path to the workspace root directory.
        node_path (str): Dot-separated path to the target node within the workspace object graph.
        workspace_config (WorkspaceConfiguration | None): Optional workspace configuration forwarded to :func:`validate_workspace`.

    Returns:
        DiagnosticsResult: Validation outcome for the specified node.
    """

    # load entire workspace
    workspace_results = validate_workspace(ws_path, workspace_config=workspace_config)
    # validate node in workspace
    if not workspace_results.workspace or node_path not in workspace_results.workspace.objects:
        workspace_results.state = WorkspaceState.INVALID
        fatal_ctx = {"node_path": node_path}
        error = InitErrorDetails(
            type=PydanticCustomError(
                "fatal",
                "unhandled exception caught: {ex}",
                fatal_ctx,
            ),
            ctx=fatal_ctx,
            input=workspace_results.model,
        )
        try:
            raise ValidationError.from_exception_data(title="partial node validation", line_errors=[error])
        except ValidationError as ex:
            workspace_results.errors[node_path] = ex.errors()
    else:
        workspace_results.model = workspace_results.workspace.objects[ObjectId(node_path)].model  # type: ignore[assignment]
    return workspace_results
