Usage
=====

Python API
----------

Convenience function
~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from flync_converter import convert

   convert(
       source="path/to/source",
       destination="path/to/output",
       destination_type="json",
       source_type="yaml",     # omit to auto-detect
   )

``Converter`` class
~~~~~~~~~~~~~~~~~~~

For more control, use the ``Converter`` class directly:

.. code-block:: python

   from flync_converter import Converter
   from flync_converter.base import ConverterConfig

   source_cfg = ConverterConfig(config_path="path/to/source")
   dest_cfg   = ConverterConfig(config_path="path/to/output")

   Converter().convert(
       source="path/to/source",
       destination="path/to/output",
       source_type="yaml",
       destination_type="json",
       source_config=source_cfg,
       destination_config=dest_cfg,
   )

When ``source_type`` is omitted the registry auto-detects the format from the source path.

CLI
---

Two entry points are available after installation:

.. list-table::
   :header-rows: 1

   * - Command
     - Purpose
   * - ``flync-converter``
     - Scriptable subcommands
   * - ``flync-converter-interactive``
     - Launches the interactive TUI directly

See :doc:`cli` for the full command reference.

Interactive TUI
---------------

``flync-converter-interactive``, ``flync-converter tui``, or ``flync-converter -i`` all open the same full terminal UI powered by `Textual <https://textual.textualize.io/>`_.

.. code-block:: bash

   flync-converter -i

The TUI is a single split-panel screen: source on the left, destination on the right. Pick a format from each dropdown and the config fields for that converter appear immediately below. Fill them in and click **Convert** — the conversion runs in a background thread and streams output into a log panel at the bottom.

Configuration forms are built automatically from each converter's Pydantic config model — no flags to remember, and validation errors appear inline. Plugin converters with extra fields (e.g. ``output_structure``, ``encoding``, ``indent``) have those fields rendered as inputs automatically, with no changes required to the TUI.

Supported Formats
-----------------

.. list-table::
   :header-rows: 1

   * - Name
     - Key
     - Reads
     - Writes
   * - FLYNC
     - ``flync``
     - yes
     - yes
   * - JSON
     - ``json``
     - yes
     - yes
   * - YAML
     - ``yaml``
     - yes
     - yes
   * - DBC
     - ``dbc``
     - no
     - yes

Additional formats can be added through :doc:`plugins <plugin_guide/introduction>`.
