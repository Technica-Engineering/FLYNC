"""
Workspace module for FLYNC SDK.

Provides classes and functions to manage workspace operations.
"""

import logging
from typing import Optional

from pydantic_core import ValidationError

from flync.core.base_models.base_model import FLYNCBaseModel
from flync.core.utils.exceptions_handling import errors_to_init_errors
from flync.model.flync_model import FLYNCModel
from flync.sdk.context.workspace_config import WorkspaceConfiguration
from flync.sdk.utils.sdk_types import PathType

from ._base import LoadNode, ParentLink
from ._saving import _WorkspaceSaving

logger = logging.getLogger(__name__)

__all__ = ["FLYNCWorkspace", "LoadNode", "ParentLink", "WorkspaceConfiguration"]


class FLYNCWorkspace(_WorkspaceSaving):
    """
    Workspace class managing documents, objects, and diagnostics.

    This class provides methods to ingest documents, run analysis, and expose semantic and source APIs for use by the SDK and language server.

    Attributes:
        name (str): Name of the workspace.

        configuration (WorkspaceConfiguration): Configuration object for workspace behavior.

        documents (Dict[str, Document]): Mapping of document URIs to Document objects.

        documents_diags (Dict[str, list[ErrorDetails]]): Validation errors indexed by document URI.

        objects (Dict[ObjectId, SemanticObject]): Semantic objects indexed by ObjectId.

        sources (Dict[ObjectId, SourceRef]): Source references indexed by ObjectId.

        flync_model (FLYNCModel | FLYNCBaseModel | None): The root FLYNC model instance, if loaded.

        workspace_root (Path | None): Absolute path to the workspace root directory.
    """

    # region creator
    @classmethod
    def load_model(
        cls,
        flync_model: FLYNCModel,
        workspace_name: str | None = "generated_workspace",
        file_path: PathType = "",
        workspace_config: Optional[WorkspaceConfiguration] = None,
    ) -> "FLYNCWorkspace":
        """
        loads a workspace object from a FLYNC Object.

        Args:
            flync_model (str): the FLYNC object from which the workspace will be created.

            workspace_name (str): The name of the workspace.

            file_path (str | Path): The path of the workspace files.

        Returns: FLYNCWorkspace
        """

        if not workspace_name:
            workspace_name = "generated_workspace"
        output = FLYNCWorkspace(
            name=workspace_name,
            workspace_path=file_path,
            configuration=workspace_config,
        )
        # assign this to the workspace if it's the root object
        output.flync_model = flync_model
        output.load_flync_model(flync_model, file_path)
        return output

    @classmethod
    def safe_load_workspace(
        cls,
        workspace_name: str,
        workspace_path: PathType,
        workspace_config: Optional[WorkspaceConfiguration] = None,
    ) -> "FLYNCWorkspace":
        """
        loads a workspace object from a location of the Yaml Configuration.

        In case this fails, the workspace will still be created, but with an empty model.

        Args:
            workspace_name (str): The name of the workspace.

            workspace_path (str | Path): The path of the workspace files.

        Returns: FLYNCWorkspace
        """

        output = FLYNCWorkspace(
            name=workspace_name,
            workspace_path=workspace_path,
            configuration=workspace_config,
        )
        output._open_documents()
        model = output._load_from_path(output.workspace_root)  # type: ignore[arg-type]

        if not isinstance(model, FLYNCBaseModel):
            logger.error("Unable to load the workspace %s", workspace_path)
        output.flync_model = model
        return output

    @classmethod
    def load_workspace(
        cls,
        workspace_name: str,
        workspace_path: PathType,
        workspace_config: Optional[WorkspaceConfiguration] = None,
    ) -> "FLYNCWorkspace":
        """
        loads a workspace object from a location of the Yaml Configuration.

        Args:
            workspace_name (str): The name of the workspace.

            workspace_path (str | Path): The path of the workspace files.

        Returns: FLYNCWorkspace
        """

        output = FLYNCWorkspace.safe_load_workspace(workspace_name, workspace_path, workspace_config=workspace_config)
        if not isinstance(output.flync_model, FLYNCBaseModel):
            raise ValidationError.from_exception_data(
                title=f"Model ({workspace_name}) Creation Error",
                line_errors=errors_to_init_errors(output.load_errors),
            )
        return output

    # endregion
