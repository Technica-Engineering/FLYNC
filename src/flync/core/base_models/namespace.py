"""Helpers that apply and undo a :class:`~flync.core.annotations.Namespaced` qualified name."""

from typing import Any, Mapping, Sequence

from flync.core.annotations.namespaced import Namespaced


def qualify_name(data: Mapping[str, Any], namespace: Sequence[str], namespaced: Namespaced) -> dict[str, Any]:
    """
    Return a copy of ``data`` whose name is prefixed with the namespace segments.

    The input is never mutated, since it is usually a cached document tree. ``data`` is returned as a
    plain copy when ``namespace`` is empty or the name is missing or not a string; validation reports a
    bad name afterwards exactly as it does for an item that is not namespaced.

    Args:
        data: The raw content of one item.
        namespace: The folder names between the list root and the item, outermost first.
        namespaced: The annotation that defines the separator and the name key.

    Returns:
        dict[str, Any]: The content with the qualified name.
    """

    result = dict(data)
    name = result.get(namespaced.name_key)
    if namespace and isinstance(name, str):
        result[namespaced.name_key] = namespaced.separator.join([*namespace, name])
    return result


def split_qualified_name(qualified_name: str, namespaced: Namespaced) -> tuple[tuple[str, ...], str]:
    """
    Split a qualified name into its namespace segments and its own name.

    Args:
        qualified_name: A name such as ``abc::def::item``.
        namespaced: The annotation that defines the separator.

    Returns:
        tuple[tuple[str, ...], str]: The namespace segments (outermost first) and the name; the
        segments are empty for a name without a separator.
    """

    *segments, name = qualified_name.split(namespaced.separator)
    return tuple(segments), name
