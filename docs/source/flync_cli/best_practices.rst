Best Practices
==============

Validation in CI
----------------

.. code-block:: bash

   flync validate /path/to/workspace || exit 1

Use ``--verbose`` locally to debug a workspace in detail when a workspace fails and you need to see exactly in which
layer the problem occured (folder structure, YAML syntax, schema, field values, system-wide) .


Workspace paths
---------------

Every command's path argument is optional and falls back to the path stored with
``flync config set`` - convenient for a single session, but do not rely on it in CI: pass the
path explicitly there, since the stored path is user- and machine-local.

When passing a path explicitly, always pass an absolute path or resolve relative paths before
invoking the CLI. The CLI does not search parent directories for workspaces.

Java requirement
----------------

The ``generate-system-uml`` command shells out to PlantUML which requires Java.
Verify that ``java -version`` works in the same environment before using this command.
