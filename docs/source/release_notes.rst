:orphan:

.. _release_notes:

Release Notes
=============

.. seealso::

   For a step-by-step description of how the FLYNC configuration model and public API changed between
   releases (and what you must update to migrate a project), see the :doc:`model_change_history`.

Release 0.16
------------

Incremental reloads rebuild the model's wiring
''''''''''''''''''''''''''''''''''''''''''''''

``FLYNCWorkspace.update_document`` now leaves a model wired exactly as a full load wires it, however often a document is
reloaded. The links between ports, switch ports and interfaces, the sockets bound to each IP address, the derived
IPv6 solicited-node multicast memberships and the multicast groups provisioned on switch VLANs are rebuilt on each
revalidation instead of being added again to the components the reload reuses. A link removed from a topology file is
gone after the reload, a socket moved to another address leaves the old one, a switch stops carrying a group whose last
sender is removed, and the time a reload takes no longer grows with each save. Multicast groups written in a switch file
are kept.


Saved switch files keep only the authored multicast groups
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

Saving a model writes the ``multicast`` groups of a switch VLAN as they were authored. The groups and ports the model
provisions from the multicast paths are rebuilt on each load and are no longer written next to the authored ones. A
switch file saved by an earlier release may already hold such groups; they load as authored, so remove them by hand
where the multicast paths provide them.


Multi-gigabit BASE-T and BASE-T1 speeds
'''''''''''''''''''''''''''''''''''''''

``BASET`` and ``BASET1`` MDI configs now also accept 2500, 5000, and 10000 Mbit/s.


LIN frames can be published by slaves and received by the master
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

