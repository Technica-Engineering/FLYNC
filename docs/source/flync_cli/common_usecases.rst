Common Use Cases
================

.. note::
   The commands in the guide will use the flync_example directory.
   Try it out or update the path accordingly to your config path!

Validate a workspace
--------------------

.. code-block:: bash

   flync validate examples/flync_example

CI/CD workspace validation
--------------------------

Run validation as a pipeline gate to catch configuration errors early:

.. code-block:: bash

   flync validate examples/flync_example --quiet

Validate a node
---------------

Use `--node` or `-n` to validate just a part of a config such as an ECU directory, a SOME/IP config, a Switch config, etc. :

.. code-block:: bash

   flync validate --node ECU examples/flync_example/ecus/eth_ecu


.. code-block:: bash

   flync validate -n Switch examples/flync_example/ecus/high_performance_compute/switches/hpc_switch1.flync.yaml

Inspect ECUs in a workspace
----------------------------

.. code-block:: bash

   flync info list-ecus examples/flync_example

Auditing IP address assignments
--------------------------------

Quickly list all IP addresses across every ECU in a workspace to spot conflicts:

.. code-block:: bash

   flync info list-ips examples/flync_example

Use `-e` to inspect a specific ECU:

.. code-block:: bash

   flync info list-ips -e eth_ecu examples/flync_example

Reviewing VLAN membership
--------------------------

Check which interfaces and ECUs belong to a specific VLAN:

.. code-block:: bash

   flync display-vlan-info 10 examples/flync_example


Debugging SOME/IP service deployments
---------------------------------------

Identify which ECUs provide or consume a service and verify IP/port configuration:

.. code-block:: bash

   flync display-service-info "Enhanced Testability Services" examples/flync_example

Generating topology documentation
-----------------------------------

Produce a PlantUML diagram of the full system topology for documentation or review:

.. code-block:: bash

   flync generate-system-uml examples/flync_example --output topology.puml


