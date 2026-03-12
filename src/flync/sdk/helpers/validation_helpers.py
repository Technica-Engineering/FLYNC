"""
Validation helper functions for the FLYNC SDK.

Provides high-level functions to validate FLYNC workspaces and individual
nodes, returning structured
:class:`~flync.sdk.context.diagnostics_result.DiagnosticsResult`
objects that capture the validation state, errors, and loaded model.
"""

import faulthandler
import logging
from pathlib import Path
from typing import Optional

from pydantic_core import (
    InitErrorDetails,
    PydanticCustomError,
    ValidationError,
)

from flync.model import FLYNCBaseModel, FLYNCModel
from flync.sdk.context.diagnostics_result import (
    DiagnosticsResult,
    WorkspaceState,
)
from flync.sdk.context.node_info import NodeInfo
from flync.sdk.utils.model_dependencies import get_model_dependency_graph
from flync.sdk.workspace.flync_workspace import (
    FLYNCWorkspace,
    WorkspaceConfiguration,
)
from flync.sdk.workspace.ids import ObjectId

logger = logging.getLogger(__name__)

faulthandler.enable()


def validate_workspace(workspace_path: str | Path) -> DiagnosticsResult:
    """Validate an entire FLYNC workspace rooted at the default ``FLYNCModel``.

    Args:
        workspace_path (str): Path to the workspace directory.

    Returns:
        DiagnosticsResult: The validation outcome including state, errors, and
        the loaded model.
    """
    return validate_external_node(FLYNCModel, workspace_path)


def type_from_input(node: str | type[FLYNCBaseModel]) -> type[FLYNCBaseModel]:
    """Resolve a node identifier to its Python type.

    Accepts either a string class name (looked up in the global dependency
    graph) or a type directly.

    Args:
        node (str | type[FLYNCBaseModel]): A model class or its string name.

    Returns:
        type[FLYNCBaseModel]: The resolved model class.
    """
    if isinstance(node, str):
        node = (
            get_model_dependency_graph(root=FLYNCModel)
            .fields_info[node]
            .python_type
        )
    return node  # type: ignore[return-value]


def available_flync_nodes(
    root_node: Optional[str | type[FLYNCBaseModel]] = FLYNCModel,
) -> dict[str, NodeInfo]:
    """Return metadata for all nodes reachable from a root model.

    Args:
        root_node (str | type[FLYNCBaseModel]): The root model class or its
            name. Defaults to :class:`~flync.model.flync_model.FLYNCModel`.

    Returns:
        dict[str, NodeInfo]: Mapping of class names to :class:`NodeInfo`
        objects describing each node in the dependency graph.
    """
    if root_node is None:
        root_node = FLYNCModel
    root_node = type_from_input(root_node)
    return get_model_dependency_graph(root_node).fields_info


def validate_external_node(
    node: str | type[FLYNCBaseModel], node_path: Path | str
) -> DiagnosticsResult:
    """Validate a specific FLYNC node type at a given filesystem path.

    Loads the node using a fresh workspace configured with ``node`` as the
    root model, then inspects per-document errors to determine the overall
    :class:`~flync.sdk.context.diagnostics_result.WorkspaceState`.

    Args:
        node (str | type[FLYNCBaseModel]): The model class to validate, or
            its string name.
        node_path (Path | str): Path to the directory containing the node's
            FLYNC configuration files.

    Returns:
        DiagnosticsResult: Validation outcome with state, per-document errors,
        the loaded model, and the workspace instance.
    """
    node = type_from_input(node)
    state = WorkspaceState.EMPTY
    errors = {}
    model = None
    ws = None
    try:
        ws = FLYNCWorkspace.safe_load_workspace(
            "validation_workspace",
            node_path,
            workspace_config=WorkspaceConfiguration(root_model=node),
        )
        model = ws.flync_model
        state = WorkspaceState.VALID
        # only add documents that have problems
        for doc_url, doc_errors in ws.documents_diags.items():
            if doc_errors:
                errors[doc_url] = doc_errors
                state = WorkspaceState.WARNING
        if ws.flync_model is None:
            state = WorkspaceState.INVALID
    except Exception as ex:
        state = WorkspaceState.BROKEN
        logger.error(
            "Encountered issue while validating node %s",
            ex.with_traceback(None),  # type: ignore[func-returns-value]
        )
    return DiagnosticsResult(
        state=state, errors=errors, model=model, workspace=ws
    )


def validate_node(
    ws_path: Path | str, node_path: str = ""
) -> DiagnosticsResult:
    """Validate a single node within an already-loaded workspace.

    First validates the full workspace, then checks that the node at
    ``node_path`` exists and extracts its model. If the node is missing, a
    fatal validation error is recorded.

    Args:
        ws_path (Path | str): Path to the workspace root directory.
        node_path (str): Dot-separated path to the target node within the
            workspace object graph.

    Returns:
        DiagnosticsResult: Validation outcome for the specified node.
    """
    # load entire workspace
    workspace_results = validate_workspace(ws_path)
    # validate node in workspace
    if (
        not workspace_results.workspace
        or node_path not in workspace_results.workspace.objects
    ):
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
            raise ValidationError.from_exception_data(
                title="partial node validation", line_errors=[error]
            )
        except ValidationError as ex:
            workspace_results.errors[node_path] = ex.errors()
    else:
        workspace_results.model = (
            workspace_results.workspace.objects[  # type: ignore[assignment]
                ObjectId(node_path)
            ].model
        )
    return workspace_results
