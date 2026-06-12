.. _signal:

**************
flync_4_signal
**************

The ``flync_4_signal`` module contains the building blocks for
describing communication data at every level of abstraction: from
individual **Signals** (raw bit-level data elements), through **PDUs**
(Protocol Data Units that group signals), up to **Frames** (the
protocol-specific transport units that carry PDUs on a bus).

.. admonition:: Expand for Schematic
   :collapsible: closed

   .. mermaid:: ../../_static/mermaid/signal.mmd


.. _signal_model:

Signal
######

A :class:`~flync.model.flync_4_signal.Signal` is the smallest
data element in FLYNC.  It describes a physical or logical value that
is transmitted on a bus, including how raw bits are scaled and
interpreted.  Signals are bus-agnostic: the same signal definition can
be reused across CAN, LIN, or Ethernet transport layers.

Signals are not placed directly into PDUs; instead a
:class:`~flync.model.flync_4_signal.SignalInstance` wraps a signal
with its placement information (bit offset and byte order).

.. autoclass:: flync.model.flync_4_signal.SignalDataType()

   Enumeration of valid signal data types: ``UINT8``, ``UINT16``, ``UINT32``,
   ``UINT64``, ``INT8``, ``INT16``, ``INT32``, ``INT64``, ``FLOAT32``,
   ``FLOAT64``, ``CHAR``, ``BYTEARRAY``. Each variant exposes the helpers
   ``natural_bit_width()``, ``is_float()``, ``is_unsigned_integer()``,
   ``is_signed_integer()``, and ``is_complex_datatype()``.

.. autoclass:: flync.model.flync_4_signal.Signal()

Value Encodings
===============

A :class:`~flync.model.flync_4_signal.Signal` may carry an optional
``value_encoding`` that converts raw integer values into text labels.
Four variants are supported and selected by the ``type`` discriminator:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - ``type``
     - Description
   * - ``text_table``
     - Maps single raw values to text labels.  Use this for ordinary
       enumerated signals and for reserved sentinel codes such as
       ``Signal_Not_Available``.
   * - ``range_text_table``
     - Maps inclusive raw value ranges to text labels.  Use this when
       one label spans many contiguous raw values (e.g.
       ``0..9 = Low``).
   * - ``bitfield_text_table``
     - Decodes the signal as a set of named bit-region groups, each with
       its own enum of mutually exclusive states.  Use this when several
       unrelated small enums are packed into one signal (status / fault
       words).
   * - ``bitmask_flags``
     - Decodes the signal as a set of independent on/off flags, each
       identified by a disjoint mask.  Multiple flags may be active
       simultaneously.  Use this for partial-network relevance vectors
       and similar feature-flag registers.

A signal can combine ``factor``/``offset``/``unit`` with any of the
text-table encodings to express the common "linear conversion plus
reserved sentinel values" pattern (e.g. a speed signal in ``km/h`` with
raw ``65535`` mapped to ``Signal_Not_Available``).

.. autoclass:: flync.model.flync_4_signal.TextTable()

.. autoclass:: flync.model.flync_4_signal.TextEntry()

.. autoclass:: flync.model.flync_4_signal.RangeTextTable()

.. autoclass:: flync.model.flync_4_signal.RangeTextEntry()

.. autoclass:: flync.model.flync_4_signal.BitfieldTextTable()

.. autoclass:: flync.model.flync_4_signal.BitfieldGroup()

.. autoclass:: flync.model.flync_4_signal.BitfieldState()

.. autoclass:: flync.model.flync_4_signal.BitmaskFlags()

.. autoclass:: flync.model.flync_4_signal.BitmaskFlag()

Examples
--------

.. admonition:: Expand for a YAML example — enumerated signal (``text_table``)
   :collapsible: closed

   A purely enumerated signal — every raw value maps to one label.

   .. code-block:: yaml

      signal:
        name: CurrentGear
        description: Currently engaged gear.
        bit_length: 8
        data_type: uint8
        value_encoding:
          type: text_table
          entries:
            - value: 0
              label: Park
            - value: 1
              label: Reverse
            - value: 2
              label: Neutral
            - value: 3
              label: Drive

.. admonition:: Expand for a YAML example — linear signal with reserved codes (``text_table``)
   :collapsible: closed

   The most common automotive pattern: a physical signal with linear
   scaling that also reserves one or more raw codes for special meaning
   (``Signal_Not_Available``, ``Sensor_Error``).  ``factor``, ``offset``,
   ``unit`` and the limits apply to every raw value **except** those
   matched by an entry in ``value_encoding``.

   .. code-block:: yaml

      signal:
        name: EngineCoolantTemp
        description: Engine coolant temperature.
        bit_length: 8
        data_type: uint8
        factor: 1.0
        offset: -40.0
        lower_limit: -40.0
        upper_limit: 215.0
        unit: degC
        value_encoding:
          type: text_table
          entries:
            - value: 254
              label: Sensor_Error
            - value: 255
              label: Signal_Not_Available

