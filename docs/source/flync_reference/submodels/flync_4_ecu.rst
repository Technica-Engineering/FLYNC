.. _ecu:

###########
flync_4_ecu
###########

ECU Config
##########


.. admonition:: Expand for Schematic
   :collapsible: closed

   .. mermaid:: ../../_static/mermaid/ecu.mmd

.. autoclass:: flync.model.flync_4_ecu.ecu.ECU()


.. _ecu_ports:

ECU Ports Config
#################


.. admonition:: Expand for Schematic
   :collapsible: closed

   .. mermaid:: ../../_static/mermaid/ecu_port.mmd


.. admonition:: Expand for a YAML example - 📄 ``ports.flync.yaml``
   :collapsible: closed

   .. note::
      The external physical ports (and PHYs) of the ECUs of the system are configured in one dedicated file.
      For an ECU config, this file is **mandatory** since all ECUs need to define (at least) one port.

   .. literalinclude:: ../../_static/flync_example/ecus/eth_ecu/ports.flync.yaml
      :language: yaml


.. hint::

   In case of a port with an external PHY, we need to include ``mdi_config`` (see :ref:`mdi_config`), and ``mii_config`` (see :ref:`mii_config`).

.. autoclass:: flync.model.flync_4_ecu.port.ECUPort()


.. _controller:

Controller Config
##################

.. admonition:: Expand for Schematic
   :collapsible: closed

   .. mermaid:: ../../_static/mermaid/controller.mmd

.. _controller_example:

.. admonition:: Expand for a YAML example - 📁 ``controllers/``
   :collapsible: closed

   .. note::
      This directory contains the configuration files that describe each one of the host controllers of the device.
      Each controller shall have its own YAML file.
      This is a **mandatory** dir for the ECU configuration, since all ECUs need to define (at least) one controller.


   .. literalinclude:: ../../_static/flync_example/ecus/eth_ecu/controllers/eth_ecu_controller1.flync.yaml
      :language: yaml


.. hint::

   For controller interfaces that have an external PHY, the ``mii_config`` (see :ref:`mii_config`) for that interface must be provided.
   For controller interfaces with integrated PHY, no ``mii_config`` is needed.

.. warning::

   In any case, the MDI configuration is **never** configured on the controller interface, but on the ECU Ports. See :ref:`ecu_ports` for more details.


.. autoclass:: flync.model.flync_4_ecu.Controller()
.. autoclass:: flync.model.flync_4_ecu.ControllerInterface()
.. autoclass:: flync.model.flync_4_ecu.VirtualControllerInterface()


.. _switch:

Switch Config
##############

.. admonition:: Expand for Schematic
   :collapsible: closed

   .. mermaid:: ../../_static/mermaid/switch.mmd


.. admonition:: Expand for a YAML example - 📁 ``switches/``
   :collapsible: closed

   .. note::
      The switches directory contains the individual configuration files for every ethernet switch that is present in that ECU.
      This is a **non-mandatory** directory for the ECU configuration, since not all ECUs have switches.

   .. literalinclude:: ../../_static/flync_example/ecus/high_processing_core/switches/hpc_switch1.flync.yaml
      :language: yaml

.. hint::

   A switch configuration contains key details regarding the following parameters:

   - switch (logical) ports
   - VLAN configuration
   - multicast configuration
   - TimeSync configuration
   - QoS configuration

.. hint::

   Similar to controller config, each port of switch with an external PHY has an ``mii_config`` (see :ref:`mii_config`),
   describing the various properties of the MII connected to that port.
   For switch ports using an integrated PHY, no ``mii_config`` is needed.

.. autoclass:: flync.model.flync_4_ecu.switch.Switch()
.. autoclass:: flync.model.flync_4_ecu.switch.SwitchPort()
.. autoclass:: flync.model.flync_4_ecu.switch.VLANEntry()
.. autoclass:: flync.model.flync_4_ecu.switch.MulticastGroup()

TCAM
=====

.. autoclass:: flync.model.flync_4_ecu.switch.TCAMRule()
.. autoclass:: flync.model.flync_4_ecu.switch.Drop()
.. autoclass:: flync.model.flync_4_ecu.switch.Mirror()
.. autoclass:: flync.model.flync_4_ecu.switch.ForceEgress()
.. autoclass:: flync.model.flync_4_ecu.switch.VLANOverwrite()
.. autoclass:: flync.model.flync_4_ecu.switch.RemoveVLAN()


.. _phy:

PHY Config
###########

.. _mdi_config:

Media-Dependent Interfaces
===========================


.. autoclass:: flync.model.flync_4_ecu.phy.BASET()
.. autoclass:: flync.model.flync_4_ecu.phy.BASET1()
.. autoclass:: flync.model.flync_4_ecu.phy.BASET1S()


.. _mii_config:

Media-Independent Interfaces
============================

.. autoclass:: flync.model.flync_4_ecu.phy.MII()
.. autoclass:: flync.model.flync_4_ecu.phy.RMII()
.. autoclass:: flync.model.flync_4_ecu.phy.SGMII()
.. autoclass:: flync.model.flync_4_ecu.phy.RGMII()
.. autoclass:: flync.model.flync_4_ecu.phy.XFI()

.. _internal_topology:

ECU Internal Topology
######################

.. admonition:: Expand for Schematic
   :collapsible: closed

   .. mermaid:: ../../_static/mermaid/ecu_topology.mmd

