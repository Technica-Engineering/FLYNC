import json
import logging
import shutil
from os import sep
from pathlib import Path

import pytest
import yaml
from approvaltests import verify

from flync.model import FLYNCModel
from flync.model.flync_4_ecu import ECU, Controller, ECUPort
from flync.model.flync_4_ecu.internal_topology import ECUPortToSwitchPort
from flync.model.flync_4_ecu.switch import Switch
from flync.sdk.context.diagnostics_result import DiagnosticsResult
from flync.sdk.context.workspace_config import (
    ListObjectsMode,
    WorkspaceConfiguration,
)
from flync.sdk.helpers.generation_helpers import (
    dump_flync_workspace,
    generate_external_node,
    generate_node,
)
from flync.sdk.helpers.validation_helpers import (
    WorkspaceState,
    validate_external_node,
    validate_workspace,
)
from flync.sdk.utils.field_utils import get_field_name_from_alias
from flync.sdk.utils.sdk_types import PathType
from flync.sdk.workspace.flync_workspace import FLYNCWorkspace
from flync.sdk.workspace.ids import ObjectId

from .helper import (
    compare_yaml_files,
    model_has_socket,
)

logger = logging.getLogger(__name__)

TEST_MODEL_TYPES = [FLYNCModel, ECU, Controller]
TEST_MODEL_TYPES_NAMES = [t.__name__ for t in TEST_MODEL_TYPES]
TEST_MODEL_PATHS = [
    "",
    sep.join(["ecus", "eth_ecu"]),
    sep.join(["ecus", "eth_ecu", "controllers", "eth_ecu_controller1.flync.yaml"]),
]
TEST_MODEL_FLYNC_PATHS = [
    ("",),
    (".".join(["ecus", "0"]), ".".join(["ecus", "eth_ecu"])),
    (
        ".".join(["ecus", "0", "controllers", "0"]),
        ".".join(["ecus", "eth_ecu", "controllers", "0"]),
        ".".join(["ecus", "0", "controllers", "eth_ecu_controller1"]),
        ".".join(["ecus", "eth_ecu", "controllers", "eth_ecu_controller1"]),
    ),
]
TEST_REFERENCES_PATHS = {
    "ecus.eth_ecu.topology.connections.0": ["ecu_port"],
    "ecus.high_performance_compute.topology.connections.2": ["ecu_port"],
    "ecus.high_performance_compute.topology.connections.3": ["controller_interface"],
    "ecus.high_performance_compute.topology.connections.4": ["switch_port"],
    "ecus.zonal_platform2.topology.connections.3": [
        "controller_interface",
        "controller_interface2",
    ],
}
TEST_OBJECTS_PATHS = [
    "ecus.eth_ecu.ports.ports.eth_ecu_p1",
    "ecus.high_performance_compute.ports.ports.hpc1_p3",
    "ecus.high_performance_compute.controllers.hpc_controller1.ethernet_interfaces.hpc_c1_iface1",
    "ecus.high_performance_compute.switches.hpc_switch1.ports.hpc_s1_p2",
    "ecus.zonal_platform2.controllers.z2_controller1.ethernet_interfaces.z2_c1_iface1",
    "ecus.zonal_platform2.controllers.z2_controller2.ethernet_interfaces.z2_c2_iface1",
]


def test_workspace_validator_api(get_flync_example_path):
    __assert_workspace_validation(get_flync_example_path)


def __assert_workspace_validation(flync_workspace_path: PathType, workspace_config: WorkspaceConfiguration | None = None) -> DiagnosticsResult:
    validation_result = validate_workspace(flync_workspace_path, workspace_config)
    assert (validation_result.state == WorkspaceState.VALID) or (validation_result.state == WorkspaceState.WARNING)
    assert validation_result.workspace is not None
    assert validation_result.model is not None
    assert validation_result.workspace.flync_model == validation_result.model
    assert isinstance(validation_result.model, FLYNCModel)
    assert validation_result.model.ecus
    assert validation_result.model.topology
    assert validation_result.model.topology.ethernet_topology
    assert validation_result.model.communication
    assert validation_result.model.communication.someip_config
    assert validation_result.model.communication.tcp_profiles
    assert validation_result.model.metadata
    assert model_has_socket(validation_result.model)
    return validation_result


params = [pytest.param(cls, path, id=name) for cls, path, name in zip(TEST_MODEL_TYPES, TEST_MODEL_PATHS, TEST_MODEL_TYPES_NAMES)]

