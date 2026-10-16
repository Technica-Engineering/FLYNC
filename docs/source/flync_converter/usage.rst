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

Several sources and several outputs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``convert_many`` decodes every source into a FLYNC model, merges the models
into one and writes the merged model to every output:

.. code-block:: python

   from flync_converter import ConversionOutput, ConversionSource, convert_many

   result = convert_many(
       sources=[
           ConversionSource(path="buses/powertrain", converter_type="dbc"),
           ConversionSource(path="buses/body", converter_type="dbc"),
       ],
       outputs=[
           ConversionOutput(path="out/workspace", converter_type="flync"),
           ConversionOutput(path="out/export", converter_type="json", config={"report_min_log_level": "DEBUG"}),
       ],
   )
   print(len(result.model.ecus), [str(output.path) for output in result.written])

Every source and output is an endpoint: a folder, or a single file, with the
type of the converter that reads or writes it. ``converter_type`` is required
for a source and defaults to ``flync`` for an output. ``config`` is optional
and resolved per endpoint (see `Converter configuration file`_): a
configuration object, a mapping of fields, or the path of a configuration
file.

A request is rejected when an endpoint is listed twice, when a source and an
output are the same folder or one contains the other, or when a configuration
object points somewhere else than its endpoint's ``path``.

Nothing is written to an output before every source is decoded and merged.
When an output fails, the remaining outputs are still written and
``ConversionOutputError`` is raised at the end; its ``result`` lists what was
written and what failed. With ``fail_fast=True`` the first failing output
raises its own exception instead.

The result holds the merged ``model``, the ``decoded`` sources, the
``written`` outputs, the ``failures`` and the merge ``conflicts``.

Merging
"""""""

The models are merged on their dumped form and the result is validated once,
as one system:

* content present in one source only is taken as it is;
* objects are merged field by field;
* lists of objects are merged item by item when the items can be told apart:
  every item has a ``name`` that is unique in its list, or failing that an
  ``id`` that is unique in its list. An ECU present in two sources becomes one
  ECU carrying the content of both;
* anything else that differs is a conflict: a value, or a list whose items
  cannot be told apart. Such a list is kept whole from one source.

``on_conflict`` decides a conflict:

``first`` (default)
    The value of the earlier source is kept.

``last``
    The value of the later source is kept.

``error``
    ``ModelMergeConflictError`` is raised, naming the path and both sources.

Every conflict resolved under ``first`` or ``last`` is logged as a warning,
returned in ``result.conflicts`` and recorded in the conversion report. Every
converter writes its own model metadata, so merging sources of different
formats always reports conflicts under ``metadata``.

Conversion manifest
"""""""""""""""""""

A conversion can be stored as a YAML file holding the arguments of
``convert_many``. Paths are relative to the folder the file is in::

   on_conflict: first
   sources:
     - {path: buses/powertrain, converter_type: dbc}
     - {path: buses/body, converter_type: dbc, config: {baud_rate_default: 250000}}
   outputs:
     - {path: out/workspace, converter_type: flync}
     - {path: out/export, converter_type: json}

.. code-block:: python

   from flync_converter import convert_request

   result = convert_request("conversion.yaml")

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

Every conversion writes a report into the ``.flync`` metadata directory of the
folders it works with. Each source and each output holds the report of its own
converter::

    <endpoint>/.flync/reports/<converter_name>/config.yaml  configuration the converter ran with
    <endpoint>/.flync/reports/<converter_name>/logs.txt     that converter's records
    <endpoint>/.flync/reports/<converter_name>/...          files the converter writes itself

Every output also holds the report of the conversion as a whole::

    <output>/.flync/reports/logs.txt     every record of the conversion
    <output>/.flync/reports/report.yaml  inputs, outputs, merge conflicts, model counts, status

For example, converting a FLYNC workspace to YAML outputs::

    path/to/workspace/.flync/reports/flync/config.yaml
    path/to/workspace/.flync/reports/flync/logs.txt
    path/to/output/.flync/reports/logs.txt
    path/to/output/.flync/reports/report.yaml
    path/to/output/.flync/reports/yaml/config.yaml
    path/to/output/.flync/reports/yaml/logs.txt

A source or output that is a single file uses the folder the file is in. A
reports folder that cannot be written is skipped with a warning, and the
conversion runs all the same.

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
       subgraph source_reports["path/to/workspace/.flync/reports/"]
           source_log["flync/logs.txt"]
       end
       subgraph reports["path/to/output/.flync/reports/"]
           shared["logs.txt"]
           destination_log["yaml/logs.txt"]
           destination_files["yaml/…<br/>(files written to report_dir)"]
       end
       driver --> shared
       source --> shared
       source --> source_log
       destination --> shared
       destination --> destination_log
       destination -. report_dir .-> destination_files

