Quick Start
===========

Installation
------------

``flync_converter`` is included in the main **flync** package. For installation instructions, see :doc:`../installation`.

CLI (Recommended)
-----------------

The CLI is the recommended way to use ``flync_converter``. It provides a streamlined interface with built-in help, format auto-detection, and interactive options.

CLI - Single Conversion
^^^^^^^^^^^^^^^^^^^^^^^

The source and destination are always **folders**, not individual files. Each one is a subcommand with its path (``-p``) and format (``-f``).

.. code-block:: bash

   # convert from FLYNC workspace to FLYNC workspace
   flync-converter convert source -p ./flync_source -f flync destination -p ./flync_output -f flync

   # convert FLYNC to DBC
   flync-converter convert source -p ./flync_source -f flync destination -p ./dbc_output -f dbc

   # convert YAML to FLYNC
   flync-converter convert source -p ./yaml_source -f yaml destination -p ./flync_output -f flync

Additional converter options are passed as ``--<field>`` options of the subcommand they apply to. List them with:

.. code-block:: bash

   flync-converter convert source -f yaml --help

CLI - Interactive TUI
^^^^^^^^^^^^^^^^^^^^^

.. note::

   The interactive TUI requires the ``tui`` extra: ``pip install "flync[tui]"`` (or ``uv sync --extra tui`` from a checkout).

.. code-block:: bash

   flync-converter -i
   # or equivalently:
   flync-converter tui
   flync-converter-interactive

The TUI opens a split-panel screen: source on the left, destination on the right. Pick a format from each dropdown, fill in the config fields, and click **Convert**. Output streams live in a log panel at the bottom.

List available converters
^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

   flync-converter list-converters

.. note::

   Built-in converters (flync, yaml, json, dbc) are always available. Additional converters from plugins are automatically discovered if the plugin package is installed via ``pip install``. For plugin development and debugging, see :doc:`plugin_guide/local_development`.

Desktop GUI
^^^^^^^^^^^

.. note::

   The desktop GUI requires the ``gui`` extra: ``pip install "flync[gui]"`` (or ``uv sync --extra gui`` from a checkout).

.. code-block:: bash

   flync-converter --gui
   # or
   flync-converter-gui

Opens the PySide6 desktop application with the same split-panel layout as the TUI but as a native window.

Python API
----------

.. code-block:: python

   from flync_converter import convert
   from flync_converter import registry
   import logging

   # set your desired logging level
   logging.basicConfig(level=logging.DEBUG)

   # load plugins to get available converters
   registry.load_plugins()


   # default: convert from FLYNC
   convert(
       source="path/to/flync_source",
       destination="path/to/output",
       destination_type="json",
   )

   # convert FLYNC to DBC
   convert(
       source="path/to/flync_source",
       destination="path/to/dbc_output",
       destination_type="dbc",
   )

   # convert from YAML to FLYNC
   convert(
       source="path/to/yaml_folder",
       destination="path/to/flync_output",
       source_type="yaml",
   )

Next Steps
----------

- :doc:`usage` - deeper usage patterns
- :doc:`cli` - all commands and options
- :doc:`plugin_guide/introduction` - add your own formats

Multiple sources and outputs
----------------------------

Repeat ``source`` and ``destination`` on the same ``convert`` command. The
sources are merged in order and the result is written to every destination.
Sources must come before destinations::

   flync-converter convert \
     source -p ./source_a -f flync \
     source -p ./source_b -f yaml \
     destination -p ./merged_json -f json \
     destination -p ./merged_yaml -f yaml

See :doc:`cli` for the conflict policy and the deprecated flat ``-s/-o`` form.
