"""
Variant analysis helpers for the FLYNC SDK.

Read the documents of a 150 % workspace from disk and run the analyses of
:mod:`flync.model.flync_4_variability.analysis` on them: trace every feature to the variation points it decides,
and compare two variants element by element.
"""

import logging
from pathlib import Path
from typing import Any

import yaml

from flync.model.flync_4_variability.analysis import (
    VariantComparison,
    VariationPoint,
    collect_variation_points,
    compare_variants,
    trace_features,
)
from flync.model.flync_4_variability.variant import Variability

logger = logging.getLogger(__name__)

FLYNC_DOCUMENT_SUFFIX = ".flync.yaml"
"""File name suffix of a FLYNC document."""


def read_workspace_documents(workspace_path: str | Path) -> dict[str, Any]:
    """
    Read every FLYNC document of a workspace as plain data.

    Args:
        workspace_path (str | Path): Path to the workspace directory.

    Returns:
        dict[str, Any]: The safe-loaded content of every ``*.flync.yaml`` file, by workspace-relative id. Files that are not
        valid YAML are left out (``flync validate`` reports them).
    """

    root = Path(workspace_path)
    documents: dict[str, Any] = {}
    for path in sorted(root.rglob(f"*{FLYNC_DOCUMENT_SUFFIX}")):
        try:
            documents[path.relative_to(root).as_posix()] = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            logger.debug("Skipping %s: %s", path, exc)
    return documents


def workspace_variation_points(workspace_path: str | Path) -> list[VariationPoint]:
    """
    List every variation point of a workspace.

    Args:
        workspace_path (str | Path): Path to the workspace directory.

    Returns:
        list[VariationPoint]: The ECU presence conditions and the conditions on system topology entries, in document order.
    """

    return collect_variation_points(read_workspace_documents(workspace_path))


def trace_workspace_features(workspace_path: str | Path, variability: Variability) -> dict[str, list[VariationPoint]]:
    """
    Find the variation points of a workspace that every feature decides.

    Args:
        workspace_path (str | Path): Path to the workspace directory.
        variability (Variability): The variability model of the workspace.

    Returns:
        dict[str, list[VariationPoint]]: For every feature, in declaration order, the variation points that refer to it.
    """

    return trace_features(variability, workspace_variation_points(workspace_path))


def compare_workspace_variants(workspace_path: str | Path, variability: Variability, left: str, right: str) -> VariantComparison:
    """
    Compare two variants of a workspace: their feature values and the elements that differ.

    Args:
        workspace_path (str | Path): Path to the workspace directory.
        variability (Variability): The variability model of the workspace.
        left (str): Name of the first variant.
        right (str): Name of the second variant.

    Returns:
        VariantComparison: The differences.

    Raises:
        KeyError: If one of the variants is not declared.
    """

    return compare_variants(variability, workspace_variation_points(workspace_path), left, right)
