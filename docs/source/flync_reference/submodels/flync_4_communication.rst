.. _communication:

******************************
flync_4_communication
******************************

The ``flync_4_communication`` module holds the system-wide
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

.. autoclass:: flync.model.flync_4_general_configuration.FLYNCChannelConfig()

TCP Options
#############


.. _tcp_option:

.. admonition:: Expand for a YAML example - 📄 ``tcp_profiles.flync.yaml``
   :collapsible: closed

   .. note::
      This file contains a list of TCP profiles that describes a bunch of TCP options that can be set in a socket.
      These profiles can be imported in a TCP socket.

   .. literalinclude:: ../../_static/flync_example/communication/tcp_profiles.flync.yaml

.. autoclass:: flync.model.flync_4_ecu.sockets.TCPOption()

.. autoclass:: flync.model.flync_4_ecu.sockets.UDPOption()
