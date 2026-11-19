"""
Diagnostic result types for the FLYNC SDK.

Provides :class:`WorkspaceState` and :class:`DiagnosticsResult`, which represent the outcome of validating a FLYNC workspace or node.
"""

from enum import Enum
from os import getcwd
from typing import Optional

from pydantic import ConfigDict, field_serializer
from pydantic.dataclasses import dataclass
from pydantic_core import ErrorDetails

from flync.core.base_models.base_model import FLYNCBaseModel
from flync.sdk.workspace.flync_workspace import FLYNCWorkspace


class WorkspaceState(str, Enum):
    """
    Enumeration of possible workspace validation states.

    Attributes:
        **UNKNOWN**: State has not been determined.

        **EMPTY**: No model was loaded; the workspace is empty.

        **LOADING**: The workspace is currently being loaded.

        **VALID**: All documents validated successfully with no errors.

        **WARNING**: Validation completed but some documents have non-fatal errors.

        **INVALID**: The model could not be constructed due to validation errors.

        **BROKEN**: An unexpected exception occurred during loading.
    """

    UNKNOWN = "unknown"
    EMPTY = "empty"
    LOADING = "loading"
    VALID = "valid"
    WARNING = "warning"
    INVALID = "invalid"
    BROKEN = "broken"


@dataclass(config=ConfigDict(arbitrary_types_allowed=True))
class DiagnosticsResult:
    """
    Result of a workspace or node validation operation.

    Attributes:
        state (WorkspaceState): The overall validation state.
        errors (dict[str, list[ErrorDetails]]): Mapping of document URIs to their associated Pydantic validation error details.
        model (Optional[FLYNCBaseModel]): The validated root model, or ``None`` if validation failed.
        workspace (Optional[FLYNCWorkspace]): The loaded workspace instance, or ``None`` if the workspace could not be created.
        variant (Optional[str]): The product variant the workspace was resolved for, or ``None`` for a workspace without
        variability.
    """

    state: WorkspaceState
    errors: dict[str, list[ErrorDetails]]
    model: Optional[FLYNCBaseModel] = None
    workspace: Optional[FLYNCWorkspace] = None
    variant: Optional[str] = None

    @property
    def passed(self) -> bool:
        """
        Whether validation got through with nothing worse than warnings.

        Checks the state as well as the diagnostics, because a workspace that never loaded reports ``BROKEN`` with an empty ``errors``
        dict. Judging by diagnostics alone would call that a pass.
        """

        if self.state not in (WorkspaceState.VALID, WorkspaceState.WARNING):
            return False

        return all(entry.get("type") == "warning" for entries in self.errors.values() for entry in entries)

    @field_serializer("workspace")
    def serialize_workspace(self, value: FLYNCWorkspace) -> str:
        """
        Serialize the workspace to a compact string representation.

        Args:
            value (FLYNCWorkspace): The workspace to serialize.

        Returns:
            str: A human-readable string with the workspace name and relative path.
        """

        workspace_path = value.workspace_root.relative_to(getcwd()) if value.workspace_root is not None else None
        return f"workspace name: {value.name}, workspace path: {workspace_path}"


_STATE_SEVERITY = {
    WorkspaceState.VALID: 0,
    WorkspaceState.EMPTY: 0,
    WorkspaceState.UNKNOWN: 1,
    WorkspaceState.LOADING: 1,
    WorkspaceState.WARNING: 2,
    WorkspaceState.INVALID: 3,
    WorkspaceState.BROKEN: 4,
}


def worst_state(states: list[WorkspaceState]) -> WorkspaceState:
    """
    Return the most severe of several validation states.

    Args:
        states (list[WorkspaceState]): The states to combine.

    Returns:
        WorkspaceState: The most severe state, or ``EMPTY`` when there are none.
    """

    return max(states, key=lambda state: _STATE_SEVERITY[state], default=WorkspaceState.EMPTY)


@dataclass(config=ConfigDict(arbitrary_types_allowed=True))
class VariantSetDiagnosticsResult:
    """
    Result of validating every product variant of a 150 % workspace.

    Attributes:
        state (WorkspaceState): The most severe state over all variants (and the variability model).
        variants (dict[str, DiagnosticsResult]): The validation result per variant name. A workspace without variability has one
            entry under the empty name ``""``.
        errors (dict[str, list[ErrorDetails]]): Findings that kept every variant from being resolved, e.g. an invalid variability
            model; empty when the variants could be resolved.
    """

    state: WorkspaceState
    variants: dict[str, DiagnosticsResult]
    errors: dict[str, list[ErrorDetails]]

    @property
    def passed(self) -> bool:
        """Whether every variant passed and no finding kept the variants from being resolved."""

        if any(entry.get("type") != "warning" for entries in self.errors.values() for entry in entries):
            return False
        return bool(self.variants) and all(result.passed for result in self.variants.values())

    def failed_variants(self) -> list[str]:
        """Names of the variants that did not pass."""

        return [name for name, result in self.variants.items() if not result.passed]