.. admonition:: Expand for a YAML example - 📄 ``topology.flync.yaml``
   :collapsible: closed

   .. note::
      This file contains all the different internal connections between entities of an ECU (ports, switch ports, controller interfaces, ...) to resolve the internal topology of the component and run validation checks on the model.
      This is a **mandatory** file for the ECU configuration, since all ECUs present (at least) one ECU port and one Controller Interface.

   .. literalinclude:: ../../_static/flync_example/ecus/eth_ecu/topology.flync.yaml


Internal Connection
===================

.. note:: The fields of a connection will be different, depending on the kind of connection.

Types of Internal Connections
=============================


.. table:: **Types of Internal Connections**
   :align: left

   +-------------------------------------------------+-------------------------------+-----------------------------+
   |``type``                                         |1st Attribute                  |2nd Attribute                |
   +=================================================+===============================+=============================+
   |``ecu_port_to_switch_port``                      |``ecu_port``                   |``switch_port``              |
   +-------------------------------------------------+-------------------------------+-----------------------------+
   |``ecu_port_to_controller_interface``             |``ecu_port``                   |``controller_interface``     |
   +-------------------------------------------------+-------------------------------+-----------------------------+
   |``switch_port_to_controller_interface``          |``switch_port``                |``controller_interface``     |
   +-------------------------------------------------+-------------------------------+-----------------------------+
   |``switch_port_to_switch_port``                   |``switch_port_1``              |``switch_port_2``            |
   +-------------------------------------------------+-------------------------------+-----------------------------+
   |``controller_interface_to_controller_interface`` |``controller_interface_1``     |``controller_interface_2``   |
   +-------------------------------------------------+-------------------------------+-----------------------------+

.. autoclass:: flync.model.flync_4_ecu.internal_topology.InternalTopology()
.. autoclass:: flync.model.flync_4_ecu.internal_topology.InternalConnectionUnion()
.. autoclass:: flync.model.flync_4_ecu.internal_topology.InternalConnection()

.. autoclass:: flync.model.flync_4_ecu.internal_topology.ECUPortToXConnection()
.. autoclass:: flync.model.flync_4_ecu.internal_topology.SwitchPortToXConnection()
.. autoclass:: flync.model.flync_4_ecu.internal_topology.ECUPortToSwitchPort()
.. autoclass:: flync.model.flync_4_ecu.internal_topology.ECUPortToControllerInterface()
.. autoclass:: flync.model.flync_4_ecu.internal_topology.SwitchPortToControllerInterface()
.. autoclass:: flync.model.flync_4_ecu.internal_topology.SwitchPortToSwitchPort()
.. autoclass:: flync.model.flync_4_ecu.internal_topology.ControllerInterfaceToControllerInterface()


.. _socket:

Socket Config
##############

.. admonition:: Expand for Schematic
   :collapsible: closed

   .. mermaid:: ../../_static/mermaid/socket.mmd


.. admonition:: Expand for a YAML example - 📁 ``sockets/``
   :collapsible: closed

   .. note::
      This directory contains files that define a group of sockets per VLAN.
      Each file defines the sockets (VLAN ID, address endpoint and port number) and
      lists the deployments that use each socket.

      It is advisable to keep sockets that provide similar functionality together
      (e.g. all SOME/IP sockets in the same file).

   .. literalinclude:: ../../_static/flync_example/ecus/eth_ecu/sockets/socket_someip.flync.yaml


.. autoclass:: flync.model.flync_4_ecu.socket_container.SocketContainer()
.. autoclass:: flync.model.flync_4_ecu.sockets.Socket()
.. autoclass:: flync.model.flync_4_ecu.sockets.SocketUDP()
.. autoclass:: flync.model.flync_4_ecu.sockets.SocketTCP()

Options
========

.. _tcp_option:

.. admonition:: Expand for a YAML example - 📄 ``tcp_profiles.flync.yaml``
   :collapsible: closed

   .. note::
      This file contains a list of TCP profiles that describes a bunch of TCP options that can be set in a socket.
      These profiles can be imported in a TCP socket.

   .. literalinclude:: ../../_static/flync_example/ecus/eth_ecu/sockets/socket_someip.flync.yaml


.. autoclass:: flync.model.flync_4_ecu.sockets.TCPOption()

.. autoclass:: flync.model.flync_4_ecu.sockets.UDPOption()

Endpoints
==========

.. autoclass:: flync.model.flync_4_ecu.sockets.IPv4AddressEndpoint()
.. autoclass:: flync.model.flync_4_ecu.sockets.IPv6AddressEndpoint()


Deployments
===========

.. autoclass:: flync.model.flync_4_ecu.sockets.DeploymentUnion()

.. _ecu_multicast:

Multicast Group Memberships
############################

.. hint::
   Multicast group memberships of an ECU are computed from several locations of a FLYNC Config.
   They are stored as a list in the field `multicast_groups` of an ECU.
   Mind that these multicast groups are not part of any YAML config, but are accessible fields in a FLYNC workspace.

.. grid::

   .. grid-item-card:: Receiving Nodes

      **Receiving nodes** are listed in the multicast group membership with the mode "rx".

      These entries are computed from:

      - the field `multicast` in a :class:`~flync.model.flync_4_ecu.controller.VirtualControllerInterface`,
      - IPv6 addresses in a :class:`~flync.model.flync_4_ecu.controller.VirtualControllerInterface`
        as solicited-node multicast addresses.

   .. grid-item-card:: Sending Nodes

      **Sender nodes** are listed in the multicast group membership with the mode "tx".

      These entries are computed from:

      - the field `multicast_tx` in a :class:`~flync.model.flync_4_ecu.sockets.Socket`,
      - IPv6 solicited-node multicast addresses per VLAN.


.. autoclass:: flync.model.flync_4_ecu.multicast_groups.MulticastGroupMembership()