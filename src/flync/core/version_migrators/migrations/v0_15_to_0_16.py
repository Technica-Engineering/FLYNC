"""
Migration of a FLYNC 0.15 workspace to the 0.16 schema.

The registry allows one migration per release, so every breaking 0.16 change is a step of
:class:`Migration016`. Each step is idempotent on its own and resolves references with the lookup
rules 0.15 itself used, so a reference that loaded on 0.15 keeps pointing at the same frame.
See ``docs/source/model_change_history/v0_15_0_16.rst``.
"""

from __future__ import annotations

import logging
from typing import Any, Iterator

from flync.core.version_migrators._base import Documents, FLYNCMigration, migration
from flync.core.version_migrators.migrations.v0_14_to_0_15 import Node, _can_interfaces, _dicts, _is_can_id, _walk

logger = logging.getLogger(__name__)

_PDU2_MIN_FORMAT = 240


def _pgn(frame: Node) -> int | None:
    """PGN of a J1939 frame document, as ``J1939Frame.pgn`` computes it; ``None`` when a field is missing."""
    edp, dp, pf, ps = (frame.get(key) for key in ("extended_data_page", "data_page", "pdu_format", "pdu_specific"))
    if not (_is_can_id(edp) and _is_can_id(dp) and _is_can_id(pf) and _is_can_id(ps)):
        return None
    return (edp << 17) | (dp << 16) | (pf << 8) | (ps if pf >= _PDU2_MIN_FORMAT else 0)


def _j1939_frames(documents: Documents) -> Iterator[tuple[str, int, str]]:
    """Yield ``(bus name, pgn, frame name)`` for every named J1939 frame of a bus document."""
    for content in documents.values():
        for bus in (node for node in _walk(content) if isinstance(node.get("name"), str)):
            for frame in _dicts(bus.get("frames")):
                pgn = _pgn(frame) if frame.get("type") == "j1939" else None
                if pgn is not None and isinstance(frame.get("name"), str):
                    yield bus["name"], pgn, frame["name"]


def _j1939_frame_names_by_bus(documents: Documents) -> dict[str, dict[int, str | None]]:
    """
    Return ``{bus name: {pgn: frame name}}``.

    0.15 rejected two J1939 frames with one PGN on a bus (error 346), so a PGN names one frame. A PGN
    that several frames share maps to ``None``: the reference it is in cannot be resolved.
    """
    buses: dict[str, dict[int, str | None]] = {}
    for bus, pgn, name in _j1939_frames(documents):
        names = buses.setdefault(bus, {})
        names[pgn] = name if pgn not in names else None
    return buses


def _migrate_j1939_frame_refs_to_names(documents: Documents) -> None:
    """
    ``J1939FrameRef`` addresses its frame by ``frame_ref`` (name) or ``can_id`` instead of ``pgn``.

    0.15 resolved a ``pgn`` on the ``bus_ref`` of the owning interface, where a PGN was unique, so the
    reference becomes the name of that frame. A ``pgn`` that names no frame, or several, did not load
    on 0.15 either; it is left in place so the load reports the reference.
    """
    frames_by_bus = _j1939_frame_names_by_bus(documents)
    for uri, interface in _can_interfaces(documents):
        bus: Any = interface.get("bus_ref")
        names = frames_by_bus.get(bus, {}) if isinstance(bus, str) else {}
        for field in ("j1939_sender_frames", "j1939_receiver_frames"):
            for ref in _dicts(interface.get(field)):
                problem = _pgn_ref_to_name(ref, names)
                if problem is not None:
                    logger.warning("%s: %s: %s on bus %r; the reference is left unchanged.", uri, field, problem, bus)


def _pgn_ref_to_name(ref: Node, names: dict[int, str | None]) -> str | None:
    """Replace the ``pgn`` of *ref* with the ``frame_ref`` it names in *names*; return why it cannot, if so."""
    pgn = ref.get("pgn")
    if not _is_can_id(pgn):
        return None
    name = names.get(pgn)
    if name is None:
        return f"{'several J1939 frames share' if pgn in names else 'no J1939 frame has'} PGN {pgn:#x}"
    del ref["pgn"]
    ref.setdefault("frame_ref", name)
    return None


def _lin_interfaces(documents: Documents) -> Iterator[Node]:
    """
    Yield every LIN interface in the workspace.

    An interface is normally its own document under a ``lin_interfaces`` folder; one written inline
    in a ``lin_interfaces`` list of its controller is found as well.
    """
    for uri, content in documents.items():
        folders = uri.replace("\\", "/").split("/")[:-1]
        if isinstance(content, dict) and "lin_interfaces" in folders:
            yield content
        for node in _walk(content):
            yield from _dicts(node.get("lin_interfaces"))


def _drop_lin_frame_ref_bus(documents: Documents) -> None:
    """``LINFrameRef`` drops ``bus_ref``; the bus is the ``bus_ref`` of the owning interface."""
    for interface in _lin_interfaces(documents):
        for field in ("sender_frames", "receiver_frames"):
            for ref in _dicts(interface.get(field)):
                ref.pop("bus_ref", None)


@migration
class Migration016(FLYNCMigration):
    """Brings a 0.15 workspace to the 0.16 schema, one step per breaking change."""

    unique_id = "v0_15_to_0_16"
    target_version = "0.16.0"
    description = "J1939 frame references address their frame by name instead of PGN; LIN frame references drop bus_ref."

    def apply(self, documents: Documents) -> None:
        _migrate_j1939_frame_refs_to_names(documents)
        _drop_lin_frame_ref_bus(documents)
