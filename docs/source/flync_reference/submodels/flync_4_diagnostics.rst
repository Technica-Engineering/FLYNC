.. _diagnostics:

********************
flync_4_diagnostics
********************

Diagnostics Configuration
##########################

.. note::
   Any diagnostics-related configuration is placed in the directory
   📁 ``communication/diagnostics/``, with one sub-directory per diagnostic protocol.
   This is a **non-mandatory** directory for the FLYNC configuration.

Everything FLYNC models today is UDS (ISO 14229) carried over DoIP (ISO 13400), so there
are two sub-configurations:

* 📁 ``diagnostics/doip/`` - the DoIP transport: its timing profiles. The DoIP logical
  address of a diagnostic entity lives on the ``doip_server`` socket deployment.
* 📁 ``diagnostics/uds/`` - the UDS servers plus the system-wide DID, routine, and DTC
  catalogs they draw from.

.. autoclass:: flync.model.flync_4_diagnostics.DiagnosticsConfig()


DoIP
####

.. autoclass:: flync.model.flync_4_diagnostics.DoIPConfig()

DoIP Timings
============

.. admonition:: Expand for a YAML example - 📄 ``doip/timings.flync.yaml``
   :collapsible: closed

   .. note::
      This file contains the DoIP protocol timers (ISO 13400) that can be imported by a
      DoIP deployment's ``doip_timings_profile``.

   .. literalinclude:: ../../_static/flync_example/communication/diagnostics/doip/timings.flync.yaml

.. autoclass:: flync.model.flync_4_diagnostics.DoIPTimingProfileSet()
.. autoclass:: flync.model.flync_4_diagnostics.DoIPTimingProfile()
.. autoclass:: flync.model.flync_4_diagnostics.DoIPTimings()


.. _doip_deployment:

DoIP Deployment
===============

.. hint::

   DoIP deployments are directly configured in a socket. For further details on the
   configuration go to: :ref:`socket`.

.. autoclass:: flync.model.flync_4_diagnostics.DoIPServerDeployment()
.. autoclass:: flync.model.flync_4_diagnostics.DoIPDiscoveryDeployment()


UDS
###

.. autoclass:: flync.model.flync_4_diagnostics.UDSConfig()

UDS Timings
===========

.. admonition:: Expand for a YAML example - 📄 ``uds/timings.flync.yaml``
   :collapsible: closed

   .. note::
      This file contains the UDS server timers (ISO 14229-2) that can be imported by a
      UDS server's ``uds_timings_profile``.

   .. literalinclude:: ../../_static/flync_example/communication/diagnostics/uds/timings.flync.yaml

.. autoclass:: flync.model.flync_4_diagnostics.UDSTimingProfileSet()
.. autoclass:: flync.model.flync_4_diagnostics.UDSTimingProfile()
.. autoclass:: flync.model.flync_4_diagnostics.UDSTimings()


UDS Server
==========

.. admonition:: Expand for a YAML example - 📁 ``uds/servers/``
   :collapsible: closed

   .. note::
      Each file describes one UDS server (ISO 14229 server side, typically one ECU): the
      timings profile it uses, the access profiles (session + security-level bundles), the
      supported UDS services, and the DIDs/DTCs it offers. Referenced by name from a
      ``doip_server`` socket deployment, which adds the DoIP logical address.

   .. literalinclude:: ../../_static/flync_example/communication/diagnostics/uds/servers/EngineEcuDiagnostic.flync.yaml

.. autoclass:: flync.model.flync_4_diagnostics.UDSServer()
.. autoclass:: flync.model.flync_4_diagnostics.AccessProfile()

UDS Services
============

Every UDS service is a :class:`~flync.model.flync_4_diagnostics.GenericUDSService`; the
services that carry structure of their own inherit from it. Which class a ``services``
entry becomes is decided by its ``sid``, so a service id FLYNC does not model in detail -
an OEM-specific one, for instance - still loads as the generic service.

