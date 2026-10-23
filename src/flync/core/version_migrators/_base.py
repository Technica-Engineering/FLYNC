"""
Base contract and registry for FLYNC workspace schema migrations.

A migration transforms a workspace's YAML *data* (never Python objects) from one FLYNC schema
to a newer one, so that workspaces exchanged between suppliers and OEMs can be brought up to the
installed release without losing content. Migrations operate on the raw parsed documents before
any Pydantic validation runs, which is what allows re-keying, restructure and cross-document moves
(the workspace is treated as data, consistent with ``root_model`` never being persisted).

The chain is keyed by the FLYNC PEP 440 release: each migration declares the ``target_version``
that introduced its change. A workspace recorded at version ``R`` is migrated to the installed
version ``T`` by applying, in ascending ``target_version`` order, every migration ``m`` for which
``R < m.target_version <= T``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict

from packaging.version import InvalidVersion, Version

#: Documents surface handed to migrations: workspace-relative URI → parsed YAML mapping/list.
#: This mirrors the ``ast`` of each :class:`~flync.sdk.workspace.document.Document`.
Documents = Dict[str, Any]

#: Oldest recorded FLYNC release for which a migration path to the current release is guaranteed.
#:
#: The migration history in ``docs/source/model_change_history.rst`` begins at 0.9.x, so any
#: workspace older than this cannot be migrated and must be re-created / re-imported. This value
#: must be raised (not lowered) as migrations are added; it can never move backwards.
LOWEST_SUPPORTED_VERSION = "0.9.0"


class FLYNCMigration(ABC):
    """
    A single schema migration from an older FLYNC release to a newer one.

    Subclass this, set the class attributes, and implement :meth:`apply` (and optionally
    :meth:`should_apply`). Decorate the subclass with :func:`migration` (or call
    :meth:`MigrationRegistry.register`) so the mechanism discovers it. The base class is abstract
    and cannot be instantiated directly.

    Attributes:
        unique_id (str): Stable, globally-unique identifier for this migration (should never
            change once shipped - it is written to the workspace history manifest).

        target_version (str): PEP 440 FLYNC release that introduced this schema change. A
            workspace older than this needs the migration applied to reach the new format.

        description (str): Human-readable summary of the change, shown by ``flync migrate``.

        error_ids (tuple[str, ...]): ``FLYNC-...`` error IDs from ``model_change_history.rst``
            that this migration resolves.
    """

    unique_id: str = ""
    target_version: str = ""
    description: str = ""
    error_ids: tuple[str, ...] = ()

    def should_apply(self, documents: Documents) -> bool:
        """
        Whether this particular workspace actually needs this transform.

        Runs before :meth:`apply` (once the workspace is already known to be older than
        ``target_version``) so migrations can be a no-op for workspaces that happen to already
        conform. Defaults to ``True``; override when the trigger can be detected precisely.

        Args:
            documents: The parsed workspace documents, keyed by URI.

        Returns:
            bool: ``True`` to record the migration as applied to this workspace.
        """
        return True

    @abstractmethod
    def apply(self, documents: Documents) -> None:
        """
        Transform ``documents`` in place from the previous schema to ``target_version``.

        Must be idempotent: running it on documents it already migrated has to leave them
        unchanged. An interrupted migration rewrites some documents before the version stamp is
        advanced, and the next run then applies the whole chain again.

        Args:
            documents: The parsed workspace documents, keyed by URI. Mutate these; do not
                return a new mapping. Only URIs whose content actually changes are rewritten
                to disk - untouched documents keep their original formatting.
        """
        raise NotImplementedError(f"{type(self).__name__}.apply is not implemented")

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.unique_id} → {self.target_version}>"


class MigrationRegistry:
    """
    Holds every :class:`FLYNCMigration` and validates their invariants.

    This is a **singleton**: ``MigrationRegistry()`` always returns the one process-wide instance
    (also exposed as :data:`migration_registry` and populated by importing
    :mod:`flync.core.version_migrators.migrations`), so migrations registered from anywhere are
    visible to the engine and CLI.

    Tests (or other code needing an isolated, disposable set of migrations) create an independent
    registry with :meth:`new` and pass it explicitly to the engine.
    """

    _singleton: MigrationRegistry | None = None

    def __new__(cls) -> MigrationRegistry:
        if cls._singleton is None:
            cls._singleton = super().__new__(cls)
        return cls._singleton

    @classmethod
    def new(cls) -> MigrationRegistry:
        """Return a fresh, independent registry (for tests / bespoke migration sets)."""
        obj = super().__new__(cls)
        obj._migrations = {}
        return obj

    def __init__(self) -> None:
        # Only initialize the backing store once; `new()` pre-seeds it and the singleton must not
        # be reset by a subsequent `MigrationRegistry()` call.
        if not hasattr(self, "_migrations"):
            self._migrations: dict[str, FLYNCMigration] = {}

    def register(self, item: FLYNCMigration | type[FLYNCMigration]) -> FLYNCMigration:
        """
        Register a migration (instance or class), enforcing uniqueness of ids and targets.

        Args:
            item: A migration class to instantiate, or an already-instantiated migration.

        Returns:
            FLYNCMigration: The registered (instantiated) migration.

        Raises:
            ValueError: If ``unique_id`` is empty/duplicated, ``target_version`` is not a PEP 440
                version, or two migrations share a ``target_version``.
        """
        migration = item() if isinstance(item, type) else item
        if not migration.unique_id:
            raise ValueError("A migration must declare a non-empty 'unique_id'.")
        try:
            Version(migration.target_version)
        except InvalidVersion as exc:
            raise ValueError(
                f"Migration {migration.unique_id!r} has target_version {migration.target_version!r}, which is not a PEP 440 version."
            ) from exc
        if migration.unique_id in self._migrations:
            raise ValueError(f"Duplicate migration unique_id: {migration.unique_id!r}.")
        for existing in self._migrations.values():
            if existing.target_version == migration.target_version:
                raise ValueError(
                    f"Migrations {existing.unique_id!r} and {migration.unique_id!r} share target_version "
                    f"{migration.target_version!r}; target versions must be unique to keep the chain ordered."
                )
        self._migrations[migration.unique_id] = migration
        return migration

    def get(self, unique_id: str) -> FLYNCMigration | None:
        """Return the migration with ``unique_id``, or ``None``."""
        return self._migrations.get(unique_id)

    def all(self) -> list[FLYNCMigration]:
        """All registered migrations."""
        return list(self._migrations.values())

    def clear(self) -> None:
        """Remove all registrations (used to reset the default registry under test)."""
        self._migrations.clear()


#: Process-global singleton registry of built-in migrations (same object returned by
#: ``MigrationRegistry()``). Populated by importing :mod:`flync.core.version_migrators.migrations`.
migration_registry = MigrationRegistry()


def migration(cls: type[FLYNCMigration]) -> type[FLYNCMigration]:
    """
    Decorator that registers a :class:`FLYNCMigration` subclass into :data:`migration_registry`.

    Use on every concrete migration class defined under
    :mod:`flync.core.version_migrators.migrations`:

    .. code-block:: python

        @migration
        class MyMigration(FLYNCMigration):
            unique_id = "my_rename"
            target_version = "0.15.0"
            description = "Renames the 'foo' key to 'bar'."

            def apply(self, documents):
                for uri, content in documents.items():
                    if isinstance(content, dict) and "foo" in content:
                        content["bar"] = content.pop("foo")
    """
    migration_registry.register(cls())
    return cls
