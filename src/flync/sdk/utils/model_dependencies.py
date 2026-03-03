import types
from collections import defaultdict
from functools import lru_cache
from typing import Annotated, Union, get_args, get_origin
from types import NoneType

from pydantic import BaseModel

from flync.core.annotations import External, OutputStrategy

from .field_utils import get_metadata


def extract_container_model(annotation):
    """
    Recursively extract BaseModel types from nested containers
    like list[Model], dict[str, Model], list[dict[str, Model]], etc.
    Returns a structure describing the container shape.
    """
    origin = get_origin(annotation)
    args = get_args(annotation)

    if origin is list:
        items = extract_container_model(args[0])
        if not items:
            return None
        return {
            "container": "list",
            "items": items,
        }

    if origin is dict:
        values = extract_container_model(args[1])
        if not values:
            return None
        return {
            "container": "dict",
            "keys": args[0],
            "values": values,
        }

    if origin in (Union, types.UnionType):
        models = []
        for arg in args:
            result = extract_container_model(arg)
            if result:
                models.append(result)
        if not models:
            return None
        return {
            "container": "union",
            "options": models,
        }

    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return {
            "container": "model",
            "model": annotation,
        }

    return None


def unwrap_annotated(annotation):
    """
    Recursively unwrap Annotated[T, ...]
    Returns (clean_type, collected_metadata)
    """
    metadata = []

    while get_origin(annotation) is Annotated:
        args = get_args(annotation)
        annotation = args[0]
        metadata.extend(args[1:])

    return annotation, metadata


@lru_cache(maxsize=None)
def extract_model_dependencies(model: type[BaseModel]) -> dict:
    return _extract_model_dependencies(model, visited=set())


def _extract_model_dependencies(
    model: type[BaseModel], visited: set[type[BaseModel]]
) -> dict:

    # ---- CYCLE BREAKER ----
    if model in visited:
        return {"__cycle__": True}
    visited.add(model)
    # Ensure forward refs are resolved
    model.model_rebuild(force=True)
    deps = {}

    for name, field in model.model_fields.items():
        annotation, _ = unwrap_annotated(field.annotation)
        external = get_metadata(field.metadata, External)

        container_info = extract_container_model(annotation)

        if container_info:
            structure_info = build_dependency_structure(
                container_info, visited
            )
            deps[name] = {
                "external": external,
                "structure": structure_info,
            }

    return deps


def build_dependency_structure(info, visited):
    """
    Convert extracted container info into a dependency tree,
    recursively resolving child model dependencies.
    """
    if info["container"] == "model":
        model = info["model"]
        return {
            "type": model,
            "children": _extract_model_dependencies(model, visited),
        }

    if info["container"] == "list":
        items = build_dependency_structure(info["items"], visited)
        return {
            "type": "list",
            "items": items,
        }

    if info["container"] == "dict":
        return {
            "type": "dict",
            "keys": str(info["keys"]),
            "values": build_dependency_structure(info["values"], visited),
        }
    if info["container"] == "union":
        return {
            "type": "union",
            "options": [
                build_dependency_structure(opt, visited)
                for opt in info["options"]
            ],
        }


def walk_structure(parent_model, structure, edges, visited=None):
    if not visited:
        visited = set()
    if structure["type"] == "list":
        walk_structure(
            parent_model, structure["items"], edges, visited=visited
        )

    elif structure["type"] == "dict":
        walk_structure(
            parent_model, structure["values"], edges, visited=visited
        )

    elif structure["type"] == "union":
        for option in structure["options"]:
            walk_structure(parent_model, option, edges, visited=visited)

    else:
        child_model = structure["type"]  # already class
        if child_model in visited:
            return
        visited.add(child_model)
        edges.add((parent_model, child_model))

        for f in extract_model_dependencies(child_model).values():
            walk_structure(child_model, f["structure"], edges, visited=visited)

        visited.remove(child_model)


def collect_edges(model: type[BaseModel], edges=None):
    if edges is None:
        edges = set()

    deps = extract_model_dependencies(model)

    for field in deps.values():
        walk_structure(model, field["structure"], edges)

    return edges


@lru_cache(maxsize=None)
def build_reverse_lookup(root_model: type[BaseModel]):
    edges = collect_edges(root_model)

    reverse = defaultdict(set)

    for parent, child in edges:
        reverse[child].add(parent)

    return dict(reverse)


class ModelDependencyGraph:
    def __init__(self, root: type[BaseModel]):
        self.root = root
        self.forward = collect_edges(root)
        self.reverse: dict[str, set[BaseModel]] = self._invert()

    def _invert(self):
        reverse = defaultdict(set)
        for p, c in self.forward:
            reverse[c].add(p)
        return dict(reverse)

    def parent_from_child(
        self, field_type: type[BaseModel], parent_attribute_name: str
    ):
        potential_parents = self.reverse[field_type]
        for parent in potential_parents:
            attribute = parent.model_fields.get(parent_attribute_name, None)
            if not attribute:
                continue
            return parent

    def field_info_from_child(
        self, field_type: type[BaseModel], parent_attribute_name: str
    ):
        parent = self.parent_from_child(field_type, parent_attribute_name)
        if not parent:
            return field_type
        return parent.model_fields[parent_attribute_name]

    def rebuild_type_from_parent(
        self, field_type: type[BaseModel], parent_attribute_name: str
    ):
        real_type = field_type
        attribute = self.field_info_from_child(
            field_type, parent_attribute_name
        )
        # in case of ommit root, we need to include a dictionary
        external = get_metadata(attribute.metadata, External)
        if OutputStrategy.SINGLE_FILE in external.output_structure:
            if NoneType not in get_args(attribute.annotation):
                real_type = attribute.annotation
            if OutputStrategy.OMMIT_ROOT not in external.output_structure:
                real_type = dict[str, real_type]
        return real_type

    def normalize_child_to_parent(
        self,
        field_type: type[BaseModel],
        parent_attribute_name: str,
        model_data,
    ):
        if not model_data:
            return None
        attribute = self.field_info_from_child(
            field_type, parent_attribute_name
        )
        # in case of ommit root, we need to include a dictionary
        external = get_metadata(attribute.metadata, External)
        if (
            OutputStrategy.SINGLE_FILE in external.output_structure
            and OutputStrategy.OMMIT_ROOT not in external.output_structure
        ):
            return model_data[parent_attribute_name]
        return model_data
