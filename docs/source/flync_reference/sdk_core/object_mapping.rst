.. _object_mapping:

Object Mapping
**************

Every value that lives inside a FLYNC workspace — whether it is the root model,
a nested ECU, a list of controllers, or a single scalar — is tracked in two
parallel dictionaries on :class:`~flync.sdk.workspace.flync_workspace.FLYNCWorkspace`:

- :attr:`~flync.sdk.workspace.flync_workspace.FLYNCWorkspace.objects` — maps each
  :class:`~flync.sdk.workspace.ids.ObjectId` to its validated
  :class:`~flync.sdk.workspace.objects.SemanticObject`.

- :attr:`~flync.sdk.workspace.flync_workspace.FLYNCWorkspace.sources` — maps each
  :class:`~flync.sdk.workspace.ids.ObjectId` to a
  :class:`~flync.sdk.workspace.source.SourceRef` that records which file the
  value came from and the exact line/column range.

This page explains how those two dictionaries are built during loading and how
to query them at runtime.

----

.. _object_id_format:

Object IDs
==========

An :class:`~flync.sdk.workspace.ids.ObjectId` is a plain dot-separated string
that encodes the full path from the root model to a value.

.. list-table::
   :header-rows: 1
   :widths: 20 40 40

   * - Segment
     - Meaning
     - Example ID fragment
   * - ``field_name``
     - Named attribute on a model
     - ``ecus``
   * - ``key``
     - Concrete dict key (resolved at load time)
     - ``ecus.gateway``
   * - ``0``, ``1``, …
     - Numeric list index (see :ref:`list_object_ids`)
     - ``ecus.gateway.controllers.0``
   * - ``name_value``
     - Optional name-based alias for a list item (see :ref:`list_object_ids`)
     - ``ecus.gateway.controllers.eth_ctrl``

The root model itself is stored under the empty string ``""``.

.. note::

   :func:`~flync.sdk.helpers.validation_helpers.available_flync_nodes` returns
   *schema-level* paths that use ``{}`` and ``[]`` as wildcards. The IDs stored
   in the workspace use concrete keys and indices that are resolved when the
   files are actually parsed. See :ref:`node_paths` for the distinction.

----

.. _list_object_ids:

List Item IDs and ``ListObjectsMode``
======================================

When the workspace encounters a list (a ``SequenceNode`` in the YAML or a
folder-based ``External`` list on disk), each item needs one or more
:class:`~flync.sdk.workspace.ids.ObjectId` values so it can be retrieved
individually. The
:attr:`~flync.sdk.context.workspace_config.WorkspaceConfiguration.list_objects_mode`
setting on :class:`~flync.sdk.context.workspace_config.WorkspaceConfiguration`
controls which IDs are generated via
:meth:`~flync.sdk.workspace.flync_workspace.FLYNCWorkspace.add_list_item_object_path`.

.. autoclass:: flync.sdk.context.workspace_config.ListObjectsMode
   :members:
   :undoc-members:

.. automethod:: flync.sdk.workspace.flync_workspace.FLYNCWorkspace.add_list_item_object_path

Modes
-----

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Mode
     - Effect
   * - ``INDEX`` only
     - Each item is registered under its zero-based integer index.
       ``controllers.0``, ``controllers.1``, …
   * - ``NAME`` only
     - Each item is registered under its name (the ``name`` attribute on the
       model, or the file/directory stem for folder-based lists). Items
       without a name are silently skipped.
       ``controllers.eth_ctrl``, ``controllers.can_ctrl``, …
   * - ``INDEX | NAME`` *(default)*
     - Both IDs are registered for the same item. The item is reachable under
       either path.
       ``controllers.0`` **and** ``controllers.eth_ctrl``

Source of the name
------------------

The name used for ``NAME`` mode depends on where the list lives:

- **Folder-based** ``External`` lists — the name is the **file or directory
  stem** (everything before the first ``.`` in the filename). This is derived
  from ``sub_item_path.stem`` as the directory is iterated.

- **Inline YAML** ``SequenceNode`` lists — the name is the **``name``
  attribute** of the validated Pydantic model at that index
  (``getattr(model[idx], "name", None)``). If the model has no ``name``
  field the item gets an index-only ID even when ``NAME`` mode is active.

Configuring the mode
--------------------

Pass a custom
:class:`~flync.sdk.context.workspace_config.WorkspaceConfiguration` when
loading the workspace:

.. code-block:: python

   from flync.sdk.context.workspace_config import WorkspaceConfiguration, ListObjectsMode
   from flync.sdk.workspace.flync_workspace import FLYNCWorkspace

   # Index-only — useful when item names are not stable
   config = WorkspaceConfiguration(
       list_objects_mode=ListObjectsMode.INDEX,
   )
   ws = FLYNCWorkspace.load_workspace("my_config", "/path/to/config", config)

   # Name-only — useful when indices may shift across reloads or for easier object lookup for manual users
   config = WorkspaceConfiguration(
       list_objects_mode=ListObjectsMode.NAME,
   )

   # Both (the default)
   config = WorkspaceConfiguration(
       list_objects_mode=ListObjectsMode.INDEX | ListObjectsMode.NAME,
   )

