import pathlib

from flync.model.flync_model import FLYNCModel
from flync.sdk.workspace.flync_workspace import FLYNCWorkspace


def dump_flync_workspace(
    flync_model: FLYNCModel,
    output_path: str | pathlib.Path,
    workspace_name: str | None,
) -> None:
    """Generate a FLYNC workspace from a FLYNC object.

    Args:
        flync_object \
        (:class:`~flync.model.flync_model.FLYNCModel`): The \
        FLYNC object to generate the workspace from.

        output_path (str | `pathlib.Path`): The path where \
        the workspace will be created.

    Returns:
        None
    """

    ws = FLYNCWorkspace.load_model(flync_model, workspace_name, output_path)
    ws.generate_configs()
