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

CLI restructure
''''''''''''''''

The ``flync`` CLI command tree was reorganized for consistency and to fix a handful of broken or
dead commands:

* ``flync info`` is now a real command group: ``ecus``, ``controllers``, ``switches``, ``ports``,
  ``ip``, ``sockets``, ``services``, ``instances``, ``vlans``.

  * ``info sockets`` (previously ``info list-sockets``, which silently printed nothing) now shows
    socket endpoints grouped by ECU and VLAN, with their interface, virtual interface, MAC, IP,
    protocol and port.
  * ``info instances`` (replaces the top-level ``display-service-info``) looks a service instance
    up by its **service ID and major version** instead of its name, and reports a clear error - with
    the list of available services - for an id/major that does not exist.
  * ``info services`` (previously ``info list-services``) now lists each service's ID, major
    version, and its providing/consuming ECUs, not just its name.
  * ``info ports`` (previously ``info list-ports``) is grouped by ECU and drops the row numbering
    that did not correspond to anything in the model.
  * ``info ip`` (previously ``info list-ips``) now shows each address's VLAN and subnet.
  * ``info vlans`` (replaces the top-level ``display-vlan-info``, which raised an ``AttributeError``)
    is grouped by VLAN and fixes the traceback; the VLAN ID is now an optional ``--vlan-id`` filter.

* ``flync display-repo-structure`` is renamed to ``flync filetree``, with an updated description:
  it exports the expected filetree of a FLYNC configuration to a txt file.
* ``flync validate``:

  * ``--quiet`` is removed.
  * ``--verbose`` now runs the layered debug checks (folder structure, YAML syntax, schema, field
    values, system-wide) that ``flync debug`` used to run.
  * The standalone ``flync debug`` command is removed.

* ``flync config set|show|clear`` stores a default workspace path for the session. Every command's
  ``path`` argument is now optional and falls back to the stored path; an explicit argument always
  wins.
* The renamed/removed commands above are still reachable under their old names as hidden, deprecated
  aliases that print a pointer to the new command.

System UML on non-Ethernet workspaces
'''''''''''''''''''''''''''''''''''''

``flync generate-system-uml`` no longer crashes with an ``AttributeError`` on a workspace without
Ethernet wiring. ``FLYNCTopology.ethernet_topology``, ``ECU.ports``, ``ECU.switches`` and
``ECU.topology`` are all optional in the model and are now handled as such.

An ECU still reaches the diagram only through its Ethernet interfaces or its switches, so a
CAN/LIN-only workspace has nothing to draw. Rather than writing a file that renders to a blank
image, the command now prints a warning naming the reason and writes no file. It still exits 0.
The same warning covers a ``--vlan-id`` filter that matches nothing.

DBC to FLYNC decoding
'''''''''''''''''''''

The DBC converter now supports decoding DBC files back into a full FLYNC model
(:meth:`flync_converter.converters.dbc.DbcConverter.decode`), not just
encoding FLYNC to DBC. Customizing the decoding is possible through the new
:class:`flync_converter.converters.dbc.DbcConverterConfig`
(``baud_rate_default``, ``fd_baud_rate_default``).

Key decoding behaviours:

* Each DBC ``BU_:`` node is synthesized as one ECU with a CAN controller and one
  interface per bus it participates on.
* The bus bit rates are read from the cantools ``Baudrate`` / ``BaudrateCANFD``
  attributes (with configurable fallbacks, default ``500000`` / ``2000000``).
* Multiplexed messages are reconstructed as a
  :class:`~flync.model.flync_4_signal.pdu.MultiplexedPDU` with the ``M`` selector
  signal and per-id mux groups plus the static group.
* Signal value tables (``VAL_``), factors, offsets, ranges and units are preserved.
* Signals/PDUs are namespaced with the DBC bus (file stem) name, e.g.
  ``BusA_SpeedMsg``.

Optional Extras
'''''''''''''''

``textual`` and ``PySide6`` are **no longer installed by default**. The core ``flync``
install is now Qt-free, cutting the installed footprint by roughly 85% for all users
and for any package that depends on ``flync``.

To restore the previous behaviour:

.. code-block:: bash

   pip install "flync[all]"

Or install individually:

.. code-block:: bash

   pip install "flync[tui]"    # for flync-converter-interactive
   pip install "flync[gui]"    # for flync-converter-gui

Commands that require a missing extra now print an actionable error message with
install instructions instead of a traceback.

Build System Migration
''''''''''''''''''''''

The project now builds and locks with **uv** (replacing Poetry). Contributors
should recreate their virtual environment:

.. code-block:: bash

   rm -rf .venv
   uv sync

The build backend is **hatchling** with ``uv-dynamic-versioning`` for version
resolution from git tags. The ``uv.lock`` file replaces ``poetry.lock``.

MACsec cipher configuration
'''''''''''''''''''''''''''

The MACsec model (`flync_4_security`) was extended:

* New :class:`~flync.model.flync_4_security.CipherSuiteBaseModel` base class holding the
  `cipher_suite` field, from which both :class:`IntegrityWithoutConfidentiality
  <flync.model.flync_4_security.IntegrityWithoutConfidentiality>` and
  :class:`IntegrityWithConfidentiality
  <flync.model.flync_4_security.IntegrityWithConfidentiality>` inherit. Each cipher entry
  now carries ``cipher_suite: GCM-AES-128 | GCM-AES-256 | GCM-AES-XPN-128 |
  GCM-AES-XPN-256`` (default ``GCM-AES-XPN-256``).
* New helper method
  :meth:`CipherSuiteBaseModel.xpn <flync.model.flync_4_security.CipherSuiteBaseModel.xpn>`
  returning ``True`` for the XPN cipher suites (``GCM-AES-XPN-128`` / ``GCM-AES-XPN-256``).
* New optional ``MACsecConfig.ethertype_bypass`` field (list of
  :class:`~flync.core.datatypes.Ethertype`, default ``[]``) naming the Ethertypes that
  shall not be protected with MACsec.
* New optional ``MACsecConfig.src_mac_address_bypass`` and
  ``MACsecConfig.dest_mac_address_bypass`` fields (lists of
  :class:`~flync.core.datatypes.FLYNCMacAddress`, default ``[]``) naming, respectively, the
  source and destination MAC addresses that shall not be protected with MACsec.
* New **required** ``MACsecConfig.ckn`` field (string, 1-32 octets, i.e. characters in
  the range 0x00-0xFF) holding the Connectivity Association Key Name (CKN) used to identify
  the CAK. Because it is required, every existing ``macsec_config`` must add a ``ckn`` entry.
* New optional ``MACsecConfig.replay_protection_window`` field (int, default ``0``) giving
  the size of the replay protection window. A non-zero value emits a warning
  (``FLYNC-SEC-WARN-VAL-251``).
