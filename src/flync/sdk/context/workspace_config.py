"""
Configuration module for FLYNC SDK.

Provides :class:`WorkspaceConfiguration` and :class:`ListObjectsMode`, which
control how a :class:`~flync.sdk.workspace.flync_workspace.FLYNCWorkspace` is
loaded, validated, and serialized.
"""

from dataclasses import asdict, dataclass, field
from enum import IntFlag
from typing import Type

from flync.model import FLYNCBaseModel, FLYNCModel

DEFAULT_EXTENSION = ".flync.yaml"


class ListObjectsMode(IntFlag):
    """Flags controlling how list items are keyed in the workspace object map.

    Flags can be combined with ``|``. The default is ``INDEX | NAME``.

    Attributes:
        INDEX: Register each list item under its zero-based integer index
            (e.g. ``controllers.0``).
        NAME: Register each list item under its name — the file/directory stem
            for folder-based lists, or the model's ``name`` attribute for
            inline YAML lists. Items without a name are skipped.
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
        map_objects (bool): tells the workspace if it should map all objects
            in the workspace (reduces performance).
        list_objects_mode (ListObjectsMode): Controls how objects are keyed
            when listed. Defaults to ``INDEX | NAME``.
    """

    flync_file_extension: str = DEFAULT_EXTENSION
    allowed_extensions: set[str] = field(
        default_factory=lambda: {DEFAULT_EXTENSION, ".flync.yml"}
    )
    exclude_unset: bool = True
    root_model: Type[FLYNCBaseModel] = FLYNCModel
    map_objects: bool = False
    list_objects_mode = ListObjectsMode.INDEX | ListObjectsMode.NAME

    @classmethod
    def create_from_config(
        cls, existing_config: "WorkspaceConfiguration", **configs
    ) -> "WorkspaceConfiguration":
        """Create a new configuration by overriding fields on an existing one.

        Converts ``existing_config`` to a dict, applies ``configs`` on top,
        then constructs and returns a new :class:`WorkspaceConfiguration`.

        Args:
            existing_config (WorkspaceConfiguration): The base configuration
                to copy from.
            **configs: Field names and new values to override.

        Returns:
            WorkspaceConfiguration: A new instance with the overrides applied.
        """
        existing_config_values = asdict(existing_config)
        existing_config_values.update(**configs)
        return WorkspaceConfiguration(**existing_config_values)
