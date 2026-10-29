"""
Read/write the workspace migration history manifest.

The manifest lives at ``.flync/migrations/history.yaml`` inside a workspace root and records, in
append-only order, every :class:`~flync.core.version_migrators._base.FLYNCMigration` that has been
applied to that workspace. It is the parsable, diffable audit trail for migrations, and lets a
workspace whose history is missing or inconsistent be diagnosed. The engine selects migrations
purely from the recorded version stamp; the manifest records what happened rather than driving
what runs next.

The file is written atomically (write to a temp file, then replace), so a crash mid-migration
never leaves a half-written manifest.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from pydantic import BaseModel, Field

from flync.core.utils import yaml_io
from flync.sdk.context.workspace_config import CONFIG_DIRNAME

#: Directory name (under ``.flync/``) holding migration bookkeeping.
MIGRATIONS_DIRNAME = "migrations"

#: Basename of the migration history manifest.
HISTORY_FILENAME = "history.yaml"

#: Header comment written to the top of every ``history.yaml``, warning that the file is managed
#: programmatically and must not be hand-edited, moved or removed.
HISTORY_DISCLAIMER = (
    "# DO NOT EDIT, MOVE OR REMOVE THIS FILE MANUALLY.\n"
    "#\n"
    "# This file is the FLYNC migration history manifest. It is written and maintained\n"
    '# programmatically by the migration engine ("flync migrate" / the SDK migration mechanism)\n'
    "# and is only ever appended to. Editing, moving or deleting it can leave a workspace\n"
    "# reporting already-applied migrations as missing.\n"
    "#\n"
)


class MigrationRecord(BaseModel):
    """One applied migration, in the order it was applied.

    Parameters
    ----------
    id : str
        Unique id of the migration (matches ``FLYNCMigration.unique_id``).
    target_version : str
        FLYNC release that introduced the migration's change.
    applied_at : str
        ISO 8601 timestamp of when the migration was applied.
    applied_by : str
        FLYNC version that performed the migration.
    """

    id: str
    target_version: str
    applied_at: str
    applied_by: str


class MigrationHistory(BaseModel):
    """The ordered list of migrations applied to a workspace.

    Parameters
    ----------
    version : int, optional
        Schema version of the history manifest (defaults to ``1``).
    migrations : list of :class:`MigrationRecord`
        The applied migrations, in the order they were applied.
    """

    version: int = 1
    migrations: list[MigrationRecord] = Field(default_factory=list)

    def applied_ids(self) -> list[str]:
        """Return the applied migration ids, in order."""
        return [record.id for record in self.migrations]


def history_path(workspace_root: Path) -> Path:
    """Resolve the history manifest path under a workspace root."""
    return Path(workspace_root) / CONFIG_DIRNAME / MIGRATIONS_DIRNAME / HISTORY_FILENAME


def load_history(workspace_root: Path) -> MigrationHistory:
    """
    Read the history manifest from a workspace, or return an empty one when absent.
    """
    path = history_path(workspace_root)
    if not path.exists():
        return MigrationHistory()
    data = yaml_io.safe_load(path.read_text(encoding="utf-8")) or {}
    return MigrationHistory(**data)


def save_history(workspace_root: Path, history: MigrationHistory) -> None:
    """
    Write the history manifest atomically (temp file + replace).

    Gaps left by a failed write are avoided because :func:`os.replace` only ever swaps in a fully
    written file.

    Args:
        workspace_root: Root of the workspace to write the manifest into.
        history: The history to persist.
    """
    path = history_path(workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".history-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(HISTORY_DISCLAIMER)
            yaml_io.safe_dump(history.model_dump(), f)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
