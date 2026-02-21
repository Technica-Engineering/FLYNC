import pytest
from pathlib import Path
from flync.sdk.workspace.flync_workspace import FLYNCWorkspace
import shutil
from pydantic import ValidationError
from tests.system_test.helper import *

# Verify workspace loads with valid absolute path
absolute_path = Path(__file__).parents[2] /'examples'/'flync_example'
def test_load_workspace_valid_absolute_path():
    workspace = FLYNCWorkspace.load_workspace("flync_example",absolute_path)
    assert workspace is not None

# Verify workspace loads with valid relative path
relative_path = Path(Path(__file__).parent, '..', '..', 'examples','flync_example')
def test_load_workspace_valid_relative_path():
    workspace = FLYNCWorkspace.load_workspace("flync_example",relative_path)
    assert workspace is not None

# Verify workspace loads with valid str path
def test_load_workspace_valid_str_path():
    workspace = FLYNCWorkspace.load_workspace("flync_example",str(absolute_path))
    assert workspace is not None

# Verify the existence of attributes
required_attributes = [
    'name', 
    'documents', 
    'objects', 
    'sources', 
    'dependencies', 
    'reverse_deps', 
    '_diagnostics'
    ]
@pytest.mark.parametrize("attribute", required_attributes)
def test_load_workspace_exsistence_attribute(attribute):
    workspace = FLYNCWorkspace.load_workspace("flync_example",absolute_path)
    assert hasattr(workspace, attribute), f"Workspace is missing attribute: {attribute}"

# Verify handling invalid workspace directory path
def test_load_workspace_invalid_yaml_path():
    with pytest.raises(FileNotFoundError):
        FLYNCWorkspace.load_workspace("flync_example","/path/to/nonexistent/directory")
    
# Verify handling invalid workspace name
def test_load_workspace_invalid_name():
    with pytest.raises(Exception):
        FLYNCWorkspace.load_workspace("invalid_name",absolute_path)

# Verify handling missing mandatory directory
subfolders = [
    Path(absolute_path,'ecus'),
    *Path(absolute_path).glob('ecus/*/controllers')
    ]
@pytest.mark.parametrize("subfolder", subfolders)
def test_load_workspace_missing_mandatory_folder(tmpdir, subfolder):
    destination_folder = Path(tmpdir) / 'copie'
    shutil.copytree(absolute_path, destination_folder)
    shutil.rmtree(destination_folder / subfolder.relative_to(absolute_path))
    with pytest.raises(FileNotFoundError):
        FLYNCWorkspace.load_workspace("flync_example",destination_folder)
    if destination_folder.exists():
        shutil.rmtree(destination_folder)
    
# Verify handling missing mandatory file 
files = [
    Path(absolute_path,'system_metadata.flync.yaml'),
    *Path(absolute_path).glob('ecus/*/ports.flync.yaml'),
    *Path(absolute_path).glob('ecus/*/topology.flync.yaml'),
    *Path(absolute_path).glob('ecus/*/ecu_metadata.flync.yaml'),
    *Path(absolute_path).glob('ecus/*/controllers/*')
    ]
@pytest.mark.parametrize("file", files)
def test_load_workspace_missing_mandatory_file(tmpdir, file):
    destination_folder = Path(tmpdir) / 'copie'
    shutil.copytree(absolute_path, destination_folder)
    path_to_remove = destination_folder / file.relative_to(absolute_path)
    path_to_remove.unlink()
    with pytest.raises(ValidationError):
        FLYNCWorkspace.load_workspace("flync_example",destination_folder)
    if destination_folder.exists():
        shutil.rmtree(destination_folder)

# Verify documentation configuration example 
def test_load_workspace_doc_exmaple(tmpdir):
    rst_file = Path(__file__).parents[2] /'docs'/'source'/'flync_example.rst'
    example_folder = Path(tmpdir) / "copie"
    extract_example_from_rst(rst_file,example_folder,"Example Configuration")
    workspace = FLYNCWorkspace.load_workspace(str(example_folder.name),example_folder)
    assert workspace is not None
    assert example_folder.exists()
    if example_folder.exists():
        shutil.rmtree(example_folder)