.. note::
   A service id standardised by ISO 14229-1 must use its canonical ``service`` name even
   when it has no dedicated model, so a typo is caught for every UDS service rather than
   only the modelled ones. The names are listed in
   :data:`~flync.model.flync_4_diagnostics.uds.services.CANONICAL_SERVICE_NAMES`.

   Services that carry no configuration of their own - WriteDataByIdentifier (0x2E),
   TransferData (0x36), RequestTransferExit (0x37), TesterPresent (0x3E) - stay the generic
   service on purpose: what they would hold already lives elsewhere, e.g. a DID's
   writability on :class:`~flync.model.flync_4_diagnostics.DataIdentifier`. The UDS server
   still checks that they are coherent with the catalogs they act on.

Sub-function values are accepted either as the ISO 14229-1 snake_case name or as the raw
number, so supplier- and manufacturer-specific sub-functions still load:

.. autodata:: flync.model.flync_4_diagnostics.uds.subfunctions.ResetType
.. autodata:: flync.model.flync_4_diagnostics.uds.subfunctions.DTCReportType
.. autodata:: flync.model.flync_4_diagnostics.uds.subfunctions.DTCStatusBit
.. autodata:: flync.model.flync_4_diagnostics.uds.subfunctions.IOControlParameter

.. autoclass:: flync.model.flync_4_diagnostics.GenericUDSService()
.. autoclass:: flync.model.flync_4_diagnostics.DiagnosticSessionControlService()
.. autoclass:: flync.model.flync_4_diagnostics.DiagnosticSessionDefinition()
.. autoclass:: flync.model.flync_4_diagnostics.EcuResetService()
.. autoclass:: flync.model.flync_4_diagnostics.SecurityAccessService()
.. autoclass:: flync.model.flync_4_diagnostics.SecurityLevelDeclaration()
.. autoclass:: flync.model.flync_4_diagnostics.RoutineControlService()
.. autoclass:: flync.model.flync_4_diagnostics.ClearDiagnosticInformationService()
.. autoclass:: flync.model.flync_4_diagnostics.DTCGroup()
.. autoclass:: flync.model.flync_4_diagnostics.ReadDTCInformationService()
.. autoclass:: flync.model.flync_4_diagnostics.ReadDataByIdentifierService()
.. autoclass:: flync.model.flync_4_diagnostics.UDSSubfunction()

Block Transfer
--------------

.. autoclass:: flync.model.flync_4_diagnostics.TransferSetupService()
.. autoclass:: flync.model.flync_4_diagnostics.RequestDownloadService()
.. autoclass:: flync.model.flync_4_diagnostics.RequestUploadService()
.. autoclass:: flync.model.flync_4_diagnostics.TransferMemoryRegion()


DIDs, Routines, and DTCs
========================

.. admonition:: Expand for a YAML example - 📄 ``uds/dids/VehicleIdentificationNumber.flync.yaml``
   :collapsible: closed

   .. literalinclude:: ../../_static/flync_example/communication/diagnostics/uds/dids/VehicleIdentificationNumber.flync.yaml

.. autoclass:: flync.model.flync_4_diagnostics.DataIdentifier()
.. autoclass:: flync.model.flync_4_diagnostics.DIDIOControl()
.. autoclass:: flync.model.flync_4_diagnostics.Routine()
.. autoclass:: flync.model.flync_4_diagnostics.DiagnosticTroubleCode()
.. autoclass:: flync.model.flync_4_diagnostics.DTCRecord()

DID/Routine Payload Datatypes
-----------------------------

.. note::
   DID and routine payloads are described with a diagnostics-local field/record model,
   independent of the SOME/IP and signal type systems.

.. autoclass:: flync.model.flync_4_diagnostics.DiagDataRecord()
.. autoclass:: flync.model.flync_4_diagnostics.DiagField()
.. autoclass:: flync.model.flync_4_diagnostics.DiagScaling()
