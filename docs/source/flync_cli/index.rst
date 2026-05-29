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
- **info** - Display workspace inventory (ECUs, controllers, switches, ports, sockets, services, IP addresses).
- **vlan-info** - Show per-VLAN membership, interfaces, and IP addresses.
- **service-info** - Inspect SOME/IP service deployments across ECUs.
- **generate-system-uml** - Generate PlantUML system topology diagrams.

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
