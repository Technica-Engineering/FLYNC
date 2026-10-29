"""
Migration engine: detect the version gap, sequence the required migrations and apply them.

This is the SDK-facing entry point for the FLYNC workspace migration mechanism. Two layers:

* :class:`MigrationEngine` - pure decision + transform logic. Given a recorded version, the
  installed version and a set of documents, it works out whether (and which) migrations apply and
  produces the transformed documents. It never touches disk, which keeps it trivially testable.

* :class:`Migrator` - the orchestrator used by the CLI and by the SDK load-time policy. It wraps an
  :class:`MigrationEngine`, resolves the recorded version from a workspace, and persists migrations
  (rewrite changed documents, append the history manifest, advance the config stamp).

The usual flow triggered on load is :func:`apply_migration_policy`, which warns when a workspace is
older than the installed release and - only when ``migration_mode`` is ``"auto"`` - migrates it in
place before the model is loaded.
"""

from __future__ import annotations

import copy
import datetime
import logging
import os
import tempfile
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from packaging.version import Version

from flync.core.utils import yaml_io
from flync.model.flync_4_metadata.metadata import BaseVersion
from flync.sdk.context.workspace_config import CONFIG_RELPATH, WorkspaceConfiguration, _get_current_flync_version
from flync.sdk.utils.sdk_types import PathType

from . import migrations as _builtin_migrations  # noqa: F401  (import registers built-in migrations into the global registry)
from ._base import LOWEST_SUPPORTED_VERSION, Documents, FLYNCMigration, MigrationRegistry, migration_registry
from .history import MigrationRecord, load_history, save_history

if TYPE_CHECKING:  # pragma: no cover - import-time only for type checking
    from flync.sdk.workspace.flync_workspace import FLYNCWorkspace

logger = logging.getLogger(__name__)


class WorkspaceMigrationState(StrEnum):
    """Classifies a workspace's version relative to the installed FLYNC release."""

    NO_VERSION = "no_version"
    """No ``.flync/config.yaml`` version stamp exists to compare against."""
    UP_TO_DATE = "up_to_date"
    """At the installed schema; nothing to do."""
    PENDING_MIGRATION = "pending_migration"
    """A chain of registered migrations can bring the workspace to the installed release."""
    UNSUPPORTED_OLD = "unsupported_old"
    """Older than the lowest supported version - no migration path exists."""
    NEWER = "newer"
    """Created by a newer FLYNC than the one installed; never migrate (downgrade case)."""


@dataclass
class MigrationStatus:
    """Outcome of comparing a workspace's recorded version to the installed FLYNC version."""

    state: WorkspaceMigrationState
    recorded: BaseVersion | None
    current: BaseVersion
    lowest_supported: Version
    pending: list[FLYNCMigration] = field(default_factory=list)
    requires_stamp: bool = False


@dataclass
class AppliedMigration:
    """
    A migration selected for a workspace.

    Attributes:
        changed (bool): Whether ``apply`` actually ran. ``False`` when ``should_apply`` reported
            the workspace already conforms, in which case the migration is still recorded but
            transformed nothing.
    """

    unique_id: str
    target_version: str
    description: str
    changed: bool


def _version(version: BaseVersion | None) -> Version | None:
    """Return a :class:`packaging.version.Version` for a pep440 ``BaseVersion`` or ``None``."""
    if version is None or version.version_schema != "pep440":
        return None
    return Version(str(version.version))


