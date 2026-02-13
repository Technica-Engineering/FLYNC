.. _installation:

Installation Guide
==================

This guide explains how to install **FLYNC** and its SDK in different environments.
FLYNC is a Python-based tool distributed as a package and built using **Poetry**.

-------

Prerequisites
-------------

Before installing FLYNC, ensure your system meets the following requirements.

System Requirements
''''''''''''''''''''''

- **Python** – 3.11 or newer

Check your Python version:

.. code-block:: bash

   python --version

.. hint:: If Python 3.11+ is not installed, download it from the official Python website or use your system package manager.

Recommended Tools
''''''''''''''''''''

While not strictly required for end users, the following tools are recommended:

- **Git** – for cloning the repository and version control
- **Poetry** – for managing dependencies and development environments

Install Poetry (if not already installed) and verify installation:

.. code-block:: bash

   # Create a new virtual environment or use an existing one.
   # You can do this also in the source directoy after git clone.
   # In this example we use the directory .venv
   python -m venv .venv

   # activate virtual environment:
   source .venv/bin/activate

   # Update PIP just in case:
   pip install --upgrade pip

   # Install Poetry:
   pip install poetry

   # Check Poetry install:
   poetry --version

--------------

Installation Options
--------------------

FLYNC can be installed in different ways depending on whether you are a user, contributor, or documentation builder.

All installation methods use **Poetry** as the dependency and environment manager.


.. warning:: The FLYNC model depends on `pydantic v2`, which is **not compatible** with code written for `pydantic v1`. Make sure all your Pydantic-based code is version 2-compliant.



Option 1 — Standard Installation (Recommended for Most Users)
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

**Use this if:** You want to use the FLYNC SDK to create and validate configurations.

**What it installs:** Core FLYNC library and all required runtime dependencies.

Clone the repository:

.. code-block:: bash

   git clone https://github.com/Technica-Engineering/FLYNC.git
   cd flync-library

Install dependencies using Poetry:

.. code-block:: bash

   poetry install --only main


.. hint:: It is recommended to install the FLYNC dependencies within a virtual environment.

.. attention:: Make sure you're in the root directory of the project (where ``pyproject.toml`` is located) before running the installation command.

Verify the installation:

.. code-block:: bash

   poetry show

If successful, you should see the list of FLYNC runtime dependencies with their installed version.

-------

Option 2 — Full Developer Installation
''''''''''''''''''''''''''''''''''''''''''''

**Use this if:** You plan to contribute to FLYNC, modify the SDK, or run tests and linters.

**What it installs:** Runtime + development + testing + documentation + static analysis tools.

.. code-block:: bash

   # You should have forked the repo on github first.
   # Let's assume it is at github.com:insert-your-name-here/FLYNC

   git clone git@github.com:insert-your-name-here/FLYNC.git
   cd flync-library
   poetry install --with dev,test,docs,static-analysis

Optional but recommended:

.. code-block:: bash

   poetry run pre-commit install

------

Option 3 — Documentation-Only Environment
''''''''''''''''''''''''''''''''''''''''''''

**Use this if:** You only want to build or edit the documentation.

**What it installs:** FLYNC + Sphinx + themes + diagram and documentation tooling.

.. code-block:: bash

   git clone https://github.com/Technica-Engineering/FLYNC.git
   cd flync-library
   poetry install --with docs

Build docs — Linux and macOS users:

.. code-block:: bash

   cd docs
   make html

Build docs — Windows users:

.. code-block:: powershell

   cd docs
   make.bat html

-------

Option 4 — Testing Environment
''''''''''''''''''''''''''''''''''''''''''''

**Use this if:** You only want to run the test suite.

**What it installs:** FLYNC + pytest + coverage tools.

.. code-block:: bash

   git clone https://github.com/Technica-Engineering/FLYNC.git
   cd flync-library
   poetry install --with test

Run tests:

.. code-block:: bash

   pytest

--------

Python Compatibility
--------------------

.. important::

   ``flync`` requires **Python 3.11+** due to newer typing features and package requirements.

If you have multiple Python versions, use ``python3.11`` or create a virtual environment with:

**For Linux and macOSx**

.. code-block:: bash

   python3.11 -m venv .venv
   source .venv/bin/activate

**For Windows**

.. code-block:: powershell

   python -m venv .venv
   .\.venv\Scripts\Activate.ps1


Happy coding! For issues, contributions, or questions, reach out to the authors listed in the project metadata.
