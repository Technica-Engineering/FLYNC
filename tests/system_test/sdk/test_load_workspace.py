import asyncio
import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError

from flync.sdk.workspace.flync_workspace import FLYNCWorkspace

from .helper_load_ws import (
    append_yaml_content,
    model_has_socket,
    update_yaml_content,
)

# Verify loading workspace multiple times
absolute_path = Path(__file__).parents[3] / "examples" / "flync_example"


def test_load_workspace_multiple_times(tmpdir):
    for i in range(1, 4):
        destination_folder = Path(tmpdir) / f"copy{i}"
        shutil.copytree(absolute_path, destination_folder)
        workspace = FLYNCWorkspace.load_workspace("flync_example", destination_folder)
        assert workspace is not None
        if destination_folder.exists():
            shutil.rmtree(destination_folder)


# Verify workspace loads with valid absolute path
def test_load_workspace_valid_absolute_path():
    workspace = FLYNCWorkspace.load_workspace("flync_example", absolute_path)
    assert workspace is not None
    assert workspace.flync_model is not None
    assert workspace.flync_model.ecus
    assert workspace.flync_model.topology
    assert workspace.flync_model.topology.system_topology
    assert workspace.flync_model.communication
    assert workspace.flync_model.communication.someip_config
    assert workspace.flync_model.communication.tcp_profiles
    assert workspace.flync_model.metadata
    assert model_has_socket(workspace)


# Verify workspace loads with valid relative path
relative_path = Path(Path(__file__).parent, "..", "..", "..", "examples", "flync_example")


def test_load_workspace_valid_relative_path():
    workspace = FLYNCWorkspace.load_workspace("flync_example", relative_path)
    assert workspace is not None
    assert workspace.flync_model is not None
    assert workspace.flync_model.ecus
    assert workspace.flync_model.topology
    assert workspace.flync_model.topology.system_topology
    assert workspace.flync_model.communication
    assert workspace.flync_model.communication.someip_config
    assert workspace.flync_model.communication.tcp_profiles
    assert workspace.flync_model.metadata
    assert model_has_socket(workspace)


def test_load_workspace_valid_str_path():
    workspace = FLYNCWorkspace.load_workspace("flync_example", str(absolute_path))
    assert workspace is not None
    assert workspace.flync_model is not None
    assert workspace.flync_model.ecus
    assert workspace.flync_model.topology
    assert workspace.flync_model.topology.system_topology
    assert workspace.flync_model.communication
    assert workspace.flync_model.communication.someip_config
    assert workspace.flync_model.communication.tcp_profiles
    assert workspace.flync_model.metadata
    assert model_has_socket(workspace)


# Verify the existence of attributes
required_attributes = [
    "name",
    "configuration",
    "documents",
    "documents_diags",
    "objects",
    "sources",
    "flync_model",
    "registry",
    "workspace_root",
]


@pytest.mark.parametrize("attribute", required_attributes)
def test_load_workspace_exsistence_attribute(attribute):
    workspace = FLYNCWorkspace.load_workspace("flync_example", absolute_path)
    assert hasattr(workspace, attribute), f"Workspace is missing attribute: {attribute}"


# Verify handling invalid workspace directory path
def test_load_workspace_invalid_yaml_path():
    with pytest.raises(FileNotFoundError):
        FLYNCWorkspace.load_workspace("flync_example", "/path/to/nonexistent/directory")


def test_load_workspace_empty_name():
    with pytest.raises(Exception):
        FLYNCWorkspace.load_workspace("", absolute_path)


def test_load_workspace_empty_path():
    with pytest.raises(Exception):
        FLYNCWorkspace.load_workspace("flync_example", "")


# Verify handling missing mandatory directory
subfolders = [
    Path(absolute_path, "ecus"),
    *Path(absolute_path).glob("ecus/*/controllers"),
]


@pytest.mark.parametrize("subfolder", subfolders)
def test_load_workspace_missing_mandatory_folder(tmpdir, subfolder):
    destination_folder = Path(tmpdir) / "copy"
    shutil.copytree(absolute_path, destination_folder)
    shutil.rmtree(destination_folder / subfolder.relative_to(absolute_path))
    with pytest.raises(FileNotFoundError):
        FLYNCWorkspace.load_workspace("flync_example", destination_folder)
    if destination_folder.exists():
        shutil.rmtree(destination_folder)


# Verify handling missing mandatory file
files = [
    Path(absolute_path, "system_metadata.flync.yaml"),
    *Path(absolute_path).glob("ecus/*/ports.flync.yaml"),
    *Path(absolute_path).glob("ecus/*/topology.flync.yaml"),
    *Path(absolute_path).glob("ecus/*/ecu_metadata.flync.yaml"),
    *Path(absolute_path).glob("ecus/*/controllers/*/ethernet_interfaces/*/interface_config.flync.yaml"),
    *Path(absolute_path).glob("ecus/*/controllers/*/controller_metadata.flync.yaml"),
]


