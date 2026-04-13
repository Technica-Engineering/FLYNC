import json
import logging
from os import sep
import os
from pathlib import Path

import pytest
import shutil
from approvaltests import verify
from approvaltests.namer import NamerFactory
import yaml

from flync.model import FLYNCModel
from flync.model.flync_4_ecu import ECU, Controller
from flync.sdk.context.workspace_config import ListObjectsMode, WorkspaceConfiguration
from flync.sdk.helpers.generation_helpers import dump_flync_workspace
from flync.sdk.helpers.nodes_helpers import available_flync_nodes
from flync.sdk.helpers.validation_helpers import (
    WorkspaceState,
    validate_external_node,
    validate_node,
    validate_workspace,
)
from flync.sdk.helpers.generation_helpers import (
    generate_external_node,
    generate_node,
)
from flync.sdk.utils.model_dependencies import get_model_dependency_graph
from flync.sdk.workspace.flync_workspace import FLYNCWorkspace
from flync.sdk.workspace.ids import ObjectId
from tests.conftest import reset_global_registery_function

from .dummy_model import DummyRoot
from .helper import (
    compare_yaml_files,
    dataclass_dict_to_json,
    model_has_socket,
    to_jsonable,
    try_load_workspace,
)

logger = logging.getLogger(__name__)
current_dir = Path(__file__).resolve().parent

TEST_MODEL_TYPES = [FLYNCModel, ECU, Controller]
TEST_MODEL_TYPES_NAMES = [t.__name__ for t in TEST_MODEL_TYPES]
TEST_MODEL_PATHS = [
    "",
    sep.join(["ecus", "eth_ecu"]),
    sep.join(
        ["ecus", "eth_ecu", "controllers", "eth_ecu_controller1.flync.yaml"]
    ),
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
    "ecus.high_processing_core.topology.connections.2": ["ecu_port"],
    "ecus.high_processing_core.topology.connections.3": ["controller_interface"],
    "ecus.high_processing_core.topology.connections.4": ["switch_port"],
    "ecus.zonal_platform2.topology.connections.3": [
        "controller_interface1",
        "controller_interface2",
    ],
}


def test_workspace_validator_api(get_flync_example_path):
    validation_result = validate_workspace(get_flync_example_path)
    assert validation_result.state == WorkspaceState.VALID
    assert not validation_result.errors
    assert validation_result.workspace is not None
    assert validation_result.model is not None
    assert validation_result.workspace.flync_model == validation_result.model
    assert isinstance(validation_result.model, FLYNCModel)
    assert validation_result.model.ecus
    assert validation_result.model.topology
    assert validation_result.model.topology.system_topology
    assert validation_result.model.general
    assert validation_result.model.general.someip_config
    assert validation_result.model.general.tcp_profiles
    assert validation_result.model.metadata
    assert model_has_socket(validation_result.model)


@pytest.mark.skip("skipped until output of test is improved.")
@pytest.mark.parametrize(
    "model_key", TEST_MODEL_TYPES, ids=TEST_MODEL_TYPES_NAMES
)
def test_available_flync_nodes(model_key):
    assert model_key.__name__ in available_flync_nodes()


def test_node_paths_structure():
    dummy_graph = get_model_dependency_graph(DummyRoot)
    verify(dataclass_dict_to_json(dummy_graph.fields_info))


params = [
    pytest.param(cls, path, id=name)
    for cls, path, name in zip(
        TEST_MODEL_TYPES, TEST_MODEL_PATHS, TEST_MODEL_TYPES_NAMES
    )
]

partial_params = [
    pytest.param(cls, path, id=name)
    for cls, path, name in zip(
        TEST_MODEL_TYPES, TEST_MODEL_FLYNC_PATHS, TEST_MODEL_TYPES_NAMES
    )
]


@pytest.mark.skip("skipped until output of test is improved.")
@pytest.mark.parametrize(
    "node_type,node_path",
    params,
)
def test_validate_partial_external_node(
    get_flync_example_path, node_type, node_path
):
    node_path = sep.join([get_flync_example_path, node_path])
    validation_result = validate_external_node(node_type, node_path)
    first_result = to_jsonable(validation_result, get_flync_example_path)
    reset_global_registery_function()
    validation_result_string_type = validate_external_node(
        node_type.__name__, node_path
    )
    second_result = to_jsonable(
        validation_result_string_type, get_flync_example_path
    )
    reset_global_registery_function()
    output = {
        "path_type_usage": {
            "value": node_type.__name__,
            "output": first_result,
        },
        "string_type_usage": {
            "value": node_type.__name__,
            "output": second_result,
        },
    }
    verify(
        json.dumps(
            output,
            indent=2,
            sort_keys=True,
        ),
        options=NamerFactory.with_parameters(str(node_type.__name__)),
    )


