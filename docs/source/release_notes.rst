:orphan:

.. _release_notes:

Release Notes
=============

.. seealso::

   For a step-by-step description of how the FLYNC configuration model and public API changed between
   releases (and what you must update to migrate a project), see the :doc:`model_change_history`.

Release 0.16
------------

``validate --verbose`` debugs a partial node
'''''''''''''''''''''''''''''''''''''''''''''

``flync validate --verbose`` accepts ``--node`` and runs the same five layers (folder structure, YAML syntax,
schema, field values, system-wide) against that node type as the root model, so a single ECU, switch or
SOME/IP directory can be debugged layer by layer. Previously ``--verbose`` was silently ignored together with
``--node`` and only the summary tables were printed. ``run_debug`` takes the node as its second argument.

The example-validation gate (``scripts/ci/validate_examples.py``) runs ``--verbose``, so a failing example names
the layer its problem came from.

Validation uses the workspace's configuration
''''''''''''''''''''''''''''''''''''''''''''''

``validate_workspace`` and ``flync validate`` read the ``.flync/config.yaml`` of a workspace folder when no
configuration is passed, as loading the workspace does. A workspace whose configuration changes how it is read,
such as its file extensions, was reported ``EMPTY`` or broken before.
