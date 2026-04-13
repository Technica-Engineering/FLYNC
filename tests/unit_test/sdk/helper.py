import json
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType

import yaml
from pydantic import BaseModel, TypeAdapter
from pydantic._internal._model_construction import ModelMetaclass
from ruamel.yaml.nodes import MappingNode, ScalarNode, SequenceNode

from flync.model import FLYNCModel
from flync.sdk.context.workspace_config import WorkspaceConfiguration
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
        raise ValueError(
            f"Found unexpected keys ({unexpected_keys}) during the roundtrip conversion"
        )

    for k in base_keys & generated_keys:
        if base_files[k] != generated_files[k]:
            return False

    return True


def model_has_socket(loaded_model: FLYNCModel):
    return any(
        address.sockets
        for ecu in loaded_model.ecus
        for controller in ecu.controllers
        for interface in controller.interfaces
        for vlan in interface.virtual_interfaces
        for address in vlan.addresses
    )


def dataclass_dict_to_json(obj_dict: dict):
    return json.dumps(
        {
            k: TypeAdapter(type(v)).dump_json(v).decode("utf-8")
            for k, v in obj_dict.items()
        },
        indent=2,
    )


def to_jsonable(obj, relative_path, seen=None):
    if seen is None:
        seen = set()

    obj_id = id(obj)
    if isinstance(obj, BaseModel) and obj_id in seen:
        return "<circular>"
    if not obj_id in seen:
        seen.add(obj_id)
    # special case since the workspace is too complex
    if isinstance(obj, FLYNCWorkspace):
        out_workspace = {
            "workspace_obj": {
                "workspace_name": obj.name,
                "workspace_path": to_jsonable(
                    obj.workspace_root, relative_path, seen
                ),
                "workspace_model": to_jsonable(
                    obj.flync_model, relative_path, seen
                ),
                "workspace_errors": len(obj.load_errors),
            }
        }
        seen.remove(obj_id)
        return out_workspace
    # relative paths
    if isinstance(obj, Path):
        path_obj = obj.relative_to(relative_path).as_posix()
        seen.remove(obj_id)
        return path_obj
    # mappingproxy or dict-like
    if isinstance(obj, Mapping) or isinstance(obj, MappingProxyType):
        out_map = {
            k: to_jsonable(v, relative_path, seen) for k, v in obj.items()
        }
        seen.remove(obj_id)
        return out_map

    if isinstance(obj, dict):
        out_dict = {
            k: to_jsonable(v, relative_path, seen) for k, v in obj.items()
        }
        seen.remove(obj_id)
        return out_dict
    if isinstance(obj, list) or isinstance(obj, set):
        out_list = [to_jsonable(v, relative_path, seen) for v in obj]
        seen.remove(obj_id)
        try:
            out_list = sorted(
                out_list,
                key=lambda x: json.dumps(x, sort_keys=True, default=str),
            )
        except Exception:
            pass
        return out_list

    if isinstance(obj, BaseModel):
        # we only care about the model type, not the content
        # (checked in other tests)
        out_obj_model = str(obj.__class__)
        seen.remove(obj_id)
        return out_obj_model

    if (
        isinstance(obj, MappingNode)
        or isinstance(obj, ScalarNode)
        or isinstance(obj, SequenceNode)
    ):
        seen.remove(obj_id)
        return yaml_node_to_python(obj)
    # ignore classes / metaclasses
    if isinstance(obj, type) or isinstance(obj, type(ModelMetaclass)):
        return obj.__name__
    if hasattr(obj, "__dict__"):
        result = {}
        for k, v in obj.__dict__.items():
            # skip descriptors and non-data attributes
            if callable(v):
                continue
            if type(v).__name__ in ("getset_descriptor", "member_descriptor"):
                continue
            result[k] = to_jsonable(v, relative_path, seen)
        seen.remove(obj_id)
        return result
    return str(obj)


def yaml_node_to_python(node):
    if isinstance(node, ScalarNode):
        return node.value
    elif isinstance(node, SequenceNode):
        items = [yaml_node_to_python(item) for item in node.value]
        try:
            items = sorted(
                items, key=lambda x: json.dumps(x, sort_keys=True, default=str)
            )
        except Exception:
            pass
        return items
    elif isinstance(node, MappingNode):
        return {
            yaml_node_to_python(k): yaml_node_to_python(v)
            for k, v in node.value
        }
    else:
        return str(node)  # fallback

def try_load_workspace(
        ws_name: str,
        output_path: Path,
        ws_config: WorkspaceConfiguration
        ) -> FLYNCWorkspace:
    if output_path.is_dir():
        return FLYNCWorkspace.safe_load_workspace(
                ws_name,
                workspace_path=output_path,
                workspace_config=ws_config,
            )
    return FLYNCWorkspace(
            name=ws_name,
            workspace_path=output_path,
            configuration=ws_config,
        )
    