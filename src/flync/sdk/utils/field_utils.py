from typing import Iterable, Optional, TypeVar

T = TypeVar("T")


def get_metadata(meta: Iterable[object], cls: type[T]) -> Optional[T]:
    """"""
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
