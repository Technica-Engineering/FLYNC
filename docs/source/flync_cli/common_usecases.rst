Common Use Cases
================

.. note::
   The commands in the guide will use the flync_example directory.
   Try it out or update the path accordingly to your config path!

Setting a default workspace for a session
-------------------------------------------

Every command's path argument is optional: store a workspace once and omit it afterwards:

.. code-block:: bash

   flync config set examples/flync_example
   flync info ecus
   flync validate

An explicit path always overrides the stored one. Use ``flync config show`` to see what is stored,
and ``flync config clear`` to forget it.

Validate a workspace
--------------------

.. code-block:: bash

   flync validate examples/flync_example

CI/CD workspace validation
--------------------------

Run validation as a pipeline gate to catch configuration errors early:

.. code-block:: bash

   flync validate examples/flync_example

Validate a node
---------------

Use `--node` or `-n` to validate just a part of a config such as an ECU directory, a SOME/IP config, a Switch config, etc. :

.. code-block:: bash

   flync validate --node ECU examples/flync_example/ecus/eth_ecu


.. code-block:: bash

   flync validate -n Switch examples/flync_example/ecus/high_performance_compute/switches/hpc_switch1/switch.flync.yaml

Debugging a workspace that fails to validate
----------------------------------------------

Use ``--verbose`` to run the layered checks (folder structure, YAML syntax, schema, field values,
system-wide) and see exactly where a workspace breaks:

.. code-block:: bash

   flync validate examples/flync_example --verbose

Inspect ECUs in a workspace
----------------------------

.. code-block:: bash

   flync info ecus examples/flync_example

Auditing IP address assignments
--------------------------------

List every IP address across every ECU, with its VLAN and subnet, to spot conflicts:

.. code-block:: bash

   flync info ip examples/flync_example

Use `-e` or `--ecu-name` to inspect a specific ECU:

.. code-block:: bash

   flync info ip -e eth_ecu examples/flync_example

Reviewing socket endpoints
---------------------------

List socket endpoints grouped by ECU and VLAN, with their interface, MAC, IP, protocol and port:

.. code-block:: bash

   flync info sockets examples/flync_example

Reviewing VLAN membership
--------------------------

Show VLAN membership grouped by VLAN, across the workspace or filtered to one VLAN or ECU:

.. code-block:: bash

   flync info vlans examples/flync_example --vlan-id 10


Debugging SOME/IP service deployments
---------------------------------------

List every SOME/IP service with its ID, version, and providing/consuming ECUs:

.. code-block:: bash

   flync info services examples/flync_example

Identify which ECUs provide or consume one specific service instance and verify IP/port
configuration, by service ID and major version:

.. code-block:: bash

   flync info instances 0x0101 1 examples/flync_example

Generating topology documentation
-----------------------------------

Produce a PlantUML diagram of the full ethernet topology for documentation or review:

.. code-block:: bash

   flync generate-system-uml examples/flync_example --output topology.puml

Exporting the expected filetree
---------------------------------

Export the expected filetree of a FLYNC configuration (or one of its model sub-trees) to a txt file:

.. code-block:: bash

   flync filetree
   flync filetree --class ecu

Registering a new error
------------------------

Get the next free number, then add it (with a ``category``) at the factory call site:

.. code-block:: bash

   flync errors get-next-number

.. code-block:: python

   raise err_major("Port {name} is invalid.", category=Category.VALUE_RANGE, error_number="175")

Keeping the error catalog in sync
-----------------------------------

Check the code against the catalog, then regenerate it:

.. code-block:: bash

   flync errors validate-catalog
   flync errors generate-catalog