# Verify handling unsupported file format
files = [
    Path(absolute_path,'system_metadata.flync.yaml'),
    *Path(absolute_path).glob('ecus/*/ports.flync.yaml'),
    *Path(absolute_path).glob('ecus/*/topology.flync.yaml'),
    *Path(absolute_path).glob('ecus/*/ecu_metadata.flync.yaml'),
    *Path(absolute_path).glob('ecus/*/controllers/*')
    ]
@pytest.mark.parametrize("file", files)
def test_load_workspace_invalid_format(tmpdir, file):
    destination_folder = Path(tmpdir) / 'copie'
    shutil.copytree(absolute_path, destination_folder)
    file_to_rename = destination_folder / file.relative_to(absolute_path)
    new_file_name = file_to_rename.name[:-len('.flync.yaml')] + 'yaml'
    new_file_path = file_to_rename.with_name(new_file_name)
    file_to_rename.rename(new_file_path)
    with pytest.raises(ValidationError):
        FLYNCWorkspace.load_workspace("flync_example",destination_folder)
    if destination_folder.exists():
        shutil.rmtree(destination_folder)

# Verify workspace loading with added image (schema/diagram)
image_path = Path(__file__).parents[2] /'docs'/'source'/'_static'/'technica-logo.png'
directories = [absolute_path] + [path for path in absolute_path.rglob('*') if path.is_dir()]
@pytest.mark.parametrize("dir", directories)
def test_load_workspace_add_image(tmpdir, dir):
    destination_folder = Path(tmpdir) / 'copie'
    shutil.copytree(absolute_path, destination_folder)
    path_to_add = destination_folder / dir.relative_to(absolute_path)
    shutil.copy(image_path, path_to_add)
    workspace = FLYNCWorkspace.load_workspace("flync_example",destination_folder)
    assert workspace is not None
    if destination_folder.exists():
        shutil.rmtree(destination_folder)

# Verify handling case sensitivity for keys
def test_load_workspace_upper_key(tmpdir):
    destination_folder = Path(tmpdir) / 'copie'
    shutil.copytree(absolute_path, destination_folder)
    file_to_update = destination_folder/'ecus'/'eth_ecu'/'controllers'/'eth_ecu_controller1.flync.yaml'
    update_yaml_content(file_to_update,'name','NAME')
    with pytest.raises(ValidationError) as exc_info:
        FLYNCWorkspace.load_workspace("flync_example",destination_folder)
    assert "name\n  Field required" in str(exc_info.value)
    if destination_folder.exists():
        shutil.rmtree(destination_folder)

# Verify handling incorrect type for value
def test_load_workspace_incorret_value_type(tmpdir):
    destination_folder = Path(tmpdir) / 'copie'
    shutil.copytree(absolute_path, destination_folder)
    file_to_update = destination_folder/'ecus'/'eth_ecu'/'controllers'/'eth_ecu_controller1.flync.yaml'
    update_yaml_content(file_to_update,'name: eth_ecu_controller1','name: 123')
    with pytest.raises(ValidationError) as exc_info:
        FLYNCWorkspace.load_workspace("flync_example",destination_folder)
    assert "name\n  Input should be a valid string" in str(exc_info.value)
    if destination_folder.exists():
        shutil.rmtree(destination_folder)

# Verify handling incorrect format for value
invalid_format = {
    '001122334455': 'mac_address_format\n  Must have the format',
    '00:11:22:33:xx:XX': 'mac_address\n  Unrecognized format',
    '00:11:22': 'mac_address\n  Length for a 00:11:22 MAC address must be 14'
    }
