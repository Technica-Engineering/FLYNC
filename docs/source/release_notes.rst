:orphan:

.. _release_notes:

Release Notes
=============

.. seealso::

   For a step-by-step description of how the FLYNC configuration model and public API changed between
   releases (and what you must update to migrate a project), see the :doc:`model_change_history`.

Release 0.15
------------

SOME/IP eventgroup serialization
''''''''''''''''''''''''''''''''

Saving a workspace now writes the members of a SOME/IP eventgroup as references to the service's events and fields, instead of
a full copy of each event and field. An eventgroup member can be referenced by name or by identifier
(event ``id``, field ``notifier_id``). A name shared by several events/fields of the service is rejected with
``FLYNC-SOM-MIN-REF-421``; such members are referenced by identifier, and saving writes them that way.


YAML parsing on PyYAML
''''''''''''''''''''''

``ruamel.yaml`` is replaced by PyYAML (libyaml when available), which loads, composes and dumps documents roughly 7-18x faster.

Improve FLYNC_4_App
'''''''''''''''''''

Adding support for CAN and J1939 references. Also adding IPC with referencing support.

Workspace schema migrations
'''''''''''''''''''''''''''

``flync migrate <path>`` brings a workspace recorded by an older FLYNC up to the installed release. It compares the
``version`` stamp in ``.flync/config.yaml`` with the installed release, applies the registered migrations in order,
rewrites only the documents that change and records each migration in ``.flync/migrations/history.yaml``.
``--dry-run`` shows the plan; ``--init`` records the installed version without changing data.

The new ``migration_mode`` setting in ``.flync/config.yaml`` controls what happens on load: ``propose`` (default)
logs a warning, ``auto`` migrates before the model is loaded, ``off`` skips the check. Saving a workspace no longer
advances its version stamp while migrations are pending. A configuration that sets ``migration_mode`` cannot be read
by FLYNC 0.14 and older. See :ref:`migrations_reference`.

J1939 support
'''''''''''''

J1939 (SAE J1939 over CAN 2.0B) is now modeled and supported by the DBC converter.

**Model**

* A J1939 node is a :class:`~flync.model.flync_4_ecu.can_interface.CANInterface` with a mandatory 64-bit
  ``j1939_name`` and an optional preferred ``source_address`` (claimed at runtime, J1939-81). A source address or
  frame references without a NAME are rejected.
* Frames are declared on a :class:`~flync.model.flync_4_bus.can_bus.CANBus` as
  :class:`~flync.model.flync_4_signal.frame.J1939Frame` (``type: j1939``): one Parameter Group identified by its
  PGN, always with an 8-byte data field.
* A node lists the frames it sends and receives via ``j1939_sender_frames`` and ``j1939_receiver_frames``. A
  :class:`~flync.model.flync_4_signal.j1939_frame_ref.J1939FrameRef` carries only the ``pgn``; the bus is the
  ``bus_ref`` of the owning interface.
* A bus reached by a J1939 node may only carry ``J1939Frame`` frames, and every referenced PGN must resolve to a
  frame on that bus.

**DBC converter**

* J1939 databases are detected and converted in both directions.
* A DBC that fails cantools' strict signal-layout check (overlapping SPNs) is retried non-strictly and reported
  under ``dbc_strict_fallback``.
* Transport Protocol / multiplexed messages that the model cannot represent are skipped and reported instead of
  failing the conversion. Transport Protocol messages are recovered on decode by widening ``J1939Frame.length``
  (see :ref:`chg__0_14__0_15`).
* ``BU_:`` node names are preserved in both directions. J1939 broadcasts are attributed to the ``Vector__XXX``
  sender, with every declared node kept as a receiver.

Conversions with several sources and outputs
''''''''''''''''''''''''''''''''''''''''''''

``convert_many(sources, outputs)`` decodes every source, merges the models into one and writes the result to every
output. Objects are merged by ``name`` (or ``id`` where names are not unique) at every depth, so an ECU described by
two sources becomes one ECU. Conflicting values are resolved by ``on_conflict``: ``first`` (default) and ``last``
keep one value and log a warning, ``error`` raises ``ModelMergeConflictError``.

The call returns a ``ConversionResult`` (merged model, outputs written, conflicts). If an output fails, the others
are still written and ``ConversionOutputError`` is raised at the end, unless ``fail_fast`` is set. A conversion can
be stored as a YAML manifest and run with ``convert_request("conversion.yaml")``. ``convert()`` and
``Converter.convert()`` keep their signature.

