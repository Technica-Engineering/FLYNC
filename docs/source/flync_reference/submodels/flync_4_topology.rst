.. _topology:

****************
flync_4_topology
****************

.. autoclass:: flync.model.flync_4_topology.FLYNCTopology()

Ethernet Topology
#################

.. admonition:: Expand for Schematic
   :collapsible: closed

   .. mermaid:: ../../_static/mermaid/ethernet_topology.mmd


.. admonition:: Expand for a YAML example - 📄 ``ethernet_topology.flync.yaml``
   :collapsible: closed

   .. note::
      In ethernet_topology the external connections between ECUs of the system are described (if more than one ECU is specified).

   .. literalinclude:: ../../_static/flync_example/topology/ethernet_topology.flync.yaml
      :language: yaml


.. hint::

   All the connections listed in a ethernet topology shall be of the ``type`` : ``ecu_port_to_ecu_port``.

.. autoclass:: flync.model.flync_4_topology.EthernetTopology()
.. autoclass:: flync.model.flync_4_topology.ExternalConnection()


.. _bus_topology:

CAN and LIN Bus Topology
########################

.. note::
   Unlike the Ethernet topology, the CAN and LIN bus topology is **never authored in YAML**. There is no bus-topology
   file. It is recomputed on every model load from the ``bus_ref`` declared on each controller's CAN and LIN interfaces
   (see :ref:`ecu`), and every CAN/LIN bus declared under ``communication.channels``.

The derived topology gives a system-wide view of which ECU interfaces attach to which bus. It is exposed on the model
via :meth:`~flync.model.flync_model.FLYNCModel.get_can_bus_topology` and
:meth:`~flync.model.flync_model.FLYNCModel.get_lin_bus_topology`, and stored on the ``can_bus_topology`` /
``lin_bus_topology`` fields of :class:`~flync.model.flync_4_topology.FLYNCTopology`.

.. hint::

   The derivation runs the following consistency checks:

   - **Unknown bus** (*major*): a CAN/LIN interface references a ``bus_ref`` that is not declared under
     ``communication.channels``.
   - **LIN master cardinality** (*major*): a LIN bus must have exactly one master interface.
   - **LIN master missing** (*warning*): a LIN bus has slave interfaces but no master.
   - **Unused bus** (*warning*): a bus is declared but no interface attaches to it.
   - **Single node** (*warning*): only one interface attaches to a bus.

.. autoclass:: flync.model.flync_4_topology.BusTopology()
.. autoclass:: flync.model.flync_4_topology.CANBusTopology()
.. autoclass:: flync.model.flync_4_topology.LINBusTopology()
.. autoclass:: flync.model.flync_4_topology.BusAttachmentPoint()

.. _ethernet_multidrop:

Ethernet Multidrop
==================

A point-to-point connection wires two ports.  An ``ethernet_multidrop`` connection wires N onto one shared
medium, so it also carries the PLCA cycle those ports have to agree on: ``plca.transmit_opportunity_count``
(how many slots one cycle has), ``plca.to_timer`` (how long a slot whose owner has nothing to send stays open,
in bit times of 100 ns, default 32), and each node's ``node_id`` (which slot that port owns).

A node without a ``node_id`` takes no part in PLCA and competes for the medium instead.  Node id
0 makes a node the **coordinator**, which opens each cycle; there is exactly one.  Leaving the ``plca`` block off
altogether makes the segment a plain CSMA/CD medium.

What stays on each port is what nodes may legitimately differ in: the PHY itself, and ``burst_count`` and
``burst_timer`` per node.  The connection stores no PHY type, so a segment mixing PHY variants needs no model
change.

.. admonition:: Expand for Schematic
   :collapsible: closed

   .. mermaid:: ../../_static/mermaid/ethernet_multidrop.mmd

.. admonition:: Expand for a YAML example - 📄 ``topology/ethernet_topology.flync.yaml``
   :collapsible: closed

   .. literalinclude:: ../../../../examples/flync_example/topology/ethernet_topology.flync.yaml
      :language: yaml

Each rule reports a ``FLYNC-TOP-...`` identifier that the
:doc:`error catalog </error_catalog>` explains in full, with its severity and message.

.. autoclass:: flync.model.flync_4_topology.EthernetMultidropConnection()
.. autoclass:: flync.model.flync_4_topology.EthernetMultidropNode()
.. autoclass:: flync.model.flync_4_topology.PLCACycle()


TSN on a shared medium is narrowed. gPTP works under two constraints
(rejects ``cmlds_linkport_enabled`` and ``two_step: false``; errors 263,
264), several time transmitters must sit in different domains (warning
265), and an egress shaper loses its latency bound to the cycle (warning
259). Each rule's severity and message live in the
:doc:`error catalog </error_catalog>`.
