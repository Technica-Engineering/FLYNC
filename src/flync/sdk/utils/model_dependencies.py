"""
Model dependency graph utilities for the FLYNC SDK.

Provides functions and classes to build, traverse, and query the dependency
graph between Pydantic models that make up a FLYNC workspace.
"""

import hashlib
import importlib
import shelve
import types
from functools import lru_cache
from os import listdir, makedirs, remove, stat, walk
from os.path import abspath, dirname, join
from types import NoneType
from typing import Annotated, Union, get_args, get_origin

import platformdirs
from pydantic import BaseModel

from flync.core.annotations import External, Implied, OutputStrategy, Reference
from flync.sdk.context.node_info import NodeInfo

from .field_utils import get_metadata


def extract_container_model(annotation):  # noqa # nosonar
    """Recursively extract ``BaseModel`` types from nested container
    annotations.

    Handles ``list[Model]``, ``dict[str, Model]``,
    ``list[dict[str, Model]]``,
    ``Union[A, B]``, and bare ``BaseModel`` subclasses.

    Args:
        annotation: A Python type annotation to inspect.

    Returns:
        dict | None: A dict describing the container shape, or ``None`` when
        no ``BaseModel`` type is reachable. The dict always has a
        ``"container"``
        key set to ``"list"``, ``"dict"``, ``"union"``, or ``"model"``.
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
    """Recursively strip ``Annotated`` wrappers from a type annotation.

    Args:
        annotation: A Python type annotation, potentially wrapped in one or
            more ``Annotated[T, ...]`` layers.

    Returns:
        tuple[type, list]: A ``(clean_type, metadata)`` pair where
        ``clean_type`` is the innermost unwrapped type and ``metadata`` is
        the flat list of all collected annotation arguments.
    """
    metadata = []

    while get_origin(annotation) is Annotated:
        args = get_args(annotation)
        annotation = args[0]
        metadata.extend(args[1:])

    return annotation, metadata


@lru_cache(maxsize=None)
def extract_model_dependencies(model: type[BaseModel]) -> dict:
    """Return the cached dependency tree for a Pydantic model.

    Results are memoized so the graph is only built once per model class.

    Args:
        model (type[BaseModel]): The model to inspect.

    Returns:
        dict: A dependency tree mapping field names to their structure and
        external annotation metadata.
    """
    return _extract_model_dependencies(model, visited=set())


def _extract_model_dependencies(
    model: type[BaseModel], visited: set[type[BaseModel]]
) -> dict:
    """Recursively extract model dependencies, guarding against cycles.

    Args:
        model (type[BaseModel]): The model being inspected.
        visited (set[type[BaseModel]]): Models currently on the call stack,
            used to detect and break circular references.

    Returns:
        dict: Dependency structure for the model's fields, or
        ``{"__cycle__": True}`` when a cycle is detected.
    """

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
        reference = get_metadata(field.metadata, Reference)
        implied = get_metadata(field.metadata, Implied)
        if reference or implied:
            continue
        container_info = extract_container_model(annotation)

        if container_info:
            structure_info = build_dependency_structure(
                container_info, visited
            )
            deps[name] = {
                "external": external,
                "structure": structure_info,
            }
    visited.remove(model)
    return deps


def build_dependency_structure(info, visited):  # noqa # nosonar
    """Convert extracted container info into a resolved dependency tree.

    Recursively replaces ``"model"`` leaf entries with their full child
    dependency trees as returned by :func:`_extract_model_dependencies`.

    Args:
        info (dict): A container-shape dict as produced by
            :func:`extract_container_model`.
        visited (set[type[BaseModel]]): Models currently on the call stack,
            forwarded to :func:`_extract_model_dependencies` for cycle
            detection.

    Returns:
        dict: A dependency tree node with a ``"type"`` key and additional
        keys depending on the container kind (``"items"``, ``"values"``,
        ``"options"``, or ``"children"``).
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
    """Walk a dependency structure and collect directed edges between models.

    Traverses container types (list, dict, union) recursively until reaching
    concrete model types, then records a directed edge from ``parent_model``
    to each discovered child model.

    Args:
        parent_model: The parent model class from which the walk started.
        structure (dict): A dependency structure dict as returned by
            :func:`build_dependency_structure`.
        edges (set): Mutable set accumulating ``(parent, child)`` model pairs.
        visited (set | None): Models currently being traversed; used to avoid
            infinite recursion on cycles.
    """
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
    """Collect all directed dependency edges reachable from a root model.

    Args:
        model (type[BaseModel]): The root model to start from.
        edges (set | None): Optional pre-existing edge set to accumulate into.

    Returns:
        tuple[set, dict]: A tuple of ``(edges, deps)`` where ``edges`` is the
        set of ``(parent, child)`` model pairs and ``deps`` is the raw
        dependency tree for ``model``.
    """
    if edges is None:
        edges = set()

    deps = extract_model_dependencies(model)

    for field in deps.values():
        walk_structure(model, field["structure"], edges)

    return edges, deps


