from pathlib import Path
from flync.sdk.helpers.generation_helpers import dump_flync_workspace
from flync.sdk.workspace.flync_workspace import FLYNCWorkspace
from .helper import compare_yaml_files, model_has_socket

current_dir = Path(__file__).resolve().parent


def test_load_workspace_from_flync_object(get_flync_example_path):
    workspace_name_object = "flync_workspace_from_folder"
    loaded_ws = FLYNCWorkspace.load_workspace(
        workspace_name_object, get_flync_example_path
    )
    assert loaded_ws is not None
    # To be improved.
    assert loaded_ws.flync_model is not None
    assert loaded_ws.flync_model.ecus
    assert loaded_ws.flync_model.topology
    assert loaded_ws.flync_model.topology.system_topology
    assert loaded_ws.flync_model.general
    assert loaded_ws.flync_model.general.someip_config
    assert loaded_ws.flync_model.general.tcp_profiles
    assert loaded_ws.flync_model.metadata
    assert model_has_socket(loaded_ws)


def test_roundtrip_conversion(get_flync_example_path):
    workspace_name_object = "flync_workspace_from_folder"
    loaded_ws = FLYNCWorkspace.load_workspace(
        workspace_name_object, get_flync_example_path
    )
    assert loaded_ws is not None
    assert loaded_ws.flync_model is not None
    output_path = current_dir / "generated" / Path(get_flync_example_path).name
    dump_flync_workspace(
        loaded_ws.flync_model,
        output_path,
        workspace_name=workspace_name_object,
    )
    assert compare_yaml_files(Path(get_flync_example_path), Path(output_path))
