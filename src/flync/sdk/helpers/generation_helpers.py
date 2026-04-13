import gc
import inspect
import pathlib
import random
from ipaddress import IPv4Address, IPv6Address
from os import curdir, sep
from pathlib import Path
from types import UnionType
from typing import Any, Literal, Optional, Union, cast, get_args, get_origin

from polyfactory.factories.pydantic_factory import ModelFactory
from pydantic import BaseModel, IPvAnyAddress
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined
from pydantic_extra_types.mac_address import MacAddress

from flync.core.base_models.unique_name import UniqueName
from flync.core.datatypes.ipaddress import IPv4AddressEntry
from flync.model.flync_4_ecu.phy import BASET1
from flync.model.flync_4_ecu.port import ECUPort
from flync.model.flync_4_ecu.sockets import IPv4AddressEndpoint
from flync.model.flync_4_topology.system_topology import ExternalConnection
from flync.model.flync_model import FLYNCBaseModel, FLYNCModel
from flync.sdk.context.workspace_config import WorkspaceConfiguration
from flync.sdk.workspace.flync_workspace import FLYNCWorkspace
from flync.sdk.workspace.ids import ObjectId
from flync.sdk.workspace.objects import SemanticObject

from .nodes_helpers import available_flync_nodes, type_from_input


def __get_valid_path(paths: list[str]) -> list[str]:
    """
    Validate and extract a meaningful path from a list of string segments.

    Args:
        paths (list[str]): A list of path-like strings.

    Returns:
        list[str]: A list of non-numeric chunks representing a valid path,
                   or an empty list if no valid path is found.
    """
    if len(paths) == 1 and paths[0] in ["", "."]:
        return []
    for p in paths:
        if not p:
            continue
        chuncks = p.split(".")
        if all(not chunk.isdigit() for chunk in chuncks):
            return chuncks
    return []


def is_union(tp) -> bool:
    """
    Determine whether a given type annotation represents a Union type.
    """
    return (
        tp is Union
        or tp is UnionType
        or get_origin(tp) is Union
        or isinstance(tp, UnionType)
    )


class Factory(object):
    """
    Factory class for managing and generating model-specific factory instances.
    """

    __MODEL_FACTORY_REGISTRY: Optional[dict[type, type[ModelFactory]]] = None
    __FACTORY_MODELS: Optional[list[type[FLYNCBaseModel]]] = None
    __UNIQUE_NAMES: set[str] = set()

    @staticmethod
    def add_names(key):
        Factory.__UNIQUE_NAMES.add(key)

    @staticmethod
    def build_name(model: type[BaseModel], idx: int = 1):
        if not issubclass(model, UniqueName):
            return model.__name__.lower()

        name = f"{model.__name__.lower()}_{idx}"
        key = f"{model.__name__}.{name}"
        if key in Factory.__UNIQUE_NAMES:
            return Factory.build_name(model, idx + 1)
        Factory.add_names(key)
        return name

    @classmethod
    def factory_model_defined(cls, model: type[FLYNCBaseModel]) -> bool:
        return (
            cls.__FACTORY_MODELS is not None and model in cls.__FACTORY_MODELS
        )

    @classmethod
    def get_factory(cls, model: type) -> type[ModelFactory]:
        if cls.__MODEL_FACTORY_REGISTRY is None:
            cls.__MODEL_FACTORY_REGISTRY = cls.__build_factory_registry()
            cls.__FACTORY_MODELS = [
                r.__model__ for r in cls.__MODEL_FACTORY_REGISTRY.values()
            ]
        if model not in cls.__MODEL_FACTORY_REGISTRY:
            cls.__MODEL_FACTORY_REGISTRY.update(cls.__build_factory_registry())

        if model not in cls.__MODEL_FACTORY_REGISTRY:
            cls.__MODEL_FACTORY_REGISTRY[model] = cast(
                type[ModelFactory[Any]],
                ModelFactory.create_factory(
                    model=model,
                    bases=(FLYNCFactory,),
                ),
            )

        return cls.__MODEL_FACTORY_REGISTRY[model]

    @classmethod
    def __build_factory_registry(cls) -> dict[type, type[ModelFactory]]:
        registry = {}

        def __get_all_subclasses(cls):
            """
            Recursively yield all subclasses of a given class.
            """
            for subclass in cls.__subclasses__():
                yield subclass
                yield from __get_all_subclasses(subclass)

        for factory_cls in __get_all_subclasses(ModelFactory):
            model = getattr(factory_cls, "__model__", None)
            if (
                model is not None
                and isinstance(model, type)
                and issubclass(model, FLYNCBaseModel)
            ):
                registry[model] = factory_cls

        return registry