@pytest.mark.parametrize("file", files)
def test_load_workspace_missing_mandatory_file(tmpdir, file):
    destination_folder = Path(tmpdir) / "copy"
    shutil.copytree(absolute_path, destination_folder)
    path_to_remove = destination_folder / file.relative_to(absolute_path)
    path_to_remove.unlink()
    try:
        loaded_ws = FLYNCWorkspace.load_workspace("flync_example", destination_folder)
        assert loaded_ws.load_errors != []
    except ValidationError:
        pass
    if destination_folder.exists():
        shutil.rmtree(destination_folder)


# Verify handling unsupported file format
files = [
    Path(absolute_path, "system_metadata.flync.yaml"),
    *Path(absolute_path).glob("ecus/*/ports.flync.yaml"),
    *Path(absolute_path).glob("ecus/*/topology.flync.yaml"),
    *Path(absolute_path).glob("ecus/*/ecu_metadata.flync.yaml"),
    *Path(absolute_path).glob("ecus/*/controllers/*/ethernet_interfaces/*/interface_config.flync.yaml"),
    *Path(absolute_path).glob("ecus/*/controllers/*/controller_metadata.flync.yaml"),
]


@pytest.mark.parametrize("file", files)
def test_load_workspace_invalid_format(tmpdir, file):
    destination_folder = Path(tmpdir) / "copy"
    shutil.copytree(absolute_path, destination_folder)
    file_to_rename = destination_folder / file.relative_to(absolute_path)
    new_file_name = file_to_rename.name[: -len(".flync.yaml")] + "yaml"
    new_file_path = file_to_rename.with_name(new_file_name)
    file_to_rename.rename(new_file_path)
    try:
        loaded_ws = FLYNCWorkspace.load_workspace("flync_example", destination_folder)
        assert loaded_ws.load_errors != []
    except ValidationError:
        pass
    if destination_folder.exists():
        shutil.rmtree(destination_folder)


# Verify workspace loading with added image (schema/diagram)
directories = [absolute_path] + [path for path in absolute_path.rglob("*") if path.is_dir()]

# Verify handling case sensitivity for keys
def test_load_workspace_upper_key(tmpdir):
    destination_folder = Path(tmpdir) / "copy"
    shutil.copytree(absolute_path, destination_folder)
    file_to_update = (
        destination_folder
        / "ecus"
        / "eth_ecu"
        / "controllers"
        / "eth_ecu_controller1"
        / "ethernet_interfaces"
        / "eth_ecu_c1_iface1"
        / "interface_config.flync.yaml"
    )
    update_yaml_content(file_to_update, "name", "NAME")
    workspace = FLYNCWorkspace.load_workspace("flync_example", destination_folder)
    assert "Field required" in str(workspace.load_errors)
    if destination_folder.exists():
        shutil.rmtree(destination_folder)

# Validate handling of extra key/value
def test_load_workspace_extra_key_value(tmpdir):
    destination_folder = Path(tmpdir) / "copy"
    shutil.copytree(absolute_path, destination_folder)
    file_to_update = (
        destination_folder
        / "ecus"
        / "eth_ecu"
        / "controllers"
        / "eth_ecu_controller1"
        / "ethernet_interfaces"
        / "eth_ecu_c1_iface1"
        / "interface_config.flync.yaml"
    )
    append_yaml_content(file_to_update, "\nnew_value: something\n")
    try:
        loaded_ws = FLYNCWorkspace.load_workspace("flync_example", destination_folder)
        assert loaded_ws.load_errors != []
    except ValidationError as exc_info:
        assert "new_value\n  Extra inputs are not permitted" in str(exc_info)
    if destination_folder.exists():
        shutil.rmtree(destination_folder)


# Verify handling indentation fault
def test_load_workspace_key_value_misplaced(tmpdir):
    destination_folder = Path(tmpdir) / "copy"
    shutil.copytree(absolute_path, destination_folder)
    file_to_update = (
        destination_folder
        / "ecus"
        / "eth_ecu"
        / "controllers"
        / "eth_ecu_controller1"
        / "ethernet_interfaces"
        / "eth_ecu_c1_iface1"
        / "interface_config.flync.yaml"
    )
    update_yaml_content(file_to_update, "  mode: mac", "mode: mac")
    try:
        loaded_ws = FLYNCWorkspace.load_workspace("flync_example", destination_folder)
        assert loaded_ws.load_errors != []
    except ValidationError as exc_info:
        assert "mii_config.sgmii.mode\n  Field required" in str(exc_info)
        assert "mode\n  Extra inputs are not permitted" in str(exc_info)
    if destination_folder.exists():
        shutil.rmtree(destination_folder)



