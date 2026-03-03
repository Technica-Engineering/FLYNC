from functools import lru_cache
from typing import Iterable, Optional, TypeVar, get_args, get_origin

from pydantic import BaseModel

from flync.core.annotations import External

T = TypeVar("T")


def get_metadata(meta: Iterable[object], cls: type[T]) -> Optional[T]:
    """
    Return the first metadata object of the specified type.

    Args:
        meta: An iterable of metadata objects.
        cls: The class type to search for.

    Returns:
        An instance of `cls` if found; otherwise, None.
    """
    for m in meta:
        if isinstance(m, cls):
            return m
    return None


def get_name(
    named_object: T, attr_name: str, fallback_name: str | None = None
) -> str:
    """Retrieve a display name for an object."""
    attr_name = attr_name or "name"
    return (
        getattr(named_object, attr_name, fallback_name)
        or type(named_object).__name__
    )


@lru_cache(maxsize=None)
def build_model_dependencies(model: type[BaseModel]) -> dict:
    deps = {}

    for name, field in model.model_fields.items():
        annotation = field.annotation
        external = get_metadata(field.metadata, External)

        origin = get_origin(annotation)
        args = get_args(annotation)

        if origin is list:
            inner = args[0]
            if isinstance(inner, type) and issubclass(inner, BaseModel):
                deps[name] = {
                    "external": external,
                    "type": f"list[{inner.__name__}]",
                    "children": build_model_dependencies(inner),
                }
        if origin is dict:
            inner = args[1]
            if isinstance(inner, type) and issubclass(inner, BaseModel):
                deps[name] = {
                    "external": external,
                    "type": f"dict[{inner.__name__}]",
                    "children": build_model_dependencies(inner),
                }
        elif isinstance(annotation, type) and issubclass(
            annotation, BaseModel
        ):
            deps[name] = {
                "external": external,
                "type": annotation.__name__,
                "children": build_model_dependencies(annotation),
            }

    return deps
