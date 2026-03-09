import pathlib
from typing import Type

from flync.model.flync_model import FLYNCModel
from flync.core.annotations.hint import Hint, HintStrategy
from flync.sdk.workspace.flync_workspace import FLYNCWorkspace
from flync.sdk.utils.field_utils import get_metadata


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


def generate_node(flync_model: Type[FLYNCModel], **kwargs) -> FLYNCModel:
    """
    Generate a Flync node from it's type with default values and
    hints and providing the additional values as keyword arguments when needed.

    Parameters
    ----------
    flync_model: Type[FLYNCModel]
        The object with pydantic's error details

    **kwargs: Any
        Additional keyword arguments for the model creation

    Returns
    -------
    FLYNCModel
    """

    hinted_fields = kwargs

    for field_name, field_info in flync_model.model_fields.items():
        hint = get_metadata(field_info.metadata, Hint)

        if hint is None:
            continue

        if hint.hint_strategy == HintStrategy.FIXED:
            hinted_fields[field_name] = hint.value

    return flync_model.model_validate({})