partial_params = [pytest.param(cls, path, id=name) for cls, path, name in zip(TEST_MODEL_TYPES, TEST_MODEL_FLYNC_PATHS, TEST_MODEL_TYPES_NAMES)]


def test_load_workspace_from_flync_object_relative_path(
    get_relative_flync_example_path,
):
    workspace_name_object = "flync_workspace_from_folder"
    loaded_ws = FLYNCWorkspace.load_workspace(workspace_name_object, get_relative_flync_example_path)
    assert loaded_ws is not None
    # To be improved.
    assert loaded_ws.flync_model is not None
    assert loaded_ws.flync_model.ecus
    assert loaded_ws.flync_model.topology
    assert loaded_ws.flync_model.topology.ethernet_topology
    assert loaded_ws.flync_model.communication
    assert loaded_ws.flync_model.communication.someip_config
    assert loaded_ws.flync_model.communication.tcp_profiles
    assert loaded_ws.flync_model.metadata
    assert model_has_socket(loaded_ws.flync_model)


def test_roundtrip_conversion(get_flync_example_path, get_flync_workspace_minimal_config, tmp_path):

    workspace_name_object = "flync_workspace_from_folder"
    loaded_ws = FLYNCWorkspace.load_workspace(workspace_name_object, get_flync_example_path, workspace_config=get_flync_workspace_minimal_config)
    assert loaded_ws is not None
    assert loaded_ws.flync_model is not None
    output_path = tmp_path / Path(get_flync_example_path).name
    dump_flync_workspace(
        loaded_ws.flync_model, output_path, workspace_name=workspace_name_object, workspace_config=get_flync_workspace_minimal_config
    )
    assert compare_yaml_files(Path(get_flync_example_path), Path(output_path))


from typing import Annotated

from flync.core.annotations import External, OutputStrategy
from flync.model import FLYNCBaseModel


class ExtraInfo(FLYNCBaseModel):
    extra_name: str


class ExtendedFLYNC(FLYNCModel):
    extra: Annotated[
        ExtraInfo,
        External(output_structure=OutputStrategy.SINGLE_FILE | OutputStrategy.OMMIT_ROOT),
    ]


def test_flync_extension(get_flync_example_path, tmp_path):
    output_extra_path = tmp_path / (Path(get_flync_example_path).name + "_extended_model")
    shutil.copytree(get_flync_example_path, output_extra_path)
    extra_file = f"extra{WorkspaceConfiguration.flync_file_extension}"
    extra_data = {"extra_name": "value"}

    with open(output_extra_path / extra_file, "w") as f:
        yaml.dump(extra_data, f, default_flow_style=False)

    output = validate_external_node(ExtendedFLYNC, output_extra_path)
    assert (output.state == WorkspaceState.VALID) or (output.state == WorkspaceState.WARNING)
    created_model: ExtendedFLYNC = output.model
    assert created_model.extra.extra_name == "value"


def test_object_referencing(
    get_relative_flync_example_path,
):
    workspace_name_object = "flync_workspace_for_test_object_referencing_from_folder"
    config = WorkspaceConfiguration(
        map_objects=True,
        list_objects_mode=ListObjectsMode.NAME,
    )
    loaded_ws = FLYNCWorkspace.load_workspace(
        workspace_name=workspace_name_object,
        workspace_path=get_relative_flync_example_path,
        workspace_config=config,
    )
    received = {}
    for object_id, field_names in TEST_REFERENCES_PATHS.items():
        for field_name in field_names:
            def_id = loaded_ws.get_definition(ObjectId(object_id), field_name)
            received[f"{object_id}.{field_name}"] = def_id

    verify(json.dumps(received, indent=4, sort_keys=True))


def test_references_object(
    get_relative_flync_example_path,
):
    workspace_name_object = "flync_workspace_from_folder"
    config = WorkspaceConfiguration(
        map_objects=True,
        list_objects_mode=ListObjectsMode.NAME,
    )
    loaded_ws = FLYNCWorkspace.load_workspace(
        workspace_name=workspace_name_object,
        workspace_path=get_relative_flync_example_path,
        workspace_config=config,
    )
    received = {}
    for path in TEST_OBJECTS_PATHS:
        received[path] = sorted(loaded_ws.get_references_of(path))

    verify(json.dumps(received, indent=4, sort_keys=True))