class FLYNCFactory(ModelFactory[FLYNCBaseModel]):
    """
    Specialized factory class for creating instances
    of FLYNCBaseModel subclasses.
    """

    __use_defaults__ = True
    __use_examples__ = True

    @staticmethod
    def random_multicast_ipv4():
        return IPv4Address(
            random.randint(
                int(IPv4Address("224.0.0.0")),
                int(IPv4Address("239.255.255.255")),
            )
        )

    @classmethod
    def get_provider_map(cls):
        original_providers = super().get_provider_map()
        original_providers[MacAddress] = lambda: "11:22:33:44:55:66"
        original_providers[IPv6Address] = lambda: IPv6Address("fe80::1")
        original_providers[IPv4Address] = (
            lambda: FLYNCFactory.random_multicast_ipv4()
        )
        original_providers[IPvAnyAddress] = (
            lambda: FLYNCFactory.random_multicast_ipv4()
        )
        return original_providers

    @staticmethod
    def __default_arg_type(arg):
        """
        Resolve the most appropriate argument type from a typing annotation.

        Args:
            arg (Any): A type annotation, possibly a Union or generic type.

        Returns:
            Any: The resolved type, either a factory-defined model,
        """

        if args := get_args(arg):
            for a in args:
                if Factory.factory_model_defined(a):
                    return a
            if arg1 := [
                t
                for t in [IPv4AddressEndpoint, IPv4AddressEntry, IPv4Address]
                if t in args
            ]:
                arg = arg1[0]
            else:
                arg = FLYNCFactory.__default_arg_type(
                    next(a for a in args if a is not type(None))
                )
        return arg

    @staticmethod
    def __get_field_default_value(field_info: FieldInfo) -> tuple[bool, Any]:
        """
        Determine the default value for a Pydantic field.

        Args:
            field_info (FieldInfo): The Pydantic field metadata object.

        Returns:
            tuple[bool, Any]:
                - `bool`: Whether a valid default value was found.
                - `Any`: The resolved default value, or `None` if unavailable.
        """

        valid, result = (False, None)
        if field_info.default is not PydanticUndefined:
            valid, result = True, field_info.default
        args = get_args(field_info.annotation)
        if field_info.default_factory is not None and type(None) in args:
            valid, result = (
                True,
                field_info.default_factory(),  # type: ignore[call-arg]
            )
        elif field_info.examples:
            valid, result = True, field_info.examples[0]
        return valid, result

    @staticmethod
    def __get_field_value_list(
        field_info, arg_type, origin_type, **kwargs
    ) -> tuple[bool, Any]:
        """
        Generate a default list of values for a Pydantic field when
        the type annotation indicates a list of FLYNCBaseModel subclasses.

        Args:
            field_info (FieldInfo): Metadata about the Pydantic field.
            arg_type (type): The type annotation for the list elements.
            origin_type (type): The origin type (e.g., `list`).
            **kwargs: Additional keyword arguments passed to the factory.

        Returns:
            tuple[bool, Any]:
                - `bool`: Whether a valid list of values was generated.
                - `Any`: The generated list of model instances.
        """
        if (
            arg_type
            and inspect.isclass(arg_type)
            and issubclass(arg_type, FLYNCBaseModel)
            and origin_type is list
        ):
            min_length: int = (
                2
                if arg_type == ECUPort
                else FLYNCFactory.__min_length_list(field_info)
            )
            return True, Factory.get_factory(arg_type).batch(
                size=min_length,
                **kwargs,
            )
        return False, None

    @staticmethod
    def __min_length_list(field_info: FieldInfo) -> int:
        """
        Determine the minimum list length for a Pydantic field.

        Args:
            field_info (FieldInfo): The Pydantic field metadata object.

        Returns:
            int: The minimum list length, either from metadata
            or the default of `1`.
        """
        min_length = 1
        if field_info.metadata is None:
            return min_length
        for m in field_info.metadata:
            if length := getattr(m, "min_length", None):
                return length
        return min_length

    @staticmethod
    def __get_field_value(
        model: type[BaseModel],
        field_name: str,
        field_info: FieldInfo,
        **kwargs,
    ) -> tuple[bool, Any]:
        field_name = field_info.alias or field_name
        valid, value = FLYNCFactory.__get_field_default_value(field_info)
        if valid:
            return valid, value

        valid, value = False, None
        origin_type = (
            get_origin(field_info.annotation) or field_info.annotation
        )
        if (
            origin_type is list
            or is_union(origin_type)
            or origin_type is Literal
        ):
            arg_type = FLYNCFactory.__default_arg_type(field_info.annotation)
            valid, value = FLYNCFactory.__get_field_value_list(
                field_info, arg_type, origin_type, **kwargs
            )
            if valid:
                return valid, value
            elif origin_type is Literal:
                valid, value = True, arg_type
            elif (
                arg_type
                and issubclass(arg_type, FLYNCBaseModel)
                and is_union(origin_type)
            ):
                valid, value = True, Factory.get_factory(arg_type).build(
                    **kwargs,
                )
            else:
                valid, value = True, []
        elif origin_type and issubclass(origin_type, FLYNCBaseModel):
            valid, value = True, Factory.get_factory(origin_type).build(
                **kwargs,
            )
        elif field_name == "name":
            name = Factory.build_name(model=model)
            valid, value = True, name

        return valid, value

    @classmethod
    def build(cls, **kwargs):
        newkwargs = {}
        res = False
        for fname, finfo in cls.__model__.model_fields.items():
            fname = finfo.alias or fname
            if finfo.exclude:
                continue
            if fname not in kwargs:
                res, value = FLYNCFactory.__get_field_value(
                    cls.__model__, fname, finfo, **kwargs
                )
                if res:
                    newkwargs[fname] = value
            else:
                newkwargs[fname] = kwargs[fname]
        obj = super().build(**newkwargs)
        if isinstance(obj, UniqueName):
            Factory.add_names(obj.get_key())
        return obj