.. admonition:: Expand for a YAML example — value ranges (``range_text_table``)
   :collapsible: closed

   When one label covers many contiguous raw values, use
   ``range_text_table`` with inclusive ``from_value``/``to_value``
   bounds.  Ranges must not overlap.

   .. code-block:: yaml

      signal:
        name: Severity
        description: Severity bucket derived from raw severity code.
        bit_length: 8
        data_type: uint8
        value_encoding:
          type: range_text_table
          entries:
            - from_value: 0
              to_value: 9
              label: Low
            - from_value: 10
              to_value: 99
              label: Medium
            - from_value: 100
              to_value: 200
              label: High
            - from_value: 255
              to_value: 255
              label: Signal_Not_Available

.. admonition:: Expand for a YAML example — packed status word (``bitfield_text_table``)
   :collapsible: closed

   Several unrelated **sub-enums** packed into one integer signal.  Each
   :class:`~flync.model.flync_4_signal.BitfieldGroup` owns a disjoint
   region of bits via its ``mask`` and contributes exactly one active
   state at a time; matching is
   ``state.from_value <= (raw & group.mask) <= state.to_value``.  The
   example below decodes a 16-bit status word into two groups —
   ``Problem`` in the low byte and ``Mode`` in the high byte.

   .. code-block:: yaml

      signal:
        name: StatusWord
        description: Packed problem indicator and operating mode.
        bit_length: 16
        data_type: uint16
        value_encoding:
          type: bitfield_text_table
          groups:
            - name: Problem
              mask: 0x00FF
              states:
                - label: ProblemNone
                  from_value: 0x0000
                  to_value: 0x0000
                - label: ProblemFailure
                  from_value: 0x0008
                  to_value: 0x0008
                - label: ProblemMajor
                  from_value: 0x0018
                  to_value: 0x0018
            - name: Mode
              mask: 0xFF00
              states:
                - label: ModeIdle
                  from_value: 0x0000
                  to_value: 0x0000
                - label: ModeActive
                  from_value: 0x0100
                  to_value: 0x0100

.. admonition:: Expand for a YAML example — partial-network bitmask (``bitmask_flags``)
   :collapsible: closed

   A relevance vector where each bit names one vehicle function as
   currently active; several flags can be set simultaneously.  Masks
   must be pairwise disjoint.  A flag is active when
   ``(raw & flag.mask) == flag.mask``, so the decoded value is the
   **set** of active labels (e.g. raw ``0b00001011`` →
   ``{MirrorLeft, MirrorRight, EngineStatus}``).

   .. code-block:: yaml

      signal:
        name: PartialNetworkRelevance
        description: >-
          Per-function partial-network relevance bitmask.  Each bit
          marks one vehicle function as currently relevant or awake;
          several bits may be set at the same time.
        bit_length: 8
        data_type: uint8
        value_encoding:
          type: bitmask_flags
          flags:
            - mask: 0x01
              label: MirrorLeft
            - mask: 0x02
              label: MirrorRight
            - mask: 0x04
              label: CabinLight
            - mask: 0x08
              label: EngineStatus
            - mask: 0x10
              label: TransmissionStatus
            - mask: 0x20
              label: VehicleDynamics

.. autoclass:: flync.model.flync_4_signal.InstancePlacement()

.. autoclass:: flync.model.flync_4_signal.SignalInstance()

Signal Groups
=============

A :class:`~flync.model.flync_4_signal.SignalGroup` collects several
:class:`~flync.model.flync_4_signal.SignalInstance` placements that are
always transmitted together.  Each contained ``SignalInstance`` carries a
``bit_position`` interpreted as an offset **relative to the group's
origin** — i.e. the
:attr:`~flync.model.flync_4_signal.SignalGroupInstance.bit_position`
where the group is placed inside a PDU; the absolute PDU offset of a
signal in a placed group is therefore
``group_instance.bit_position + signal_instance.bit_position``.

A :class:`~flync.model.flync_4_signal.SignalGroupInstance` places the
entire group at a single bit offset within a PDU, analogous to how
:class:`~flync.model.flync_4_signal.SignalInstance` places a single signal.
The group's footprint inside a PDU is the largest end-bit reached by any
of its placed signal instances; instances without a ``bit_position`` are
treated as unplaced and skipped during footprint and overlap checks.
Signal instances inside the same group are also checked for mutual
overlap, mirroring the placement checks performed at the PDU level.