class MigrationEngine:
    """
    Pure decision and transform logic for schema migrations.

    Args:
        registry: The set of migrations to consider. Defaults to the process-global
            :data:`flync.core.version_migrators._base.migration_registry`.

        lowest_supported: Oldest recorded release for which a migration path is guaranteed.
    """

    def __init__(
        self,
        registry: MigrationRegistry | None = None,
        lowest_supported: str = LOWEST_SUPPORTED_VERSION,
    ):
        self.registry = registry if registry is not None else migration_registry
        self.lowest_supported = Version(lowest_supported)

    def evaluate(self, recorded: BaseVersion | None, current: BaseVersion) -> MigrationStatus:
        """
        Classify a workspace, given its recorded version and the installed version.

        Args:
            recorded: Version stamp read from the workspace (``None`` when absent).
            current: Installed FLYNC version.

        Returns:
            MigrationStatus: The classification plus the ordered chain of applicable migrations.
        """
        current_v = Version(str(current.version))
        rec = _version(recorded)
        lowest = self.lowest_supported

        state = WorkspaceMigrationState.NO_VERSION if rec is None else WorkspaceMigrationState.UP_TO_DATE
        extra: dict[str, Any] = {}
        if rec is not None:
            if rec > current_v:
                state = WorkspaceMigrationState.NEWER
            elif rec < lowest:
                state = WorkspaceMigrationState.UNSUPPORTED_OLD
            else:
                chain = self.chain(rec, current_v)
                if chain:
                    state = WorkspaceMigrationState.PENDING_MIGRATION
                    extra["pending"] = chain
                else:
                    extra["requires_stamp"] = rec < current_v
        return MigrationStatus(state, recorded, current, lowest, **extra)

    def chain(self, recorded: Version, current: Version) -> list[FLYNCMigration]:
        """
        Return migrations that bring ``recorded`` up to ``current``, ordered by target version.

        A migration applies when ``recorded < target_version <= current``. Sorting by
        ``target_version`` produces the deterministic chain the runner applies in order.
        """
        chain = [m for m in self.registry.all() if recorded < Version(m.target_version) <= current]
        chain.sort(key=lambda m: Version(m.target_version))
        return chain

    def apply(self, documents: Documents, recorded: BaseVersion, current: BaseVersion) -> tuple[list[AppliedMigration], Documents, list[str]]:
        """
        Apply the required migrations to a *copy* of ``documents``.

        The input mapping is left untouched; the transformed copy is returned so the caller decides
        when (and whether) to persist it. This is what enables ``--dry-run``.

        Args:
            documents: Parsed workspace documents keyed by URI.
            recorded: The workspace's recorded version.
            current: The installed FLYNC version.

        Returns:
            tuple: ``(applied, working, changed_uris)`` where ``applied`` lists each run migration,
            ``working`` is the transformed copy, and ``changed_uris`` are the URIs whose content
            actually differs from the input.
        """
        working = copy.deepcopy(documents)
        applied: list[AppliedMigration] = []
        rec = _version(recorded)
        cur = Version(str(current.version))
        if rec is None:
            return applied, working, []
        for migration in self.chain(rec, cur):
            needed = migration.should_apply(working)
            if needed:
                migration.apply(working)
            applied.append(
                AppliedMigration(
                    unique_id=migration.unique_id,
                    target_version=migration.target_version,
                    description=migration.description,
                    changed=needed,
                )
            )
        changed_uris = [uri for uri, ast in working.items() if not _deep_equal(ast, documents.get(uri))]
        return applied, working, changed_uris


def _recorded_version(config_file: Path) -> BaseVersion | None:
    """
    Return the version stamp written in ``config_file``, or ``None`` when there is none.

    :class:`WorkspaceConfiguration` fills a missing ``version`` with the installed release, so the
    raw file is inspected to tell a recorded stamp from that default.
    """
    if not config_file.exists():
        return None
    with open(config_file, "r", encoding="utf-8") as f:
        data = yaml_io.safe_load(f)
    if not isinstance(data, dict) or "version" not in data:
        return None
    return WorkspaceConfiguration.from_yaml_file(config_file).version


def _deep_equal(left: Any, right: Any) -> bool:
    """Cheap structural equality between two parsed-YAML values."""
    result = left is right
    if not result and isinstance(left, dict) and isinstance(right, dict):
        result = left.keys() == right.keys() and all(_deep_equal(left[k], right[k]) for k in left)
    elif not result and isinstance(left, list) and isinstance(right, list):
        result = len(left) == len(right) and all(_deep_equal(a, b) for a, b in zip(left, right))
    elif not result:
        result = left == right
    return result