Example — dual IDs in practice
--------------------------------

Given a workspace whose ``controllers/`` directory contains
``eth_ctrl.flync.yaml`` and the default ``INDEX | NAME`` mode:

.. code-block:: python

   ws = FLYNCWorkspace.load_workspace("cfg", "/path/to/config")

   # Both of these refer to the same SemanticObject
   by_index = ws.get_object("ecus.gateway.controllers.0")
   by_name  = ws.get_object("ecus.gateway.controllers.eth_ctrl")

   assert by_index.model is by_name.model  # same validated instance

----

.. _source_types:

Source Types
============

.. autoclass:: flync.sdk.workspace.source.SourceRef
   :members:
   :undoc-members:

.. autoclass:: flync.sdk.workspace.source.Range
   :members:
   :undoc-members:

.. autoclass:: flync.sdk.workspace.source.Position
   :members:
   :undoc-members:

.. autoclass:: flync.sdk.workspace.objects.SemanticObject
   :members:
   :undoc-members:

.. autoclass:: flync.sdk.workspace.ids.ObjectId

----

.. _runtime_retrieval:

Runtime Retrieval
=================

Once the workspace is loaded, four methods expose the object and source maps.

List all object IDs
-------------------

.. automethod:: flync.sdk.workspace.flync_workspace.FLYNCWorkspace.list_objects

.. code-block:: python

   ws = FLYNCWorkspace.load_workspace("my_config", "/path/to/config")

   for oid in ws.list_objects():
       print(oid)
   # ""
   # "ecus"
   # "ecus.gateway"
   # "ecus.gateway.controllers.0"        ← index-based ID
   # "ecus.gateway.controllers.eth_ctrl" ← name-based ID (same object)
   # ...

Retrieve a semantic object
--------------------------

.. automethod:: flync.sdk.workspace.flync_workspace.FLYNCWorkspace.get_object

.. code-block:: python

   obj = ws.get_object("ecus.gateway")
   print(obj.model)   # EcuConfig instance
   print(obj.id)      # "ecus.gateway"

Retrieve the source location
----------------------------

.. automethod:: flync.sdk.workspace.flync_workspace.FLYNCWorkspace.get_source

.. code-block:: python

   src = ws.get_source("ecus.gateway")
   print(src.uri)              # "ecus/gateway/ecu_metadata.flync.yaml"
   print(src.range.start)      # Position(line=1, character=1)  ← 1-based (YAML-backed)
   print(src.range.end)        # Position(line=42, character=1)

.. note::

   :class:`~flync.sdk.workspace.source.Position` values are **1-based** for
   objects loaded from a YAML file (ruamel.yaml marks are shifted by +1).
   Objects that have no YAML source (implied or externally loaded without a
   resolved file) carry ``Position(line=0, character=0)`` as a sentinel.

Look up objects by file position
---------------------------------

.. automethod:: flync.sdk.workspace.flync_workspace.FLYNCWorkspace.objects_at

This is the primary entry point for language-server features such as hover and
go-to-definition. Given a document URI and a cursor position, it returns every
:class:`~flync.sdk.workspace.ids.ObjectId` whose source range contains that
position.

.. code-block:: python

   ids = ws.objects_at(
       uri="ecus/gateway/ecu_metadata.flync.yaml",
       line=10,
       character=5,
   )
   for oid in ids:
       obj = ws.get_object(oid)
       print(oid, "→", type(obj.model).__name__)

.. note::

   ``objects_at`` uses **1-based** line and character numbers, matching the
   :class:`~flync.sdk.workspace.source.Position` values stored during YAML
   parsing. Pass ``line=0, character=0`` to query objects with no YAML source.

----

.. _object_path_helpers:

Object Path Helpers
===================

These utility methods are used internally during loading but are also available
for tooling that needs to build or resolve object paths at runtime.

.. automethod:: flync.sdk.workspace.flync_workspace.FLYNCWorkspace.document_id_from_path

.. automethod:: flync.sdk.workspace.flync_workspace.FLYNCWorkspace.new_object_path

.. automethod:: flync.sdk.workspace.flync_workspace.FLYNCWorkspace.update_objects_path

.. automethod:: flync.sdk.workspace.flync_workspace.FLYNCWorkspace.fill_path_from_object

----

Data structure summary
======================

.. code-block:: text

   FLYNCWorkspace
   ├── objects: Dict[ObjectId, SemanticObject]
   │              │               │
   │              │               └── .model  (validated Pydantic value)
   │              │               └── .id     (same as the key)
   │              │
   │              ├── "ecus.gateway.controllers.0"        ─┐ both point to the
   │              └── "ecus.gateway.controllers.eth_ctrl" ─┘ same SemanticObject
   │                   (generated by add_list_item_object_path via ListObjectsMode)
   │
   └── sources: Dict[ObjectId, SourceRef]
                  │               │
                  │               └── .uri    (workspace-relative file path)
                  │               └── .range  ─┬─ .start  Position(line, character)  ← 1-based for YAML; (0,0) if no source
                  │                            └─ .end    Position(line, character)  ← 1-based for YAML; (0,0) if no source
                  │
                  └── key: same ObjectId used in objects
                       (one entry per ID, so index and name both have a SourceRef)
