from flync.sdk.context.workspace_config import ListObjectsMode
from flync.sdk.workspace.flync_workspace import FLYNCWorkspace, WorkspaceConfiguration
from flync.sdk.workspace.objects import SemanticObject


def _index_path_for_name(ws, name_path):
    """Return the positional ``ecus.<n>`` path that maps to the same model as ``name_path``.

    Resolving the slot from the name keeps the assertions correct even if ECUs
    are added to or reordered within the example.
    """
    target_model = ws.get_object(name_path).model
    for obj_id in ws.list_objects():
        if obj_id.startswith("ecus.") and obj_id.split(".", 2)[1].isdigit() and ws.get_object(obj_id).model is target_model:
            return obj_id
    raise AssertionError(f"No positional path found for {name_path!r}")


# -- has_object ----------------------------------------------------------------


def test_has_object_index_and_name_path_found(loaded_workspace_with_object_map):
    ws = loaded_workspace_with_object_map
    eth_ecu_id = "ecus.eth_ecu"
    assert ws.has_object(eth_ecu_id)
    z1_index = _index_path_for_name(ws, "ecus.zonal_platform1")
    eth_ecu_index = _index_path_for_name(ws, eth_ecu_id)
    assert ws.has_object(f"{z1_index}.switches.z1_switch1.switch_config.ports.z1_s1_p0.ingress_streams.0.stream_identification.0")
    assert ws.has_object(f"{eth_ecu_index}.controllers.0.controller_metadata.controller_metadata.compatible_flync_version")
    assert ws.has_object(f"{eth_ecu_index}.controllers.eth_ecu_controller1.controller_metadata.controller_metadata.compatible_flync_version")
    eth_ecu = ws.get_object(eth_ecu_id).model
    eth_ecu_objects = ws.get_semantic_objects_from_model(eth_ecu)
    assert len(eth_ecu_objects) == 2
    obj_id_index = next(obj.id for obj in eth_ecu_objects if obj.id != eth_ecu_id)
    assert ws.has_object(f"{obj_id_index}.topology.connections.0")
    assert ws.has_object(f"{eth_ecu_id}.topology.connections.0")


def test_has_object_name_path_in_index_only_mode(loaded_workspace_index_only):
    ws = loaded_workspace_index_only
    # In INDEX-only mode, name paths are NOT registered
    assert ws.has_object("ecus.0")
    assert not ws.has_object("ecus.eth_ecu")


def test_has_object_not_found(loaded_workspace_with_object_map):
    ws = loaded_workspace_with_object_map
    assert not ws.has_object("nonexistent.path")


# -- get_child_ids -------------------------------------------------------------


def test_get_child_ids_known_parent(loaded_workspace_with_object_map):
    ws = loaded_workspace_with_object_map
    children = ws.get_child_ids("ecus.0")
    assert len(children) > 0
    for child in children:
        assert child.startswith("ecus.0.")


def test_get_child_ids_unknown_parent(loaded_workspace_with_object_map):
    ws = loaded_workspace_with_object_map
    assert ws.get_child_ids("does.not.exist") == []


def test_get_child_ids_works_same_in_both_modes(
    loaded_workspace_with_object_map,
    loaded_workspace_index_only,
):
    ws_dual = loaded_workspace_with_object_map
    ws_idx = loaded_workspace_index_only
    children_dual = ws_dual.get_child_ids("ecus.0")
    children_idx = ws_idx.get_child_ids("ecus.0")
    # Same parent yields same children regardless of mode
    assert children_dual == children_idx


# -- get_object (exercises _try_get_from_duplicated_id) ------------------------


def test_get_object_by_index_path(loaded_workspace_with_object_map):
    ws = loaded_workspace_with_object_map
    obj = ws.get_object("ecus.0")
    assert obj.id == "ecus.0"


def test_get_object_by_name_path(loaded_workspace_with_object_map):
    ws = loaded_workspace_with_object_map
    # Name path resolves to the SemanticObject stored under the index path
    obj = ws.get_object("ecus.eth_ecu")
    assert obj is not None
    assert isinstance(obj.model, type(ws.get_object("ecus.0").model))


def test_get_object_index_and_name_refer_to_same_semantic_object(loaded_workspace_with_object_map):
    ws = loaded_workspace_with_object_map
    # The name path resolves to the same SemanticObject instance as the index path
    name_paths = ws._duplicated_objects_ids["ecus.0"]
    assert len(name_paths) == 1
    obj_idx = ws.get_object("ecus.0")
    obj_name = ws.get_object(name_paths[0])
    assert isinstance(obj_idx, SemanticObject)
    assert isinstance(obj_name, SemanticObject)
    assert obj_idx.model is obj_name.model


# -- list_objects backward compatibility ---------------------------------------


def test_list_objects_returns_known_paths(loaded_workspace_with_object_map):
    ws = loaded_workspace_with_object_map
    all_ids = ws.list_objects()
    assert "ecus.0" in all_ids
    assert "ecus.eth_ecu" in all_ids
    assert isinstance(all_ids, list)


def test_list_objects_mode_respects_index_flag(get_flync_example_path):
    ws_idx = FLYNCWorkspace.load_workspace(
        "test",
        get_flync_example_path,
        WorkspaceConfiguration(map_objects=True, list_objects_mode=ListObjectsMode.INDEX),
    )
    ws_dual = FLYNCWorkspace.load_workspace(
        "test",
        get_flync_example_path,
        WorkspaceConfiguration(map_objects=True, list_objects_mode=ListObjectsMode.INDEX | ListObjectsMode.NAME),
    )
    idx_ids = ws_idx.list_objects()
    dual_ids = ws_dual.list_objects()
    # INDEX-only has fewer entries (no name-path aliases)
    assert len(idx_ids) < len(dual_ids)
    for dual_i in dual_ids:
        assert ws_dual.has_object(dual_i)
