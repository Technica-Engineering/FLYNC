import json
import logging
import shutil
from os import sep
from pathlib import Path

import pytest
import yaml
from approvaltests import verify

from flync.model import FLYNCModel
from flync.model.flync_4_ecu.controller import Controller
from flync.model.flync_4_ecu.ecu import ECU
from flync.sdk.context.diagnostics_result import DiagnosticsResult
from flync.sdk.context.workspace_config import (
    DEFAULT_EXTENSION,
    ListObjectsMode,
    WorkspaceConfiguration,
)
from flync.sdk.helpers.generation_helpers import dump_flync_workspace
from flync.sdk.helpers.validation_helpers import (
    WorkspaceState,
    validate_external_node,
    validate_workspace,
)
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
    "ecus.high_performance_compute.switches.hpc_switch1.switch_config.ports.hpc_s1_p2",
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
    extra_file = f"extra{DEFAULT_EXTENSION}"
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
