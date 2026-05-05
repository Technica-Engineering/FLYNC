.. _flync_reference:

================
FLYNC Reference
================

The source is structured in 3 main parts:

.. toctree::
   :hidden:
   :caption: this toctree is needed for the sidepanel structure.

   flync_reference/core
   flync_reference/model
   flync_reference/sdk

- :doc:`flync_reference/core`  -   Additional functionalities for the model, such as utils, field annotations and validators.
- :doc:`flync_reference/model`  -   The heart of FLYNC is a pydantic model. Find a comprehensive reference of the model in this section.
- :doc:`flync_reference/sdk`  -  Pythonic API for developers to interact with the project modules and integrating FLYNC capabilities into applications.


.. _writing_flync_config:

***********************
Writing a FLYNC config
***********************

Authoring configurations with FLYNC is fully YAML-based using the extension ``.flync.yaml``.

The built-in loaders and validators expect a specific repository structure that we'll explore in this next section.


Repository Structure for FLYNC configs
############################################

The root of a FLYNC config repository holds four main parts: System Metadata, Topology, ECUs, and General.

.. rubric:: Guidelines

- For better usability of any FLYNC configuration, the **📂directories**, and **📄files** are expected to follow a certain structure.
- In this section any directory or file with ❗is **mandatory**.
- Certain files should adhere to naming conventions, so make sure to follow the checklists below. ✔


System Metadata
****************

The system metadata file defines the system context for the configuration, such as platform, system variant, and config release.

.. code-block::

   📄❗ system_metadata.flync.yaml

.. important::

   ✔ The file name **system_metadata** must be respected.

   ✔ The file is placed in the root of the config repo.


.. seealso::

   :ref:`SystemMetadata <system_meta>`

Topology
********

This directory describes the interconnections between nodes of the system.

.. code-block::

   📂 topology
   │
   └── 📄(❗) system_topology.flync.yaml

.. important::

   ✔ The file names **system_topology** must be respected.

   ✔ The files are placed in a directory named **topology** .

   ✔  A system_topology must be defined, if there is more than one ECU in the system.

.. seealso::

   :ref:`System Topology <topology>`


ECUs
****

The ecus directory contains several sub-directories describing all the ECUs in the system and their configuration.
This includes controllers of the ECU, port configuration, switches, and internal topology.
All components inside the ECU are described in an internal topology where the structure inside an ECU is defined.

.. code-block::

   📂❗ ecus
   │
   ├── 📂 ecu_1_name
   │   |
   │   ├── 📄❗ ports.flync.yaml
   │   ├── 📄❗ topology.flync.yaml
   │   ├── 📄❗ ecu_metadata.flync.yaml
   │   ├── 📄   mac_multicast_endpoints.flync.yaml
   │   |
   │   ├── 📂❗ controllers
   │   │   └── ... (see next section)
   │   |
   │   └── 📂 switches
   │       ├── 📄 switch1.flync.yaml
   │       └── 📄 switch2.flync.yaml
   │
   └── 📂 ecu_n_name
      └── ...

.. important::

   ✔ The directory names must be respected: ``ecus/``, ``controllers/``, and ``switches/``

   ✔ The file names must be respected:  ``ports``, ``topology``, ``ecu_metadata`` and ``mac_multicast_endpoints``
      All others are suggested.


.. seealso::

   Explore the whole ECU config further:

   - :ref:`ECU Config <ecu>`
   - :ref:`ECU Ports Config <ecu_ports>`
   - :ref:`Switch Config <switch>`
   - :ref:`MAC Multicast Endpoints <mac_multicast_endpoints>`
   - :ref:`internal_topology`
   - :ref:`ECU Metadata <ecu_meta>`

.. _controller_config_reference:

ECUs - Controllers
==================

.. version-changed:: 0.11.0

   The Structure of the Controller configuration was significantly updated with Version 0.11.0!
   Make sure to upgrade your config to the new structure described in this section.


Each controller of an ECU is represented as a **directory**.

Ethernet interfaces are grouped in the sub-directory ``ethernet_interfaces/``, where each interface is its own named directory.
One interface directory consists of:
- an interface configuration
- optionally a ``sockets/`` directory for socket deployments.

.. code-block::

   📂❗ ecus
   │
   └── 📂 ecu_1_name
       |
       ├── 📂❗ controllers
       │   |
       │   ├── 📂❗ ecu_1_controller_1
       |   │   |
       │   │   ├── 📄❗ controller_metadata.flync.yaml
       │   │   ├── 📄   virtual_switch.flync.yaml
       |   │   |
       │   │   └── 📂❗ ethernet_interfaces
       |   │       |
       │   │       ├── 📂 interface_1_name
       │   │       │   ├── 📄❗ interface_config.flync.yaml
       |   │       |   |
       │   │       │   └── 📂   sockets
       │   │       │       ├── 📄 socket_someip.flync.yaml
       │   │       │       └── 📄 ...
       |   │       |
       │   │       └── 📂 interface_n_name
       │   │           └── ...
       |   │
       │   └── 📂 ecu_1_controller_n
       │       └── ...
       |
       └── ... (see section above for other ECU config)


.. important::

   ✔ The directory names must be respected: ``controllers/``, ``ethernet_interfaces/``, ``sockets/``.

   ✔ The file names must be respected: ``controller_metadata`` and ``interface_config``.
      All others are suggested.

   ✔ Each controller is a **directory**, not a file. The directory name is used as the controller name.

   ✔ Each ethernet interface is a **directory** inside ``ethernet_interfaces/``. The directory name is used as the interface name.

   ✔ Sockets are defined **per ethernet interface** inside the ``sockets/`` sub-directory of that interface.


.. seealso::

   Explore the whole Controller config further:

   - :ref:`Controller Config <controller>`
   - :ref:`Sockets <socket>`

General
*******

This directory contains several sub-directories and files that describe assets and configurations for the whole system, such as TCP profiles or SOME/IP services.
This is a **non-mandatory** directory for the FLYNC configuration.

.. code-block::

   📂 general
   │
   ├── 📄 tcp_profiles.flync.yaml
   │
   └── 📂 someip
      |
      ├── 📂 services
      │   ├── 📄 someip_service.flync.yaml
      │   └── 📄 ...
      |
      └── 📄 sd_config.flync.yaml

.. important::

   ✔ If this directory is added, namings of sub-directories must be respected.

.. seealso::

   Explore the whole ECU config further:

   - :ref:`General Config <general>`
   - :ref:`TCPOptions <tcp_option>`
   - :ref:`SOME/IP Config <someip>`
   - :ref:`ServiceInterface <someip_serviceinterface>`


****************************
Validate your configuration
****************************

After writing your FLYNC config you can use this helper script from the FLYNC SDK to **validate** it.

.. code-block::

   python3 src/flync/sdk/helpers/validate_workspace.py --help