class ModelDependencyGraph:
    """Dependency graph for a hierarchy of Pydantic models.

    Builds and exposes a directed graph of model relationships, enabling
    look-ups of parent–child relationships and path resolution.

    Attributes:
        root (type[BaseModel]): The root model of the graph.
        edges (set): Set of ``(parent, child)`` model-class pairs.
        tree (dict): Raw dependency tree rooted at ``root``.
        reverse_tree (dict[type, set[type]]): Inverted graph mapping each
            child model to its set of parent models.
        fields_info (dict[str, NodeInfo]): Metadata for every node in the
            graph, keyed by class name.
    """

    def __init__(self, root: type[BaseModel]):
        """Build the dependency graph for the given root model.

        Args:
            root (type[BaseModel]): The root Pydantic model class.
        """
        self.root = root
        self.edges, self.tree = collect_edges(root)
        self.reverse_tree: dict[type[BaseModel], set[type[BaseModel]]] = (
            self._invert()
        )
        self.fields_info: dict[str, NodeInfo] = self._field_info()

    def _invert(self):
        """Invert the edge set to produce a child-to-parents mapping.

        Returns:
            dict[type, set[type]]: Mapping of each child model class to the
            set of parent model classes that reference it.
        """
        reverse: dict[type[BaseModel], set[type[BaseModel]]] = {}
        for p, c in self.edges:
            if c not in reverse:
                reverse[c] = set()
            reverse[c].add(p)
        return dict(reverse)

    def _field_info(self):  # noqa # nosonar
        """Build per-node metadata including all paths from the root model.

        Walks the full dependency tree starting from ``self.root`` and
        records, for every reachable model class, the dot-separated paths
        through which it can be reached. Internal nested helpers ``walk``
        and ``walk_structure`` drive the recursion.

        Returns:
            dict[str, NodeInfo]: Mapping of class names to :class:`NodeInfo`
            objects. Each ``NodeInfo`` carries the Python type and the list
            of dot-separated FLYNC paths leading to it.
        """
        field_info: dict[str, NodeInfo] = {}
        # add root to info
        field_info[self.root.__name__] = NodeInfo(
            self.root.__name__, self.root
        )

        def walk(current_model, subtree, path=(), container_chain=()):
            """Iterate over a model's dependency subtree and dispatch to
            ``walk_structure``.

            Args:
                current_model: The Pydantic model class whose fields are being
                    walked.
                subtree (dict): The dependency tree for ``current_model`` as
                    returned by :func:`_extract_model_dependencies`.
                path (tuple): Accumulated path segments from the root to the
                    current position.
                container_chain (tuple): Accumulated container kinds (e.g.
                    ``"list"``, ``"dict"``) that wrap the current field.
            """
            for field_name, info in subtree.items():
                # add currnet path to dict
                if field_name == "__cycle__":  # found a cyclic item
                    continue
                structure = info["structure"]
                walk_structure(
                    current_model, field_name, structure, path, container_chain
                )

        def walk_structure(
            parent_model, field_name, structure, path, container_chain
        ):
            """Recursively resolve a single field's structure and record its
            path.

            Descends through ``"list"``, ``"dict"``, and ``"union"`` container
            nodes, accumulating container kinds in ``container_chain``, until a
            ``BaseModel`` leaf is reached.  At that point the leaf is recorded
            in ``field_info`` and the walk continues into its children.

            Args:
                parent_model: The Pydantic model class that owns the field.
                field_name (str): The attribute name of the field on
                    ``parent_model``.
                structure (dict): The dependency structure node to resolve.
                path (tuple): Path segments accumulated from the root to the
                    current node.
                container_chain (tuple): Container kinds wrapping the current
                    field, used to produce ``[]`` / ``{}`` path segments.
            """
            t = structure["type"]

            if t in ("list", "dict"):
                child_struct = (
                    structure.get("items")
                    if t == "list"
                    else structure.get("values")
                )
                walk_structure(
                    parent_model,
                    field_name,
                    child_struct,
                    path,
                    container_chain + (t,),
                )

            elif t == "union":
                for option in structure["options"]:
                    walk_structure(
                        parent_model,
                        field_name,
                        option,
                        path,
                        container_chain + ("union",),
                    )

            elif issubclass(t, BaseModel):
                child_model = t
                new_path = path + ((child_model, field_name, container_chain),)
                model_field_key = child_model.__name__
                if child_model not in field_info:
                    field_info[model_field_key] = NodeInfo(
                        child_model.__name__, child_model
                    )
                field_info[model_field_key].flync_paths.append(
                    ModelDependencyGraph.complex_path_to_string_path(new_path)
                )

                # recurse into children
                if "children" in structure:
                    walk(child_model, structure["children"], new_path)

            else:
                # leaf type, ignore
                return

        walk(self.root, self.tree)
        return dict(field_info)

    def parent_from_child(
        self, field_type: type[BaseModel], parent_attribute_name: str
    ):
        """Find the parent model class that owns a given child field.

        Args:
            field_type (type[BaseModel]): The child model class.
            parent_attribute_name (str): The field name on the parent that
                holds the child.

        Returns:
            type[BaseModel] | None: The parent model class, or ``None`` if
            not found.
        """
        potential_parents = self.reverse_tree[field_type]
        for parent in potential_parents:
            attribute = parent.model_fields.get(parent_attribute_name, None)
            if not attribute:
                continue
            return parent

    def field_info_from_child(
        self, field_type: type[BaseModel], parent_attribute_name: str
    ):
        """Return the field info object for a child field on its parent model.

        Args:
            field_type (type[BaseModel]): The child model class.
            parent_attribute_name (str): The attribute name on the parent.

        Returns:
            FieldInfo | type[BaseModel]: The Pydantic ``FieldInfo`` for the
            attribute on the parent, or ``field_type`` itself when no parent
            is found.
        """
        parent = self.parent_from_child(field_type, parent_attribute_name)
        if not parent:
            return field_type
        return parent.model_fields[parent_attribute_name]

    def rebuild_type_from_parent(
        self, field_type: type[BaseModel], parent_attribute_name: str
    ):
        """Compute the effective validation type for a child field.

        Accounts for ``SINGLE_FILE`` and ``OMMIT_ROOT`` output strategies
        that change how the YAML is structured on disk.

        Args:
            field_type (type[BaseModel]): The child model class.
            parent_attribute_name (str): The attribute name on the parent.

        Returns:
            type: The adjusted type to use for validation.
        """
        real_type = field_type
        attribute = self.field_info_from_child(
            field_type, parent_attribute_name
        )
        # in case of ommit root, we need to include a dictionary
        external = get_metadata(attribute.metadata, External)
        if (
            external is not None
            and OutputStrategy.SINGLE_FILE in external.output_structure
        ):
            if NoneType not in get_args(attribute.annotation):
                real_type = attribute.annotation
                # Re-attach any pydantic validators (BeforeValidator, etc.)
                # that live in the field metadata so they run on the raw file
                # data during validate_with_policy. The External annotation
                # itself is not a pydantic validator and must be excluded.
                validator_metadata = [
                    m
                    for m in attribute.metadata
                    if not isinstance(m, External)
                ]
                if validator_metadata:
                    real_type = Annotated[  # type: ignore[assignment]
                        real_type, *validator_metadata
                    ]
            if OutputStrategy.OMMIT_ROOT not in external.output_structure:
                real_type = dict[
                    str, real_type  # type: ignore[valid-type, assignment]
                ]
        return real_type

    def normalize_child_to_parent(
        self,
        field_type: type[BaseModel],
        parent_attribute_name: str,
        model_data,
    ):
        """Strip the wrapper dict added by ``rebuild_type_from_parent`` when
        needed.

        When a field was loaded as ``dict[str, T]`` due to ``SINGLE_FILE``
        without ``OMMIT_ROOT``, this method extracts the inner value so the
        parent receives the correctly typed object.

        Args:
            field_type (type[BaseModel]): The original child model class.
            parent_attribute_name (str): The attribute name on the parent.
            model_data: The raw validated data (may be a wrapping dict).

        Returns:
            The unwrapped value, or ``None`` if ``model_data`` is falsy.
        """
        if not model_data:
            return None
        attribute = self.field_info_from_child(
            field_type, parent_attribute_name
        )
        # in case of ommit root, we need to include a dictionary
        external = get_metadata(attribute.metadata, External)
        if (
            external is not None
            and OutputStrategy.SINGLE_FILE in external.output_structure
            and OutputStrategy.OMMIT_ROOT not in external.output_structure
        ):
            return model_data[parent_attribute_name]
        return model_data

    def path_from_object(
        self, model_object: BaseModel, parent_name: str
    ) -> str:
        """Return the dot-separated FLYNC path to an object given its parent
        field name.

        Args:
            model_object (BaseModel): The model instance to locate.
            parent_name (str): The field name on the parent that holds this
                object.

        Returns:
            str: The dot-separated path string.

        Raises:
            ValueError: If no matching path can be inferred.
        """
        object_info = self.fields_info[str(type(model_object))]
        for portential_path in object_info.flync_paths:
            if parent_name in portential_path:
                return portential_path
        raise ValueError("Could not infer path from object")

    @staticmethod
    def complex_path_to_string_path(complex_path: list[tuple]) -> str:
        """Convert an internal complex path representation to a dot-separated
        string.

        Each element of ``complex_path`` is a tuple of
        ``(model_class, field_name, container_chain)``. Container chains of
        ``"dict"`` produce ``{}`` segments and ``"list"`` produce ``[]``
        segments in the output.

        Args:
            complex_path (list[tuple]): The internal path representation.

        Returns:
            str: A dot-separated path string such as ``"items.[].name"``.
        """
        parts = []
        for parent in complex_path:
            parts.append(parent[1])
            container = parent[2]
            if not len(container):
                continue
            if container[0] == "dict":
                parts.append("{}")
            if container[0] == "list":
                parts.append("[]")
        return ".".join(parts)


