"""
Migration of a FLYNC 0.14 workspace to the 0.15 schema.

The registry allows one migration per release, so every breaking 0.15 change is a step of
:class:`Migration0_15`. Each step is idempotent on its own and resolves references with the lookup
rules 0.14 itself used, so a reference that loaded on 0.14 keeps pointing at the same frame.
See ``docs/source/model_change_history/v0_14_0_15.rst``.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Iterator

from flync.core.version_migrators._base import Documents, FLYNCMigration, migration

logger = logging.getLogger(__name__)

_STANDARD = "standard_11bit"
_EXTENDED = "extended_29bit"
_MAX_STANDARD_ID = 0x7FF

#: A mapping of a parsed YAML document.
Node = dict[str, Any]


def _walk(node: Any) -> Iterator[Node]:
    """Yield every mapping nested anywhere in ``node``, ``node`` itself included."""
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk(item)


def _dicts(value: Any) -> list[Node]:
    """The mapping items of ``value`` when it is a list, else nothing."""
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _is_can_id(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _can_interfaces(documents: Documents) -> Iterator[tuple[str, Node]]:
    """
    Yield ``(uri, interface)`` for every CAN interface in the workspace.

    An interface is normally its own document under a ``can_interfaces`` folder; one written inline
    in a ``can_interfaces`` list of its controller is found as well.
    """
    for uri, content in documents.items():
        folders = uri.replace("\\", "/").split("/")[:-1]
        if isinstance(content, dict) and "can_interfaces" in folders:
            yield uri, content
        for node in _walk(content):
            for interface in _dicts(node.get("can_interfaces")):
                yield uri, interface


def _can_frames_by_bus(documents: Documents) -> dict[str, list[Node]]:
    """Return ``{bus name: [CAN / CAN FD frame, ...]}`` for every bus declaring frames with a ``can_id``."""
    buses: dict[str, list[Node]] = {}
    for content in documents.values():
        for node in _walk(content):
            frames = [frame for frame in _dicts(node.get("frames")) if _is_can_id(frame.get("can_id"))]
            if frames and isinstance(node.get("name"), str):
                buses.setdefault(node["name"], []).extend(frames)
    return buses


def _id_format_of(frames: list[Node], can_id: int) -> str | None:
    """``id_format`` of the frame with ``can_id``; the last one wins on a duplicate id, as in 0.14."""
    found = None
    for frame in frames:
        if frame.get("can_id") == can_id and frame.get("id_format") in (_STANDARD, _EXTENDED):
            found = frame["id_format"]
    return found


def _resolve_id_format(frames_by_bus: dict[str, list[Node]], bus: Any, can_id: int, where: str) -> str:
    """
    ``id_format`` of the frame ``can_id`` on ``bus``.

    A reference to a frame the bus does not declare was already dangling on 0.14 and still is. Its
    format is inferred from the id's range so the load reports only the dangling reference.
    """
    found = _id_format_of(frames_by_bus.get(bus, []), can_id) if isinstance(bus, str) else None
    if found is None:
        found = _STANDARD if 0 <= can_id <= _MAX_STANDARD_ID else _EXTENDED
        logger.warning("%s: no frame with CAN id %#x on bus %r; inferred id_format %r from the id's range.", where, can_id, bus, found)
    return found


def _migrate_can_frame_refs(documents: Documents) -> None:
    """
    ``CANFrameRef`` drops ``bus_ref`` and gains the required ``id_format``.

    The bus is now the ``bus_ref`` of the owning interface. ``id_format`` is taken from the referenced
    frame, which 0.14 looked up on the reference's own ``bus_ref``.
    """
    frames_by_bus = _can_frames_by_bus(documents)
    for uri, interface in _can_interfaces(documents):
        for field in ("sender_frames", "receiver_frames"):
            for ref in _dicts(interface.get(field)):
                bus = ref.pop("bus_ref", interface.get("bus_ref"))
                if "id_format" not in ref and _is_can_id(ref.get("frame_ref")):
                    ref["id_format"] = _resolve_id_format(frames_by_bus, bus, ref["frame_ref"], f"{uri}: {field}")


_STEPS: tuple[Callable[[Documents], None], ...] = (_migrate_can_frame_refs,)


@migration
class Migration0_15(FLYNCMigration):
    """Brings a 0.14 workspace to the 0.15 schema, one step per breaking change."""

    unique_id = "v0_14_to_0_15"
    target_version = "0.15.0"
    description = "CAN frame references drop bus_ref and gain id_format."

    def apply(self, documents: Documents) -> None:
        for step in _STEPS:
            step(documents)
