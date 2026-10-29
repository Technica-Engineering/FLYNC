"""
Built-in FLYNC schema migrations.

Each concrete migration lives in its own module and is a :class:`~flync.core.version_migrators._base.FLYNCMigration`
subclass decorated with ``@migration``. Importing this package (which ``Migrator`` does) triggers
registration into the default :data:`~flync.core.version_migrators._base.migration_registry`.

A migration is authored whenever a *breaking* workspace/schema change is introduced
(see ``docs/source/model_change_history.rst``): one migration class per version transition, with
``target_version`` set to the release that introduced the change. The mechanism picks them up
automatically and applies them (in ascending ``target_version`` order) to any workspace older than
that release.
"""

from __future__ import annotations

from flync.core.version_migrators._base import (  # noqa: F401  (re-export base helpers)
    FLYNCMigration,
    MigrationRegistry,
    migration,
    migration_registry,
)

# Import every concrete migration module below so the decorator registers them.
from .v0_14_to_0_15 import Migration015

__all__ = ["migration", "MigrationRegistry", "FLYNCMigration", "migration_registry", "Migration015"]


# ---------------------------------------------------------------------------
# Authoring a migration (template — use as a starting point; do NOT ship this)
# ---------------------------------------------------------------------------
#
# A migration transforms a workspace's YAML *data* (plain dicts keyed by workspace-relative URI)
# before Pydantic validation runs. Write one class per breaking change and set ``target_version``
# to the release that introduced the change. The engine applies migrations in ascending
# ``target_version`` order to any workspace older than that release.
#
#     import re
#
#     from flync.core.version_migrators._base import FLYNCMigration, migration
#
#     # Register it in this package's __init__ so loading the package registers the migration.
#     # This example renames a legacy ECU field (see docs/source/model_change_history.rst).
#
#     @migration
#     class RenameLegacyEcuField(FLYNCMigration):
#         unique_id = "rename_legacy_ecu_field"     # stable, unique — stored in history.yaml
#         target_version = "0.15.0"                 # release that introduced the change
#         description = "Renames ECUs 'legacy_type' to 'ecu_type'."
#         error_ids = ("FLYNC-ECU-MAJ-CONS-042",)  # resolved errors from model_change_history
#
#         def should_apply(self, documents):
#             # Optional fast-path: skip when no document has the key at all.
#             return any(
#                 isinstance(doc, dict) and "legacy_type" in str(doc.get("ecus", ""))
#                 for doc in documents.values()
#             )
#
#         def apply(self, documents):
#             for uri, content in documents.items():
#                 if not isinstance(content, dict):
#                     continue
#                 for ecu in content.get("ecus", []):
#                     if isinstance(ecu, dict) and "legacy_type" in ecu:
#                         ecu["ecu_type"] = ecu.pop("legacy_type")
#
#     # The engine only rewrites URIs whose content actually changed, so untouched documents keep
#     # their original formatting. Never mutate the workspace's persisted files yourself here.
