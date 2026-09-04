.. _flync_cli:

FLYNC CLI
=========

The FLYNC CLI (``flync``) is a command-line tool for validating FLYNC workspaces,
inspecting network topology, and generating system UML diagrams.

To use it follow the :doc:`../installation`.
Now the ``flync`` command is available on your PATH.

Commands
--------

- **validate** - Load and validate a FLYNC workspace, reporting all errors.
- **info** - Command group displaying workspace inventory: ``ecus``, ``controllers``, ``switches``, ``ports``,
  ``ip``, ``sockets``, ``services``, ``instances``, ``vlans``.
- **filetree** - Export the expected filetree of a FLYNC configuration to a txt file.
- **generate-system-uml** - Generate PlantUML topology diagrams.
- **config** - Store, show, or clear the workspace path used when a command omits its path argument in a CLI session.
- **errors** - Inspect and maintain the :doc:`../error_catalog`.

Show all available commands
---------------------------

.. code-block:: bash

   flync --help
   flync <command> --help

Next Steps
----------

- See :doc:`usage` for all command options
- Understand :doc:`best_practices`
- Explore :doc:`common_usecases`



.. toctree::
   :hidden:

   usage
   best_practices
   common_usecases
