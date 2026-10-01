.. _instrumentation:

***********************
flync_4_instrumentation
***********************

The ``flync_4_instrumentation`` module declares the **measurement points** of a network:
the physical capture locations a measurement or logging setup reads, each identified by the
ASAM CMP / TECMP interface ids that carry its frames.

The module's public face is the :class:`~flync.model.flync_4_instrumentation.Instrumentation`
wrapper, which maps to the ``instrumentation/`` workspace folder. Its ``measurement_points``
lists every capture point the author has recorded.

A measurement point taps exactly one medium - a point-to-point Ethernet link (one or two ECU
ports), an Ethernet shared-medium segment, a CAN bus, or a LIN bus. Which medium it taps is
what the point *is*: the ``type`` discriminator picks one of the four shapes, and the medium
dictates the captured payload - only a CAN bus asks the author to say more than the bus name,
because a CAN FD bus carries both classic and FD frames.

The overlay is optional: a workspace that is not being instrumented has no ``instrumentation/``
folder, ``flync_model.instrumentation`` stays ``None``, and every measurement point's reference
resolves against the same loaded network model that defines its bus, segment or port.

.. admonition:: Expand for a YAML example - 📄 ``instrumentation/measurement_points.flync.yaml``
   :collapsible: closed

   .. note::
      All measurement points of a workspace live in this single file (the wrapper's
      ``measurement_points`` field).  The overlay is **optional** - omit the folder when the
      system is not instrumented.

   .. literalinclude:: ../../../../examples/flync_example/instrumentation/measurement_points.flync.yaml
      :language: yaml

.. note::
   A point-to-point link can be tapped from both ends - one interface id per direction, each
   tied to the ECU port on that side:

   .. code-block:: yaml

      - name: gateway_to_hpc_link
        type: ethernet_ports
        ports:
          - ecu_port: zgw_p1
            interface_id: 0x00010001   # gateway -> HPC direction
          - ecu_port: hpc1_p5
            interface_id: 0x00010002   # HPC -> gateway direction

   The two ports must be the two ends of the same ``EthernetPointToPointConnection``; to tap a
   link that is not point-to-point (a shared medium), use ``type: ethernet_bus`` instead.


Processing
##########

The overlay is loaded into :class:`~flync.model.flync_4_instrumentation.Instrumentation`,
available on the root model as ``flync_model.instrumentation`` (``None`` when the workspace is
not instrumented). Its ``measurement_points`` are parsed from the single overlay file, and two
helpers drive their lifecycle:

.. autoclass:: flync.model.flync_4_instrumentation.Instrumentation()

.. autofunction:: flync.model.flync_4_instrumentation.validate_measurement_points_local

.. autofunction:: flync.model.flync_4_instrumentation.bind_measurement_points


Measurement Points
##################

The ``type`` discriminator on :class:`~flync.model.flync_4_instrumentation.MeasurementPoint`
(described below) selects the concrete class at load time.

.. autoclass:: flync.model.flync_4_instrumentation.MeasurementPointType()

.. autoclass:: flync.model.flync_4_instrumentation.MeasurementPoint()

.. autoclass:: flync.model.flync_4_instrumentation.CANBusMeasurementPoint()

.. autoclass:: flync.model.flync_4_instrumentation.LINBusMeasurementPoint()

.. autoclass:: flync.model.flync_4_instrumentation.EthernetBusMeasurementPoint()

.. autoclass:: flync.model.flync_4_instrumentation.EthernetPortsMeasurementPoint()

.. autoclass:: flync.model.flync_4_instrumentation.PortCapture()