def test_load_workspace_with_old_field_name(get_relative_flync_example_path, tmp_path):
    ws_name_obj = Path(get_relative_flync_example_path).name + "_with_old_fied_name"
    output_path = tmp_path / ws_name_obj
    shutil.copytree(get_relative_flync_example_path, output_path, dirs_exist_ok=True)

    communication_path = output_path / "communication"
    general_path = output_path / "general"
    # rename fails on macOS and should not be used!
    # communication_path.rename(general_dir)

    # make sure that general_path does not exist
    if general_path.exists():
        shutil.rmtree(general_path)
    shutil.move(communication_path, general_path)

    loaded_ws = FLYNCWorkspace.load_workspace(
        workspace_name=ws_name_obj,
        workspace_path=output_path,
    )
    expected_warning = "The 'general' attribute is deprecated. Please use 'communication' instead."
    assert loaded_ws.flync_model
    assert loaded_ws.flync_model.communication is not None
    assert loaded_ws.flync_model.communication is loaded_ws.flync_model.general
    assert any(loaded_ws.flync_model.communication.tcp_profiles)
    assert [e for e in loaded_ws.load_errors if e.get("type") == "warning" and e.get("msg", "") == expected_warning]


@pytest.mark.parametrize(
    "node_type, override_values",
    [
        pytest.param(
            ECU,
            {"controllers": [{"lin_interfaces": [{"name": "lin_inter1"}]}]},
            id="ECU",
        ),
        pytest.param(
            Controller,
            {"lin_interfaces": [{"name": "lin_inter2"}]},
            id="Controller",
        ),
    ],
)
def test_generate_external_node_scaffold(node_type, override_values, tmp_path):
    """Scaffolding a node exercises the factory/generate path (Factory.build,
    list-field generation, name assignment) and writes it to disk."""
    output_path = tmp_path / f"generated_{node_type.__name__}"
    generate_external_node(node_type, output_path, workspace_config=None, **override_values)

    produced = list(output_path.rglob("*.yaml")) + list(output_path.rglob("*.yml"))
    assert produced, f"expected generate_external_node to write files for {node_type.__name__}"


GENERATE_NODE_PARAMS = [
    pytest.param(
        ["ecus.eth_ecu.ports"],
        "ports",
        ".ports",
        ECUPort,
        "test_port",
        id="ECUPort",
    ),
    pytest.param(
        ["ecus.eth_ecu.ports"],
        "ports",
        ".ports",
        ECUPort,
        "test_port2",
        id="ECUPort",
    ),
]


@pytest.mark.no_xdist
@pytest.mark.parametrize("node_paths,field,extra_field,expected_type,generated_name", GENERATE_NODE_PARAMS)
def test_generate_node_add_to_list(
    get_flync_example_path,
    tmp_path,
    node_paths,
    field,
    extra_field,
    expected_type,
    generated_name,
):
    """
    Generate a node and add it to an existing list field on a parent model.
    Verifies the node appears in the workspace, on disk, and persists after reload.
    """
    workspace_path = tmp_path / "test_generate"
    shutil.copytree(get_flync_example_path, workspace_path)
    config = WorkspaceConfiguration(map_objects=True)
    ws = FLYNCWorkspace.load_workspace("test_generate", workspace_path, config)

    # The generated node should be attached to ecus.eth_ecu.<field>
    parent_obj_id = ObjectId("ecus.eth_ecu")
    parent_obj = ws.get_object(parent_obj_id)
    original_count = len(getattr(parent_obj.model, field))

    assert generate_node(ws, node_paths, name=generated_name), "Node not generated"

    new_ws = FLYNCWorkspace.load_workspace("reload_test_generate", workspace_path, config)

    new_obj_id = ObjectId(f"{parent_obj_id}.{field}{extra_field}.{generated_name}")
    assert new_ws.has_object(new_obj_id), f"Expected {new_obj_id} to exist in workspace"

    new_node = new_ws.get_object(new_obj_id)
    assert isinstance(new_node.model, expected_type)

    parent_obj = new_ws.get_object(parent_obj_id)
    assert len(getattr(parent_obj.model, field)) == original_count + 1