The conversion log captures the main converter logger (``flync_converter``), so
it holds the records of the conversion itself and of every converter, plus the
records of the libraries the converters delegate to (for example ``flync.sdk``
for the FLYNC converter). A converter's own ``logs.txt`` holds only the records
that converter and its libraries wrote while it was running, so it is a subset
of the conversion log, also when several sources use the same converter.

Converter configuration file
----------------------------

A folder stores what belongs to the converters that work with it, one folder
per converter, next to the workspace configuration::

    <folder>/.flync/converters/<converter_name>/config.yaml
    <folder>/.flync/converters/<converter_name>/sideload/

``config.yaml`` is the converter's stored configuration. It serves the
converter in both directions, whether the folder is read or written.
``sideload/`` is the location of extra data read and written with the folder.

Several outputs of one converter therefore keep separate configurations by
being separate folders: each one reads its own stored file, and may be given
its own values on top.

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

In Python, ``source_config`` / ``destination_config``, and the ``config`` of a
``ConversionSource`` or ``ConversionOutput``, take either the path of a
configuration file, which replaces the stored file, or a configuration object,
whose set fields (see ``model_fields_set``) override the stored file. The
``config`` of an endpoint also takes a mapping of fields, layered the same way.
Folder loaders such as the YAML and JSON converters never read the ``.flync``
folder, so stored configurations and reports do not end up in the model.

The source side reads ``<source>/.flync/converters/<converter_name>/config.yaml``.
A source that is a single file, such as a ``.dbc`` file, has no stored
configuration. For example, storing
``my_workspace/.flync/converters/dbc/config.yaml`` with::

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

Reporting is controlled per source and output, by three fields of its
converter's configuration. The conversion log and ``report.yaml`` follow the
configuration of the output they are written to:

``report_enabled``
    Whether the report of this source or output is written. Defaults to
    ``True``.

``report_dir``
    Folder the reports of this source or output are written to, for a source
    that must not be written to, for example. A relative path is resolved
    against the folder itself. Defaults to ``<folder>/.flync/reports``. Two
    converters of one type cannot share a reports folder.

``report_min_log_level``
    Lowest severity captured: a level name (``"DEBUG"``, ``"INFO"``,
    ``"WARNING"``, ``"ERROR"``, ``"CRITICAL"``, case-insensitive) or a number.
    Stored as the level name. Defaults to ``"INFO"``.

Each ``logs.txt`` holds the records of the latest conversion only. When a
conversion fails, the exception and its traceback are the last entry of the
conversion log. Only loggers
under ``flync_converter`` are captured, and only the level of the
``flync_converter`` logger is changed during the conversion. Loggers exist once
per process, so run one conversion at a time per process.

Next to the logs, the report holds structured data, again shared and per
converter. ``reports/report.yaml`` describes the conversion as a whole::

    inputs:
      - {converter: flync, path: examples/flync_example, report: examples/flync_example/.flync/reports/flync}
    outputs:
      - {converter: yaml, path: path/to/output, report: path/to/output/.flync/reports/yaml}
    merge:                       # with several inputs
      policy: first
      conflicts:
        - {path: metadata.author, kept: System_Architect, dropped: dbc-converter, kept_source: ..., dropped_source: ...}
    model: {ecus: 16, apps: 0, can_buses: 4, lin_buses: 1, shared_pdus: 14, ethernet_pdus: 4}
    status: succeeded            # or failed, with the error

An output that failed while the others were written carries its ``error``.

Each converter's folder holds what that converter recorded, source and
destination alike: model content it ``skipped``, content its format leaves
``unsupported``, and any ``custom`` data. Groups with nothing in them are left
out, and a converter that recorded nothing has no such file. The converter's
reporters decide the files: ``report.yaml`` by default, ``report.json`` for a
converter that lists the JSON reporter, or any format a plugin adds (see
:doc:`plugin_guide/creating_plugin`).

The conversion report is written the same way, by the reporters passed to
``convert`` or ``convert_many``, ``report.yaml`` by default:

.. code-block:: python

    from flync_converter import convert
    from flync_converter.base import JsonReporter, YamlReporter

    convert("path/to/source", "path/to/output", destination_type="yaml",
            reporters=(YamlReporter(), JsonReporter()))

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