# Verify handling missing dashe in list items
def test_load_workspace_missing_dashe(tmpdir):
    destination_folder = Path(tmpdir) / "copy"
    shutil.copytree(absolute_path, destination_folder)
    file_to_update = (
        destination_folder
        / "ecus"
        / "eth_ecu"
        / "controllers"
        / "eth_ecu_controller1"
        / "ethernet_interfaces"
        / "eth_ecu_c1_iface1"
        / "interface_config.flync.yaml"
    )
    update_yaml_content(
        file_to_update,
        "multicast:\n            - 224.0.0.1",
        "multicast:\n            224.0.0.1",
    )
    try:
        loaded_ws = FLYNCWorkspace.load_workspace("flync_example", destination_folder)
        assert loaded_ws.load_errors != []
    except ValidationError as exc_info:
        assert "multicast\n  Input should be a valid list" in str(exc_info)
    if destination_folder.exists():
        shutil.rmtree(destination_folder)


# Verify handling missing key/value
def test_load_workspace_missing_key_value(tmpdir):
    destination_folder = Path(tmpdir) / "copy"
    shutil.copytree(absolute_path, destination_folder)
    file_to_update = (
        destination_folder
        / "ecus"
        / "eth_ecu"
        / "controllers"
        / "eth_ecu_controller1"
        / "ethernet_interfaces"
        / "eth_ecu_c1_iface1"
        / "interface_config.flync.yaml"
    )
    update_yaml_content(file_to_update, "name: eth_ecu_c1_iface1", "")
    try:
        loaded_ws = FLYNCWorkspace.load_workspace("flync_example", destination_folder)
        assert loaded_ws.load_errors != []
    except ValidationError as exc_info:
        assert "name\n  Field required" in str(exc_info)
    if destination_folder.exists():
        shutil.rmtree(destination_folder)


def _assert_workspace_valid(ws: FLYNCWorkspace):
    assert ws is not None
    assert ws.flync_model is not None
    # Model loaded successfully. Note: workspace may have warnings/diagnostics
    # in load_errors, but the model is still considered valid if it loads.
    # Only verify core attributes that should always be present.
    assert len(ws.flync_model.ecus) > 0, "No ECUs loaded in the workspace"
    assert ws.flync_model.topology
    assert ws.flync_model.topology.system_topology
    assert ws.flync_model.communication
    assert ws.flync_model.communication.someip_config
    assert ws.flync_model.communication.tcp_profiles
    assert ws.flync_model.metadata


# Verify loading multiple independent workspace copies sequentially
def test_load_multiple_workspaces_sync(tmpdir):
    workspaces = []
    for i in range(1, 4):
        destination = Path(tmpdir) / f"copy{i}"
        shutil.copytree(absolute_path, destination)
        ws = FLYNCWorkspace.load_workspace(f"flync_example_{i}", destination)
        workspaces.append(ws)

    for ws in workspaces:
        _assert_workspace_valid(ws)


# Verify loading multiple independent workspace copies concurrently
def test_load_multiple_workspaces_async(tmpdir):
    paths = []
    for i in range(1, 4):
        destination = Path(tmpdir) / f"copy{i}"
        shutil.copytree(absolute_path, destination)
        paths.append((f"flync_example_{i}", destination))

    async def load_all():
        tasks = [asyncio.to_thread(FLYNCWorkspace.load_workspace, name, path) for name, path in paths]
        return await asyncio.gather(*tasks)

    workspaces = asyncio.run(load_all())

    for ws in workspaces:
        _assert_workspace_valid(ws)


# Regression for the union-type diagnostics swallow:
# __try_load_union_type used to delete diagnostics whenever a union member
# returned None, including for legitimate semantic errors raised by
# @model_validator on the matched type. With Optional[FLYNCChannelConfig]
# wrapping the channels field, the cross-PDU-reference major error from
# FLYNCChannelConfig.validate_pdu_refs disappeared entirely from the result.
def test_validate_workspace_surfaces_unknown_pdu_ref(tmpdir):
    from flync.sdk.helpers.validation_helpers import validate_workspace

    destination_folder = Path(tmpdir) / "copy"
    shutil.copytree(absolute_path, destination_folder)
    # Target the Frame_EngineDiagResponse line; its PDU ref name only appears
    # once in this file and is independent of the LightDiagRequest content.
    diag_can = destination_folder / "communication" / "channels" / "can" / "diag_can.flync.yaml"
    update_yaml_content(diag_can, "pdu_ref: PDU_EngineStatus", "pdu_ref: nonexistent_pdu")

    result = validate_workspace(destination_folder)

    surfaced = [e for errs in result.errors.values() for e in errs if e.get("type") == "major" and "nonexistent_pdu" in (e.get("msg") or "")]
    assert surfaced, f"Expected major error about unknown PDU 'nonexistent_pdu', got: {dict(result.errors)}"

    if destination_folder.exists():
        shutil.rmtree(destination_folder)