@pytest.mark.parametrize(
    "node_paths,override_kwargs,expected_type,assertions",
    [
        (
            ["ecus.new"],
            {
                "name": "new",
                "ports": [{"name": "d", "mode": {"autonegotiation": True, "mode": "base_t1s"}}],
                # bus_ref / sender_frames must resolve against communication.channels: generate_node otherwise
                # scaffolds placeholder refs, which are dangling by construction.
                "controllers": [
                    {
                        "name": "new_controller",
                        "lin_interfaces": [
                            {
                                "name": "lin_inter",
                                "node_type": "slave",
                                "bus_ref": "BodyLIN",
                                "receiver_frames": [{"bus_ref": "BodyLIN", "frame_ref": 1}],
                            }
                        ],
                    }
                ],
            },
            ECU,
            [("name", "new")],
        ),
        (
            ["ecus.eth_ecu.ports.ports.override_port"],
            {"name": "override_port"},
            ECUPort,
            [("name", "override_port")],
        ),
        (
            ["ecus.high_performance_compute.topology.connections.ECUPortToSwitchPort"],
            {
                "id": "connn25",
                "switch": "hpc_switch1",
                "switch_port": "hpc_s1_p0",
                "ecu_port": "hpc1_p3",
            },
            ECUPortToSwitchPort,
            [
                ("id", "connn25"),
                ("switch", "hpc_switch1"),
                ("switch_port", "hpc_s1_p0"),
                ("ecu_port", "hpc1_p3"),
            ],
        ),
    ],
)
def test_generate_node_override_values(
    get_flync_example_path,
    tmp_path,
    node_paths,
    override_kwargs,
    expected_type,
    assertions,
):
    """Override values passed to generate_node should propagate to the generated model."""
    workspace_path = tmp_path / "test_override"
    shutil.copytree(get_flync_example_path, workspace_path)
    config = WorkspaceConfiguration(map_objects=True, list_objects_mode=ListObjectsMode.NAME)
    ws: FLYNCWorkspace = FLYNCWorkspace.load_workspace("test_override", workspace_path, config)
    parent_id = node_paths[0].rsplit(".", 1)[0]
    old_children = ws.get_child_ids(parent_id)

    generate_node(ws, node_paths, **override_kwargs)

    # Reload the workspace to verify the node was persisted correctly
    ws2 = FLYNCWorkspace.load_workspace("test_override", workspace_path, config)
    sym_diff = set(ws2.get_child_ids(parent_id)) ^ set(old_children)
    assert len(sym_diff) > 0
    new_node = ws2.get_object(list(sym_diff)[0])
    assert isinstance(new_node.model, expected_type)

    for attr, expected_value in assertions:
        assert getattr(new_node.model, get_field_name_from_alias(type(new_node.model), attr)) == expected_value


def test_generate_node_set_attribue(get_flync_example_path, tmp_path):
    workspace_path = tmp_path / "test_set_attr"
    shutil.copytree(get_flync_example_path, workspace_path)
    file = workspace_path / Path("ecus/zonal_platform1/switches/z1_switch1.flync.yaml")
    import yaml

    with open(file, "r") as f:
        data = yaml.safe_load(f)

    host_controller = {}
    if "host_controller" in data:
        host_controller = data["host_controller"]
        del data["host_controller"]

    with open(file, "w") as f:
        yaml.safe_dump(data, f, sort_keys=False)

    config = WorkspaceConfiguration(map_objects=True)
    ws = FLYNCWorkspace.load_workspace("test_set_attr", workspace_path, config)

    owner_model_id = "ecus.zonal_platform1.switches.z1_switch1"
    attr_fname = "host_controller"
    so = ws.get_object(owner_model_id)
    assert isinstance(so.model, Switch) and so.model.host_controller is None
    generate_node(
        ws=ws,
        node_paths=[f"{owner_model_id}.{attr_fname}"],
        **host_controller,
    )
    ws_updated = FLYNCWorkspace.load_workspace("test_set_attr_updated", workspace_path, config)
    assert ws_updated.get_object(f"{owner_model_id}.{attr_fname}").model.mac_address == "00:11:03:03:01:01"


def test_revalidate_changed_model(get_relative_flync_example_path, tmp_path):
    output_path = tmp_path / "generated" / "revalidate_changed_model"
    shutil.copytree(get_relative_flync_example_path, output_path, dirs_exist_ok=True)

    config = WorkspaceConfiguration(
        map_objects=True,
        list_objects_mode=ListObjectsMode.NAME,
    )
    loaded_ws = FLYNCWorkspace.load_workspace(
        workspace_name="flync_workspace_from_folder",
        workspace_path=output_path,
        workspace_config=config,
    )
    object_id = "ecus.eth_ecu.ports.ports.eth_ecu_p1"
    port = loaded_ws.get_object(object_id).model
    port.name = "changed_port"
    need_revalidate = loaded_ws.get_references_of(object_id)
    loaded_ws.revalidate_references_of(object_id)

    validated_ws = __assert_workspace_validation(output_path, config).workspace
    validated_changed_port = validated_ws.get_object("ecus.eth_ecu.ports.ports.changed_port").model

    assert validated_changed_port.name == "changed_port"

    updated_models = [validated_ws.get_object(nr).model for nr in need_revalidate]
    assert len(updated_models) == 2
    assert updated_models[0] == "changed_port"
