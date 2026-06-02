.. _quickstart:

######################
Quickstart to FLYNC
######################

This guide helps you get up and running with **FLYNC** quickly. In just a few steps, you will install the main packages, create your first configuration model, and validate it using the FLYNC SDK.

.. warning:: If you haven't set up your environment yet, head over to the :doc:`installation`  first.

----------

Where to Find FLYNC
-------------------

FLYNC is distributed as an open-source project and can be accessed via its official repository and package distribution channels.

The public project contains:

- **FLYNC configuration models**.
- **FLYNC SDK**
- **FLYNC CLI**
- **FLYNC converters**
- **Documentation and reference materials**

For more information about the project, refer to the `FLYNC Homepage <https://flync-language.com/>`_.

----

Project Namespaces
--------------------

.. list-table::
   :header-rows: 1
   :widths: 20 20 45 20

   * - Namespace
     - Location
     - Purpose
     - Go to
   * - ``flync``
     - ``src/flync/``
     - The **core library** - includes the FLYNC language model, SDK, validation engine, and workspace logic.
       This is the foundation that everything else builds on.
     - :doc:`FLYNC Reference <flync_reference>`
   * - ``flync_cli``
     - ``src/flync_cli/``
     - A **Typer-based command-line interface** for day-to-day engineering tasks:
       workspace validation, node information, VLAN inspection, SOME/IP service summaries,
       and system-level PlantUML diagram generation.
     - :doc:`FLYNC CLI <flync_cli/index>`
   * - ``flync_converter``
     - ``src/flync_converter/``
     - A **pluggy-powered converter framework** that transforms data between formats
       (JSON, YAML, FLYNC, and any third-party format added via plugins).
       Ships with a scriptable CLI, an interactive Textual TUI, and a PySide6 desktop GUI.
     - :doc:`FLYNC Converter <flync_converter/index>`

----------

Installation
------------

To install **FLYNC** follow the standard installation procedure for your environment.

.. note:: For detailed platform-specific instructions, dependency information, and advanced setup options, please refer to the :doc:`Installation Guide <installation>`.

------------

Next Steps
----------

Now that you have successfully installed **FLYNC**, you can explore more advanced topics:

- :doc:`Examples <flync_example>` — Realistic configuration samples for common SDV scenarios
- :doc:`FLYNC Reference <flync_reference>` — Complete language and model specification. Here you can learn how to author and validate your first FLYNC configuration.

These resources will help you model more complex architectures, services, and communication patterns.

-------

You are now ready to start building **Configuration-as-Code workflows** with FLYNC!
