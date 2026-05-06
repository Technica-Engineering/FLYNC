.. _general:

******************************
flync_4_general_configuration
******************************

The ``flync_4_general_configuration`` module holds the system-wide
configuration shared across all ECUs in the project, including bus
definitions, PDU and frame definitions, SOME/IP service descriptions,
and TCP profiles.

.. admonition:: Expand for Schematic
   :collapsible: closed

   .. mermaid:: ../../_static/mermaid/general_configs.mmd

.. autoclass:: flync.model.flync_4_general_configuration.FLYNCGeneralConfig()


.. _channel_config:

Channel Configuration
#####################

:class:`~flync.model.flync_4_general_configuration.FLYNCChannelConfig`
groups all bus and PDU definitions that are stored under
``general/channels/``.  Every sub-field is **optional** — omit the
corresponding sub-folder entirely when the system does not use that
channel type.

.. list-table:: Channel sub-folders
   :header-rows: 1
   :widths: 35 65

   * - Sub-folder
     - Content
   * - ``general/channels/pdus/``
     - :ref:`PDU <pdu_model>` definitions (:ref:`Standard <pdu_model>`, :ref:`Multiplexed <pdu_model>`, :ref:`Container <pdu_model>`). One file per PDU.
   * - ``general/channels/can/``
     - :ref:`CAN / CAN FD <can_bus>` bus configurations. One file per bus.
   * - ``general/channels/lin/``
     - :ref:`LIN <lin_bus>` bus configurations. One file per bus.
   * - ``general/channels/ethernet_pdu_containers/``
     - :ref:`Ethernet <container_pdu>` definitions.

.. autoclass:: flync.model.flync_4_general_configuration.FLYNCChannelConfig()

TCP Options
#############


.. _tcp_option:

.. admonition:: Expand for a YAML example - 📄 ``tcp_profiles.flync.yaml``
   :collapsible: closed

   .. note::
      This file contains a list of TCP profiles that describes a bunch of TCP options that can be set in a socket.
      These profiles can be imported in a TCP socket.

   .. literalinclude:: ../../_static/flync_example/general/tcp_profiles.flync.yaml

.. autoclass:: flync.model.flync_4_ecu.sockets.TCPOption()

.. autoclass:: flync.model.flync_4_ecu.sockets.UDPOption()
