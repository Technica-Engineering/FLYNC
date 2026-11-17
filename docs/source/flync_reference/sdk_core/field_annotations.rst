.. _field_annotations:

Field Annotations
*******************

The annotations control how a field is loaded, generated or derived from external data.
They are expressed directly on the pydantic model attributes, inside ``Annotated[...]``.

.. seealso::

   :ref:`structure_and_polymorphism` in the Model Development Guide shows how to *choose*
   between these annotations when adding a field. This page is the behavior reference.


Overview
--------

In *FLYNC* a field can stray away from standard yaml serialization by being:

* **External** - the value is read from or written to a separate file / folder.
* **Implied** - the value is not stored but calculated on the fly using a defined strategy.
* **Reference** - the value is a key naming an object that was loaded elsewhere.

A fourth annotation, **Namespaced**, refines an ``External`` folder list (see below).

All of them are frozen dataclasses in ``flync.core.annotations``, together with the strategy
enums that refine them:

* ``NamingStrategy`` - how the external file / folder is named.
* ``OutputStrategy`` - how the external representation is organized (single file vs folder).
* ``ImpliedStrategy`` - how an implied field is calculated.
* ``ReferenceStrategy`` - how a reference is stored and resolved.

.. important::

   Import them from ``flync.core.annotations``. The package re-exports everything, and
   importing from the defining submodules invites circular imports.


Using ``External`` in a model
-----------------------------

.. code-block:: python

    from typing import Annotated

    from pydantic import Field

    from flync.core.annotations import External, NamingStrategy, OutputStrategy
    from flync.core.base_models import FLYNCBaseModel


    class FLYNCModel(FLYNCBaseModel):
        ecus: Annotated[
            list[ECU],
            External(
                output_structure=OutputStrategy.FOLDER,
                naming_strategy=NamingStrategy.FIELD_NAME,
            ),
        ]
        metadata: Annotated[
            SystemMetadata,
            External(
                output_structure=OutputStrategy.SINGLE_FILE | OutputStrategy.OMMIT_ROOT,
                naming_strategy=NamingStrategy.FIXED_PATH,
                path="system_metadata",
            ),
        ]

``External`` takes four fields:

* ``path`` - location of the external resource relative to the current component. Left empty,
  it is derived from ``naming_strategy``.
* ``root`` - re-bases the location on a directory other than the parent's; used with
  ``OutputStrategy.FIXED_ROOT``.
* ``output_structure`` - an ``IntFlag``, so members combine with ``|``:

  .. list-table::
     :header-rows: 1

     * - Member
       - Effect
     * - ``FOLDER`` (alias of ``AUTO``, the default)
       - creates a directory containing one file per item
     * - ``SINGLE_FILE``
       - creates one ``<name>.flync.yaml``
     * - ``OMMIT_ROOT``
       - suppresses the wrapper key inside the written file
     * - ``FIXED_ROOT``
       - resolves the path against ``root`` instead of the parent

* ``naming_strategy`` - ``FIELD_NAME`` (alias of ``AUTO``, the default) derives the name from
  the field name; ``FIXED_PATH`` uses the explicit ``path``.


Using ``Implied`` in a model
----------------------------

.. code-block:: python

    from flync.core.annotations import Implied, ImpliedStrategy

    class Controller(FLYNCBaseModel):
        name: Annotated[str, Implied(strategy=ImpliedStrategy.FOLDER_NAME)] = Field()

When the model is instantiated, *flync* computes ``name`` from the surrounding path:

* ``ImpliedStrategy.FOLDER_NAME`` (alias of ``AUTO``, the default) - the containing directory's
  name, used for identifiers that follow the directory layout.
* ``ImpliedStrategy.FILE_NAME`` - the file's own name.


Using ``Reference`` in a model
------------------------------

A reference field is a **string in YAML** and an **object in Python**. The public field holds
the key; a private attribute named by ``source`` holds the resolved model, wired in during
workspace resolution and exposed through a property.

.. code-block:: python

    from flync.core.annotations import Reference

    class ECUPortToXConnection(InternalConnection):
        ecu_port_name: Annotated[str, Reference(source="_ecu_port")] = Field(alias="ecu_port")

        _ecu_port: ECUPort | None = None

        @property
        def ecu_port(self) -> ECUPort | None:
            return self._ecu_port

``Reference`` takes:

* ``source`` - name of the private attribute holding the referenced model object.
* ``source_key`` - attribute on the referenced model whose value is the key written back.
  Defaults to ``"name"``; set it when objects are identified by something else.
* ``reference_strategy`` - ``PRIVATE_ATTR`` (alias of ``AUTO``, the default).

:func:`~flync.core.annotations.reference.resolve_reference` returns the concrete object a
field's annotation points at, accepting either the Python name or the alias.


Using ``Namespaced`` in a model
-------------------------------

``Namespaced`` is added to a ``List`` field that is already ``External`` and stored as a folder. The items
of such a list may sit directly in the folder or in nested sub-folders; each sub-folder is one namespace
segment, and the loader prefixes the item's ``name`` with the segments, joined by ``separator``:

.. code-block:: python

    from flync.core.annotations import External, Namespaced

    services: Annotated[List[SOMEIPServiceInterface], External(), Namespaced()] = Field()

.. code-block:: text

    services/
      ets.flync.yaml            name: ets            ->  ets
      abc/ets.flync.yaml        name: ets            ->  abc::ets
      abc/def/ets.flync.yaml    name: ets            ->  abc::def::ets

The name is qualified before validation, so the model, its uniqueness checks and registries only ever see the
qualified name, and every reference to the object must use it. Items without a sub-folder are unchanged.
Saving splits the qualified name again, so no separator reaches a file name. The helpers live in
``flync.core.base_models.namespace`` (``qualify_name``, ``split_qualified_name``).

Rules: every directory inside a namespaced list is a namespace (an item cannot be a folder), a folder name must
not contain the separator, and the annotation is ignored on a field stored as a single file.

Combining annotations
---------------------

A field can be declared as either ``External`` **or** ``Implied`` - they are mutually exclusive.
If both are needed, split the logic into separate helper properties. ``Reference`` is orthogonal
and may be combined with ``Field`` constraints, as ``SOMEIPServiceDeployment.service`` does.


Key points
----------

* Choose the appropriate ``NamingStrategy`` to control file naming.
* Use ``OutputStrategy.FOLDER`` when a field naturally maps to multiple files (e.g. controllers).
* ``ImpliedStrategy.FOLDER_NAME`` is handy for identifiers that follow the directory layout.
* The annotation on a field *is* the repository layout a config author sees - the expected tree
  is documented at :ref:`writing_flync_config`. Changing one changes the other.
