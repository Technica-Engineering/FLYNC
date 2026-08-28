:orphan:

.. _release_notes:

Release Notes
=============

.. seealso::

   For a detailed, step-by-step description of how the FLYNC configuration model and public
   API changed between releases (and what you must update to migrate a project), see the
   :doc:`model_change_history`.

Release 0.14
------------

DBC to FLYNC decoding
'''''''''''''''''''''

The DBC converter now supports decoding DBC files back into a full FLYNC model
(:meth:`flync_converter.converters.dbc.DbcConverter.decode`), not just
encoding FLYNC to DBC. Customizing the decoding is possible through the new
:class:`flync_converter.converters.dbc.DbcConverterConfig`
(``baud_rate_default``, ``fd_baud_rate_default``).

Key decoding behaviours:

* Each DBC ``BU_:`` node is synthesized as one ECU with a CAN controller and one
  interface per bus it participates on.
* The bus bit rates are read from the cantools ``Baudrate`` / ``BaudrateCANFD``
  attributes (with configurable fallbacks, default ``500000`` / ``2000000``).
* Multiplexed messages are reconstructed as a
  :class:`~flync.model.flync_4_signal.pdu.MultiplexedPDU` with the ``M`` selector
  signal and per-id mux groups plus the static group.
* Signal value tables (``VAL_``), factors, offsets, ranges and units are preserved.
* Signals/PDUs are namespaced with the DBC bus (file stem) name, e.g.
  ``BusA_SpeedMsg``.

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
