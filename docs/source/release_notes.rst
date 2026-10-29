:orphan:

.. _release_notes:

Release Notes
=============

.. seealso::

   For a step-by-step description of how the FLYNC configuration model and public API changed between
   releases (and what you must update to migrate a project), see the :doc:`model_change_history`.

Release 0.16
------------

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
