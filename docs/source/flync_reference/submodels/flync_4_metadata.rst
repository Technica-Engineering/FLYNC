.. _metadata:

****************
flync_4_metadata
****************

Metadata
########

.. admonition:: Expand for Schematic
   :collapsible: closed

   .. mermaid:: ../../_static/mermaid/metadata.mmd

.. hint::

    Components in a FLYNC configuration, including the configuration itself, hold additional metadata.
    This helps keeping track of changes and compatibilities.

.. autoclass:: flync.model.flync_4_metadata.BaseMetadata()

.. _system_meta:

.. admonition:: Expand for a YAML example - 📄❗ system_metadata.flync.yaml
   :collapsible: closed

   .. note::
      This file defines the system context for the FLYNC configuration.
      This is a **mandatory** file.

   .. literalinclude:: ../../_static/flync_example/system_metadata.flync.yaml


.. autoclass:: flync.model.flync_4_metadata.SystemMetadata()

.. _ecu_meta:

.. admonition:: Expand for a YAML example - 📄 ``ecu_metadata.flync.yaml``
   :collapsible: closed

   .. note::
      The system-level identification of an ECU with optional hardware and software descriptions is defined in the metadata file.
      This is a **mandatory** file for the ECU configuration.

   .. literalinclude:: ../../_static/flync_example/ecus/high_performance_compute/ecu_metadata.flync.yaml

.. autoclass:: flync.model.flync_4_metadata.ECUMetadata()

.. _embedded_meta:

.. admonition:: Expand for a YAML example - 📄 ``controller_metadata.flync.yaml`` (EmbeddedMetadata)
   :collapsible: closed

   .. note::
      Embedded Metadata is for example used for controllers inside the respective directory.
      Go to :ref:`Controller <controller>` to get more details on the config directory.

   .. literalinclude:: ../../_static/flync_example/ecus/high_performance_compute/ecu_metadata.flync.yaml

.. autoclass:: flync.model.flync_4_metadata.EmbeddedMetadata()

.. _socketspervlan_meta:

.. autoclass:: flync.model.flync_4_metadata.SocketsPerVLANMetadata()

.. _someipservice_meta:

.. autoclass:: flync.model.flync_4_metadata.SOMEIPServiceMetadata()

----

Versioning
###########

.. hint::

    Versioning inside of the metadata can be either done by following Semantic Versioning (https://semver.org/) or pep440 versioning (https://peps.python.org/pep-0440/).
    Per default semver is used.

.. autoclass:: flync.model.flync_4_metadata.BaseVersion()

.. _hw_meta:

.. autoclass:: flync.model.flync_4_metadata.HardwareBaseMetadata()

.. _componentsw_meta:

.. autoclass:: flync.model.flync_4_metadata.SoftwareBaseMetadata()