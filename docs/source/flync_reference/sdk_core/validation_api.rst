.. _validation_api:

Validation API
**************

The FLYNC SDK exposes a Python API for validating workspaces and individual
nodes programmatically. This is the foundation for CI/CD pipelines, tooling
integrations, and language server diagnostics.

All functions return a :class:`~flync.sdk.context.diagnostics_result.DiagnosticsResult`
that captures the validation state, per-document errors, the loaded model, and
the workspace instance.

.. tip::

   For a quick sanity-check from the command line, you can also use the
   :doc:`validate_workspace <../../flync_reference>` helper script instead of
   the Python API.

----

Imports
=======

.. code-block:: python

   from flync.sdk.helpers.validation_helpers import (
       validate_workspace,
       validate_external_node,
       validate_node,
   )
   from flync.sdk.helpers.nodes_helpers import (
       available_flync_nodes,
       type_from_input,
   )
   from flync.sdk.context.diagnostics_result import DiagnosticsResult, WorkspaceState

----

.. _diagnostics_result_reference:

DiagnosticsResult
=================

Every validation function returns a :class:`~flync.sdk.context.diagnostics_result.DiagnosticsResult`.

.. autoclass:: flync.sdk.context.diagnostics_result.DiagnosticsResult
   :members:
   :undoc-members:

.. autoclass:: flync.sdk.context.diagnostics_result.WorkspaceState
   :members:
   :undoc-members:

Reading results
---------------

.. code-block:: python

   result = validate_workspace("/path/to/workspace")

   # Check overall state
   if result.state == WorkspaceState.VALID:
       print("All good!", result.model)

   elif result.state == WorkspaceState.WARNING:
       # Model was created but some documents have non-fatal errors
       for doc_uri, errors in result.errors.items():
           for err in errors:
               print(f"[{doc_uri}] {err['msg']} @ {err['loc']}")

   elif result.state in (WorkspaceState.INVALID, WorkspaceState.BROKEN):
       print("Validation failed:", result.errors)

----

.. _node_paths:

Discovering Node Paths
======================

Before validating a specific node you need to know its path in the model
hierarchy. Use :func:`~flync.sdk.helpers.validation_helpers.available_flync_nodes`
to list every node reachable from a root model together with the dot-separated
paths through which they can be accessed.

.. autofunction:: flync.sdk.helpers.nodes_helpers.available_flync_nodes

Example
-------

.. code-block:: python

   from flync.sdk.helpers.nodes_helpers import available_flync_nodes

   nodes = available_flync_nodes()   # defaults to FLYNCModel as root

   for name, info in nodes.items():
       print(f"{name}:")
       print(f"  type  : {info.python_type}")
       print(f"  paths : {info.flync_paths}")

Example output::

   FLYNCModel:
     type  : <class 'flync.model.flync_model.FLYNCModel'>
     paths : []
   EcuConfig:
     type  : <class 'flync.model.ecu.ecu_config.EcuConfig'>
     paths : ['ecus.{}']
   ControllerConfig:
     type  : <class 'flync.model.ecu.controller.ControllerConfig'>
     paths : ['ecus.{}.controllers.[]']

The ``paths`` list uses ``{}`` for dict keys and ``[]`` for list indices.
These correspond directly to the segments you pass to
:func:`~flync.sdk.helpers.validation_helpers.validate_node`.

You can also scope the query to a subtree by passing a different root:

.. code-block:: python

   from flync.model.ecu.ecu_config import EcuConfig

   ecu_nodes = available_flync_nodes(EcuConfig)

----

.. _validate_full_workspace:

Validating a Full Workspace
============================

:func:`~flync.sdk.helpers.validation_helpers.validate_workspace` validates an
entire workspace directory against the default :class:`~flync.model.flync_model.FLYNCModel`.

.. autofunction:: flync.sdk.helpers.validation_helpers.validate_workspace

Example
-------

