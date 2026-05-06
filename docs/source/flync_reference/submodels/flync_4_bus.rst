.. _bus:

***********
flync_4_bus
***********

The ``flync_4_bus`` module defines the physical communication buses
that carry :ref:`Frames <frame_model>` across the vehicle network.
Each bus configuration file lives in its own sub-folder under
``general/channels/`` and contains the bus-level parameters, the
participating nodes, and the full list of frames transmitted on that
bus.

.. hint::

   Frames referenced inside a bus configuration are defined inline
   within the bus YAML file.  They reference PDUs by name
   (``pdu_ref``) — the PDU definitions themselves live in
   ``general/channels/pdus/`` (see :ref:`pdu_model`).


.. _can_bus:

CAN Bus
#######

.. admonition:: Expand for Schematic
   :collapsible: closed

   .. mermaid:: ../../_static/mermaid/can.mmd

.. admonition:: Expand for a YAML example - 📄 ``general/channels/can/<bus_name>.flync.yaml``
   :collapsible: closed

   .. note::
      Each CAN or CAN FD bus is stored in its own ``.flync.yaml``
      file under ``general/channels/can/``.  The bus identity comes
      from the ``name`` field inside the file, not from the file name.
      This directory is **optional** — omit it when the system has no
      CAN buses.

   .. literalinclude:: ../../../../examples/flync_example/general/channels/can/powertrain_can.flync.yaml
      :language: yaml

.. autoclass:: flync.model.flync_4_bus.CANBus()


.. _lin_bus:

LIN Bus
#######

.. admonition:: Expand for Schematic
   :collapsible: closed

   .. mermaid:: ../../_static/mermaid/lin.mmd

.. admonition:: Expand for a YAML example - 📄 ``general/channels/lin/<bus_name>.flync.yaml``
   :collapsible: closed

   .. note::
      Each LIN bus is stored in its own ``.flync.yaml`` file under
      ``general/channels/lin/``.  A LIN bus must have **exactly one**
      master node and any number of slave nodes.  Schedule tables
      reference frames by name — all frame names used in
      ``schedule_tables`` must be defined in ``frames``.
      This directory is **optional** — omit it when the system has no
      LIN buses.

   .. literalinclude:: ../../../../examples/flync_example/general/channels/lin/body_lin.flync.yaml
      :language: yaml

.. autoclass:: flync.model.flync_4_bus.LINBus()

Schedule Tables
===============

.. autoclass:: flync.model.flync_4_bus.LINScheduleTable()

.. autoclass:: flync.model.flync_4_bus.LINScheduleEntry()
