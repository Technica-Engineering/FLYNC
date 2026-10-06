"""Helper utilities for Flync converter.

This module provides utility functions for working with Pydantic models,
data serialization and the files of a converted folder.
"""

from collections.abc import Iterator
from pathlib import Path

from pydantic import BaseModel

from flync.sdk.context.workspace_config import CONFIG_DIRNAME
from flync.sdk.utils.model_dumper import dump_model_with_discriminators


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
