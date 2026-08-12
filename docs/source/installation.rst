.. _installation:

Installation Guide
==================

This guide explains how to install **FLYNC** and its SDK in different environments.
FLYNC is a Python-based tool distributed as a package and built using **hatchling**.

-------

Prerequisites
-------------

Before installing FLYNC, ensure your system meets the following requirements.

System Requirements
''''''''''''''''''''''

- **Python** – 3.12 or newer

Check your Python version:

.. code-block:: bash

   python --version

.. hint:: If Python 3.12+ is not installed, download it from the official Python website or use your system package manager.

Recommended Tools
''''''''''''''''''''

While not strictly required for end users, the following tools are recommended:

- **Git** – for cloning the repository and version control
- **uv** – for managing dependencies and development environments

Install uv (if not already installed) and verify installation:

.. code-block:: bash

   # Install uv:
   pip install uv

   # Check uv install:
   uv --version

--------------

Installation Options
--------------------

FLYNC can be installed in different ways depending on whether you are a user, contributor, or documentation builder.

All installation methods use **uv** as the dependency and environment manager.


.. warning:: The FLYNC model depends on `pydantic v2`, which is **not compatible** with code written for `pydantic v1`. Make sure all your Pydantic-based code is version 2-compliant.



Option 1 - Standard Installation (Recommended for Most Users)
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

**Use this if:** You want to use the FLYNC SDK to create and validate configurations.

**What it installs:** Core FLYNC library and all required runtime dependencies.

Clone the repository:

.. code-block:: bash

   git clone https://github.com/Technica-Engineering/FLYNC.git
   cd flync-library

Install dependencies using uv:

.. code-block:: bash

   uv sync --no-dev


.. hint:: uv automatically creates and manages a virtual environment in ``.venv``.

.. attention:: Make sure you're in the root directory of the project (where ``pyproject.toml`` is located) before running the installation command.

Verify the installation:

.. code-block:: bash

   uv pip list

If successful, you should see the list of FLYNC runtime dependencies with their installed version.

-------

Option 2 - Full Developer Installation
''''''''''''''''''''''''''''''''''''''''''''

**Use this if:** You plan to contribute to FLYNC, modify the SDK, or run tests and linters.

**What it installs:** Runtime + development + testing + documentation + static analysis tools, plus both graphical extras.

.. code-block:: bash

   # You should have forked the repo on github first.
   # Let's assume it is at github.com:insert-your-name-here/FLYNC

   git clone git@github.com:insert-your-name-here/FLYNC.git
   cd flync-library
   uv sync --all-groups --all-extras

.. note::

   ``--all-extras`` is required alongside ``--all-groups``: the ``qt`` group pulls in
   ``pytest-qt``, which aborts pytest collection unless a Qt binding (the ``gui``
   extra) is also installed.

Optional but recommended:

.. code-block:: bash

   pre-commit install

------

Option 3 - Documentation-Only Environment
''''''''''''''''''''''''''''''''''''''''''''

**Use this if:** You only want to build or edit the documentation.

**What it installs:** FLYNC + Sphinx + themes + diagram and documentation tooling.

.. code-block:: bash

   git clone https://github.com/Technica-Engineering/FLYNC.git
   cd flync-library
   uv sync --group docs

Build docs - Linux and macOS users:

.. code-block:: bash

   cd docs
   make html

Build docs - Windows users:

.. code-block:: powershell

   cd docs
   make.bat html

-------

Option 4 - Testing Environment
''''''''''''''''''''''''''''''''''''''''''''

**Use this if:** You only want to run the test suite.

**What it installs:** FLYNC + pytest + coverage tools.

.. code-block:: bash

   git clone https://github.com/Technica-Engineering/FLYNC.git
   cd flync-library
   uv sync --group test

Run tests:

.. code-block:: bash

   uv run pytest

-------

Option 5 - Graphical Front-ends
'''''''''''''''''''''''''''''''''

**Use this if:** You want to use the interactive TUI or desktop GUI for flync-converter.

The core install is deliberately Qt-free — ``textual`` and ``PySide6`` are optional extras.

.. code-block:: bash

   # Interactive Textual TUI only
   pip install "flync[tui]"

   # PySide6 desktop GUI only
   pip install "flync[gui]"

   # Both
   pip install "flync[all]"

From a development checkout:

.. code-block:: bash

   uv sync --extra gui --extra tui

--------

Python Compatibility
--------------------

.. important::

   ``flync`` requires **Python 3.12+** due to newer typing features and package requirements.

If you have multiple Python versions, use ``python3.12`` or create a virtual environment with:

**For Linux and macOSx**

.. code-block:: bash

   python3.12 -m venv .venv
   source .venv/bin/activate

**For Windows**

.. code-block:: powershell

   python -m venv .venv
   .\.venv\Scripts\Activate.ps1



Verify Installation
--------------------

After installation, the following console commands are available:

.. list-table::
   :header-rows: 1
   :widths: 30 40 15 15

   * - Command
     - Entry point
     - Origin
     - Requires
   * - ``flync``
     - ``flync_cli:app``
     - flync_cli
     - —
   * - ``puml-to-html``
     - ``flync_cli.convert_puml:main``
     - flync_cli
     - —
   * - ``flync-converter``
     - ``flync_converter.cli:main``
     - flync_converter
     - —
   * - ``flync-converter-interactive``
     - ``flync_converter.cli:main_interactive``
     - flync_converter
     - ``flync[tui]``
   * - ``flync-converter-gui``
     - ``flync_converter.cli:main_gui``
     - flync_converter
     - ``flync[gui]``

.. note::

   Commands requiring an extra will print an actionable error message (not a traceback) if the extra is not installed. For example::

      Error: The desktop GUI requires 'PySide6', which is an optional dependency of flync.
        Install it with:  pip install 'flync[gui]'
        From a checkout:  uv sync --extra gui


Happy coding! For issues, contributions, or questions, reach out to the authors listed in :doc:`contact`.
