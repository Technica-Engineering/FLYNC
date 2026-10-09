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

The report also holds structured data. ``reports/report.yaml`` records the converters, the outcome (with the
error when the conversion failed) and the counts of the decoded model, written by the reporters passed to
``convert(..., reporters=...)``. Each converter, source or destination,
records what it ``skipped``, what its format leaves ``unsupported`` and any ``custom`` data through
``self.report``; that is written into its folder by the reporters it lists in ``reporters``: ``report.yaml`` by
default, ``report.json`` with ``JsonReporter``, or a format added by subclassing ``BaseReporter``. The built-in
converters report the files they read or write; the FLYNC converter its workspace diagnostics; the DBC converter the
model and DBC content it cannot convert, which it also logs, together with the ``cantools`` records.

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

J1939 node modeling
'''''''''''''''''''

New in this release: J1939 (SAE J1939) modeling over CAN 2.0B. A J1939 node is modeled as a
:class:`~flync.model.flync_4_ecu.can_interface.CANInterface` that declares a 64-bit ``j1939_name`` and an
optional preferred ``source_address`` (the SA the node claims at runtime through address claiming, J1939-81).
Each controller that participates in J1939 exposes one such interface.

* J1939 frames are declared on a :class:`~flync.model.flync_4_bus.can_bus.CANBus` as
  :class:`~flync.model.flync_4_signal.frame.J1939Frame` (``type: j1939``). A J1939 frame carries a single
  Parameter Group, identified by its PGN (priority, PDU format, PDU specific, data and extended data pages),
  and always has an 8-byte data field.
* A node lists the J1939 frames it sends / receives by PGN via ``j1939_sender_frames`` and
  ``j1939_receiver_frames``, referencing a frame by ``(bus_ref, pgn)``.
* ``j1939_name`` is the mandatory identity of a J1939 node; ``source_address`` is optional and claimed
  at runtime. Declaring an SA without a NAME (or frame references without a NAME) is rejected.
* A bus reached by a J1939 node may only carry ``J1939Frame`` frames, and every referenced PGN must resolve
  to a frame declared on the referenced bus. J1939 frames cannot be addressed over classical CAN IDs.

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
