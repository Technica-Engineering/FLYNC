.. _app:

***********
flync_4_app
***********

The app layer describes applications of a system in a top-level ``apps`` directory.
Applications are then bind inside an ECU Controller in an optional ``app_bindings`` file.

Applications (experimental)
###########################

Each file in the top-level ``apps`` directory defines one set that maps onto transport services.
The set name is implied from the filename on disk.

.. admonition:: Expand for a YAML example - 📄 ``apps/application1.flync.yaml``
   :collapsible: closed

   .. literalinclude:: ../../_static/flync_example_experimental/apps/application1.flync.yaml
      :language: yaml


.. autoclass:: flync.model.flync_4_app.App()
.. autoclass:: flync.model.flync_4_app.ServiceConsumerReference()
.. autoclass:: flync.model.flync_4_app.ServiceProviderReference()

CAN and J1939 references (experimental)
#######################################

An application lists the CAN / CAN FD frames, J1939 frames and PDUs it sends or receives. Each reference names the
CAN bus and a ``direction``. A frame reference that does not resolve on its bus is an error; a bound controller
without a matching CAN interface only produces a warning.

.. autoclass:: flync.model.flync_4_app.AppCANFrameRef()
.. autoclass:: flync.model.flync_4_app.AppJ1939FrameRef()
.. autoclass:: flync.model.flync_4_app.AppCANPDURef()
.. autoclass:: flync.model.flync_4_app.AppJ1939PDURef()

ECU-internal IPC channels (experimental)
########################################

An ECU declares its IPC channels in ``ipc_channels.flync.yaml``. Apps bound inside that ECU join a channel through
``ipc_refs``; a reference to a channel the ECU does not declare is an error, and a channel without a producer or
consumer among its bound apps produces a warning.

.. autoclass:: flync.model.flync_4_app.IPCChannel()
.. autoclass:: flync.model.flync_4_app.IPCChannelReference()

App Bindings (experimental)
###########################

Each controller can declare one ``app_bindings.flync.yaml`` file where system applications are referenced.

.. admonition:: Expand for a YAML example - 📄 ``app_bindings.flync.yaml``
   :collapsible: closed

   .. literalinclude:: ../../_static/flync_example_experimental/ecus/high_performance_compute/controllers/hpc_controller1/app_bindings.flync.yaml
      :language: yaml


.. autoclass:: flync.model.flync_4_app.AppBindings()
