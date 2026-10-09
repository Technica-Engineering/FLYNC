"""Helper utilities for Flync converter.

This module provides utility functions for working with Pydantic models,
data serialization and the files of a converted folder.
"""

from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from flync.sdk.context.workspace_config import CONFIG_DIRNAME
from flync.sdk.utils.model_dumper import dump_model_with_discriminators

from ..base.converter_report import ConverterReport


def content_files(root: str | Path, pattern: str) -> Iterator[Path]:
    """Yield the files under ``root`` matching ``pattern``, outside any ``.flync`` folder.

    The ``.flync`` metadata folder holds tooling data (stored converter
    configurations, conversion reports), not model content, so loaders that
    merge every file of a folder must not read it.

    Args:
        root: Folder to search recursively.
        pattern: Glob pattern of the file names, e.g. ``"*.yaml"``.

    Yields:
        Matching file paths, in ``rglob`` order.
    """
    root_path = Path(root)
    for path in root_path.rglob(pattern):
        if CONFIG_DIRNAME not in path.relative_to(root_path).parts:
            yield path


def merge_tracking_overrides(
    combined: dict[str, Any], data: Mapping[str, Any], path: Path, origins: dict[str, Path], report: ConverterReport
) -> None:
    """Merge one loaded file into ``combined``, reporting the top-level keys it overrides.

    A top-level key already loaded from an earlier file is replaced by this
    file's value; the earlier value is recorded as ``skipped`` in ``report``.

    Args:
        combined: The content merged so far, updated in place.
        data: The content of the file being merged.
        path: The file being merged.
        origins: The file each key of ``combined`` comes from, updated in place.
        report: The converter's report.
    """
    for key in data:
        if key in origins:
            report.skipped(f"{origins[key]}: {key}", reason=f"overridden by {path}")
        origins[key] = path
    combined.update(data)


def pydantic_dump(model: BaseModel):
    """Serialize a Pydantic model to a JSON-safe dictionary.

    Uses exclude_unset=True to omit computed/default fields that are populated
    by FLYNC SDK validators during model construction (e.g. switch VLAN
    multicast groups derived from SOME/IP multicast_groups). Omitting these
    lets the decoder recompute them from source data rather than doubling them.
    mode='json' converts all Python types (IPv4Address, enums, ...) to
    primitives.

    Ensures Literal discriminator fields are included even if they weren't
    explicitly set during model construction.

    Args:
        model: A Pydantic BaseModel instance to serialize.

    Returns:
        A dictionary with explicitly-set fields serialized to JSON-compatible
        primitives, with discriminators included.
    """
    return dump_model_with_discriminators(model, mode="json", exclude_unset=True)
