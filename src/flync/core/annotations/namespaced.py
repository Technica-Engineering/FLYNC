"""Annotation that derives the qualified name of list items from the folders they are stored in."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Namespaced(object):
    """
    Indicates that the items of an external folder list are namespaced by their sub-folders.

    Use it next to :class:`~flync.core.annotations.External` on a ``List[...]`` field stored as a folder.
    Items may then sit directly in the folder or in nested sub-folders; every sub-folder is a namespace
    segment. When loading, the item's name is prefixed with these segments, so ``abc/def/item.flync.yaml``
    holding ``name: item`` is loaded as ``abc::def::item``. Items outside any sub-folder keep their name.

    References to a namespaced item must use its qualified name. The annotation has no effect on a field
    stored as a single file.

    Args:
        separator: String joining the namespace segments and the name.
        name_key: Key of the item's name in its document.
    """

    separator: str = "::"
    name_key: str = "name"