_cache_cleaned = False
_cache_name = ""


def hash_directory_fast(directory: str, ext=".py") -> str:
    """Calculates an md5 hash from a directory.

    Args:
        directory (str): The location of the cache files.
        ext (str): which files to include (default python).
    """
    # only used for file name selection
    h = hashlib.md5()  # NOSONAR python:S4790
    for root, _, files in walk(directory):
        for fname in sorted(files):
            if fname.endswith(ext):
                fpath = join(root, fname)
                file_stat = stat(fpath)
                # Hash metadata only, not file contents
                h.update(
                    f"{fpath}{file_stat.st_mtime}{file_stat.st_size}".encode()
                )
    return h.hexdigest()


def get_package_root(package_name: str | None = None) -> str:
    """Gets the location of a package, will default to current package.

    Args:
        package_name (str): The location of the cache files.
            None or default means FLYNC package.
    """
    if not package_name:
        package_name = __package__.split(".")[0]
    package = importlib.import_module(package_name)
    package_path = package.__file__
    if not package_path or not isinstance(package_path, str):
        raise ValueError(
            "Unable to figure out the package location %s", package_name
        )
    package_path = abspath(package_path)
    return dirname(package_path)


def delete_unwanted_cache_files(cache_location: str, cache_file_name: str):
    """deletes the cache files of the library when different.

    Args:
        cache_location (str): The location of the cache files.
        cache_file_name (str): The name of the cache file to keep.
    """
    for f in listdir(cache_location):
        if cache_file_name not in f:
            remove(join(cache_location, f))


