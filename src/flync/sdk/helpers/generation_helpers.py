import pathlib

from flync.model.flync_model import FLYNCModel
from flync.sdk.workspace.flync_workspace import (
    FLYNCWorkspace,
    WorkspaceConfiguration,
)


def dump_flync_workspace(
    flync_model: FLYNCModel,
    output_path: str | pathlib.Path,
    workspace_name: str | None,
    workspace_config: WorkspaceConfiguration | None = None,
) -> None:
    """Generate a FLYNC workspace from a FLYNCModel object.

    Args:
        flync_model (:class:`~flync.model.flync_model.FLYNCModel`): The
            FLYNC model to generate the workspace from.
        output_path (str | pathlib.Path): The path where the workspace
            will be created.
        workspace_name (str | None): Optional name for the workspace.
        workspace_config (WorkspaceConfiguration | None): Optional
            workspace configuration. Uses defaults if ``None``.

    Returns:
        None
    """

    ws = FLYNCWorkspace.load_model(
        flync_model,
        workspace_name,
        output_path,
        workspace_config=workspace_config,
    )
    ws.generate_configs()
