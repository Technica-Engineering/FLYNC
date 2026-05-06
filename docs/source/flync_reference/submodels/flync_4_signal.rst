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
   :members:
   :undoc-members:

.. autoclass:: flync.model.flync_4_signal.Signal()

.. autoclass:: flync.model.flync_4_signal.ValueDescription()

.. autoclass:: flync.model.flync_4_signal.InstancePlacement()

.. autoclass:: flync.model.flync_4_signal.SignalInstance()

Signal Groups
=============

A :class:`~flync.model.flync_4_signal.SignalGroup` collects several
signals that are always transmitted together.  A
:class:`~flync.model.flync_4_signal.SignalGroupInstance` places the
entire group at a single bit offset within a PDU, analogous to how
:class:`~flync.model.flync_4_signal.SignalInstance` places a single signal.

.. autoclass:: flync.model.flync_4_signal.SignalGroup()

.. autoclass:: flync.model.flync_4_signal.SignalGroupInstance()


.. _pdu_model:

PDU
###

A **PDU** (Protocol Data Unit) is the container that groups signals
for transmission.  PDUs are defined independently of any specific bus
and stored in ``general/channels/pdus/``.  A
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

.. admonition:: Expand for a YAML example - 📄 ``general/channels/pdus/PDU_EngineStatus.flync.yaml``
   :collapsible: closed

   .. note::
      Each PDU is stored in its own ``.flync.yaml`` file under
      ``general/channels/pdus/``.  This directory is **optional** and
      may be omitted when no PDUs are defined.

   .. literalinclude:: ../../../../examples/flync_example/general/channels/pdus/PDU_EngineStatus.flync.yaml
      :language: yaml

.. autoclass:: flync.model.flync_4_signal.StandardPDU()

Multiplexed PDU
===============

.. admonition:: Expand for a YAML example - 📄 ``general/channels/pdus/PDU_TransmissionStatus.flync.yaml``
   :collapsible: closed

   .. note::
      A multiplexed PDU uses a ``selector_signal`` (the MUX switch)
      to select which ``mux_groups`` block of signals is active on each
      transmission cycle.  This corresponds to the DBC ``M``/``mN``
      multiplexer notation.

   .. literalinclude:: ../../../../examples/flync_example/general/channels/pdus/PDU_TransmissionStatus.flync.yaml
      :language: yaml

.. autoclass:: flync.model.flync_4_signal.MultiplexedPDU()

.. autoclass:: flync.model.flync_4_signal.MuxGroup()


.. _container_pdu:

Container PDU
=============

.. admonition:: Expand for a YAML example - 📄 ``general/channels/ethernet_pdu_containers/eth_powertrain_container.flync.yaml``
   :collapsible: closed

   .. note::
      An Ethernet Container PDU is stored in its own ``.flync.yaml``
      file under ``general/channels/pdus/``, alongside all other PDU
      types.  It bundles several application PDUs into one Ethernet
      payload.  The per-slot header format is configured via the ``header``
      block, which specifies ``id_length_bits`` and ``length_field_bits``.

   .. literalinclude:: ../../../../examples/flync_example/general/channels/ethernet_pdu_containers/eth_powertrain_container.flync.yaml
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
inside ``general/channels/can/``; LIN frames inside
``general/channels/lin/``.  All frame types reference PDUs by
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

Frame Timing
============

Transmission timing is configured at the **frame** layer for every
protocol.  Each CAN, CAN FD, or LIN frame may carry an optional
``timing`` field that drives cyclic, event-driven, and debounce
scheduling of the frame as a whole on the wire.

.. autoclass:: flync.model.flync_4_signal.FrameTransmissionTiming()

.. autoclass:: flync.model.flync_4_signal.FrameCyclicTiming()

.. autoclass:: flync.model.flync_4_signal.FrameEventTiming()