def cleanup_old_caches():
    """Resets the cache of the library if the current version is different."""
    global _cache_cleaned, _cache_name
    shelv_location = platformdirs.user_cache_dir("FLYNC")
    if not _cache_name:
        # only keep official version cache
        makedirs(shelv_location, exist_ok=True)
        shelv_file_name = "dependency_graph_cache"
        shelv_file_name += "_" + hash_directory_fast(get_package_root())
        if not _cache_cleaned:
            delete_unwanted_cache_files(shelv_location, shelv_file_name)
            _cache_cleaned = True
            _cache_name = shelv_file_name
    return shelv_location, _cache_name


def get_model_dependency_graph(root: type[BaseModel]) -> ModelDependencyGraph:
    """Return a cached :class:`ModelDependencyGraph` for the given root model.

    Building a graph is expensive, so instances are cached by root model class.
    Always prefer this factory over instantiating :class:`ModelDependencyGraph`
    directly.

    Args:
        root (type[BaseModel]): The root Pydantic model class.

    Returns:
        ModelDependencyGraph: The (possibly cached) dependency graph.
    """
    key = str(root)
    shelv_location, shelv_file_name = cleanup_old_caches()
    with shelve.open(join(shelv_location, shelv_file_name)) as cache:
        if key not in cache:
            cache[key] = ModelDependencyGraph(root)
        return cache[key]
