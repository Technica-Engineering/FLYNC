"""
Configuration module for FLYNC SDK.

Provides a simple configuration object.
"""

from dataclasses import dataclass, field
from enum import IntFlag
from typing import Type

from flync.model import FLYNCBaseModel, FLYNCModel

DEFAULT_EXTENSION = ".flync.yaml"


class ListObjectsMode(IntFlag):
    """Flags controlling how objects are listed in the workspace.

    Attributes:
    INDEX: List objects by their positional index.
    NAME: List objects by their name.
    """

    INDEX = 1
    NAME = 2


@dataclass(frozen=True)
class WorkspaceConfiguration:
    """Configuration object for the FLYNC SDK workspace.

    Attributes:
        flync_file_extension (str): The primary file extension used when
            writing FLYNC configuration files. Defaults to ``".flync.yaml"``.
        allowed_extensions (set[str]): Set of file extensions recognized as
            FLYNC files. Defaults to ``{".flync.yaml", ".flync.yml"}``.
        exclude_unset (bool): When ``True``, fields that were not explicitly
            set on a model are omitted from serialized output.
        root_model (Type[FLYNCBaseModel]): The root Pydantic model class used
            to validate workspace contents.
        list_objects_mode (ListObjectsMode): Controls how objects are keyed
            when listed. Defaults to ``INDEX | NAME``.
    """

    flync_file_extension: str = DEFAULT_EXTENSION
    allowed_extensions: set[str] = field(
        default_factory=lambda: {DEFAULT_EXTENSION, ".flync.yml"}
    )
    exclude_unset: bool = True
    root_model: Type[FLYNCBaseModel] = FLYNCModel
    list_objects_mode = ListObjectsMode.INDEX | ListObjectsMode.NAME
