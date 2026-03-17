.. _topology:

****************
flync_4_topology
****************

.. autoclass:: flync.model.flync_4_topology.FLYNCTopology()

System Topology
################

.. admonition:: Expand for Schematic
   :collapsible: closed

   .. mermaid:: ../../_static/mermaid/system_topology.mmd


.. admonition:: Expand for a YAML example - 📄 ``system_topology.flync.yaml``
   :collapsible: closed

   .. note::
      In system_topology the external connections between ECUs of the system are described (if more than one ECU is specified).

   .. literalinclude:: ../../_static/flync_example/topology/system_topology.flync.yaml
      :language: yaml


.. hint::

   All the connections listed in a system topology shall be of the ``type`` : ``ecu_port_to_ecu_port``.

.. autoclass:: flync.model.flync_4_topology.SystemTopology()
.. autoclass:: flync.model.flync_4_topology.ExternalConnection()