class ExternalConnectionFactory(FLYNCFactory):
    """
    Factory for ExternalConnection model.
    """

    __model__ = ExternalConnection

    @classmethod
    def build(cls, **kwargs):
        insts = list(ECUPort.INSTANCES.keys())
        kwargs["ecu1_port"] = insts[0]
        kwargs["ecu2_port"] = insts[1]
        return super().build(**kwargs)


class BASET1Factory(FLYNCFactory):
    """
    Factory for BASET1 model.
    """

    __model__ = BASET1

    @classmethod
    def build(cls, **kwargs):
        insts = list(ECUPort.INSTANCES.values())
        if len(insts) > 0:
            kwargs["role"] = (
                "slave" if insts[0].mdi_config.role == "master" else "master"
            )
        return super().build(**kwargs)


def dump_flync_workspace(
    flync_model: FLYNCModel,
    output_path: str | pathlib.Path,
    workspace_name: str | None,
    workspace_config: WorkspaceConfiguration | None = None,
) -> None:
    """Generate a FLYNC workspace from a FLYNCModel object.

    Args:
        flync_model (:class:`~flync.model.flync_model.FLYNCModel`): The
            FLYNC model to generate the workspace from.
        output_path (str | pathlib.Path): The path where the workspace
            will be created.
        workspace_name (str | None): Optional name for the workspace.
        workspace_config (WorkspaceConfiguration | None): Optional
            workspace configuration. Uses defaults if ``None``.

    Returns:
        None
    """

    ws = FLYNCWorkspace.load_model(
        flync_model,
        workspace_name,
        output_path,
        workspace_config=workspace_config,
    )
    ws.generate_configs()


