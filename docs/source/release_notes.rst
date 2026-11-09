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
reloaded. The links between ports, switch ports and interfaces, the sockets bound to each IP address and the derived
IPv6 solicited-node multicast memberships are rebuilt on each revalidation instead of being added again to the
components the reload reuses. A link removed from a topology file is gone after the reload, and the time a reload takes
no longer grows with each save.


Multi-gigabit BASE-T and BASE-T1 speeds
'''''''''''''''''''''''''''''''''''''''

``BASET`` and ``BASET1`` MDI configs now also accept 2500, 5000, and 10000 Mbit/s.


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
