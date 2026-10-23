.. _migrations_reference:

############################
Schema Migrations
############################

FLYNC workspaces are stored as YAML documents whose shape is tied to a specific release of the
library. When the model changes between releases, a workspace recorded by an older FLYNC may no
longer map cleanly onto the installed version's schema. The **migration mechanism** brings such a
workspace up to date.

This mechanism operates on the **raw parsed YAML documents** (keyed by workspace-relative URI)
*before* they are fed to Pydantic. Migrations therefore transform plain dictionaries, not model
objects, and can be written and reasoned about independently of the model definitions.

How it works
============

Every workspace records the FLYNC release that last wrote it in
``.flync/config.yaml`` (the ``version`` stamp, PEP 440). On load the SDK compares that stamp with
the installed FLYNC release and classifies the workspace:

.. list-table::
   :header-rows: 1

   * - State
     - Condition
     - Result
   * - ``NO_VERSION``
     - ``.flync/config.yaml`` is missing or has no ``version`` entry
     - Loaded as the installed schema; ``flync migrate --init`` records that (no data changed)
   * - ``UP_TO_DATE``
     - ``recorded == current`` (or nothing pending, stamp lags)
     - Nothing to do; stamp may be advanced
   * - ``PENDING_MIGRATION``
     - ``lowest_supported <= recorded < current`` and a chain exists
     - Apply migrations in order, then advance the stamp
   * - ``UNSUPPORTED_OLD``
     - ``recorded < LOWEST_SUPPORTED_VERSION``
     - No path forward; re-create / re-import the workspace
   * - ``NEWER``
     - ``recorded > current``
     - Refuse: a workspace from a newer FLYNC is never migrated

Migrations are keyed by the ``target_version`` (the release that introduced the change) and applied
in ascending order. A migration applies when ``recorded < target_version <= current``. Each applied
migration is recorded, in order, in the append-only history manifest at
``.flync/migrations/history.yaml``.

Safety guarantees
=================

* Migrations run on a **deep copy** of the documents; the originals are only touched once every
  migration in the chain succeeds.
* Changed documents are first written to temporary files and only then swapped in, so a failure
  while writing leaves every document unchanged.
* The history manifest is written **atomically** (temp file + ``os.replace``), so a failure never
  leaves a half-written manifest.
* The version stamp is **never moved backwards**, and the rest of the workspace configuration is
  preserved when it is advanced.
* Saving a workspace (``generate_configs`` or ``save_workspace_config``) does **not** advance the
  stamp while migrations are pending or the workspace is older than ``LOWEST_SUPPORTED_VERSION``.
  Saving does not migrate the documents, so the stamp keeps pointing at their actual schema until
  ``flync migrate`` (or ``auto`` mode) has run.

.. warning::

   Migrated documents are **re-serialized**, so comments and hand-authored formatting in the
   documents a migration touches are lost; the order of keys is kept. The final swap of the
   rewritten documents is one rename per file, so an interrupted migration can still leave the
   workspace partly migrated, with the stamp not yet advanced. The next run then applies the whole
   chain again, which is why every migration must be idempotent. Commit or back up a workspace
   before migrating it.

* The ``compatible_flync_version`` field (semver, user-authored) is intentionally *not* used as the
  migration baseline — it is a compatibility hint, not a format stamp.

Timing & ``migration_mode``
===========================

By default migrations are **proposed, not applied**: loading a stale workspace only logs a warning.
In ``auto`` mode a failing migration is logged as an error and the workspace is loaded unmigrated,
with its stamp unchanged, so the migration is attempted again on the next load.
Set ``migration_mode`` in ``.flync/config.yaml``:

.. code-block:: yaml

   migration_mode: propose   # default: warn only
   migration_mode: auto      # migrate before loading the model
   migration_mode: off       # never check

Explicit migration is always available regardless of the mode:

.. code-block:: bash

   flync migrate <path> --dry-run   # show what would run, change nothing
   flync migrate <path>             # apply pending migrations, record history
   flync migrate <path> --init      # only stamp a baseline version

For library users, :class:`~flync.core.version_migrators.engine.Migrator` orchestrates the workflow
(check → plan → run), while :class:`~flync.core.version_migrators.engine.MigrationEngine` classifies
a workspace and computes/executes the migration chain.

Writing a migration
===================

Subclass :class:`~flync.core.version_migrators._base.FLYNCMigration`, set a stable ``unique_id`` and
the ``target_version`` the change ships in, and implement ``apply`` (and optionally ``should_apply``)
to transform the in-memory documents. Register it with the built-in registry via the
:func:`~flync.core.version_migrators._base.migration` decorator.

A migration receives the workspace's parsed YAML as a ``{workspace-relative URI: parsed document}``
mapping and mutates it in place. The engine only rewrites URIs whose content actually changed, so
untouched documents keep their original formatting.

Rules for a migration:

* ``target_version`` is a PEP 440 version; registration rejects anything else.
* ``apply`` is idempotent: running it on documents it has already migrated leaves them unchanged.
* ``should_apply`` is a guard, not a safety net: an exception raised in it aborts the migration run.

.. code-block:: python

    from flync.core.version_migrators._base import FLYNCMigration, migration


    @migration
    class RenameLegacyEcuField(FLYNCMigration):
        unique_id = "rename_legacy_ecu_field"     # stable & unique; stored in history.yaml
        target_version = "0.15.0"                 # release that introduced the change
        description = "Renames ECUs 'legacy_type' to 'ecu_type'."
        error_ids = ("FLYNC-ECU-MAJ-CONS-042",)   # errors from model_change_history that this fixes

        def should_apply(self, documents):
            # Optional fast-path: skip when no document has the key at all.
            return any(
                isinstance(doc, dict) and "legacy_type" in str(doc.get("ecus", ""))
                for doc in documents.values()
            )

        def apply(self, documents):
            for uri, content in documents.items():
                if not isinstance(content, dict):
                    continue
                for ecu in content.get("ecus", []):
                    if isinstance(ecu, dict) and "legacy_type" in ecu:
                        ecu["ecu_type"] = ecu.pop("legacy_type")

After authoring it, place the module under
:mod:`flync.core.version_migrators.migrations` and import it from that package's ``__init__`` so the
``@migration`` decorator registers it. The engine then places it in the chain by ``target_version``
and applies it to any workspace older than that release.

API Reference
=============

.. autoclass:: flync.core.version_migrators._base.FLYNCMigration
   :members:

.. autoclass:: flync.core.version_migrators._base.MigrationRegistry
   :members:

.. autoclass:: flync.core.version_migrators.engine.MigrationEngine
   :members:

.. autoclass:: flync.core.version_migrators.engine.Migrator
   :members:

.. autoclass:: flync.core.version_migrators.history.MigrationHistory
   :members:
