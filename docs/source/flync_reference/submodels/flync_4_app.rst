.. _app:

***********
flync_4_app
***********

The app layer describes applications of a system in a top-level ``apps`` directory.
Applications are then bind inside an ECU Controller in an optional ``app_bindings`` file.

Applications
##############

Each file in the top-level ``apps`` directory defines one set that maps onto transport services.
The set name is implied from the filename on disk.

.. admonition:: Expand for a YAML example - 📄 ``apps/application1.flync.yaml``
   :collapsible: closed

   .. literalinclude:: ../../_static/flync_example/apps/application1.flync.yaml
      :language: yaml


.. autoclass:: flync.model.flync_4_app.App()
.. autoclass:: flync.model.flync_4_app.ServiceConsumerReference()
.. autoclass:: flync.model.flync_4_app.ServiceProviderReference()

App Bindings
############

Each controller can declare one ``app_bindings.flync.yaml`` file where system applications are referenced.

.. admonition:: Expand for a YAML example - 📄 ``app_bindings.flync.yaml``
   :collapsible: closed

   .. literalinclude:: ../../_static/flync_example/ecus/high_performance_compute/controllers/hpc_controller1/app_bindings.flync.yaml
      :language: yaml


.. autoclass:: flync.model.flync_4_app.AppBindings()

