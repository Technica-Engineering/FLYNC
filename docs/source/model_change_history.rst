.. _model_change_history:

========================
Model Change History
========================

This guide documents how the FLYNC **configuration model** and its **public Python/CLI
API** changed between consecutive releases, starting with  **0.9.x** (first public
release). It is written as a reference for *human users* and *AI assistants* to better
understand changes and enable adaptions to code.

It deliberately covers both:

* the **YAML schema** (the ``.flync.yaml`` files that make up a FLYNC configuration), and
* the **Python API** (import paths, class / method names, signatures) of the ``flync``
  package, its ``flync_cli`` command-line application, and the ``flync_converter``
  framework.

.. rubric:: Change classification

The guide classifies every change into one of three buckets:

* **Breaking — config/code must change.** Renamed / removed / relocated fields, files, and
  directories; dropped aliases; newly required fields; changed enums, types, or defaults;
  renamed or moved Python classes, methods, and modules; changed CLI commands/flags; and
  new validation rules that reject previously-accepted configurations.
* **Additive — backward compatible.** New optional fields, modules, or CLI features. No
  action required, listed so you are aware of new capabilities.
* **Internal only.** Pure refactors with no user-facing effect. Notable ones are mentioned
  in footnotes, but they are just added for information.

.. rubric:: Error IDs

From 0.13 onward every validation error carries a globally-unique ID of the form
``FLYNC-<MODULE>-<SEVERITY>-<CATEGORY>-<NNN>``. Releasing versions **0.9.x–0.12.x raise
``PydanticCustomError`` values typed ``"minor"`` / ``"major"`` / ``"fatal"`` with a human
message, but no stable ID** — the structured error scheme arrived in 0.13. Where a version
below 0.13 has no ID, this guide names the concrete validation that fails instead.

.. _model_change_overview:

Model Change Overview
=====================

* :ref:`0.13 -> 0.14 <chg__0_13__0_14>`
* :ref:`0.12 -> 0.13 <chg__0_12__0_13>`
* :ref:`0.11 -> 0.12 <chg__0_11__0_12>`
* :ref:`0.10 -> 0.11 <chg__0_10__0_11>`
* :ref:`0.9 -> 0.10 <chg__0_9__0_10>`

It is always recommended to use ``flync validate`` on your workspace root.

.. _chg__0_13__0_14:

0.13.x → 0.14.x (Work in Progress)
==================================

This is the current release. Several convenience aliases from earlier releases were dropped,
multiplexed PDUs were reworked, App service references were re-keyed, topology was split,
and the validator modules were reorganized.

Breaking — YAML schema
----------------------

Multiplexed PDU rework: inline ``StandardPDU`` → ``pdu_ref`` references
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In ``MultiplexedPDU``, ``mux_groups[].pdu`` changed from an inline ``StandardPDU`` to a
``PDUInstance`` reference (``pdu_ref`` + optional ``bit_position``/``update_bit_position``);
``MultiplexedPDU.static_group`` changed from an inline ``StandardPDU`` to ``List[PDUInstance]``.
The referenced PDUs must be declared separately.

.. code-block:: yaml

   # before (0.13.x)
   mux_groups:
     - selector_value: 0
       pdu:
         name: PDU_TransmissionStatus_Gear
         type: standard
         length: 8
         signals: [ ... ]

   # after (0.14.x)
   mux_groups:
     - selector_value: 0
       pdu:
         pdu_ref: PDU_TransmissionStatus_Gear

* **Unknown PDU ref:** ``FLYNC-CMN-MAJ-REF-237``
* **Container PDU refs:** ``FLYNC-CMN-MAJ-REF-236``

The ``dbc`` converter output for multiplexed PDUs changes accordingly.

``ContainedPDURef.pdu_id`` → ``header_id``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The field was renamed ``pdu_id`` → ``header_id`` and constrained ``>0``.

.. code-block:: yaml

   # before
   contained_pdus: [{ pdu_id: 5, ... }]
   # after
   contained_pdus: [{ header_id: 5, ... }]

Mis-keyed ``pdu_id:`` is a plain extra/missing-field error.

