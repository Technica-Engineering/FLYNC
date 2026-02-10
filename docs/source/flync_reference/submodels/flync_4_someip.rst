.. _someip:

**************
flync_4_someip
**************

SOME/IP Configuration
######################

.. note::
   Any SOME/IP related configuration such as service descriptions or timings profiles are placed in the directory 📁 ``general/someip/``.
   This is a **non-mandatory** directory for the FLYNC configuration.

.. autoclass:: flync.model.flync_4_someip.SOMEIPConfig()


SOME/IP Datatypes
#################

.. note::
   SOME/IP Datatypes are used to describe the parameters of messages that are transported in the payload.

.. autoclass:: flync.model.flync_4_someip.someip_datatypes.PrimitiveDatatype()
.. autoclass:: flync.model.flync_4_someip.someip_datatypes.ComplexDatatype()
.. autoclass:: flync.model.flync_4_someip.someip_datatypes.BaseInt()
.. autoclass:: flync.model.flync_4_someip.someip_datatypes.BaseFloat()
.. autoclass:: flync.model.flync_4_someip.someip_datatypes.Typedef()

----

.. autoclass:: flync.model.flync_4_someip.someip_datatypes.ArrayType()
.. autoclass:: flync.model.flync_4_someip.someip_datatypes.ArrayDimension()

----

.. autoclass:: flync.model.flync_4_someip.someip_datatypes.BitfieldEntryValue()
.. autoclass:: flync.model.flync_4_someip.someip_datatypes.BitfieldEntry()
.. autoclass:: flync.model.flync_4_someip.someip_datatypes.Bitfield()

----

.. autoclass:: flync.model.flync_4_someip.someip_datatypes.EnumEntry()
.. autoclass:: flync.model.flync_4_someip.someip_datatypes.Enum()

----

.. autoclass:: flync.model.flync_4_someip.someip_datatypes.Boolean()

----

.. autoclass:: flync.model.flync_4_someip.someip_datatypes.UInt8()
.. autoclass:: flync.model.flync_4_someip.someip_datatypes.UInt16()
.. autoclass:: flync.model.flync_4_someip.someip_datatypes.UInt32()
.. autoclass:: flync.model.flync_4_someip.someip_datatypes.UInt64()

----

.. autoclass:: flync.model.flync_4_someip.someip_datatypes.SInt8()
.. autoclass:: flync.model.flync_4_someip.someip_datatypes.SInt16()
.. autoclass:: flync.model.flync_4_someip.someip_datatypes.SInt32()
.. autoclass:: flync.model.flync_4_someip.someip_datatypes.SInt64()

----

.. autoclass:: flync.model.flync_4_someip.someip_datatypes.Float32()
.. autoclass:: flync.model.flync_4_someip.someip_datatypes.Float64()

----

.. autoclass:: flync.model.flync_4_someip.someip_datatypes.BaseString()
.. autoclass:: flync.model.flync_4_someip.someip_datatypes.FixedLengthString()
.. autoclass:: flync.model.flync_4_someip.someip_datatypes.DynamicLengthString()

----

.. autoclass:: flync.model.flync_4_someip.someip_datatypes.Struct()

----

.. autoclass:: flync.model.flync_4_someip.someip_datatypes.UnionMember()
.. autoclass:: flync.model.flync_4_someip.someip_datatypes.Union()

----

.. autoattribute:: flync.model.flync_4_someip.someip_datatypes.AllTypes()



Service Discovery
=================

.. admonition:: Expand for a YAML example - 📄 ``sd_config.flync.yaml``
   :collapsible: closed

   .. note::
      This file contains the list of SOME/IP-SD timing profiles that can be imported
      and used when deploying a service on an ECU socket.

   .. literalinclude:: ../../_static/flync_example/general/someip/sd_config.flync.yaml

.. autoclass:: flync.model.flync_4_someip.SDConfig()
.. autoclass:: flync.model.flync_4_someip.SDTimings()

.. _someip_serviceinterface:


Service Interface
#################

.. admonition:: Expand for Schematic
   :collapsible: closed

   .. mermaid:: ../../_static/mermaid/someip_service_iface.mmd

.. admonition:: Expand for a YAML example - 📁 ``services/``
   :collapsible: closed

   .. note::
      All the SOME/IP services used in the system are configured in this directory.
      Each file contains following configuration parameters required to create a manifest of a SOME/IP service used in the system:

      - Name of the SOME/IP Service
      - Unique Service Identifier of the SOME/IP Service
      - Optional configuration for the Fields used in the SOME/IP Service
      - Optional configuration for the Events used in the SOME/IP Service
      - Optional configuration for the Eventgroups used in the SOME/IP Service
      - Optional configuration for the Methods used in the SOME/IP Service

      The example file below shows the Enhanced Testability from TC8.

   .. literalinclude:: ../../_static/flync_example/general/someip/services/ets.flync.yaml


.. autoclass:: flync.model.flync_4_someip.SOMEIPServiceInterface()

Method
======

.. autoclass:: flync.model.flync_4_someip.SOMEIPMethod()
.. autoclass:: flync.model.flync_4_someip.SOMEIPFireAndForgetMethod()
.. autoclass:: flync.model.flync_4_someip.SOMEIPRequestResponseMethod()
.. autoclass:: flync.model.flync_4_someip.SOMEIPTP()

Eventgroup
==========

.. autoclass:: flync.model.flync_4_someip.SOMEIPEventgroup()

Event
=====

.. autoclass:: flync.model.flync_4_someip.SOMEIPEvent()
.. autoclass:: flync.model.flync_4_someip.Parameters()


Field
=====

.. autoclass:: flync.model.flync_4_someip.SOMEIPField()


.. _someip_deployment:

Service Deployment
##################

.. admonition:: Expand for Schematic
   :collapsible: closed

   .. mermaid:: ../../_static/mermaid/someip_deployment.mmd

.. hint::

   Service Deployments are directly configured in a socket. For further details on the configuration go to: :ref:`socket`.

.. autoclass:: flync.model.flync_4_someip.SOMEIPServiceProvider()
.. autoclass:: flync.model.flync_4_someip.SOMEIPServiceConsumer()
.. autoclass:: flync.model.flync_4_someip.SOMEIPSDDeployment()

----

.. autoclass:: flync.model.flync_4_someip.Layer4Endpoint()
.. autoclass:: flync.model.flync_4_someip.MulticastEndpoint()
.. autoclass:: flync.model.flync_4_someip.MulticastSDEndpoint()
.. autoclass:: flync.model.flync_4_someip.SOMEIPServiceDeployment()
.. autoclass:: flync.model.flync_4_someip.BaseUDPDeployment()
.. autoclass:: flync.model.flync_4_someip.UDPDeployment()
.. autoclass:: flync.model.flync_4_someip.TCPDeployment()
