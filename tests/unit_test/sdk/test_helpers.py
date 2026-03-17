import json
import logging
from os import sep
from pathlib import Path

import pytest
from approvaltests import verify
from approvaltests.namer import NamerFactory

from flync.model import FLYNCModel
from flync.model.flync_4_ecu import ECU, Controller
from flync.sdk.helpers.generation_helpers import dump_flync_workspace
from flync.sdk.helpers.nodes_helpers import available_flync_nodes
from flync.sdk.helpers.validation_helpers import (
    WorkspaceState,
    validate_external_node,
    validate_node,
    validate_workspace,
)
from flync.sdk.utils.model_dependencies import get_model_dependency_graph
from flync.sdk.workspace.flync_workspace import FLYNCWorkspace
from tests.conftest import reset_global_registery_function

from .dummy_model import DummyRoot
from .helper import (
    compare_yaml_files,
    dataclass_dict_to_json,
    model_has_socket,
    to_jsonable,
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
TEST_MODEL_FLLYNC_PATHS = [
    ("",),
    (".".join(["ecus", "0"]), ".".join(["ecus", "eth_ecu"])),
    (
        ".".join(["ecus", "0", "controllers", "0"]),
        ".".join(["ecus", "eth_ecu", "controllers", "0"]),
        ".".join(["ecus", "0", "controllers", "eth_ecu_controller1"]),
        ".".join(["ecus", "eth_ecu", "controllers", "eth_ecu_controller1"]),
    ),
]


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
        TEST_MODEL_TYPES, TEST_MODEL_FLLYNC_PATHS, TEST_MODEL_TYPES_NAMES
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
        logger.info("will be outputting {}", output)
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