App service references keyed by name → service id (``FLYNC-1412``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``ServiceConsumerReference.service_name: str`` → ``service_id: int`` (required,
``0 < id < 0xFFFF``); ``ServiceProviderReference.service_name: str`` → ``service_id: int``
and the provider ``minor_version`` field was **removed**. Reference identity changed from
``(service_name, major_version)`` to ``(service_id, major_version, instance_id)``.

.. code-block:: yaml

   # before
   service_consumer_refs:
     - type: consumer
       service_name: my_service
       instance_id: 1
       major_version: 1

   # after
   service_consumer_refs:
     - type: consumer
       service_id: 0x1234
       instance_id: 1
       major_version: 1

* **Referenced service not found (now by id):** ``FLYNC-CMN-MAJ-REF-186``
* **Every app consumer ref must be matched by a ``someip_consumer`` deployment on the bound
  controller (new, strictly enforced):** ``FLYNC-CMN-MAJ-CONS-245``
* Warning when an app consumes+provides the same instance: ``FLYNC-CMN-MAJ-CONS-242``

Top-level communication alias dropped: ``general:`` now rejected
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The root ``communication`` field lost ``Field(alias="general", ...)``; the deprecated
``general`` property and its 0.13 warnings (162/163) were removed. Because the base model
uses ``extra="forbid"``, a top-level ``general:`` key is now **rejected** with
``extra_forbidden`` (no FLYNC ID). The folder remains ``communication/`` — this only matters
for flat/single-document ``FLYNCModel`` construction that used ``general:``.

``MACsecConfig`` requires a ``ckn``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``MACsecConfig`` gained a **required** string field ``ckn`` (Connectivity Association Key
Name, 1-32 octets, i.e. characters in the range 0x00-0xFF, no default). Every existing
``macsec_config`` block must add a ``ckn`` entry or it fails validation. A value containing
characters outside 0x00-0xFF raises ``FLYNC-SEC-MIN-FMT-252``:

.. code-block:: yaml

   # before
   macsec_config:
     vlan_bypass: []
     ...

   # after
   macsec_config:
     vlan_bypass: []
     ckn: 0123456789abcdef0123456789abcdef
     ...

Topology: ``SystemTopology`` → ``EthernetTopology`` (+ split)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``system_topology.py`` was renamed ``ethernet_topology.py`` (new sibling ``bus_topology.py``);
the class ``SystemTopology`` → ``EthernetTopology``; the ``FLYNCTopology`` attribute
``system_topology`` → ``ethernet_topology``, keeping ``alias="system_topology"`` so the old
YAML key still loads with a deprecation warning:

* **ID:** ``FLYNC-TOP-MIN-LIFE-229`` (attribute ``system_topology`` deprecated → use
  ``ethernet_topology``)

.. code-block:: yaml

   # before (still loads, warns)
   topology:
     system_topology: ...
   # after
   topology:
     ethernet_topology: ...

CAN/LIN bus topologies (``can_bus_topology`` / ``lin_bus_topology``) are **derived
automatically** at validation — no YAML authoring required.

New/strengthened topology and interface rules
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* Ethernet topology required when system-wide Ethernet/multicast features are used:
  **``FLYNC-CMN-MAJ-REQ-219``** (plus warning ``FLYNC-CMN-MAJ-CONS-220``).
* Unconnected ECU port: **``FLYNC-ECU-MIN-STRUCT-214``** (warning).
* CAN/LIN interface ``bus_ref`` must point to a declared bus in ``communication.channels``:
  **``FLYNC-CMN-MAJ-REF-215/216/217``**; unknown bus **``FLYNC-BUS-MAJ-CONS-221``** /
  unverifiable **``222``**; LIN bus exactly one master **``223``**; declared-but-unattached
  bus **``226``**; single-node bus **``230``**.
* Duplicate SOME/IP provider/consumer deployment for the same
  ``(service, major_version, instance_id)`` on one socket: error **``244``** (provider),
  warning **``241``** (consumer).
* Provided service with eventgroup multicast on a **TCP** socket:
  **``FLYNC-CMN-MAJ-CONS-218``**.
* New ECU-level rules (no-port / no-topology on Ethernet interfaces, switch port wiring):
  **``202/209/210/227/228/250``** and warnings ``211/212/213/238``.
* Duplicate interface name across types and duplicate MAC across Ethernet interfaces:
  **``FLYNC-ECU-MAJ-UNIQ-248``** / **``249``**; bitfield duplicate bit-position
  **``FLYNC-SOM-MIN-UNIQ-246``**.

TCAM ``TCAMRule`` / ``FrameMask`` rework (``FLYNC-1402``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* ``TCAMRule.frame_mask``: single ``FrameMask`` → ``List[FrameMask]``.
* ``frame_window`` moved from ``FrameMask`` (default 96) to ``TCAMRule`` (optional, unbounded
  when omitted).
* ``vehicle_state`` (int) + separate ``vehicle_state_mask`` (int) merged into a single
  ``vehicle_state: Bitmask`` object ``{data, mask}``; ``vehicle_state_mask`` removed.
* ``data``/``mask`` are ints parsed from ``0x``/``0b`` literals only — plain binary strings
  like ``"01010101"`` (no prefix) are rejected (error **177**); ``mask`` is optional (defaults
  to all bits of ``data``).
* A rule no longer needs exactly one of ``match_filter``/``frame_mask`` (relaxation).

.. code-block:: yaml

   # before
   frame_mask:
     offset: 12
     data: "0x0800"
     mask: "0xffff"
   vehicle_state: 5
   vehicle_state_mask: 255

   # after
   frame_mask:
     - { offset: 12, data: "0x0800", mask: "0xffff" }
   vehicle_state: { data: "0x05", mask: "0xff" }

The old errors 176/179/180/181/182 were removed; new ones **231–235** (vehicle_state >8-bit,
frame_masks overlap, exceeds frame_window, data bits outside mask, and a warning).

.. _chg__0_13__0_14_validators:

Validator import relocation (deleted modules)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The validator helper modules were moved out of ``flync.core.utils`` into
``flync.core.validators``. Any integrator importing the old paths must update:

* ``flync.core.utils.common_validators`` (deleted) →
  ``flync.core.validators.{generic,address,bit_ranges,connection_compatibility,traffic_classes}``
* ``flync.core.utils.forwarder_validators`` → ``flync.core.validators.forwarder``
* ``flync.core.utils.state_management_validators`` → ``flync.core.validators.state_management``
* ``flync.core.validators.address_validators`` (deleted) →
  ``flync.core.validators.address.before_validate_mac_address``

No aliases are kept for the old paths.

Breaking — CLI / converter
--------------------------

* ``flync errors`` subcommands renamed: ``validate-catalogue`` → ``validate-catalog``,
  ``generate-catalogue`` → ``generate-catalog`` (``get-next-number`` unchanged). Generated
  doc moved to ``docs/source/error_catalog.rst``.
* ``flync validate`` now exits **non-zero** on validation errors (``sys.exit(1)``) — CI-visible.
* ``flync info`` is now a real command group instead of one command with an enum argument:
  ``info list-ecus`` → ``info ecus``, ``list-controllers`` → ``controllers``, ``list-switches`` →
  ``switches``, ``list-ports`` → ``ports``, ``list-ips`` → ``ip``, ``list-sockets`` (previously
  dead — silently printed nothing) → ``sockets``, ``list-services`` → ``services``. New:
  ``info instances`` (looks up a SOME/IP service instance by ``service_id`` + ``major_version``,
  not by name) and ``info vlans`` (grouped by VLAN, replacing the crashing top-level
  ``display-vlan-info``).
* ``flync display-service-info`` → ``flync info instances`` (name lookup replaced by
  service ID + major version).
* ``flync display-repo-structure`` → ``flync filetree``.
* ``flync validate --quiet`` removed; ``flync debug`` removed (its layered checks moved to
  ``flync validate --verbose``).
* Every command's ``path`` argument is now optional, falling back to the workspace stored with
  the new ``flync config set``.
* All of the above old names remain callable as hidden, deprecated aliases (they print a
  pointer to the replacement) — only ``--quiet`` has no replacement flag.

Breaking — Python API
---------------------

* ``from flync.model.flync_4_topology import SystemTopology`` /
  ``...system_topology`` no longer resolves → import from ``...ethernet_topology`` /
  ``...bus_topology``.
* ``FLYNCModel.get_system_topology_info()`` → ``get_ethernet_topology_info()``.
* SOME/IP datatypes split: ``someip_datatypes.py`` → ``someip_simple_datatypes.py`` +
  ``someip_complex_datatypes.py`` (``AllTypes`` re-exported from the package ``__init__``);
  the direct module path ``flync_4_someip.someip_datatypes`` is gone.
* MACsec: Renamed the ``offset_preference`` field on both ``IntegrityWithoutConfidentiality`` and
  ``IntegrityWithConfidentiality`` to ``confidentiality_offset`` (same semantics and defaults).

Additive (0.14.x)
-----------------

* ECU ``ports``/``topology`` now optional (a CAN/LIN-only ECU may omit both) — relaxation.
* ``FLYNCTopology`` itself optional (a workspace without ``topology/`` loads as an empty
  topology).
* New runtime-derived CAN/LIN bus topology in ``FLYNCTopology.can_bus_topology`` /
  ``lin_bus_topology`` and new ``FLYNCModel.get_can_bus_topology()`` /
  ``get_lin_bus_topology()`` / ``get_someip_services_by_identity()``.
* New generic ``core.datatypes.Bitmask`` (used by TCAM matching).
* SOME/IP models relaxed ``extra="forbid"`` → unknown extra keys ignored
  (``SOMEIPServiceInterface``, ``SOMEIPMethod``/``Field``/``Event``/``Eventgroup``).
* ``FLYNCBaseModel`` sets ``validate_assignment=True``.
* New MACsec cipher configuration: ``CipherSuiteBaseModel`` base class with a ``cipher_suite``
  field (``GCM-AES-128``/``GCM-AES-256``/``GCM-AES-XPN-128``/``GCM-AES-XPN-256``, default
  ``GCM-AES-XPN-256``); both ``IntegrityWithoutConfidentiality`` and
  ``IntegrityWithConfidentiality`` inherit from it and gain ``cipher_suite`` plus an
  ``xpn()`` helper (``True`` for the XPN suites). New optional ``MACsecConfig.ethertype_bypass``
  (list of ``core.datatypes.Ethertype``, default ``[]``) — Ethertypes not protected with
  MACsec. New optional ``MACsecConfig.src_mac_address_bypass`` /
  ``dest_mac_address_bypass`` (lists of ``core.datatypes.FLYNCMacAddress``, default ``[]``)
  — source/destination MAC addresses not protected with MACsec. New optional
  ``MACsecConfig.replay_protection_window`` (int, default ``0``, ``>=0``);
  a non-zero value warns ``FLYNC-SEC-WARN-VAL-251``.
* ``IntegrityWithConfidentiality`` now rejects a non-zero ``confidentiality_offset`` with a
  XPN ``cipher_suite`` (``GCM-AES-XPN-128``/``GCM-AES-XPN-256``); Non XPN is required for any
  confidentiality offset other than ``0`` (``FLYNC-SEC-MIN-CONS-253``). Breaking for configs
  that set ``confidentiality_offset`` to ``30``/``50`` on a non-XPN cipher.
* Converter front-end loading refactored into ``cli/_optional.py`` with actionable install
  hints; entry points preserved.
* New ``flync config set|show|clear`` command group persists a default workspace path for the
  session (stored via ``platformdirs``); ``flync info ip``/``sockets``/``vlans`` reports now
  include VLAN and subnet information that the old ``list-ips``/``list-sockets``/
  ``display-vlan-info`` did not.

Internal only
-------------

The SDK ``FLYNCWorkspace`` module was decomposed into ``_base/_loading/_object_mapping/
_incremental/_saving`` (class name, constructor, and public methods preserved); the
``catalogue`` → ``catalog`` rename touched internal code and the generated error catalog path
(see CLI above).

.. _chg__0_12__0_13:

0.12.x → 0.13.x
===============

This release removed the auto-registration registry machinery (a Python-API break), renamed
several interface/deployment classes, and introduced the experimental App model and the
vendor-neutral NM layer. The structured ``FLYNC-...`` error-ID scheme began here.

Breaking — Python API
---------------------

Registry / instances machinery removed
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The auto-registration base classes and global registry were deleted: ``UniqueName``,
``DictInstances``, ``NamedDictInstances``, ``ListInstances``, ``NamedListInstances``,
``Registry``, ``get_registry``. Any importer breaks:

.. code-block:: python

   from flync.core.base_models import Registry, get_registry   # ImportError in 0.13

Uniqueness that was previously enforced via the registry is now enforced by explicit
``validate_list_items_unique(...)`` validators (see under Breaking — YAML). No error ID — a
plain ``ImportError``.

``ControllerInterface`` split (breaking import)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The former Ethernet-config class ``ControllerInterface`` was renamed **``EthernetInterfaceConfig``**,
and a new minimal base class **``ControllerInterface``** (single ``name`` field) was created
in ``flync_4_ecu/controller_interface.py``.

.. code-block:: python

   # ImportError in 0.13:
   from flync.model.flync_4_ecu.controller import ControllerInterface
   # Correct:
   from flync.model.flync_4_ecu import ControllerInterface          # now the MINIMAL base
   from flync.model.flync_4_ecu.controller import EthernetInterfaceConfig  # the old config class

YAML is unchanged: ``ethernet_interfaces[].interface_config{...}`` has the same shape.

Public class renames (Python imports)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - 0.12 name
     - 0.13 name
   * - ``CANInterfaceConfig``
     - ``CANInterface``
   * - ``LINMasterInterfaceConfig``
     - ``LINMasterInterface``
   * - ``LINSlaveInterfaceConfig``
     - ``LINSlaveInterface``
   * - ``AnyLINInterfaceConfig``
     - ``AnyLINInterface``
   * - ``ControllerInterface`` (config class)
     - ``EthernetInterfaceConfig``

YAML discriminators (``node_type: master/slave``, ``protocol``) are unchanged.

``PDUSender`` / ``PDUReceiver`` relocated
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

These moved out of ``flync_4_signal/frame.py`` into the new ``flync_4_signal/pdu_deployment.py``
(re-exported from the package ``__init__``):

.. code-block:: python

   from flync.model.flync_4_signal.frame import PDUSender        # ImportError in 0.13
   from flync.model.flync_4_signal.pdu_deployment import PDUSender  # correct

Semantic change: ``pdu_ref`` may now point to **any** PDU declared under
``communication.channels`` (workspace-validated by ``validate_pdu_deployment_refs``) rather
than only a ``ContainerPDU``. An unresolved ref raises ``FLYNC-SIG-MAJ-REF-...``.

``SOMEIPServiceDeployment.service`` stays an int (breaking for code)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In 0.12 a ``field_validator`` replaced the integer ``service`` with the resolved
``SOMEIPServiceInterface`` object; in 0.13 the field keeps the raw **int** service id and the
resolved object is a ``PrivateAttr`` ``_service_ref`` bound later:

.. code-block:: python

   deployment.service          # int (id) in 0.13; calling .service.name raises AttributeError
   resolve_reference(deployment, "service").name   # new public helper (flync.core.annotations.reference)

YAML is unaffected; only Python consumers of the resolved attribute are affected. The CLI was
updated accordingly.

Breaking — YAML schema
----------------------

New stricter top-level uniqueness validators
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``FLYNCModel`` added ``validate_unique_ecu_names`` and ``validate_unique_port_names``: ECU
names and **all ECU port names across the workspace** must now be globally unique. Reusing a
port name across two ECUs now fails:

* **ID:** ``FLYNC-<MODULE>-MAJ-UNIQ-009`` (from ``validate_list_items_unique``)

Additive (0.13.x)
-----------------

* New root field **``FLYNCModel.apps``** — optional ``List[App]``, emitted as folder
  ``apps/``. When set it warns **``FLYNC-GEN-WARN-LIFE-188``** ("Apps are currently
  experimental!"). App refs validated against known SOME/IP services
  (**``FLYNC-GEN-MAJ-REF-186``**) and controller ``app_bindings``
  (**``FLYNC-GEN-MAJ-REF-187``**). Additive.
* New **``flync_4_app``** package: ``App`` (name implied from file name, ``service_consumer_refs`` /
  ``service_provider_refs``), ``ServiceConsumerReference`` / ``ServiceProviderReference``,
  ``AppBindings``.
* New **NM layer** ``flync_4_nm/state_management.py``: ``StateManagementGroup``,
  ``StateMembershipRef``, timing classes. New optional ``state_memberships`` field on
  ``Controller``/``ECU``/``CANBus``/``LINBus`` and new ``FLYNCCommunicationConfig.state_management``.
* TCAM features (``switch.py``): ``FrameMask`` byte-pattern match, ``FrameFilter.ethertype``
  (new ``Ethertype`` enum), TCAM rule ``vehicle_state``/``vehicle_state_mask``; port-scoped
  terminal actions now default to **all** ports. Loosening (previously-invalid configs now
  valid); ``match_filter`` and ``frame_mask`` became mutually exclusive (exactly one required).
* ``FLYNCCommunicationConfig.tcp_profiles`` made optional (loosening).
* New ``Ethertype`` datatype in ``core.datatypes``.
* New CLI: ``flync errors`` group (``get-next-number``, ``validate-catalogue``,
  ``generate-catalog``) and ``flync debug``; error tables now display the ``ID`` column.

Internal only
-------------

The registry → ``bind()`` resolution rework across the model, migration of
``DictInstances``/``NamedListInstances`` subclasses to plain ``FLYNCBaseModel``, and the
large error-catalogue plumbing (every error now carries ``category`` + ``error_number`` and
packages gained a ``KEY`` so IDs auto-compose). ``flync`` with no subcommand now prints help.

.. _chg__0_11__0_12:

0.11.x → 0.12.x
===============

This release renamed the general configuration domain to communication, reworked CAN/LIN
frame references and signal encodings, and introduced the CLI and converter framework.

Breaking — YAML schema
----------------------

Root field ``general:`` → ``communication:`` (kept alias, warning only)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The root-model field ``general`` became ``communication``, the package
``flync_4_general_configuration`` became ``flync_4_communication``, and the folder
``general/channels/`` became ``communication/channels/``.

.. code-block:: yaml

   # before
   general:
     tcp_profiles: ...
     channels:
       can/...

   # after
   communication:
     tcp_profiles: ...
     channels:
       can/...

Because the field keeps ``Field(alias="general")`` plus a deprecation warning
(``"The 'general' attribute is deprecated. Please use 'communication' instead."``), the old
``general:`` key **still loads** but warns. Output is always written under
``communication/``, never ``general/``. The old key is not an error in 0.12 — 0.14 removes
the alias (see :ref:`chg__0_13__0_14`).

CAN / LIN frame references: ``frame_ref`` name → ``bus_ref`` + integer ``frame_ref``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

On CAN and LIN interfaces, a frame was referenced by name; it is now referenced by **bus +
frame ID**.

.. code-block:: yaml

   # before
   sender_frames:
     - frame_ref: MyFrameName

   # after
   sender_frames:
     - bus_ref: ChassisCAN
       frame_ref: 0x123

``CANInterfaceConfig`` / ``LINMasterInterfaceConfig`` / ``LINSlaveInterfaceConfig`` gained a
``name`` field — implied from the folder/file name, so not required in YAML. If
``frame_ref`` stays a string, Pydantic raises an int-coercion error; unknown bus/ID refs
surface as major reference-resolution errors.

``Signal.value_descriptions`` → ``Signal.value_encoding``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``ValueDescription`` class and ``value_descriptions`` list were replaced by a
``value_encoding`` discriminated union (``TextTable`` / ``BitfieldTextTable`` /
``BitmaskFlags``, discriminator ``type``).

.. code-block:: yaml

   # before
   value_descriptions:
     - value: 0
       description: Off

   # after
   value_encoding:
     type: text_table
     entries:
       - value: 0
         label: Off

``value_encoding`` is prohibited on float/char/bytearray signals.

``SignalGroup.signals``: ``List[Signal]`` → ``List[SignalInstance]``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Group members are now placed ``SignalInstance``\ s (referencing a signal by name + relative
``bit_position``) instead of bare inline ``Signal`` definitions. Overlap / footprint are
validated. This is breaking for any existing ``SignalGroup`` config.

SOME/IP: ``SOMEIPEventgroup.multicast_threshold`` removed (moved to provider)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The eventgroup-level ``multicast_threshold`` was deleted and replaced by provider-level
``SOMEIPServiceProvider.multicast_config`` (new class ``SOMEIPEventgroupMulticastConfig``).

.. code-block:: yaml

   # before (on the eventgroup)
   eventgroup:
     name: EG1
     id: 1
     multicast_threshold: 5

   # after (on the someip_provider deployment)
   deployment_type: someip_provider
   multicast_config:
     - ip_address: 239.0.0.1
       port: 40000
       threshold: 5
       eventgroups: [EG1]

Using the old ``multicast_threshold`` hits ``extra=forbid`` (``extra_forbidden`` error).

Default change: ``MulticastGroupMembership.mode`` ``"tx"`` → ``"rx"``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Omitting ``mode`` previously meant **tx**; now it means **rx**. A config with explicit
``mode: tx`` is unaffected, but silent behavior changes if you relied on the default.
IP (IPv4/IPv6) multicast groups in ``tx`` mode without ``src_ip`` now raise a minor error.

Controller interface naming
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Do not declare ``name`` inside ``interface_config:`` (the ``ControllerInterface`` block)
anymore — the interface name is implied from the ethernet **folder** name
(``ImpliedStrategy.FOLDER_NAME``). Any YAML declaring ``name`` directly on the
``interface_config`` block breaks (``extra=forbid``).

Breaking — Python API
---------------------

* ``FLYNCGeneralConfig`` → **``FLYNCCommunicationConfig``**;
  ``flync.model.flync_4_general_configuration`` → ``flync.model.flync_4_communication``.
  ``ValueDescription``/``ValueDescriptions`` moved to the new ``ValueEncoding`` family:
  ``TextEntry``, ``TextTable``, ``ValueEncoding``, ``BitfieldState``, ``BitfieldGroup``,
  ``BitfieldTextTable``, ``BitmaskFlag``, ``BitmaskFlags``.
* The whole **CLI** (``flync``, Typer + Rich: ``validate``, ``info``, ``vlan-info``,
  ``generate-system-uml``, ``service-info``, ``--version``, shell completion) and the whole
  **converter framework** (``flync_converter``, pluggy; ``flync``/``json``/``yaml``/``dbc``
  converters; ``flync-converter`` / ``-interactive`` / ``-gui`` entry points) are **new in
  0.12** — all additive.

Additive (0.12.x)
-----------------

* **Forwarders/gateways**: ``flync_4_signal/forwarder.py`` — ``PDUForwarder``
  (``deployment_type="pdu_forwarder"``), ``CANFrameForwarder``, ``ForwarderEgress``;
  ``CANInterfaceConfig.forwarder_frames``; root-model forwarder validation with
  locality/cycle checks.
* New core validator ``before_validate_mac_address`` + the ``FLYNCMacAddress`` annotated
  type with improved error messages (no YAML change).
* ``pdu_usage``/``frame_usage`` became typed enumerated literals (application, bap,
  diag_request, diag_response, diag_state, network_management, other, service, tpl,
  xcp_pre_configured, xcp_runtime_configured). A non-listed custom tag now raises.
* ``Frame.packed_pdus`` relocated from the CAN/LIN frame bases (no YAML change).
* SOME/IP provider ``multicast_config`` + eventgroup multicast validation.

Internal only
-------------

Controller/interface/switch base-class rework (``NamedDictInstances`` → ``FLYNCBaseModel`);
``validate_by_name=True`` on the base model. Attempted
``system_topology``/``someip_datatypes`` renames were reverted before this tag — 0.12 still
ships those names.

.. _chg__0_10__0_11:

0.10.x → 0.11.x
===============

This is the release with the largest structural change: **controllers became directories**.
``src/flync_cli`` is unchanged in this range (the Typer CLI did not exist until 0.12).

Breaking — YAML schema
----------------------

Controller layout: single file → directory, ``meta`` → ``controller_metadata``  ⚠️
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In 0.10 each controller was **one file** ``<ecu>/controllers/<name>.flync.yaml`` with a
top-level ``meta`` block. In 0.11 each controller is a **directory**
``<ecu>/controllers/<name>/`` containing ``controller_metadata.flync.yaml``.

.. code-block:: yaml

   # before (0.10.x) — controllers/eth_ecu_controller1.flync.yaml
   meta:
     author: Dev
     compatible_flync_version:
       version_schema: semver
       version: 0.9.x
     target_system: flync_os
   name: eth_ecu_controller1
   interfaces:
     - name: eth_ecu_c1_iface1
       mac_address: 00:11:22:33:44:55

   # after (0.11.x) — controllers/eth_ecu_controller1/controller_metadata.flync.yaml
   controller_metadata:
     type: embedded
     author: Dev
     compatible_flync_version:
       version_schema: semver
       version: 0.11.x
     target_system: flync_os

The controller ``name`` is now implied from the folder name.

**Auto error on unmigrated config:** the Controller model runs a ``mode="before"`` validator
that detects the legacy top-level ``meta.compatible_flync_version`` shape and raises a fatal
error:

* **ID:** ``FLYNC-GEN-FAT-COMP-048``
* **Message:** *"Incompatible Controller Config detected (compatible_flync_version=...).
  FLYNC 0.11.x requires every controller to live in its own directory containing
  'controller_metadata.flync.yaml'. Update the configuration to the new layout or downgrade
  FLYNC to 0.10.x."*

Controller field ``interfaces`` → ``ethernet_interfaces`` + on-disk layout
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``Controller.interfaces: List[ControllerInterface]`` became
``ethernet_interfaces: List[EthernetInterface]`` where ``EthernetInterface =
{interface_config: ControllerInterface, sockets: List[SocketContainer]}``. Each ethernet
interface is now a directory ``controllers/<name>/ethernet_interfaces/<iface>/
interface_config.flync.yaml`` (optionally with a ``sockets/`` sub-directory). ``Controller.can_interfaces``
and ``Controller.lin_interfaces`` were also added.

A 0.10 ``interfaces: [ ... ]`` key under a controller no longer resolves.

ECU-level ``sockets`` removed → moved under the interface
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``ECU.sockets: List[SocketContainer]`` (stored in ``<ecu>/sockets/*.flync.yaml``) was
**removed**. Sockets are now attached per ethernet interface and stored at
``controllers/<name>/ethernet_interfaces/<iface>/sockets/socket_<x>.flync.yaml``.

:action: move the contents of ``<ecu>/sockets/`` into the owning controller interface's ``sockets/`` directory. The file content (``vlan_id`` + ``sockets``) is unchanged.

VLAN / multicast address validation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``vlan_entry.py`` (extracted from ``switch.py``): ``MulticastGroup.address`` is now required
to be a **multicast** MAC/IP address, and ``VLANEntry`` default handling changed. Configs
that used non-multicast addresses in switch VLAN multicast lists now fail.

Top-level load behavior: failed ECUs/controllers are dropped
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``FLYNCModel`` now silently drops ECUs/controllers that fail to load (and raises a major
error at the ECU level) instead of cascading model-wide errors. Callers reading
``model.ecus`` should expect a malformed ECU to be absent rather than the whole load
failing. Duplicate-IP detection now **warns** instead of raising.

Breaking — Python API
---------------------

* ``Controller.interfaces`` → ``controller.ethernet_interfaces``.
* ``ECU.sockets`` (field) no longer exists — use the owning interface's ``.sockets`` or
  ``ecu.get_all_sockets()``.
* ``ControllerInterface.mac_address`` is now ``Optional`` (default ``None``) — guard for
  ``None`` in code that read it directly.
* The registry / instance machinery was reworked in this range (``DictInstances`` /
  ``ListInstances`` etc. now build on a new ``BaseRegistry``). Public model fields are
  unchanged, but code touching class-level ``INSTANCES``/``NAMES`` dicts must adapt.

Additive (0.11.x)
-----------------

* New domain packages: **``flync_4_signal``** (``Signal``/``SignalDataType``,
  ``StandardPDU``/``MultiplexedPDU``/``ContainerPDU``, ``CANFrame``/``CANFDFrame``/``LINFrame``,
  ``PDUSender``/``PDUReceiver``) and **``flync_4_bus``** (``CANBus``, ``LINBus`` +
  ``LINScheduleTable``). Sockets can now carry ``deployment_type: pdu_sender`` /
  ``pdu_receiver``.
* ``FLYNCGeneralConfig.channels`` (new ``flync_channels.py``) loaded from
  ``general/channels/`` (``pdus/``, ``can/``, ``lin/``, ``ethernet_pdu_containers/``).
* New ECU classes: ``router.py`` (``RouteEntry`` / controller ``routing_table``),
  ``mac_multicast_endpoint.py`` (``MACMulticastEndpoint`` + new ``ECU.mac_multicast_endpoints``),
  CAN/LIN interfaces (``CANInterfaceConfig``, ``LINMasterInterfaceConfig`` /
  ``LINSlaveInterfaceConfig`` discriminated on ``node_type``), and the experimental
  ``VirtualControllerInterface`` / ``VirtualSwitch`` / ``ComputeNodes``.
* SOME/IP: ``SOMEIPServiceProvider.provided_eventgroups``; timing-profile discriminated union
  rework (backward compatible at the YAML level).
* SDK: new ``has_object``/``get_definition``/``get_references_of``/``find_path_from_field``/
  ``get_semantic_object_from_model``; ``load_flync_model`` became public.

Internal only
-------------

The ``VersionMigrators`` package was introduced for this controller migration. The
``Reference`` annotation was rewritten to resolve from a registry; topology connection
checks were reimplemented with identical error text.

.. _chg__0_9__0_10:

0.9.x → 0.10.x
==============

This release reworked the SOME/IP type system, socket multicast configuration, SD timing
units, and TSN shaping. There are no error IDs in this range — failures surface as
``PydanticCustomError`` typed ``minor``/``major``/``fatal``.

Breaking — YAML schema
----------------------

SOME/IP parameter ``type`` → ``datatype`` (nested object)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The bare datatype literal ``type`` on a ``SOMEIPParameter`` became a nested ``datatype``
object. This affects every parameter of events, fields, and method
``input_parameters``/``output_parameters``.

.. code-block:: yaml

   # before (0.9.x)
   parameters:
     - name: InterfaceVersion_Param
       type: uint8

   # after (0.10.x)
   parameters:
     - name: InterfaceVersion_Param
       datatype:
         type: uint8

Fails as: the old ``type:`` key is unexpected and rejected (``extra=forbid``).

Signed-integer datatypes renamed ``sint*`` → ``int*``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``SInt8/16/32/64`` became ``Int8/16/32/64`` and the YAML ``type`` literal changed
``sint8/16/32/64`` → ``int8/16/32/64``. Applies wherever a datatype literal is used
(parameters, union members, enum ``base_type``, method args). Unsigned ``uint*``,
``float32/64``, ``boolean`` are unchanged.

Socket container ``vlan_name`` → ``vlan_id``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``SocketContainer`` field ``vlan_name: str`` was renamed and re-typed to ``vlan_id: int``.
The value must now be the numeric VLAN ID matching a ``VirtualControllerInterface.vlanid``.

.. code-block:: yaml

   # before
   vlan_name: hpc_c1_i1_viface1
   sockets: [ ... ]

   # after
   vlan_id: 20
   sockets: [ ... ]

Socket multicast / endpoint configuration rework
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Sockets gained ``endpoint_type`` (``unicast`` | ``multicast``) and ``multicast_tx`` (list
of multicast IP strings). Per-deployment multicast (driven by
``SOMEIPServiceDeployment.find_service_multicast``) was removed; multicast TX is now
declared on the socket itself.

.. code-block:: yaml

   # before
   - name: sd_multicast_socket
     endpoint_address: 10.0.10.5
     port_no: 30490
     protocol: udp
     deployments:
       - deployment_type: someip_sd
         multicast:
           ip_address: 224.244.224.245
           port: 30490
           ip_ttl: 1

   # after
   - name: sd_multicast_socket
     endpoint_address: 10.0.20.5
     endpoint_type: multicast
     port_no: 30490
     protocol: udp
     multicast_tx: [224.244.224.245]
     deployments:
       - deployment_type: someip_sd
         multicast:
           ip_address: 224.244.224.245
           port: 30490
           ip_ttl: 1

The old per-deployment ``find_service_multicast`` / derived multicast config is rejected.

``FLYNCTopology.multicast_paths`` removed
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``multicast_paths`` field on the (then) ``SystemTopology`` was removed and
``topology/multicast_paths.flync.yaml`` is now **ignored** as an unrelated file (the loader
drops unrelated docs with a warning). Multicast routing is now computed automatically from
socket ``multicast_tx`` lists plus the virtual-interface multicast addresses.

:action: delete ``topology/multicast_paths.flync.yaml`` from your repositories.

SD timings: float (seconds) → int (milliseconds), TTL defaults changed
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``SDTimings`` fields changed from ``float`` seconds to ``int`` **milliseconds** (e.g.
``0.050`` → ``50``). Defaults shifted to ms: ``offer_ttl`` 3 → 3000, ``subscribe_ttl`` 3 →
3000, ``offer_cyclic_delay`` 1 → 1000.

.. code-block:: yaml

   # before
   initial_delay_min: 0.050
   repetitions_base_delay: 0.300
   offer_ttl: 3

   # after
   initial_delay_min: 50
   repetitions_base_delay: 300
   offer_ttl: 3000

Service keying by ``(id, major_version)``; provider version fields required
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Services are now keyed by ``(id, major_version)`` instead of ``id`` alone; deployments are
resolved by id *and* major version, so a version mismatch is no longer silently tolerated.
A provider deployment now requires both ``major_version`` **and** ``minor_version``; a
consumer deployment requires ``major_version > 0``. Omitted/zero versions fail validation.

TSN: ``prio`` → ``filter_priority``; ``ChildClass.priority`` required
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``HTBFilter.prio`` was renamed ``filter_priority`` (old key rejected). ``ChildClass`` gained
a required ``priority: int``, and ``child_classes`` must be a real list.

.. code-block:: yaml

   # before
   filters:
     - prio: 1

   # after
   filters:
     - filter_priority: 1
   child_classes: []

Phy MII discriminator lowercased
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``MII.type`` changed from ``"MII"`` to ``"mii"``. Configs using ``type: MII`` (uppercase)
no longer match the discriminated union.

Breaking — Python API
---------------------

SOME/IP datatypes moved out of ``flync.core.datatypes``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The SOME/IP datatype modules (``array``, ``bitfield``, ``enum``, ``primitive``, ``string``,
``struct``, ``typedef``, ``union``) were deleted from ``flync.core.datatypes`` and moved to
``flync.model.flync_4_someip.someip_datatypes`` (the new home of ``AllTypes``).

.. code-block:: python

   # before
   from flync.core.datatypes import SInt8, UInt8, Enum, Struct, ArrayType, AllTypes
   # after
   from flync.model.flync_4_someip.someip_datatypes import Int8, UInt8, Enum, Struct, ArrayType, AllTypes

In ``flync.core.datatypes.macaddress``: ``UnicastMACAddressEntry`` → ``MACAddressUnicast``
and ``MulticastMACAddressEntry`` → ``MACAddressMulticast`` (these are still re-exported from
``core.datatypes``, but the class names changed).

Additive (0.10.x)
-----------------

* ``Socket.endpoint_type`` and ``Socket.multicast_tx`` (see breaking §5 above).
* ``SOMEIPServiceInterface.someip_timing`` profiles: ``someip_timing: <profile_id>`` on
  events/fields (``event_default`` / ``field_default``) plus the ``SOMEIPFieldTimings`` class.
* `e2e` on SOME/IP events is now concrete: ``e2e: {profile: AUTOSAR_Profile_4, data_id: ...}``.
* Datatype growth: ``Struct``/``Array`` gain ``bit_alignment`` (8/16/32/64/128/256) and
  ``length_of_length_field`` (0/8/16/32); ``Typedef`` added to ``AllTypes``; enum duplicate /
  out-of-range validators.
* New ``ImpliedStrategy.FILE_NAME`` and the new ``flync.core.annotations.reference.Reference``
  annotation.
* SDK: many new public helpers for LSP integration (``safe_load_workspace``, ``load_errors``,
  ``load_model``, ``get_object``, ``list_objects``, …).

Internal only
-------------

``flync_cli`` and ``flync_converter`` have **no diff** in this range. The SDK workspace
loader was rewritten (ruamel AST compose) but keeps the existing method signatures. The
workspace loader now ignores unrelated/non-model YAML files instead of erroring.


========================

Appendix — Quick renames
========================

Datatypes & classes
-------------------

* ``SInt8/16/32/64`` → ``Int8/16/32/64`` (0.10)
* ``UnicastMACAddressEntry`` → ``MACAddressUnicast``; ``MulticastMACAddressEntry`` → ``MACAddressMulticast`` (0.10)
* ``FLYNCGeneralConfig`` → ``FLYNCCommunicationConfig`` (0.12)
* ``ValueDescription`` → ``ValueEncoding`` / ``TextTable`` / … (0.12)
* ``CANInterfaceConfig`` → ``CANInterface``; ``LIN*InterfaceConfig`` → ``LIN*Interface``;
  ``ControllerInterface`` (config) → ``EthernetInterfaceConfig`` (0.13)
* ``SystemTopology`` → ``EthernetTopology`` (0.14)

Field / key renames
-------------------

* ``type`` (parameter) → ``datatype`` (0.10)
* ``sint*`` → ``int*`` (0.10)
* ``vlan_name`` → ``vlan_id`` (0.10)
* ``prio`` → ``filter_priority`` (0.10)
* ``meta`` (controller) → ``controller_metadata`` (0.11)
* ``general`` → ``communication`` (0.12 alias / 0.14 dropped)
* ``frame_ref`` (name) → ``bus_ref`` + ``frame_ref`` (ID) (0.12)
* ``value_descriptions`` → ``value_encoding`` (0.12)
* ``system_topology`` → ``ethernet_topology`` (0.14 alias / warning)
* ``pdu_id`` → ``header_id``; ``service_name`` → ``service_id`` (0.14)

Key error IDs
-------------

``FLYNC-GEN-FAT-COMP-048`` (0.11 legacy controller),
``FLYNC-GEN-WARN-LIFE-188`` (apps experimental),
``FLYNC-CMN-MAJ-REF-186/236/237`` (0.14 refs),
``FLYNC-CMN-MAJ-CONS-245`` (0.14 app↔deployment),
``FLYNC-CMN-MAJ-REQ-219`` & ``FLYNC-TOP-MIN-LIFE-229`` (0.14 topology),
``FLYNC-BUS-MAJ-CONS-221/222/223/226/230`` (0.14 bus topology).
See :doc:`error_catalog` for the full, machine-generated list.