.. autoclass:: flync.model.flync_4_signal.SignalGroup()

.. autoclass:: flync.model.flync_4_signal.SignalGroupInstance()


.. _pdu_model:

PDU
###

A **PDU** (Protocol Data Unit) is the container that groups signals
for transmission.  PDUs are defined independently of any specific bus
and stored in ``communication/channels/pdus/``.  A
:class:`~flync.model.flync_4_signal.PDUInstance` then places a named
PDU at a given bit offset inside a :ref:`frame <frame_model>`.

.. admonition:: Expand for Schematic
   :collapsible: closed

   .. mermaid:: ../../_static/mermaid/pdu.mmd

There are three PDU types, distinguished by the ``type`` discriminator field:

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - ``type``
     - Description
   * - ``standard``
     - Non-multiplexed PDU containing a flat list of signal (group) instances.
   * - ``multiplexed``
     - PDU with a selector signal; the active signal group depends on its value.
   * - ``container``
     - Ethernet Container PDU that packs several other PDUs into one payload.

.. autoclass:: flync.model.flync_4_signal.PDU()

Standard PDU
============

.. admonition:: Expand for a YAML example - 📄 ``communication/channels/pdus/PDU_EngineStatus.flync.yaml``
   :collapsible: closed

   .. note::
      Each PDU is stored in its own ``.flync.yaml`` file under
      ``communication/channels/pdus/``.  This directory is **optional** and
      may be omitted when no PDUs are defined.

   .. literalinclude:: ../../../../examples/flync_example/communication/channels/pdus/PDU_EngineStatus.flync.yaml
      :language: yaml

.. autoclass:: flync.model.flync_4_signal.StandardPDU()

Multiplexed PDU
===============

.. admonition:: Expand for a YAML example - 📄 ``communication/channels/pdus/PDU_TransmissionStatus.flync.yaml``
   :collapsible: closed

   .. note::
      A multiplexed PDU uses a ``selector_signal`` (the MUX switch)
      to select which ``mux_groups`` block of signals is active on each
      transmission cycle.  This corresponds to the DBC ``M``/``mN``
      multiplexer notation.

   .. literalinclude:: ../../../../examples/flync_example/communication/channels/pdus/PDU_TransmissionStatus.flync.yaml
      :language: yaml

.. autoclass:: flync.model.flync_4_signal.MultiplexedPDU()

.. autoclass:: flync.model.flync_4_signal.MuxGroup()


.. _container_pdu:

Container PDU
=============

.. admonition:: Expand for a YAML example - 📄 ``communication/channels/ethernet_pdu_containers/eth_powertrain_container.flync.yaml``
   :collapsible: closed

   .. note::
      An Ethernet Container PDU is stored in its own ``.flync.yaml``
      file under ``communication/channels/pdus/``, alongside all other PDU
      types.  It bundles several application PDUs into one Ethernet
      payload.  The per-slot header format is configured via the ``header``
      block, which specifies ``id_length_bits`` and ``length_field_bits``.

   .. literalinclude:: ../../../../examples/flync_example/communication/channels/ethernet_pdu_containers/eth_powertrain_container.flync.yaml
      :language: yaml

.. autoclass:: flync.model.flync_4_signal.ContainerPDUHeader()

.. autoclass:: flync.model.flync_4_signal.ContainerPDU()

.. autoclass:: flync.model.flync_4_signal.ContainedPDURef()

.. autoclass:: flync.model.flync_4_signal.PDUInstance()


.. _frame_model:

Frame
#####

A **Frame** is the protocol-specific transport unit that carries one
or more PDUs on a physical bus.  CAN and CAN FD frames are defined
inside ``communication/channels/can/``; LIN frames inside
``communication/channels/lin/``.  All frame types reference PDUs by
name via :class:`~flync.model.flync_4_signal.PDUInstance`.

For Ethernet, there is no frame layer — sockets reference a
:class:`~flync.model.flync_4_signal.ContainerPDU` directly via a
``pdu_sender`` or ``pdu_receiver`` deployment.

.. admonition:: Expand for Schematic
   :collapsible: closed

   .. mermaid:: ../../_static/mermaid/frame.mmd

.. autoclass:: flync.model.flync_4_signal.Frame()

.. autoclass:: flync.model.flync_4_signal.CANFrameBase()

.. autoclass:: flync.model.flync_4_signal.CANFrame()

.. autoclass:: flync.model.flync_4_signal.CANFDFrame()

.. autoclass:: flync.model.flync_4_signal.LINFrame()

PDU Sender / Receiver Deployments
==================================