def _to_yaml_text(value: Any) -> str:
    """Serialize a parsed-YAML value with the SDK's document dumper, keeping mapping order."""
    if isinstance(value, (dict, list)):
        return yaml_io.safe_dump(value) or ""
    return "" if value is None else str(value)


def _write_documents(ws_root: Path, texts: dict[str, str]) -> None:
    """
    Write migrated documents, staging every file before any original is replaced.

    New contents go to temporary files next to their targets first, so a failure while writing
    leaves the workspace untouched. Only the final :func:`os.replace` swaps can leave it partly
    migrated, which is why migrations must be idempotent.

    Args:
        ws_root: Root of the workspace.
        texts: New document text keyed by workspace-relative URI.
    """
    staged: list[tuple[str, Path]] = []
    try:
        for uri, text in texts.items():
            target = ws_root / uri
            target.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=str(target.parent), prefix=f".{target.name}-", suffix=".tmp")
            staged.append((tmp, target))
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(text)
    except BaseException:
        for tmp, _ in staged:
            Path(tmp).unlink(missing_ok=True)
        raise
    for tmp, target in staged:
        os.replace(tmp, target)


class Migrator:
    """
    Orchestrates workspace migrations: check status, apply, or stamp a baseline.

    This is the public API for both the CLI (``flync migrate``) and the SDK load-time policy.

    Args:
        registry: Override the migration registry (primarily for tests).
        lowest_supported: Override the lowest-supported version.
    """

    def __init__(self, registry: MigrationRegistry | None = None, lowest_supported: str = LOWEST_SUPPORTED_VERSION):
        self.engine = MigrationEngine(registry=registry, lowest_supported=lowest_supported)

    # -- inspection -----------------------------------------------------------

    def check(self, workspace_path: PathType, workspace_config: WorkspaceConfiguration | None = None) -> MigrationStatus:
        """
        Determine the migration status of a workspace on disk without modifying it.

        Args:
            workspace_path: Root of the workspace.

            workspace_config: Optional configuration; when omitted, ``.flync/config.yaml`` is
                auto-discovered. Only its ``version`` is inspected.

        Returns:
            MigrationStatus: The classification. :attr:`WorkspaceMigrationState.NO_VERSION` when
            no configuration is given and ``.flync/config.yaml`` is missing or has no ``version``
            entry. The workspace is never written to.
        """
        if workspace_config is not None:
            recorded: BaseVersion | None = workspace_config.version
        else:
            recorded = _recorded_version(Path(workspace_path) / CONFIG_RELPATH)
        current = _get_current_flync_version()
        return self.engine.evaluate(recorded, current)

    def plan(self, workspace_path: PathType, workspace_config: WorkspaceConfiguration | None = None) -> MigrationStatus:
        """Alias of :meth:`check` - the plan for what would run (used by ``flync migrate --dry-run``)."""
        return self.check(workspace_path, workspace_config=workspace_config)

    # -- mutation -------------------------------------------------------------

    def run(self, workspace_path: PathType, workspace_config: WorkspaceConfiguration | None = None) -> ApplicationResult:
        """
        Apply pending migrations to the workspace on disk and record them in history.

        This is destructive: changed documents are rewritten, the history manifest is updated and
        the config stamp is advanced to the installed version. It is a no-op unless the status is
        :attr:`WorkspaceMigrationState.PENDING_MIGRATION`.

        Args:
            workspace_path: Root of the workspace.
            workspace_config: Optional configuration; auto-discovered when omitted.

        Returns:
            ApplicationResult: Summary of what was applied.

        Raises:
            RuntimeError: If the workspace is unsupported (too old), from a newer FLYNC, or has no
                recorded version.
        """
        status = self.check(workspace_path, workspace_config=workspace_config)
        if status.state is WorkspaceMigrationState.NO_VERSION:
            raise RuntimeError(
                "Workspace has no recorded FLYNC version (.flync/config.yaml is missing or has no `version` entry), "
                "so it is treated as already in the installed schema. Run `flync migrate --init <path>` to record that."
            )
        assert status.recorded is not None  # every non-NO_VERSION branch carries a stamp
        if status.state is WorkspaceMigrationState.UNSUPPORTED_OLD:
            raise RuntimeError(
                f"Workspace records FLYNC {status.recorded.version}, older than the lowest supported "
                f"{status.lowest_supported}. It cannot be migrated; re-create or re-import the workspace."
            )
        if status.state is WorkspaceMigrationState.NEWER:
            raise RuntimeError(
                f"Workspace records FLYNC {status.recorded.version}, newer than the installed "
                f"{status.current.version}. Refusing to migrate a workspace from a newer FLYNC."
            )
        if status.state is not WorkspaceMigrationState.PENDING_MIGRATION:
            if status.requires_stamp:
                self.stamp(workspace_path, workspace_config=workspace_config)
                return ApplicationResult(applied=[], stamped=True, message="No schema migration needed; version stamp advanced.")
            return ApplicationResult(applied=[], message="Workspace is already up to date.")

        from flync.sdk.workspace.flync_workspace import FLYNCWorkspace

        # The workspace's own configuration is what gets written back when the stamp is advanced,
        # so it has to survive this load. Deriving the load-time override from it (rather than
        # constructing a fresh one) keeps every user setting intact; a default config here would
        # silently replace them and persist ``migration_mode: off``, opting the workspace out of
        # all future migration checks.
        persisted_config = workspace_config if workspace_config is not None else WorkspaceConfiguration.from_workspace(workspace_path)
        workspace = FLYNCWorkspace.safe_load_workspace(
            "migration_workspace",
            workspace_path,
            # "off" only for this load, so the load-time policy does not recurse into this run.
            workspace_config=WorkspaceConfiguration.create_from_config(persisted_config, migration_mode="off"),
        )
        workspace.configuration = persisted_config
        return self.apply_in_place(workspace, status)

    def apply_in_place(self, workspace: FLYNCWorkspace, status: MigrationStatus | None = None) -> ApplicationResult:
        """
        Apply pending migrations to an already-opened workspace, rewriting changed documents and
        recording history. Mutates ``workspace.documents`` so the caller can keep loading from them.

        Args:
            workspace: A workspace whose documents are opened, with ``migration_mode="off"``.
            status: Precomputed status; recomputed from the workspace's configuration when omitted.

        Returns:
            ApplicationResult: Summary of what was applied.
        """
        if status is None:
            status = self.engine.evaluate(workspace.configuration.version, _get_current_flync_version())
        if status.state is not WorkspaceMigrationState.PENDING_MIGRATION or status.recorded is None:
            return ApplicationResult(applied=[], message="Nothing to migrate.")
        if workspace.workspace_root is None:
            return ApplicationResult(applied=[], message="Nothing to migrate.")

        documents: Documents = {uri: doc.ast for uri, doc in workspace.documents.items()}
        applied, working, changed_uris = self.engine.apply(documents, status.recorded, status.current)

        ws_root = workspace.workspace_root
        texts = {uri: _to_yaml_text(working[uri]) for uri in changed_uris}
        _write_documents(ws_root, texts)
        for uri in changed_uris:
            doc = workspace.documents[uri]
            doc.ast = working[uri]
            doc.text = texts[uri]
            # The composed tree holds source positions of the old text; it is rebuilt lazily.
            doc.compose_ast = None

        history = load_history(ws_root)
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        applied_by = str(status.current.version)
        for record in applied:
            history.migrations.append(
                MigrationRecord(
                    id=record.unique_id,
                    target_version=record.target_version,
                    applied_at=now,
                    applied_by=applied_by,
                )
            )
        save_history(ws_root, history)

        # The documents are now in the installed schema, so the stamp moves to it. Saving keeps the
        # stamp of a configuration that still has pending migrations.
        workspace.configuration = WorkspaceConfiguration.create_from_config(workspace.configuration, version=status.current)
        workspace.save_workspace_config()
        return ApplicationResult(
            applied=[record.unique_id for record in applied],
            changed_uris=changed_uris,
            message=f"Applied {len(applied)} migration(s).",
        )

    @staticmethod
    def stamp(workspace_path: PathType, workspace_config: WorkspaceConfiguration | None = None) -> None:
        """
        Record the installed FLYNC version as the workspace baseline without transforming anything.

        Writes ``.flync/config.yaml`` with the current version so a workspace that has no stamp (or
        whose schema has not changed) stops the migration warning. ``flync migrate --init``.

        Args:
            workspace_path: Root of the workspace.
            workspace_config: Optional configuration; auto-discovered when omitted.
        """
        from flync.sdk.workspace.flync_workspace import FLYNCWorkspace

        ws_root = Path(workspace_path)
        config = workspace_config or (
            WorkspaceConfiguration.from_yaml_file(ws_root / CONFIG_RELPATH) if (ws_root / CONFIG_RELPATH).exists() else WorkspaceConfiguration()
        )
        workspace = FLYNCWorkspace(
            name="migration_stamp",
            workspace_path=str(ws_root),
            configuration=config,
        )
        workspace.save_workspace_config()


