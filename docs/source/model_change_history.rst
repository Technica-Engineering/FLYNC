.. _model_change_history:

####################
Model Change History
####################

This guide documents how the FLYNC **configuration model** and its **public Python/CLI
API** changed between consecutive releases, starting with  **0.9.x** (first public
release). It is written as a reference for *human users* and *AI assistants* to better
understand changes and enable adaptions to code.

It deliberately covers both:

* the **YAML schema** (the ``.flync.yaml`` files that make up a FLYNC configuration), and
* the **Python API** (import paths, class / method names, signatures) of the ``flync``
  package, its ``flync_cli`` command-line application, and the ``flync_converter``
  framework.

.. rubric:: Change classification

The guide classifies every change into one of three buckets:

* **Breaking — config/code must change.** Renamed / removed / relocated fields, files, and
  directories; dropped aliases; newly required fields; changed enums, types, or defaults;
  renamed or moved Python classes, methods, and modules; changed CLI commands/flags; and
  new validation rules that reject previously-accepted configurations.
* **Additive — backward compatible.** New optional fields, modules, or CLI features. No
  action required, listed so you are aware of new capabilities.

.. toctree::
   :hidden:
   :caption: this toctree is needed for the sidepanel structure.

   model_change_history/v0_14_0_15
   model_change_history/v0_13_0_14
   model_change_history/v0_12_0_13
   model_change_history/v0_11_0_12
   model_change_history/v0_10_0_11
   model_change_history/v0_9_0_10

.. _model_change_overview:

Model Change Overview
=====================

* :doc:`0.14 -> 0.15 <model_change_history/v0_14_0_15>`
* :doc:`0.13 -> 0.14 <model_change_history/v0_13_0_14>`
* :doc:`0.12 -> 0.13 <model_change_history/v0_12_0_13>`
* :doc:`0.11 -> 0.12 <model_change_history/v0_11_0_12>`
* :doc:`0.10 -> 0.11 <model_change_history/v0_10_0_11>`
* :doc:`0.9 -> 0.10 <model_change_history/v0_9_0_10>`

It is always recommended to use ``flync validate`` on your workspace root.
