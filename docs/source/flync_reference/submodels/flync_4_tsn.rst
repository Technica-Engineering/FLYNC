.. _tsn:

***********
flync_4_tsn
***********

.. _time_sync:

Time Synchronization (gPTP)
###########################

.. admonition:: Expand for Schematic
   :collapsible: closed

   .. mermaid:: ../../_static/mermaid/timesync.mmd

.. hint::
   Find a YAML example for gPTP inside the :ref:`Switch example <switch>` (key ptp_config).

.. autoclass:: flync.model.flync_4_tsn.PTPTimeTransmitterConfig()
.. autoclass:: flync.model.flync_4_tsn.PTPTimeReceiverConfig()
.. autoclass:: flync.model.flync_4_tsn.PTPPdelayConfig()
.. autoclass:: flync.model.flync_4_tsn.PTPPort()
.. autoclass:: flync.model.flync_4_tsn.PTPConfig()

.. _qos:

Quality of Service (QoS)
#########################

.. admonition:: Expand for Schematic
   :collapsible: closed

   .. mermaid:: ../../_static/mermaid/qos.mmd

.. autoclass:: flync.model.flync_4_tsn.FrameFilter()

Ingress Per-Stream Filtering and Policing
==========================================

.. hint::
   Find a YAML example for Ingress Streams inside the :ref:`Switch example <switch>` (key ingress_streams).

.. autoclass:: flync.model.flync_4_tsn.Stream()
.. autoclass:: flync.model.flync_4_tsn.ATSInstance()
.. autoclass:: flync.model.flync_4_tsn.SingleRateTwoColorMarker()
.. autoclass:: flync.model.flync_4_tsn.SingleRateThreeColorMarker()
.. autoclass:: flync.model.flync_4_tsn.DoubleRateThreeColorMarker()


Egress Traffic Shaping
######################

.. hint::
   Find a YAML example for Traffic Classes inside the :ref:`Switch example <switch>` (key traffic_classes).

.. autoclass:: flync.model.flync_4_tsn.TrafficClass()

Shapers
========

.. autoclass:: flync.model.flync_4_tsn.CBSShaper()
.. autoclass:: flync.model.flync_4_tsn.ATSShaper()

.. autoclass:: flync.model.flync_4_tsn.HTBInstance()
.. autoclass:: flync.model.flync_4_tsn.HTBFilter()
.. autoclass:: flync.model.flync_4_tsn.ChildClass()