@dataclass
class ApplicationResult:
    """Summary returned by :meth:`Migrator.run`."""

    applied: list[str] = field(default_factory=list)
    changed_uris: list[str] = field(default_factory=list)
    stamped: bool = False
    message: str = ""


def apply_migration_policy(workspace: FLYNCWorkspace, registry: MigrationRegistry | None = None) -> None:
    """
    SDK load-time policy: warn about (or, when ``auto``, perform) migrations for a loaded workspace.

    Called from :meth:`~flync.sdk.workspace.flync_workspace.FLYNCWorkspace.safe_load_workspace`
    after documents are opened but before the model is assembled, so an ``auto`` migration can
    rewrite the in-memory documents that the subsequent load validates against.

    Behavior follows ``workspace.configuration.migration_mode``:
        - ``"off"``: never checks versions.
        - ``"propose"`` (default): only warns and suggests ``flync migrate``.
        - ``"auto"``: applies pending migrations before the model is loaded.

    Args:
        workspace: A workspace whose documents are already opened.
        registry: Migration registry to use; defaults to the built-in set.
    """
    config = workspace.configuration
    current = _get_current_flync_version()
    rec = _version(config.version)
    cur = Version(str(current.version))

    if config.migration_mode == "off":
        return

    if rec is not None and rec != cur:
        if rec > cur:
            logger.warning(
                "Workspace %s was created with FLYNC %s, newer than the installed %s. Refusing to migrate a "
                "workspace from a newer FLYNC; load it with at least FLYNC %s.",
                workspace.name,
                rec,
                cur,
                rec,
            )
        elif rec < Version(LOWEST_SUPPORTED_VERSION):
            logger.warning(
                "Workspace %s records FLYNC %s, older than the lowest supported %s. It cannot be migrated; re-create or re-import the workspace.",
                workspace.name,
                rec,
                LOWEST_SUPPORTED_VERSION,
            )
        else:
            _run_or_report(workspace, config, registry, rec, cur, current)


def _run_or_report(
    workspace: FLYNCWorkspace,
    config: WorkspaceConfiguration,
    registry: MigrationRegistry | None,
    rec: Version,
    cur: Version,
    current: BaseVersion,
) -> None:
    """Apply pending migrations (``auto``) or warn that they are pending (``propose``)."""
    engine = MigrationEngine(registry=registry)
    chain = engine.chain(rec, cur)
    if chain:
        if config.migration_mode == "auto":
            try:
                Migrator(registry=registry).apply_in_place(workspace, status=engine.evaluate(config.version, current))
            except Exception:  # a failed migration is reported, but must not break the load
                logger.exception(
                    "Automatic migration of workspace %s from FLYNC %s to %s failed. Its version stamp stays at %s, so the "
                    "migration is attempted again on the next load; run `flync migrate %s` to retry it explicitly.",
                    workspace.name,
                    rec,
                    cur,
                    rec,
                    workspace.workspace_root,
                )
        else:
            logger.warning(
                "Workspace %s was created with FLYNC %s (installed: %s). The schema changed; run `flync migrate %s` to update it.",
                workspace.name,
                rec,
                cur,
                workspace.workspace_root,
            )
