.. _model_development:

=======================
Model Development Guide
=======================

This guide documents the modelling conventions of ``flync.core`` and ``flync.model`` — what
makes a new class, field, or validator feel native to FLYNC. Nearly every rule here is enforced
somewhere — by ``mypy`` with the pydantic plugin, by ``scripts/ci/check_lazy_typing.py``, by the
model docstring check, by the error catalog tooling, or by SonarQube — and each page names the
gate that backs it, so you can tell a checked rule from a convention.

.. toctree::
   :maxdepth: 2
   :hidden:

   model_patterns
   structure_and_polymorphism
   validators_and_errors

.. grid:: 1 1 2 2

   .. grid-item-card:: :doc:`model_patterns`

      Anatomy of a model: base class, fields, docstrings, private attributes, typing rules.

   .. grid-item-card:: :doc:`structure_and_polymorphism`

      How fields map to the repository layout, and how variant types are discriminated.

   .. grid-item-card:: :doc:`validators_and_errors`

      Choosing a validator, raising catalogued errors, pinning them in tests.

Rules at a glance
-----------------

* Every model extends :class:`~flync.core.base_models.base_model.FLYNCBaseModel` —
  ``extra="forbid"`` and the dump behaviour come with it.
* Every field is documented in the class docstring's NumPy ``Parameters`` section, with a
  ``:class:`` cross-reference for its type and the default stated — as a ``", optional"`` suffix
  or in the description. ``Literal`` tags and ``default_factory`` collections are exempt.
* Variant types carry a ``Literal`` tag field and are referenced with
  ``Field(discriminator=...)`` — never branched on with ``if``/``else`` over dict keys.
* Private attributes are written ``_name: T | None = None``; ``PrivateAttr(default=...)`` is
  no longer used anywhere in ``src/``.
* New code uses PEP 604 unions (``A | B``, ``X | None``) — a convention SonarQube checks, not
  something the tree already satisfies everywhere. Annotations are not quoted unless the name is
  genuinely unbound at that point, which ``check_lazy_typing.py`` does gate.
* ``@model_validator(mode="after")`` methods return ``typing.Self``.
* Validation failures raise ``err_minor`` / ``err_major`` / ``err_fatal`` from
  :mod:`flync.core.utils.exceptions` with a ``Category`` and a globally unique ``error_number``;
  warnings use ``warn`` and are *not* raised. New ids come from ``flync errors get-next-number``,
  the catalog is brought in step with ``flync errors sync``.
* Negative tests pin the exact id with ``assert_single_error`` and ``assert_single_warning``
  from ``tests/error_assertions.py``.

Further reading in the SDK reference: :ref:`field_annotations`, :ref:`error_propagation`.
