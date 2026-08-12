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

   .. literalinclude:: ../../_static/flync_example/topology/system_topology.flync.yaml
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

