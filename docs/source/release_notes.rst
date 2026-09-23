:orphan:

.. _release_notes:

Release Notes
=============

.. seealso::

   For a detailed, step-by-step description of how the FLYNC configuration model and public
   API changed between releases (and what you must update to migrate a project), see the
   :doc:`model_change_history`.

Release 0.15
------------

JSON Schema export
''''''''''''''''''

``flync.sdk.utils.model_schema`` exports the FLYNC model as a set of JSON Schema (draft 2020-12)
files, one per Pydantic model class. ``dump_model_schemas(FLYNCModel, "schemas")`` writes
``FLYNCModel.schema.json`` plus one file for every nested class and enum, with ``$ref`` entries pointing at the sibling files
(``"$ref": "ECU.schema.json"``) instead of a bundled ``$defs`` section. ``build_model_schemas``
returns the same documents as dictionaries. Pass ``base_uri`` to give every file an absolute
``$id`` when the schemas are published. The same export is available on the command line as
``flync schema <output_dir>``.

Field descriptions come from ``Field(description=...)`` when set and otherwise from the ``Parameters``
section of the class docstring, so the schemas document the same fields as the API reference.


Model Development Guide
'''''''''''''''''''''''

A new documentation section, :doc:`development/index` was added.
