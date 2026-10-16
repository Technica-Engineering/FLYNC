"""Merge several decoded FLYNC models into one.

Merging happens on dumped mappings, not on model instances: the merged mapping
is validated once, so every cross-cutting :class:`~flync.model.FLYNCModel`
validator (unique names, references, multicast paths) sees the union of the
sources.

The rules, applied at every nesting depth:

* a key present in one source only is taken as it is;
* two mappings are merged key by key;
* two lists of mappings are merged item by item when their items can be told
  apart: every item of both lists has a ``name``, unique within its list, or
  failing that an ``id``, unique within its list;
* anything else that differs (scalars, other lists, values of different
  kinds) is a conflict, resolved by the :class:`OnConflict` policy.

A list whose items cannot be told apart is never combined: the merger cannot
tell a set from a sequence, so it keeps one source's list whole.
"""

from __future__ import annotations

import enum
import logging
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from flync.model import FLYNCModel

from .converters.helpers import pydantic_dump

logger = logging.getLogger(__name__)

#: Keys that can identify an item of a list of mappings, most preferred first.
IDENTITY_KEYS = ("name", "id")

#: Source reported for a value whose origin is not known.
UNKNOWN_SOURCE = "unknown"


class OnConflict(str, enum.Enum):
    """What to do when two sources disagree on the same value."""

    FIRST = "first"
    LAST = "last"
    ERROR = "error"


@dataclass(frozen=True)
class PartialModel:
    """A decoded model together with the source it was decoded from."""

    source: Path | str
    model: FLYNCModel


@dataclass(frozen=True)
class MergeConflict:
    """One value two sources disagreed on, and which one the merge kept."""

    path: str
    kept: Any
    dropped: Any
    kept_source: Path | str
    dropped_source: Path | str

    def as_mapping(self) -> dict[str, Any]:
        """Return the conflict as plain data, for a report."""
        return {
            "path": self.path,
            "kept": self.kept,
            "dropped": self.dropped,
            "kept_source": str(self.kept_source),
            "dropped_source": str(self.dropped_source),
        }


@dataclass(frozen=True)
class MergeResult:
    """The merged model and the conflicts resolved on the way."""

    model: FLYNCModel
    conflicts: tuple[MergeConflict, ...] = ()


class ModelMergeConflictError(ValueError):
    """Raised under :attr:`OnConflict.ERROR` when two sources disagree."""

    def __init__(
        self, *, path: str, existing_value: object, incoming_value: object, existing_source: Path | str, incoming_source: Path | str
    ) -> None:
        self.path = path
        self.existing_value = existing_value
        self.incoming_value = incoming_value
        self.existing_source = existing_source
        self.incoming_source = incoming_source
        super().__init__(
            f"Cannot merge FLYNC models: conflict at '{path}'. "
            f"Source '{existing_source}' provides {existing_value!r}; "
            f"source '{incoming_source}' provides {incoming_value!r}."
        )


def _format_path(path: tuple[str, ...]) -> str:
    """Render a path as ``ecus[NODE3].controllers[CONTROLLER].name``."""
    text = ""
    for part in path:
        if part.startswith("["):
            text += part
        else:
            text += f".{part}" if text else part
    return text or "<root>"


def _index(items: list[Any], key: str) -> dict[Any, int] | None:
    """Return ``identity -> position`` for a list of mappings uniquely identified by ``key``, else ``None``."""
    index: dict[Any, int] = {}
    for position, item in enumerate(items):
        if not isinstance(item, Mapping) or not isinstance(item.get(key), (str, int)):
            return None
        index[item[key]] = position
    return index if len(index) == len(items) else None


def _shared_identity(current: list[Any], incoming: list[Any]) -> tuple[str, dict[Any, int]] | None:
    """Return the first identity key both lists are identified by, with the index of ``current``, else ``None``."""
    for key in IDENTITY_KEYS:
        index = _index(current, key)
        if index is not None and _index(incoming, key) is not None:
            return key, index
    return None