@pytest.mark.parametrize("key, value",invalid_format.items())
def test_load_workspace_incorret_value_format(tmpdir,key, value):
    destination_folder = Path(tmpdir) / 'copie'
    shutil.copytree(absolute_path, destination_folder)
    file_to_update = destination_folder/'ecus'/'eth_ecu'/'controllers'/'eth_ecu_controller1.flync.yaml'
    update_yaml_content(file_to_update,'mac_address: 00:11:22:33:44:55',f'mac_address: {key}')
    with pytest.raises(ValidationError) as exc_info:
        FLYNCWorkspace.load_workspace("flync_example",destination_folder)
    assert value in str(exc_info.value)
    if destination_folder.exists():
        shutil.rmtree(destination_folder)

# Validate handling of extra key/value
def test_load_workspace_extra_key_value(tmpdir):
    destination_folder = Path(tmpdir) / 'copie'
    shutil.copytree(absolute_path, destination_folder)
    file_to_update = destination_folder/'ecus'/'eth_ecu'/'controllers'/'eth_ecu_controller1.flync.yaml'
    append_yaml_content(file_to_update,'\nnew_value: something\n')
    with pytest.raises(ValidationError) as exc_info:
        FLYNCWorkspace.load_workspace("flync_example",destination_folder)
    assert "new_value\n  Extra inputs are not permitted" in str(exc_info.value)
    if destination_folder.exists():
        shutil.rmtree(destination_folder)

# Verify handling indentation fault
def test_load_workspace_key_value_misplaced(tmpdir):
    destination_folder = Path(tmpdir) / 'copie'
    shutil.copytree(absolute_path, destination_folder)
    file_to_update = destination_folder/'ecus'/'eth_ecu'/'controllers'/'eth_ecu_controller1.flync.yaml'
    update_yaml_content(file_to_update,'  mode: mac','mode: mac')
    with pytest.raises(ValidationError) as exc_info:
        FLYNCWorkspace.load_workspace("flync_example",destination_folder)
    assert "interfaces.0.mii_config.sgmii.mode\n  Field required" in str(exc_info.value)
    assert "interfaces.0.mode\n  Extra inputs are not permitted" in str(exc_info.value)
    if destination_folder.exists():
        shutil.rmtree(destination_folder)

# Verify handling duplicate keys
def test_load_workspace_duplicate_key(tmpdir):
    destination_folder = Path(tmpdir) / 'copie'
    shutil.copytree(absolute_path, destination_folder)
    file_to_update = destination_folder/'ecus'/'eth_ecu'/'controllers'/'eth_ecu_controller1.flync.yaml'
    update_yaml_content(file_to_update,'mac_address: 00:11:22:33:44:55','mac_address: 00:11:22:33:44:55\n    mac_address: 11:22:33:44:55:66')
    with pytest.raises(Exception):
        FLYNCWorkspace.load_workspace("flync_example",destination_folder)
    if destination_folder.exists():
        shutil.rmtree(destination_folder)

# Verify handling missing dashe in list items
def test_load_workspace_missing_dashe(tmpdir):
    destination_folder = Path(tmpdir) / 'copie'
    shutil.copytree(absolute_path, destination_folder)
    file_to_update = destination_folder/'ecus'/'eth_ecu'/'controllers'/'eth_ecu_controller1.flync.yaml'
    update_yaml_content(file_to_update,'multicast:\n          - 224.0.0.23','multicast:\n           224.0.0.23')
    with pytest.raises(ValidationError) as exc_info:
        FLYNCWorkspace.load_workspace("flync_example",destination_folder)
    assert "multicast\n  Input should be a valid list" in str(exc_info.value)
    if destination_folder.exists():
        shutil.rmtree(destination_folder)

# Verify handling missing key/value
def test_load_workspace_missing_key_value(tmpdir):
    destination_folder = Path(tmpdir) / 'copie'
    shutil.copytree(absolute_path, destination_folder)
    file_to_update = destination_folder/'ecus'/'eth_ecu'/'controllers'/'eth_ecu_controller1.flync.yaml'
    update_yaml_content(file_to_update,'name: eth_ecu_controller1','')
    with pytest.raises(ValidationError) as exc_info:
        FLYNCWorkspace.load_workspace("flync_example",destination_folder)
    assert "name\n  Field required" in str(exc_info.value)
    if destination_folder.exists():
        shutil.rmtree(destination_folder)