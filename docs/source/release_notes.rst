:orphan:

.. _release_notes:

Release Notes
=============

.. seealso::

   For a detailed, step-by-step description of how the FLYNC configuration model and public
   API changed between releases (and what you must update to migrate a project), see the
   :doc:`model_change_history`.

Release 0.15
------------

Converter configuration file and conversion log
'''''''''''''''''''''''''''''''''''''''''''''''

Every conversion writes a report into ``<destination>/.flync/reports/``: a shared ``logs.txt`` for the whole
conversion, and one folder per converter (source and destination) holding the configuration it ran with
(``config.yaml``), its own ``logs.txt`` and any files it writes to its ``report_dir``. Converters list the loggers that belong to them in
``report_loggers``; the shared log captures the ``flync_converter`` logger and every listed logger, and no other
logger is captured or has its level changed. A failed conversion ends the shared log with the exception and its
traceback. The FLYNC converter lists ``flync.sdk`` and logs the workspace diagnostics, one line per finding with
its error id, after loading or writing a workspace.

Converter configurations are stored per workspace in ``<workspace>/.flync/converters/<converter_name>.yaml``.
Both the source and the destination configuration are resolved from the field defaults, then a configuration
file, then the values set by the caller. The file is the one passed with ``--src-config`` / ``--dst-config``,
otherwise the one stored in that side's workspace. In Python, ``source_config`` / ``destination_config`` accept
either a configuration object or the path of a configuration file. The YAML and JSON converters no longer read
files inside a ``.flync`` folder when loading a folder. The resolved destination configuration is written back after every conversion (unless
``persist_config`` is ``False``); ``ConverterConfig.to_yaml_file`` writes one explicitly. ``ConverterConfig``
is now frozen and rejects unknown fields.

Reporting is configured through the ``report_enabled`` and ``report_min_log_level`` fields of the destination
configuration (``--dst-report-enabled`` and ``--dst-report-min-log-level`` on the command line). The
``FLYNC_REPORT_ENABLED`` and ``FLYNC_REPORT_MIN_LOG_LEVEL`` environment variables and the ``report_enabled`` /
``min_log_level`` arguments of ``convert`` and ``Converter.convert`` are removed. Unknown level names and
non-boolean ``report_enabled`` values raise a validation error.

JSON Schema export
''''''''''''''''''

``flync.sdk.utils.model_schema`` exports the FLYNC model as a set of JSON Schema (draft 2020-12)
files, one per Pydantic model class. ``dump_model_schemas(FLYNCModel, "schemas")`` writes
``FLYNCModel.schema.json`` plus one file for every nested class and enum, with ``$ref`` entries pointing at the sibling files
(``"$ref": "ECU.schema.json"``) instead of a bundled ``$defs`` section. ``build_model_schemas``
returns the same documents as dictionaries. Pass ``base_uri`` to give every file an absolute
``$id`` when the schemas are published. The same export is available on the command line as
``flync schema <output_dir>``.

Field descriptions come from ``Field(description=...)`` when set and otherwise from the ``Parameters``
section of the class docstring, so the schemas document the same fields as the API reference.


Measurement Points (Instrumentation)
''''''''''''''''''''''''''''''''''''''

A new optional model domain, :ref:`flync_4_instrumentation <instrumentation>`, declares the
measurement points of a network. Each measurement point taps exactly one medium - a
point-to-point Ethernet link (one or two ECU ports, one CMP interface id per direction), an
Ethernet shared-medium segment, a CAN bus, or a LIN bus - and carries the ASAM CMP / TECMP
interface ids that capture it.

The points are grouped under an :class:`~flync.model.flync_4_instrumentation.Instrumentation`
wrapper on the root model (``flync_model.instrumentation``) that maps to the ``instrumentation/``
folder; ``measurement_points`` loads from ``instrumentation/measurement_points.flync.yaml``. The
overlay stays optional - a workspace with no ``instrumentation/`` folder has
``flync_model.instrumentation`` as ``None``.


Model Development Guide
'''''''''''''''''''''''

A new documentation section, :doc:`development/index` was added.