.. code-block:: python

   result = validate_workspace("/path/to/my_config")

   if result.state == WorkspaceState.VALID:
       model = result.model          # fully constructed FLYNCModel
       workspace = result.workspace  # FLYNCWorkspace with all objects

   else:
       for doc, errors in result.errors.items():
           for err in errors:
               print(err["msg"], err["loc"])

----

.. _validate_external_node_section:

Validating an External Node
============================

An *external node* is any model type that is stored in its own directory,
separate from the workspace root. Use
:func:`~flync.sdk.helpers.validation_helpers.validate_external_node` when you
want to validate a subtree in isolation — for example, a single ECU directory
— without loading the entire workspace.

.. autofunction:: flync.sdk.helpers.validation_helpers.validate_external_node

The ``node`` argument can be either the model class itself or its string name
as returned by :func:`~flync.sdk.helpers.validation_helpers.available_flync_nodes`.

Example — using a type
----------------------

.. code-block:: python

   from flync.model.ecu.ecu_config import EcuConfig
   from flync.sdk.helpers.validation_helpers import validate_external_node

   result = validate_external_node(EcuConfig, "/path/to/ecus/my_ecu")

   if result.state == WorkspaceState.VALID:
       ecu = result.model   # EcuConfig instance

Example — using a string name
-------------------------------

.. code-block:: python

   result = validate_external_node("EcuConfig", "/path/to/ecus/my_ecu")

----

.. _validate_partial_node:

Validating a Partial (In-Workspace) Node
==========================================

:func:`~flync.sdk.helpers.validation_helpers.validate_node` validates the
entire workspace first, then extracts and returns the model for a specific
node identified by its dot-separated path.

Use this when you already have a workspace loaded and want to focus on a
single node — for instance in a language server hover or diagnostic request.

.. autofunction:: flync.sdk.helpers.validation_helpers.validate_node

The ``node_path`` is the dot-separated object path within the workspace. You
can discover valid paths with :func:`~flync.sdk.helpers.validation_helpers.available_flync_nodes`
(see :ref:`node_paths`) or by inspecting
:attr:`~flync.sdk.workspace.flync_workspace.FLYNCWorkspace.objects` on an
already-loaded workspace.

Path syntax reference
---------------------

.. list-table::
   :header-rows: 1
   :widths: 20 40 40

   * - Segment
     - Meaning
     - Example
   * - ``field_name``
     - Named attribute on a model
     - ``ecus``
   * - ``{}``
     - Dictionary key (wildcard in schema paths)
     - ``ecus.my_ecu``
   * - ``[]``
     - List index (wildcard in schema paths)
     - ``ecus.my_ecu.controllers.0``

Example
-------

.. code-block:: python

   from flync.sdk.helpers.validation_helpers import validate_node

   # Validate the controller at index 0 inside "my_ecu"
   result = validate_node(
       ws_path="/path/to/my_config",
       node_path="ecus.my_ecu.controllers.0",
   )

   if result.state == WorkspaceState.VALID:
       controller = result.model
   else:
       print("Node errors:", result.errors)

.. note::

   When ``node_path`` does not exist in the loaded workspace,
   :func:`~flync.sdk.helpers.validation_helpers.validate_node` sets the state
   to :attr:`~flync.sdk.context.diagnostics_result.WorkspaceState.INVALID`
   and records a ``fatal`` error under the given ``node_path`` key.

----

Node metadata reference
========================

.. autoclass:: flync.sdk.context.node_info.NodeInfo
   :members:
   :undoc-members:

----

Function reference
==================

.. autofunction:: flync.sdk.helpers.validation_helpers.validate_workspace

.. autofunction:: flync.sdk.helpers.validation_helpers.validate_external_node

.. autofunction:: flync.sdk.helpers.validation_helpers.validate_node

.. autofunction:: flync.sdk.helpers.nodes_helpers.available_flync_nodes

.. autofunction:: flync.sdk.helpers.nodes_helpers.type_from_input