def generate_external_node(
    node: str | type[FLYNCBaseModel],
    node_path: Path | str,
    workspace_config: WorkspaceConfiguration | None = None,
    **override_values,
):
    """
    Generate external node.
    """
    node = type_from_input(node)
    # generate object from type
    model_factory = Factory.get_factory(node)
    flync_obj = model_factory.build(
        **override_values,
    )
    # dump to output
    if not isinstance(node_path, Path):
        node_path = Path(node_path)
    FLYNCWorkspace.load_model(
        flync_obj, file_path=node_path, workspace_config=workspace_config
    ).generate_configs()


def _get_flync_path(model: BaseModel | list | set, field_name: str) -> str:
    """Determine the flync path based on model type."""
    if isinstance(model, (list, set)):
        return f"{field_name}.[]"
    if (
        isinstance(model, FLYNCBaseModel)
        and field_name in type(model).model_fields
    ):
        return f"{field_name}"
    return ""


def __resolve_semantic_object(
    so: SemanticObject,
    field_name: str,
) -> tuple[str, FLYNCBaseModel | None, type[FLYNCBaseModel] | None]:
    """
    Resolve semantic object information for a given field.

    Args:
        so (SemanticObject): The semantic object containing the model.
        field_name (str): The name of the field to resolve.

    Returns:
        tuple[str, FLYNCBaseModel | None, type[FLYNCBaseModel] | None]:
            - `str`: The resolved FLYNC path for the field.
            - `FLYNCBaseModel | None`: The parent object if applicable.
            - `type[FLYNCBaseModel] | None`: The root model type if applicable.
    """

    model = so.model
    flync_path = _get_flync_path(model, field_name)
    parent = model if isinstance(model, (FLYNCBaseModel, list, set)) else None
    root = type(model) if isinstance(model, FLYNCBaseModel) else None
    return flync_path, parent, root


def __resolve_path(
    valid_path: list[str], ws: FLYNCWorkspace
) -> tuple[type[FLYNCBaseModel], FLYNCBaseModel | None, str]:
    """
    Walk valid_path segments and resolve the FLYNC
    root type, parent model, and flync_path.
    """
    root: type[FLYNCBaseModel] = FLYNCModel
    parent: FLYNCBaseModel | None = None
    flync_path = ""
    parent_path: list[str] = []
    for field_name in valid_path:
        parent_path.append(field_name)
        path = ObjectId(curdir.join(parent_path))
        if not ws.has_object(path):
            continue

        so = ws.get_object(path)
        if not isinstance(so, SemanticObject):
            continue

        flync_path, parent, resolved_root = __resolve_semantic_object(
            so, field_name
        )
        if resolved_root is not None:
            root = resolved_root

    return root, parent, flync_path


def generate_node(
    ws: FLYNCWorkspace,
    node_paths: list[str] = [],
    **override_values,
):
    """
    Generate node.
    """
    valid_path = __get_valid_path(node_paths)
    root, parent, flync_path = __resolve_path(valid_path, ws)
    nodes = available_flync_nodes(root_node=root)
    generated_node: FLYNCBaseModel | None = None
    for node_info in nodes.values():
        if (
            flync_path in node_info.flync_paths
            or valid_path == node_info.flync_paths
        ):
            instances = [
                obj for obj in gc.get_objects() if isinstance(obj, UniqueName)
            ]
            for inst in instances:
                Factory.add_names(inst.get_key())

            model_factory = Factory.get_factory(node_info.python_type)
            generated_node = model_factory.build(
                **override_values,
            )
            break

    if isinstance(generated_node, FLYNCModel):
        ws.flync_model = generated_node
    elif parent is not None and isinstance(parent, (list, set)):
        parent.append(generated_node)

    if generated_node is not None and ws.workspace_root is not None:
        rel_path = Path(sep.join(valid_path))
        ws.load_flync_model(
            flync_model=generated_node,
            file_path=(ws.workspace_root / rel_path),
        )
