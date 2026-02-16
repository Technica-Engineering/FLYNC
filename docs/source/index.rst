.. flync-library documentation master file, created by
   sphinx-quickstart on Tue May 20 13:50:10 2025.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

FLYNC — Configuration Platform for SDV
=======================================

Welcome to the official documentation hub for **FLYNC (FLexible Yaml-based Network Configuration)**, an open-source, repository-native solution that turns
vehicle network configuration into clean, version-controlled code.

The heart of FLYNC is a single, human-readable model schema together with a comprehensive SDK that lets you create, validate, and manipulate configurations programmatically.

By organizing system definitions in a central, version-controlled repository, this tool helps engineering teams manage complexity, enable reuse, and maintain consistency across domains.

.. important:: **FLYNC bridges Architecture, Development, and Testing** — A clear, extensible modeling foundation that supports communication design, ECU software allocation, and system architecture — enabling collaboration across the full E/E development lifecycle.

----

Key Features
------------

- **Layered Configuration Validation**
   Designed for automotive networks, the language models configurations across multiple abstraction layers to catch inconsistencies early.

- **Configuration-as-Code paradigm to enable**
      - Git-based version control and workflows.
      - CI/CD pipeline integration.
      - Traceability and reproducibility

- **Fast and Reliable Process**
   Optimized validation and parsing logic make the library suitable for large-scale configurations with high performance.

- **Developer-Friendly Design**
   Easy to learn and integrate, with intuitive syntax and clear documentation — ideal for both domain experts and software engineers.

- **Open Source & Collaborative**
   Licensed openly to encourage community contributions, integrations, and extensions. Your feedback and contributions are welcome!

- **Lightweight & Dependency-Free Core**
   Minimal external dependencies make it easy to embed, distribute, and automate within any automotive tooling stack.




.. table::
   :align: left


   +--------------------------+----------------------------+-----------------------------+
   |                          | Traditional Approach       | With FLYNC                  |
   +==========================+============================+=============================+
   | Configuration storage    | Multiple formats & files   | One unified YAML-based model|
   +--------------------------+----------------------------+-----------------------------+
   | Version control          | Partial / inconsistent     | Git-native                  |
   +--------------------------+----------------------------+-----------------------------+
   | CI/CD integration        | Rare / custom scripts      | Built-in workflow friendly  |
   +--------------------------+----------------------------+-----------------------------+
   | Cross-team collaboration | Siloed                     | Shared source of truth      |
   +--------------------------+----------------------------+-----------------------------+


.. note:: FLYNC is built to integrate — not replace — existing engineering toolchains.

----

Target Users
---------------

FLYNC is designed for:

- E/E architecture teams.
- Network and platform engineers.
- SDV DevOps and integration teams.
- Validation and test engineers.
- Toolchain and automation specialists.

---------


Get Started in 2 Minutes
------------------------

Read the quickstart guide (:doc:`quickstart`) and start exploring!

.. hint:: Check out the :doc:`flync_example` for configuration examples. You may find exactly what you are looking for!

----

About the Project
-----------------

FLYNC is open source under the **Apache-2.0** license, and thrives on community input!

We welcome:

- **Bug reports** - Open an issue with a clear description and minimal reproducible example.

- **Feature requests** - Propose new models, validation rules, or SDK adaptions.

- **Pull requests** - Follow the standard GitHub flow: fork, feature branch, commit, PR.

- **Documentation improvements** - Keep the docs up-to-date and user-friendly.

Check out the repository's ``CONTRIBUTING.md`` for detailed guidelines, coding standards, and the review process.

----

Resources
---------

.. toctree::
   :maxdepth: 2

   quickstart
   installation
   flync_reference
   flync_example
   license
   release_notes
   contact
