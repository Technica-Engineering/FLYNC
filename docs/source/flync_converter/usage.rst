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

.. note::

   The interactive TUI requires the ``tui`` extra: ``pip install "flync[tui]"`` (or ``uv sync --extra tui`` from a checkout).

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

Conversion reports
------------------

Every conversion writes a report into the destination workspace's ``.flync``
metadata directory: one shared log for the whole conversion, and one folder per
converter taking part in it, source and destination::

    <destination>/.flync/reports/logs.txt                      whole conversion
    <destination>/.flync/reports/<converter_name>/config.yaml  configuration the converter ran with
    <destination>/.flync/reports/<converter_name>/logs.txt     that converter's records
    <destination>/.flync/reports/<converter_name>/...          files the converter writes itself

For example, converting a FLYNC workspace to YAML outputs::

    path/to/output/.flync/reports/logs.txt
    path/to/output/.flync/reports/flync/config.yaml
    path/to/output/.flync/reports/flync/logs.txt
    path/to/output/.flync/reports/yaml/config.yaml
    path/to/output/.flync/reports/yaml/logs.txt

``config.yaml`` records every value of the configuration that converter ran
with, defaults and ``config_path`` included. It describes the conversion that
produced the report, while the stored configuration (see below) is the
starting point of the next one.

The loggers of that conversion and the files they are written to:

.. mermaid::

   flowchart LR
       subgraph loggers["Loggers during a flync → yaml conversion"]
           driver["flync_converter<br/>(conversion driver)"]
           source["flync_converter.converters.flync_converter<br/>flync.sdk<br/>(source: flync)"]
           destination["flync_converter.converters.yaml_converter<br/>(destination: yaml)"]
       end
       subgraph reports["path/to/output/.flync/reports/"]
           shared["logs.txt"]
           source_log["flync/logs.txt"]
           destination_log["yaml/logs.txt"]
           destination_files["yaml/…<br/>(files written to report_dir)"]
       end
       driver --> shared
       source --> shared
       source --> source_log
       destination --> shared
       destination --> destination_log
       destination -. report_dir .-> destination_files

The shared log captures the main converter logger (``flync_converter``), so it
holds the records of the conversion itself and of every converter, plus the
records of the libraries the converters delegate to (for example ``flync.sdk``
for the FLYNC converter). A converter's own ``logs.txt`` holds only that
converter's records and those of its libraries, so it is a subset of the
shared log.

Converter configuration file
----------------------------

A workspace stores the configuration of the converters that work with it, one
file per converter, next to the workspace configuration::

    <workspace>/.flync/converters/<converter_name>.yaml

The file holds only values that differ from the defaults, plus the FLYNC
version that last wrote it. ``config_path`` is never stored, because it is the
location the file belongs to. Unknown keys are rejected, so a typo in a
hand-edited file is reported instead of ignored.

Every conversion resolves the source and the destination configuration in
three layers, each overriding the one before:

1. The field defaults of the converter's configuration class.
2. A configuration file: the one given with ``--src-config`` /
   ``--dst-config``, otherwise the file stored in that side's workspace, when
   it exists.
3. The values set on the command line with ``--src-<field>`` /
   ``--dst-<field>``. Options left unset do not override the file.

In Python, ``source_config`` / ``destination_config`` take either the path of
a configuration file, which replaces the stored file, or a configuration
object, whose set fields (see ``model_fields_set``) override the stored file.
Folder loaders such as the YAML and JSON converters never read the ``.flync``
folder, so stored configurations and reports do not end up in the model.

The source side reads ``<source>/.flync/converters/<converter_name>.yaml``. A
source that is a single file, such as a ``.dbc`` file, has no stored
configuration. For example, storing ``my_workspace/.flync/converters/dbc.yaml``
with::

   baud_rate_default: 250000

makes every DBC conversion from ``my_workspace`` use a ``250000`` default baud
rate, without any option:

.. code-block:: bash

   flync-converter convert -s my_workspace -o path/to/output -sf dbc -of yaml

To use the same settings across several workspaces, keep them in one file and
pass it explicitly. It replaces the stored file for that conversion, and
options given on the command line still override it:

.. code-block:: bash

   flync-converter convert -s my_workspace -o path/to/output -sf dbc -of yaml \
       --src-config shared/dbc.yaml --src-baud-rate-default 500000

After the destination configuration is resolved, it is written back to the
destination's stored file, so the next conversion into the same destination
starts from it. Set ``persist_config`` to ``False`` to skip that write. The
source configuration is never written.
:meth:`~flync_converter.ConverterConfig.to_yaml_file` writes a file regardless
of ``persist_config``:

.. code-block:: python

   from flync_converter import ConverterConfig
   from flync_converter.base.converter_config import converter_config_file

   config = ConverterConfig(config_path="path/to/output", report_min_log_level="DEBUG")
   config.to_yaml_file(converter_config_file("path/to/output", "flync"))

   loaded = ConverterConfig.from_workspace("path/to/output", "flync")

Controlling reports
~~~~~~~~~~~~~~~~~~~

Reporting is controlled by two fields of the destination configuration:

``report_enabled``
    Whether the report (shared log and converter folders) is written.
    Defaults to ``True``.

``report_min_log_level``
    Lowest severity captured: a level name (``"DEBUG"``, ``"INFO"``,
    ``"WARNING"``, ``"ERROR"``, ``"CRITICAL"``, case-insensitive) or a number.
    Stored as the level name. Defaults to ``"INFO"``.

Each ``logs.txt`` holds the records of the latest conversion only. When a
conversion fails, the exception and its traceback are the last entry of the
shared log. Only loggers
under ``flync_converter`` are captured, and only the level of the
``flync_converter`` logger is changed during the conversion. Loggers exist once
per process, so run one conversion at a time per process.

On the command line:

.. code-block:: bash

   flync-converter convert -s path/to/source -o path/to/output -sf yaml -of flync \
       --dst-report-min-log-level DEBUG

In Python:

.. code-block:: python

   from flync_converter import ConverterConfig, convert

   convert(
       source="path/to/source",
       destination="path/to/output",
       source_type="yaml",
       destination_type="flync",
       destination_config=ConverterConfig(
           config_path="path/to/output",
           report_enabled=True,          # set to False to disable the report
           report_min_log_level="DEBUG",
       ),
   )
