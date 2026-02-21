from pathlib import Path
from typing import Tuple
import yaml

from flync.sdk.workspace.flync_workspace import FLYNCWorkspace

def flatten_yaml(data, parent_key="", sep="."):
    items = {}
    if isinstance(data, dict):
        for key, value in data.items():
            new_key = f"{parent_key}{sep}{key}" if parent_key else key
            items.update(flatten_yaml(value, new_key, sep))
    elif isinstance(data, list):
        for index, value in enumerate(data):
            new_key = f"{parent_key}{sep}{index}"
            items.update(flatten_yaml(value, new_key, sep))
    else:
        items[parent_key] = data
    return items


def load_yaml_folder(folder_path: Path, sep="."):
    result = {}
    sorted_files = sorted(folder_path.rglob("*.*"), key=lambda f: f.name)
    for yaml_file in sorted_files:
        if yaml_file.suffix not in (".yml", ".yaml"):
            continue

        with open(yaml_file, "r") as f:
            data = yaml.safe_load(f)

        if data is None:
            continue

        flat_data = flatten_yaml(data, sep=sep)

        # Build prefix: folder.subfolder.file
        relative_path = yaml_file.relative_to(folder_path)
        file_key = sep.join(relative_path.with_suffix("").parts[:-1])

        for key, value in flat_data.items():
            full_key = f"{file_key}{sep}{key}"
            result[full_key] = value
    return result

def compare_yaml_files(base_folder: Path, generated_folder: Path) -> bool:
    base_files = load_yaml_folder(base_folder)
    generated_files = load_yaml_folder(generated_folder)

    base_keys = set(base_files.keys())
    generated_keys = set(generated_files.keys())

    unexpected_keys = generated_keys ^ base_keys
    if unexpected_keys:
        raise ValueError(f"Found unexpected keys ({unexpected_keys}) during the roundtrip conversion")

    for k in base_keys & generated_keys:
        if base_files[k] != generated_files[k]:
            return False

    return True

def model_has_socket(loaded_ws: FLYNCWorkspace):
    return any(
        address.sockets
        for ecu in loaded_ws.flync_model.ecus
        for controller in ecu.controllers
        for interface in controller.interfaces
        for vlan in interface.virtual_interfaces
        for address in vlan.addresses
        )