.. admonition:: Expand for a YAML example - 📄 ``ecus/high_performance_compute/controllers/hpc_controller1/ethernet_interfaces/hpc_c1_iface1/sockets/socket_pdu.flync.yaml``
   :collapsible: closed

   .. note::
      A ``pdu_sender`` deployment binds a
      :class:`~flync.model.flync_4_signal.ContainerPDU` to a socket on
      the publishing ECU.  A ``pdu_receiver`` deployment does the same for
      the subscribing ECU.  Both are added to the ``deployments`` list of a
      :class:`~flync.model.flync_4_ecu.SocketTCP` or
      :class:`~flync.model.flync_4_ecu.SocketUDP`.

   .. literalinclude:: ../../../../examples/flync_example/ecus/high_performance_compute/controllers/hpc_controller1/ethernet_interfaces/hpc_c1_iface1/sockets/socket_pdu.flync.yaml
      :language: yaml

.. autoclass:: flync.model.flync_4_signal.PDUSender()

.. autoclass:: flync.model.flync_4_signal.PDUReceiver()

PDU Forwarder Deployments
==========================

A **PDU Forwarder** is a third per-PDU role (alongside ``pdu_sender``
and ``pdu_receiver``) that consumes a PDU on its parent carrier and re-emits
it on one or more **egresses**. The same primitive exists on both sides of the
modelled network:

* :class:`~flync.model.flync_4_signal.PDUForwarder` is an Ethernet-side
  deployment that lives inside a socket's ``deployments`` block.
* :class:`~flync.model.flync_4_signal.CANFrameForwarder` is a CAN-interface
  list entry under ``forwarder_frames`` on
  :class:`~flync.model.flync_4_ecu.CANInterfaceConfig`.

Each forwarder lists one or more
:class:`~flync.model.flync_4_signal.ForwarderEgress` items — a discriminated
union of :class:`~flync.model.flync_4_signal.CANFrameEgress` (re-emit on a CAN
frame) and :class:`~flync.model.flync_4_signal.EthSocketEgress` (re-emit on an
Ethernet socket). Optional ``extract_pdu_ref`` on an egress selects a single
inner PDU when the ingress is a
:class:`~flync.model.flync_4_signal.ContainerPDU`.

.. admonition:: Expand for a YAML example - 📄 ``ecus/high_performance_compute/controllers/hpc_controller1/can_interfaces/powertrain_can_interface.flync.yaml``
   :collapsible: closed

   .. note::
      A ``forwarder_frames`` entry consumes ``frame_ref`` from the parent
      interface's bus and re-emits it on one or more egresses. The example
      below fans ``Frame_EngineStatus`` to a CAN frame on ``DiagCAN`` (CAN →
      CAN) and to an Ethernet socket (CAN → Ethernet).

   .. literalinclude:: ../../../../examples/flync_example/ecus/high_performance_compute/controllers/hpc_controller1/can_interfaces/powertrain_can_interface.flync.yaml
      :language: yaml

.. admonition:: Expand for a YAML example - 📄 ``ecus/high_performance_compute/controllers/hpc_controller1/ethernet_interfaces/hpc_c1_iface1/sockets/socket_pdu.flync.yaml``
   :collapsible: closed

   .. note::
      A ``pdu_forwarder`` deployment consumes ``pdu_ref`` on the parent
      socket. The forwarder on ``pdu_powertrain_rx`` extracts
      ``PDU_EngineStatus`` from the inbound container and emits it on the
      ``DiagCAN`` diagnostic frame (Ethernet → CAN), and also re-bridges the
      whole container to a peer Ethernet socket (Ethernet → Ethernet).

   .. literalinclude:: ../../../../examples/flync_example/ecus/high_performance_compute/controllers/hpc_controller1/ethernet_interfaces/hpc_c1_iface1/sockets/socket_pdu.flync.yaml
      :language: yaml

.. autoclass:: flync.model.flync_4_signal.PDUForwarder()

.. autoclass:: flync.model.flync_4_signal.CANFrameForwarder()

.. autoclass:: flync.model.flync_4_signal.ForwarderEgress()

.. autoclass:: flync.model.flync_4_signal.CANFrameEgress()

.. autoclass:: flync.model.flync_4_signal.EthSocketEgress()

Frame Timing
============

Transmission timing is configured at the **frame** layer for every
protocol.  Each CAN, CAN FD, or LIN frame may carry an optional
``timing`` field that drives cyclic, event-driven, and debounce
scheduling of the frame as a whole on the wire.

.. autoclass:: flync.model.flync_4_signal.FrameTransmissionTiming()

.. autoclass:: flync.model.flync_4_signal.FrameCyclicTiming()

.. autoclass:: flync.model.flync_4_signal.FrameEventTiming()
