flync.core
###########

flync.core.annotations
=======================

external
--------

.. automodule:: flync.core.annotations.external
   :members:

implied
--------
.. automodule:: flync.core.annotations.implied
   :members:

flync.core.base_models
=======================

base_models
-----------
.. automodule:: flync.core.base_models.base_model
   :members:

unique_names
-------------

.. automodule:: flync.core.base_models.unique_name
   :members:

registry
--------

The registry is a **context-local store** that tracks every validated model
instance during a single load or build operation.  It is the mechanism that
lets validators look up objects that were created earlier in the same
workspace -- for example, resolving a port name string into the actual
``ECUPort`` object that was already validated.

Two storage structures are maintained:

* ``dict_by_class`` -- keyed lookups (via :class:`~flync.core.base_models.dict_instances.DictInstances` / :class:`~flync.core.base_models.dict_instances.NamedDictInstances`)
* ``list_by_class`` -- ordered collections (via :class:`~flync.core.base_models.list_instances.ListInstances` / :class:`~flync.core.base_models.list_instances.NamedListInstances`)

.. autoclass:: flync.core.base_models.instances_registery.Registry
   :members:

.. autofunction:: flync.core.base_models.instances_registery.registry_context

.. autofunction:: flync.core.base_models.instances_registery.get_registry

.. autofunction:: flync.core.base_models.instances_registery.ensure_registry

.. _registry_workspace_usage:

Using the registry with FLYNCWorkspace
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Loading a workspace from files
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

:meth:`~flync.sdk.workspace.flync_workspace.FLYNCWorkspace.load_workspace`
and
:meth:`~flync.sdk.workspace.flync_workspace.FLYNCWorkspace.safe_load_workspace`
automatically wrap all YAML loading inside a fresh
:func:`~flync.core.base_models.instances_registery.registry_context`.
Every model validated during that call shares the same registry, so
cross-references (switch-port names, controller-interface names, service
IDs, etc.) resolve correctly.  You do **not** need to manage the registry
yourself when using these methods:

.. code-block:: python

   from flync.sdk.workspace.flync_workspace import FLYNCWorkspace

   workspace = FLYNCWorkspace.load_workspace("my_workspace", "/path/to/workspace")
   # All cross-references inside the workspace are already resolved.

.. warning::

   Each call to ``load_workspace`` / ``safe_load_workspace`` creates an
   **isolated** registry.  Objects from one workspace cannot be referenced
   by validators of another workspace loaded in a separate call.  If you
   need to validate connections that span two workspaces you must build a
   combined model manually (see below).

Building a model programmatically
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

When you create FLYNC model objects in Python code without going through
``load_workspace``, Pydantic validators run immediately at construction
time.  Any validator that calls
:func:`~flync.core.base_models.instances_registery.get_registry` will
raise a ``RuntimeError`` if no registry is active.

Wrap the entire construction block in
:func:`~flync.core.base_models.instances_registery.registry_context` so
that all objects -- and all validators -- share the same store:

.. code-block:: python

   from flync.core.base_models.instances_registery import (
       Registry,
       registry_context,
   )
   from flync.model.flync_4_ecu.switch import Switch, SwitchPort

   with registry_context(Registry()):
       port = SwitchPort(name="p0", silicon_port_no=0, ...)
       switch = Switch(name="sw0", ports=[port], ...)
       # port is now registered; switch validators can look it up.

Use :func:`~flync.core.base_models.instances_registery.ensure_registry`
instead when the code may be called either inside or outside an existing
registry context (for example, from a helper that is also used during a
``load_workspace`` call):

.. code-block:: python

   from flync.core.base_models.instances_registery import ensure_registry

   with ensure_registry():
       # Uses the caller's active registry if one exists,
       # or creates a new one for this block.
       model = MyModel(...)

dict_instances
--------------
.. automodule:: flync.core.base_models.dict_instances
   :members:

list_instances
--------------
.. automodule:: flync.core.base_models.list_instances
   :members:


flync.core.datatypes
====================

.. autoclass:: flync.core.datatypes.Datatype()

----

.. autoclass:: flync.core.datatypes.IPv4AddressEntry()
.. autoclass:: flync.core.datatypes.IPv6AddressEntry()

----

.. autoclass:: flync.core.datatypes.MACAddressEntry()
.. autoclass:: flync.core.datatypes.MACAddressUnicast()
.. autoclass:: flync.core.datatypes.MACAddressMulticast()

----

.. autoclass:: flync.core.datatypes.BitRange()

----

.. autoclass:: flync.core.datatypes.ValueRange()
.. autoclass:: flync.core.datatypes.ValueTable()


flync.core.utils
=================

base_utils
-----------

.. automodule:: flync.core.utils.base_utils
   :members:

common_validators
------------------

.. automodule:: flync.core.utils.common_validators
   :members:

exceptions
----------

.. automodule:: flync.core.utils.exceptions
   :members:

exceptions_handling
-------------------

.. automodule:: flync.core.utils.exceptions_handling
   :members:
