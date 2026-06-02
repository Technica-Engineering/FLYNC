Best Practices
==============

Validation in CI
----------------

Use ``--quiet`` combined with a non-zero exit code check to gate pipelines on
workspace validity:

.. code-block:: bash

   flync validate /path/to/workspace --quiet || exit 1


Workspace paths
---------------

Always pass an absolute path or resolve relative paths before invoking the CLI.
The CLI does not search parent directories for workspaces.

Java requirement
----------------

The ``generate-system-uml`` command shells out to PlantUML which requires Java.
Verify that ``java -version`` works in the same environment before using this command.