@pytest.mark.skip("skipped until output of test is improved.")
@pytest.mark.parametrize(
    "node_type,node_paths",
    partial_params,
)
def test_validate_partial_node(get_flync_example_path, node_type, node_paths):
    output = {}
    for path in node_paths:
        reset_global_registery_function()
        validation_result = validate_node(get_flync_example_path, path)
        assert isinstance(validation_result.model, node_type)
        output[f"path_type_usage_path_{path}"] = to_jsonable(
            {
                "value": node_type.__name__,
                "path": path,
                "output": validation_result,
            },
            get_flync_example_path,
        )
        logger.info(f"will be outputting {output}")
        reset_global_registery_function()
    verify(
        json.dumps(
            output,
            indent=2,
            sort_keys=True,
        ),
        options=NamerFactory.with_parameters(f"{node_type.__name__}"),
    )


def test_load_workspace_from_flync_object_relative_path(
    get_relative_flync_example_path,
):
    workspace_name_object = "flync_workspace_from_folder"
    loaded_ws = FLYNCWorkspace.load_workspace(
        workspace_name_object, get_relative_flync_example_path
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
    assert model_has_socket(loaded_ws.flync_model)


@pytest.mark.skip(
    reason="Sockets in ECU are not dumped correctly. False positive on local execution. "
    "Generated folder is not cleaned up after test execution, making it pass on local execution but fail in CI. To be fixed."
)
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


@pytest.mark.parametrize(
    "node_type,node_path",
    params,
)
def test_generate_partial_external_node(node_type, node_path):
    if node_type is Controller:
        pytest.skip("Skipped until the generation of external controller is fixed")

    output_path = (
        current_dir
        / "generated"
        / (node_type.__name__ + "_external_partial_generator")
    )
    generate_external_node(node_type, output_path)
    to_check_output_file = Path(str(output_path) + "_checker")
    to_check_output_file.mkdir(parents=True, exist_ok=True)
    shutil.copytree(output_path, to_check_output_file, dirs_exist_ok=True)
    ws_validation = validate_external_node(node_type, to_check_output_file)
    assert ws_validation.state == WorkspaceState.VALID
    assert len(ws_validation.errors) == 0
    assert isinstance(ws_validation.model, node_type)


@pytest.mark.parametrize(
    "node_type,node_path",
    partial_params,
)
@pytest.mark.no_xdist
def test_generate_partial_node(get_flync_example_path, node_type, node_path):
    if isinstance(node_path, FLYNCModel):
        pytest.skip(
            "No need to generate a full FLYNC Model with the partial generator"
        )
    output_path = (
        current_dir
        / "generated"
        / (Path(get_flync_example_path).name + "_partial_generator")
    )
    if node_type == FLYNCModel and output_path.is_dir():
        shutil.rmtree(output_path)
    reset_global_registery_function()
    generated_workspace = try_load_workspace(ws_name="generated_workspace",
                                             output_path=output_path,
                                             ws_config=WorkspaceConfiguration(map_objects=True))
    generate_node(generated_workspace, list(node_path))
    to_check_output_file = Path(str(output_path) + "_checker")
    to_check_output_file.mkdir(parents=True, exist_ok=True)
    shutil.copytree(output_path, to_check_output_file, dirs_exist_ok=True)
    reset_global_registery_function()
    ws_validation = validate_workspace(to_check_output_file, generated_workspace.configuration)
    assert ws_validation.state == WorkspaceState.VALID
    assert len(ws_validation.errors) == 0
    assert any(p in ws_validation.workspace.objects for p in node_path)
    assert isinstance(ws_validation.workspace.get_object(node_path[0]).model, node_type)

from flync.model import FLYNCBaseModel
from flync.core.annotations import External, OutputStrategy
from typing import Annotated


class ExtraInfo(FLYNCBaseModel):
    extra_name: str


class ExtendedFLYNC(FLYNCModel):
    extra: Annotated[
        ExtraInfo,
        External(
            output_structure=OutputStrategy.SINGLE_FILE
            | OutputStrategy.OMMIT_ROOT
        ),
    ]


def test_flync_extension(get_flync_example_path):
    output_extra_path = (
        current_dir
        / "generated"
        / (Path(get_flync_example_path).name + "_extended_model")
    )
    shutil.copytree(get_flync_example_path, output_extra_path, dirs_exist_ok=True)    
    extra_file = f"extra{WorkspaceConfiguration.flync_file_extension}"
    extra_data = {"extra_name": "value"}

    with open(output_extra_path / extra_file, "w") as f:
        yaml.dump(extra_data, f, default_flow_style=False)

    output = validate_external_node(ExtendedFLYNC, output_extra_path)
    assert output.state == WorkspaceState.VALID
    created_model: ExtendedFLYNC = output.model
    assert created_model.extra.extra_name == "value"



def test_object_referencing(
    get_relative_flync_example_path,
):
    workspace_name_object = (
        "flync_workspace_for_test_object_referencing_from_folder"
    )
    config = WorkspaceConfiguration(
        map_objects=True, list_objects_mode=ListObjectsMode.NAME,
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
