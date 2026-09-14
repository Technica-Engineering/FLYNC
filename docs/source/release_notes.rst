:orphan:

.. _release_notes:

Release Notes
=============

.. seealso::

   For a detailed, step-by-step description of how the FLYNC configuration model and public
   API changed between releases (and what you must update to migrate a project), see the
   :doc:`model_change_history`.

Release 0.14
------------

Controller virtualization
'''''''''''''''''''''''''

A controller can now describe what runs *inside* it. Each controller may host
:class:`~flync.model.flync_4_ecu.compute_node.ComputeNode` guests - nestable, so a hypervisor
with its own guests is expressible - and virtual switches modelled with the same
:class:`~flync.model.flync_4_ecu.switch.Switch` class as a hardware switch. The links between
them are declared in a new ``controller_topology.flync.yaml`` per controller.

This replaces the previous ``compute_nodes`` block inside an interface config and the single
``virtual_switch.flync.yaml``; both are breaking changes. See ``ecu_variant_10`` in
:ref:`flync_example` for the full layout, and :doc:`model_change_history` to migrate.

DoIP/UDS diagnostics
''''''''''''''''''''

Added a new :ref:`flync_4_diagnostics <diagnostics>` domain package under
``communication/diagnostics/``, with one sub-directory per diagnostic protocol - everything
modelled today is UDS (ISO 14229) over DoIP (ISO 13400). It covers DoIP and UDS timing
profiles, UDS servers (sessions, security access, supported services) and the DID, routine
and DTC catalogs.

Sockets gained two matching deployment types: ``doip_server`` (TCP, carries the logical
address and the UDS server reference) and ``doip_discovery`` (UDP, vehicle identification and
announcement).

10BASE-T1S multidrop segments
'''''''''''''''''''''''''''''

The Ethernet topology gained a second connection type, ``ethernet_multidrop``, describing a
shared-medium segment: an optional PLCA cycle (``transmit_opportunity_count``, ``to_timer``)
and one entry per participating ECU port with its ``node_id`` and burst configuration.
``BASET1S`` gained ``topology: p2p | multidrop`` to select between the two.

CLI restructure
'''''''''''''''

The ``flync`` CLI command tree was reorganized for consistency and to fix a handful of broken
or dead commands:

.. list-table::
   :header-rows: 1

   * - Old
     - New
   * - ``info list-ecus`` / ``list-controllers`` / ``list-switches``
     - ``info ecus`` / ``controllers`` / ``switches``
   * - ``info list-ports`` / ``list-ips`` / ``list-sockets`` / ``list-services``
     - ``info ports`` / ``ip`` / ``sockets`` / ``services``
   * - ``display-vlan-info``
     - ``info vlans``
   * - ``display-service-info``
     - ``info instances``
   * - ``display-repo-structure``
     - ``filetree``
   * - ``debug``
     - ``validate --verbose``

``flync info`` is now a real command group. Several of its reports were also fixed or
extended: ``sockets`` previously printed nothing, ``vlans`` previously raised an
``AttributeError``, ``ip`` and ``sockets`` now show VLAN and subnet, ``services`` now lists
service ID, major version and providing/consuming ECUs, and ``instances`` looks a service
instance up by its **service ID and major version** instead of its name.

Also new:

* ``flync config set|show|clear`` stores a default workspace path for the session. Every
  command's ``path`` argument is now optional and falls back to it; an explicit argument wins.
* ``flync errors fix-numbers`` and ``flync errors sync`` keep error numbers unique against the
  base branch and regenerate the catalog in one step.
* ``flync validate`` exits non-zero on validation errors. ``--quiet`` was removed.

The renamed and removed commands above are still reachable under their old names as hidden,
deprecated aliases that print a pointer to the new command.

System UML on non-Ethernet workspaces
'''''''''''''''''''''''''''''''''''''

``flync generate-system-uml`` no longer crashes with an ``AttributeError`` on a workspace
without Ethernet wiring. Since an ECU reaches the diagram only through its Ethernet interfaces
or switches, a CAN/LIN-only workspace has nothing to draw: rather than writing a file that
renders to a blank image, the command now prints a warning naming the reason, writes no file,
and still exits 0. The same warning covers a ``--vlan-id`` filter that matches nothing.
Multidrop segments are drawn where present.

MACsec cipher configuration
'''''''''''''''''''''''''''

The MACsec model (:ref:`flync_4_security <security>`) was extended with per-entry cipher
suite selection (``GCM-AES-128`` / ``-256`` / ``-XPN-128`` / ``-XPN-256``), bypass lists for
Ethertypes and source/destination MAC addresses, and a replay protection window.

``MACsecConfig`` now **requires** a ``ckn`` (Connectivity Association Key Name), so every
existing ``macsec_config`` must add one. ``offset_preference`` was renamed
``confidentiality_offset``, and a non-zero offset is now rejected with an XPN cipher suite.
Enabling MACsec without MKA is now only a warning rather than an error.

DBC to FLYNC decoding
'''''''''''''''''''''

The DBC converter now supports decoding DBC files back into a full FLYNC model
(:meth:`flync_converter.converters.dbc.DbcConverter.decode`), not just encoding FLYNC to DBC.
Nodes become ECUs with CAN controllers, bit rates are read from the cantools ``Baudrate``
attributes, and multiplexed messages, value tables, factors, offsets, ranges and units are
preserved. Customizing the decoding is possible through the new
:class:`flync_converter.converters.dbc.DbcConverterConfig`.

Examples and workspace configuration
''''''''''''''''''''''''''''''''''''

``examples/flync_example`` is now the stable reference configuration, with everything
experimental (applications and app bindings, among others) moved into the new
``examples/flync_example_experimental`` superset. A minimal ``examples/can_lin_example``
demonstrates a workspace with no Ethernet at all - ``topology/`` and ECU ``ports`` are both
optional now.

Saving a workspace also writes a ``.flync/config.yaml`` holding its configuration, so tooling
picks up the same settings on the next load.

Installation and build
''''''''''''''''''''''

The project also builds and locks with **uv** instead of Poetry, using **hatchling** with
``uv-dynamic-versioning`` for version resolution from git tags. Contributors should recreate
their virtual environment with ``uv sync``.