``LINSlaveInterface`` gained ``sender_frames`` and ``LINMasterInterface`` gained ``receiver_frames``, so both roles
read like a CAN interface: ``sender_frames`` is what the node transmits, ``receiver_frames`` what it receives. A
frame published by a slave is listed in that slave's ``sender_frames`` and in the master's (and/or another slave's)
``receiver_frames``. A frame still has exactly one publisher (``FLYNC-CMN-MAJ-UNIQ-489``). A frame that a node sends
or receives must now also appear in one of the bus's ``schedule_tables`` (``FLYNC-TOP-MAJ-CONS-490``): the master
issues a header only for frames it schedules, so an unscheduled frame would never be transmitted. Workspaces that
already scheduled every frame they referenced load unchanged.


Namespaces for SOME/IP services and PDUs
''''''''''''''''''''''''''''''''''''''''

Services under ``communication/someip/services`` and PDUs under ``communication/channels/pdus`` may now be stored
in sub-folders, so two people can define an object with the same name in parallel. Every sub-folder is a
namespace segment: ``abc/def/CameraService.flync.yaml`` holding ``name: CameraService`` is loaded as
``abc::def::CameraService``. Objects outside any sub-folder keep their plain name, so existing workspaces load
unchanged.

The qualified name is the name everywhere after loading, so a ``pdu_ref`` to a PDU in a sub-folder must be written
``abc::PDU_Name``; the plain name only resolves a PDU stored directly in ``pdus``. Saving a workspace writes the
objects back into the same sub-folders. The behavior is declared per field with the new ``Namespaced`` annotation
(``flync.core.annotations``), next to ``External``; see :ref:`field_annotations`.


Internal model parts moved; some error ids changed module code
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

The private ``flync.model._model_parts`` package is gone. The ``FLYNCModel`` mixins now live in
``flync.core.utils.model_mixins``, the application-reference checks in ``flync.core.validators.app_references``,
and the check that a CAN (non-J1939) frame must not pack a PDU carrying an SPN is a validator of
:class:`~flync.model.flync_4_communication.FLYNCChannelConfig`. The public ``FLYNCModel`` API is unchanged.

Because the module segment of an error id follows the package the code lives in, these ids changed from
``FLYNC-GEN-...`` to ``FLYNC-CMN-...``: 169, 173, 174 (multicast), 367 (SPN on a CAN PDU), 409, 410, 411, 413,
414, 416 and 417 (application references). Update any suppression or assertion that matches them by full id.


Conditional ECU ports and topology
''''''''''''''''''''''''''''''''''

The reference documentation now states that only ``ecu_metadata.flync.yaml`` and ``controllers/`` are
required for every ECU. ``ports.flync.yaml`` is required only when the ECU has Ethernet ports or a switch,
and ``topology.flync.yaml`` only when it has internal connections. This matches the model defaults and
``examples/flync_example``, where CAN/LIN/J1939-only ECUs have neither file.

``validate --verbose`` debugs a partial node
'''''''''''''''''''''''''''''''''''''''''''''

``flync validate --verbose`` accepts ``--node`` and runs the same five layers (folder structure, YAML syntax,
schema, field values, system-wide) against that node type as the root model, so a single ECU, switch or
SOME/IP directory can be debugged layer by layer. Previously ``--verbose`` was silently ignored together with
``--node`` and only the summary tables were printed. ``run_debug`` takes the node as its second argument.

The example-validation gate (``scripts/ci/validate_examples.py``) runs ``--verbose``, so a failing example names
the layer its problem came from.


J1939 frames addressed by name or CAN id
''''''''''''''''''''''''''''''''''''''''

* J1939 frames are declared on a :class:`~flync.model.flync_4_bus.can_bus.CANBus` as
  :class:`~flync.model.flync_4_signal.frame.J1939Frame` (``type: j1939``). A J1939 frame carries a single
  Parameter Group, identified by its PGN (priority, PDU format, PDU specific, data and extended data pages),
  and always has an 8-byte data field.
* A node lists the J1939 frames it sends / receives via ``j1939_sender_frames`` and
  ``j1939_receiver_frames``. A
  :class:`~flync.model.flync_4_signal.j1939_frame_ref.J1939FrameRef` addresses its frame by ``frame_ref``
  (the frame name) and/or by ``can_id`` (the full on-bus CAN identifier, Source Address in its low byte);
  the bus is the ``bus_ref`` of the owning
  :class:`~flync.model.flync_4_ecu.can_interface.CANInterface`.
* ``j1939_name`` is the mandatory identity of a J1939 node; ``source_address`` is optional and claimed
  at runtime. Declaring an SA without a NAME (or frame references without a NAME) is rejected.
* Several J1939 frames on a bus may share a PGN, and a bus reached by a J1939 node may also carry classical
  CAN frames. J1939 frame names are unique per bus, and every referenced frame (by name or CAN id) must
  resolve to a J1939 frame declared on the interface's bus.
* ``J1939Frame`` names must be unique on a CAN bus: a node addresses a J1939 frame by name, so a duplicate
  is rejected (``FLYNC-BUS-MAJ-UNIQ-426``) instead of silently shadowing the frame declared earlier.

LIN frame references drop ``bus_ref``
'''''''''''''''''''''''''''''''''''''

A :class:`~flync.model.flync_4_ecu.lin_interface.LINFrameRef` in the ``sender_frames`` / ``receiver_frames`` of a
LIN interface now holds only ``frame_ref``. The bus is the ``bus_ref`` of the owning interface; the reference's own
``bus_ref`` was never used. ``flync migrate`` (``v0_15_to_0_16``) removes it from existing workspaces.

Variant Management
'''''''''''''''''''

A new optional model domain, :ref:`flync_4_variability <variability>`, lets one workspace hold every product
variant of a system, covering optional ECUs and architecture alternatives. A ``variability/`` folder declares
the feature model and the variants, and a ``variant_condition`` on an ECU's ``ecu_metadata`` or on a system
topology entry marks what varies. The loader resolves one variant before validation, so existing models and
validators are unchanged and workspaces without ``variability/`` load as before. ``flync validate`` checks
every variant, the new ``flync variants`` commands list, trace, and diff them, and the SDK can select,
validate and export variants. See :ref:`variability` and the examples in :ref:`variability_examples`.


Schema errors in optional documents are reported
''''''''''''''''''''''''''''''''''''''''''''''''

A schema error inside an existing document of an optional field - for example an out-of-range ``node_id`` in
``topology/ethernet_topology.flync.yaml``, or an unknown key in an ECU's ``topology.flync.yaml`` - was discarded
together with the document: the field was left out without a word, and only its consequences were reported, such
as unconnected ports or a topology "missing". The error is now reported in the document, at its line, and the
validation fails. A workspace that passed before because such a document was silently dropped now reports it.


Validation uses the workspace's configuration
''''''''''''''''''''''''''''''''''''''''''''''

``validate_workspace`` and ``flync validate`` read the ``.flync/config.yaml`` of a workspace folder when no
configuration is passed, as loading the workspace does. A workspace whose configuration changes how it is read,
such as its file extensions, was reported ``EMPTY`` or broken before.


MII-Lite
''''''''

:class:`~flync.model.flync_4_ecu.mii.MII` has a new ``lite`` flag (default ``false``) for MII without the TX_ER, RX_ER, CRS and COL
signals. It carries full duplex only.

New xMII type: QSGMII
'''''''''''''''''''''

:class:`~flync.model.flync_4_ecu.mii.QSGMII` is a new ``mii_config`` type: four 10/100/1000 Mbps channels over one serial link.

Structured converter options as JSON
''''''''''''''''''''''''''''''''''''

Converter configuration fields that are mappings or lists — for example ``package_paths`` and ``sender_ecus``
of the ARXML converter — are prompted, previewed and passed as JSON text in the CLI, the interactive prompt,
the TUI and the GUI. An empty value leaves the field unset so its default applies, and invalid JSON is reported
against the offending field. Nested model fields are shown in the preview but are not offered as command-line
options.
