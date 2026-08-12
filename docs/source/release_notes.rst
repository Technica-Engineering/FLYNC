:orphan:

.. _release_notes:

Release Notes
=============

Release 0.14
------------

Optional Extras
'''''''''''''''

``textual`` and ``PySide6`` are **no longer installed by default**. The core ``flync``
install is now Qt-free, cutting the installed footprint by roughly 85% for all users
and for any package that depends on ``flync``.

To restore the previous behaviour:

.. code-block:: bash

   pip install "flync[all]"

Or install individually:

.. code-block:: bash

   pip install "flync[tui]"    # for flync-converter-interactive
   pip install "flync[gui]"    # for flync-converter-gui

Commands that require a missing extra now print an actionable error message with
install instructions instead of a traceback.

Build System Migration
''''''''''''''''''''''

The project now builds and locks with **uv** (replacing Poetry). Contributors
should recreate their virtual environment:

.. code-block:: bash

   rm -rf .venv
   uv sync

The build backend is **hatchling** with ``uv-dynamic-versioning`` for version
resolution from git tags. The ``uv.lock`` file replaces ``poetry.lock``.

Release 0.11
------------