Converter configuration and conversion reports
''''''''''''''''''''''''''''''''''''''''''''''

**Configuration**

* Configurations are stored per folder in ``<folder>/.flync/converters/<converter_name>/config.yaml``.
* Source and destination configurations resolve from field defaults, then a configuration file, then values set by
  the caller. The file is the one passed with ``--src-config`` / ``--dst-config``, otherwise the one stored in that
  side's workspace. In Python, ``source_config`` / ``destination_config`` accept a configuration object or a file
  path.
* The resolved destination configuration is written back after every conversion (unless ``persist_config`` is
  ``False``); ``ConverterConfig.to_yaml_file`` writes one explicitly.
* ``ConverterConfig`` is now frozen and rejects unknown fields.
* The YAML and JSON converters no longer read files inside a ``.flync`` folder when loading a folder.

**Reports**

* Every conversion writes a report into the ``.flync/reports/`` folder of each source and output. Each holds one
  folder per converter with its ``config.yaml``, its own ``logs.txt`` and any files written to its ``report_dir``;
  every output also holds a ``logs.txt`` for the whole conversion. A failed conversion ends the shared log with the
  exception and traceback. A reports folder that cannot be written is skipped with a warning.
* ``report_enabled``, ``report_min_log_level`` and ``report_dir`` are set per source and output in its converter
  configuration (``--dst-report-enabled`` and ``--dst-report-min-log-level`` on the command line). Unknown level
  names and non-boolean ``report_enabled`` values raise a validation error.
* The shared log captures the ``flync_converter`` logger and the loggers a converter lists in ``report_loggers``;
  no other logger is captured or has its level changed. The FLYNC converter lists ``flync.sdk`` and logs the
  workspace diagnostics, one line per finding with its error id.
* ``reports/report.yaml`` in every output records the ``inputs`` and ``outputs`` with their report folders, the
  merge conflicts, the counts of the merged model and the outcome (with the error on failure). It is written by the
  reporters passed to ``convert(..., reporters=...)``.
* Each converter records what it ``skipped``, what its format leaves ``unsupported`` and any ``custom`` data through
  ``self.report``. The reporters it lists in ``reporters`` write it into its folder: ``report.yaml`` by default,
  ``report.json`` with ``JsonReporter``, or a custom format via ``BaseReporter``. The built-in converters report the
  files they read or write; the FLYNC converter its workspace diagnostics; the DBC converter the content it cannot
  convert, together with the ``cantools`` records.

**Removed:** the ``FLYNC_REPORT_ENABLED`` and ``FLYNC_REPORT_MIN_LOG_LEVEL`` environment variables and the
``report_enabled`` / ``min_log_level`` arguments of ``convert`` and ``Converter.convert``.

JSON Schema export
''''''''''''''''''

``flync.sdk.utils.model_schema`` exports the FLYNC model as JSON Schema (draft 2020-12), one file per Pydantic
model class. ``dump_model_schemas(FLYNCModel, "schemas")`` writes ``FLYNCModel.schema.json`` plus one file for every
nested class and enum, linked by sibling ``$ref`` entries (``"$ref": "ECU.schema.json"``) instead of a bundled
``$defs`` section. ``build_model_schemas`` returns the same documents as dictionaries; ``base_uri`` gives every file
an absolute ``$id``. On the command line: ``flync schema <output_dir>``.

Field descriptions come from ``Field(description=...)``, otherwise from the ``Parameters`` section of the class
docstring, so the schemas match the API reference.

Measurement points (instrumentation)
''''''''''''''''''''''''''''''''''''

The new optional domain :ref:`flync_4_instrumentation <instrumentation>` declares the measurement points of a
network. Each point taps exactly one medium (a point-to-point Ethernet link with one or two ECU ports and one CMP
interface id per direction, an Ethernet shared-medium segment, a CAN bus or a LIN bus) and carries the ASAM CMP /
TECMP interface ids that capture it.

Points are grouped under :class:`~flync.model.flync_4_instrumentation.Instrumentation` on the root model
(``flync_model.instrumentation``), mapped to the ``instrumentation/`` folder; ``measurement_points`` loads from
``instrumentation/measurement_points.flync.yaml``. Without that folder, ``flync_model.instrumentation`` is ``None``.

xMII rework: USXGMII, USGMII, multi-port links
''''''''''''''''''''''''''''''''''''''''''''''

The xMII model moved from ``phy.py`` to :mod:`flync.model.flync_4_ecu.mii` and gained
:class:`~flync.model.flync_4_ecu.mii.USXGMII` and :class:`~flync.model.flync_4_ecu.mii.USGMII`. One link can carry
several logical ports through a ``channels`` list; the other ports on the link reference it with the new
``mii_subport_of`` and ``mii_subport_id`` fields. See :ref:`chg__0_14__0_15`.

Port extenders
''''''''''''''

A switch can control port extenders (chips that add ports to it) through ``port_extenders`` in
``switch.flync.yaml``. The extender's ports stay ordinary switch ports; it joins the switch through a ``tagged`` or
``channelized`` uplink. See :ref:`port_extender` and :ref:`chg__0_14__0_15`.

Stricter typing for ``flync.core`` and ``flync.model``
''''''''''''''''''''''''''''''''''''''''''''''''''''''

Both packages are now fully annotated; mypy enforces ``disallow_untyped_defs``, ``disallow_any_generics`` and
``warn_unreachable``. Fixes that came out of this:

* A MAC multicast endpoint without ``multicast_tx`` no longer requires a matching interface.
* ``InternalConnection.ecu`` returns the owning ECU instead of always ``None``.
* A socket with ``deployments: null`` no longer crashes the loader.
* A SOME/IP event or field without a ``name`` no longer crashes eventgroup resolution; the regular field
  validation reports the missing name.

The Python API changes (list fields that are no longer ``Optional``, the deprecated ``ecus`` argument of
``ECUPort.get_internal_connected_component()``, the removed ``FLYNCWorkspace.get_semantic_object_from_model()``)
are listed in the :ref:`model change history <chg__0_14__0_15>`.

Smaller changes
'''''''''''''''

* **Frame filter MAC lists:** ``FrameFilter.src_mac`` and ``dst_mac`` given as a list are validated element by
  element and stay a list. Previously only the last element's result was returned.
* **Conversion preview:** the converter shows the source, destination, non-default converter options and the
  equivalent command line before running. ``convert``, ``convert-interactive``, the TUI and the GUI all show it;
  ``--no-preview`` hides it.
* **Ctrl+C:** closes ``flync-converter-gui`` immediately, also during a conversion. Workspace loading (e.g.
  ``flync validate``, the SDK) stops cleanly: worker processes exit with status 130 instead of each printing a
  ``KeyboardInterrupt`` traceback.
* **Model Development Guide:** new documentation section :doc:`development/index`.