class _Merge:
    """State of one merge run: the policy, the conflicts and where each value came from."""

    def __init__(self, on_conflict: OnConflict) -> None:
        self.on_conflict = on_conflict
        self.conflicts: list[MergeConflict] = []
        # Source of each subtree, recorded where the subtree was inserted. The source of a
        # nested value is the one recorded for its nearest ancestor.
        self._origins: dict[tuple[str, ...], Path | str] = {}

    def _origin(self, path: tuple[str, ...]) -> Path | str:
        for length in range(len(path), -1, -1):
            source = self._origins.get(path[:length])
            if source is not None:
                return source
        return UNKNOWN_SOURCE

    def mapping(self, current: dict[str, Any], incoming: Mapping[str, Any], path: tuple[str, ...], source: Path | str) -> None:
        """Merge ``incoming`` into ``current`` in place."""
        for key, value in incoming.items():
            child = (*path, str(key))
            if key not in current:
                current[key] = value
                self._origins[child] = source
            else:
                current[key] = self._value(current[key], value, child, source)

    def _value(self, current: Any, incoming: Any, path: tuple[str, ...], source: Path | str) -> Any:
        """Return the merge of two values found at the same path."""
        if current == incoming:
            merged = current
        elif isinstance(current, dict) and isinstance(incoming, Mapping):
            self.mapping(current, incoming, path, source)
            merged = current
        elif isinstance(current, list) and isinstance(incoming, list):
            merged = self._list(current, incoming, path, source)
        else:
            merged = self._resolve(current, incoming, path, source)
        return merged

    def _list(self, current: list[Any], incoming: list[Any], path: tuple[str, ...], source: Path | str) -> list[Any]:
        """Merge two different lists: by identity when both are identified by one key, else as one conflicting value."""
        if not current or not incoming:
            if not current:
                self._origins[path] = source
            return current or incoming
        identity = _shared_identity(current, incoming)
        if identity is None:
            return self._resolve(current, incoming, path, source)
        return self._identified_list(current, incoming, *identity, path, source)

    def _identified_list(
        self, current: list[Any], incoming: list[Any], key: str, index: dict[Any, int], path: tuple[str, ...], source: Path | str
    ) -> list[Any]:
        """Merge two lists of mappings whose items are identified by ``key``."""
        for item in incoming:
            identity = item[key]
            child = (*path, f"[{identity}]")
            position = index.get(identity)
            if position is None:
                index[identity] = len(current)
                current.append(item)
                self._origins[child] = source
            else:
                current[position] = self._value(current[position], item, child, source)
        return current

    def _resolve(self, current: Any, incoming: Any, path: tuple[str, ...], source: Path | str) -> Any:
        """Apply the conflict policy to one disagreement and record it."""
        where = _format_path(path)
        existing_source = self._origin(path)
        if self.on_conflict is OnConflict.ERROR:
            raise ModelMergeConflictError(
                path=where, existing_value=current, incoming_value=incoming, existing_source=existing_source, incoming_source=source
            )
        if self.on_conflict is OnConflict.LAST:
            self.conflicts.append(MergeConflict(where, kept=incoming, dropped=current, kept_source=source, dropped_source=existing_source))
            logger.warning("Merge conflict at %s: %r from %s overrides %r from %s", where, incoming, source, current, existing_source)
            self._origins[path] = source
            return incoming
        self.conflicts.append(MergeConflict(where, kept=current, dropped=incoming, kept_source=existing_source, dropped_source=source))
        logger.warning("Merge conflict at %s: keeping %r from %s, dropping %r from %s", where, current, existing_source, incoming, source)
        return current


class FLYNCModelMerger:
    """Merge decoded models, or their dumped mappings, into one."""

    def __init__(self, on_conflict: OnConflict = OnConflict.FIRST) -> None:
        """Create a merger.

        Args:
            on_conflict: Policy for values two sources disagree on.
        """
        self.on_conflict = OnConflict(on_conflict)

    def merge(self, partial_models: Sequence[PartialModel]) -> MergeResult:
        """Merge decoded models into a single validated model.

        A single model is returned as it is, without a dump and validation
        round trip.

        Args:
            partial_models: The models, in the order their sources were given.

        Returns:
            The merged model, validated as one system, and the conflicts.

        Raises:
            ValueError: If ``partial_models`` is empty.
            ModelMergeConflictError: Under :attr:`OnConflict.ERROR`, on the first disagreement.
        """
        if not partial_models:
            raise ValueError("At least one partial model is required")
        if len(partial_models) == 1:
            return MergeResult(partial_models[0].model)

        merged, conflicts = self._merge([(partial.source, pydantic_dump(partial.model)) for partial in partial_models])
        logger.info("Merged %d models with %d conflict(s)", len(partial_models), len(conflicts))
        return MergeResult(FLYNCModel.model_validate(merged), tuple(conflicts))

    def merge_mappings(self, mappings: Sequence[tuple[Path | str, Mapping[str, Any]]]) -> tuple[dict[str, Any], list[MergeConflict]]:
        """Merge dumped mappings without validating the result.

        This is the merge applied to content that is not a valid model on its
        own, such as a partial FLYNC document.

        Args:
            mappings: ``(source, mapping)`` pairs, in merge order. They are not modified.

        Returns:
            The merged mapping and the conflicts.

        Raises:
            ModelMergeConflictError: Under :attr:`OnConflict.ERROR`, on the first disagreement.
        """
        return self._merge([(source, deepcopy(dict(mapping))) for source, mapping in mappings])

    def _merge(self, owned: Sequence[tuple[Path | str, dict[str, Any]]]) -> tuple[dict[str, Any], list[MergeConflict]]:
        """Merge mappings this call owns; they are consumed."""
        run = _Merge(self.on_conflict)
        merged: dict[str, Any] = {}
        for source, mapping in owned:
            run.mapping(merged, mapping, (), source)
        return merged, run.conflicts
