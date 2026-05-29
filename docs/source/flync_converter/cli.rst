CLI Reference
=============

``flync_converter`` ships with three entry points after installation:

.. list-table::
   :header-rows: 1

   * - Command
     - Entry point
   * - ``flync-converter``
     - Non-interactive, scriptable subcommands
   * - ``flync-converter-interactive``
     - Launches the interactive TUI directly
   * - ``flync-converter-gui``
     - Launches the PySide6 desktop GUI

``flync-converter -i`` (or ``--interactive``) is a shorthand flag on the main command that also opens the TUI without needing to type the subcommand.

----

Commands
--------

``list-converters``
~~~~~~~~~~~~~~~~~~~

Lists all converters currently registered, including any discovered plugins.

.. code-block:: bash

   flync-converter list-converters

Output is a table with the converter name and a short description taken from each converter's docstring.

----

``convert``
~~~~~~~~~~~

Quick, non-interactive conversion from a source path to a destination path.

.. code-block:: bash

   flync-converter convert \
     --source <source_path> \
     --output <output_path> \
     [--source-format <format>] \
     [--output-format <format>] \
     [--src-<field> <value> ...] \
     [--dst-<field> <value> ...]

.. list-table::
   :header-rows: 1

   * - Option
     - Short
     - Description
     - Default
   * - ``--source``
     - ``-s``
     - Source location to convert from
     - *(prompted if omitted)*
   * - ``--output``
     - ``-o``
     - Output location to write to
     - *(prompted if omitted)*
   * - ``--source-format``
     - ``-sf``
     - Source format name (e.g. ``json``, ``yaml``, ``flync``)
     - auto-detected
   * - ``--output-format``
     - ``-of``
     - Output format name
     - ``flync``
   * - ``--src-<field>``
     - N/A
     - Config field for the source converter (see below)
     - per-field default
   * - ``--dst-<field>``
     - N/A
     - Config field for the destination converter (see below)
     - per-field default

When ``--source-format`` is omitted, the registry attempts to auto-detect the format from the source path. If source and output formats are identical, no conversion is performed.

Converter config options (``--src-*`` / ``--dst-*``)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Each converter can declare its own Pydantic config model with extra fields beyond the base ``config_path``. The ``convert`` command exposes every such field as a CLI option, prefixed with ``--src-`` (source converter) or ``--dst-`` (destination converter). Field names use hyphens (e.g. a field named ``output_type`` becomes ``--dst-output-type``).

**Discovering available fields**

Pass ``--source-format`` and/or ``--output-format`` together with ``--help`` to see the full list of options for those converters:

.. code-block:: bash

   flync-converter convert -sf yaml -of flync --help

.. note::

   ``--help`` must appear *after* the format flags on the command line. If ``--help`` comes first, Click processes it before the format flags are read, so the dynamic options will not yet be listed.

**Examples:**

.. code-block:: bash

   # Auto-detect source format, write FLYNC output
   flync-converter convert -s data.json -o output/

   # Explicit formats
   flync-converter convert -s data.yaml -o out/ -sf yaml -of flync

   # Pass converter-specific config fields for full automation
   flync-converter convert \
     -s data.yaml -o out/ \
     -sf yaml -of flync \
     --dst-output-type CLASSIC

   # Enum fields accept the enum value as a string
   flync-converter convert \
     -s workspace/ -o converted/ \
     -sf flync -of flync \
     --src-some-flag true \
     --dst-output-type EXTENDED

----

``tui``
~~~~~~~

Launches the interactive Textual TUI session. Equivalent to ``flync-converter -i`` and ``flync-converter-interactive``.

.. code-block:: bash

   flync-converter tui
   # or
   flync-converter -i
   # or
   flync-converter-interactive

----

``convert-interactive``
~~~~~~~~~~~~~~~~~~~~~~~

A plain-terminal interactive session driven by `Rich <https://github.com/Textualize/rich>`_ prompts. Prints a numbered table of converters and asks for each config field sequentially. No mouse, no panels, works over SSH and in environments where a full TUI is not supported.

.. code-block:: bash

   flync-converter convert-interactive

Prefer ``tui`` when running locally; use ``convert-interactive`` when you need a lighter, prompt-only flow.

----

Interactive TUI (``tui`` / ``flync-converter-interactive``)
-----------------------------------------------------------

The TUI is built with `Textual <https://textual.textualize.io/>`_ and presents a single split-panel screen:

.. code-block:: text

   ┌─ Source ────────────────────┬─ Destination ────────────────┐
   │ Format: [ flync          ▼] │ Format: [ flync           ▼] │
   │                             │                              │
   │ * config_path               │ * config_path                │
   │ [________________________]  │ [________________________]   │
   │                             │                              │
   │ output_type                 │ output_type                  │
   │ [ CLASSIC               ▼]  │ [ CLASSIC               ▼]  │
   └─────────────────────────────┴──────────────────────────────┘
   ┌─ Output ────────────────────────────────────────────────────┐
   │ INFO flync_converter: Starting conversion                   │
   │ Conversion completed successfully.                          │
   └─────────────────────────────────────────────────────────── ┘
   [ WARNING ▼]                                      [ Convert ]

- **Source panel (left)** - defaults to ``flync``; pick any registered format from the dropdown. Config fields appear immediately below. Required fields are marked with a red ``*``; optional fields show their default value.
- **Destination panel (right)** - same layout, also defaults to ``flync``.
- **Log panel** - displays Python log output from the library in real time. Level is controlled by the selector bottom-left.
- **Log level selector** - choose DEBUG / INFO / WARNING / ERROR to filter what appears in the log panel. Defaults to WARNING.
- **Convert button** - enabled only when both formats are selected. Validates both panels inline, then runs the conversion in a background thread with live output in the log panel.
- Config fields are generated automatically from each converter's Pydantic model. If a plugin defines extra fields such as ``output_structure``, ``encoding``, or ``indent``, they appear without any TUI changes. **Enum fields render as a dropdown** rather than a text box.

**Keyboard shortcut:**

.. list-table::
   :header-rows: 1

   * - Key
     - Action
   * - ``Ctrl+Q``
     - Quit

----

Desktop GUI (``gui`` / ``flync-converter-gui``)
------------------------------------------------

The GUI is a `PySide6 <https://doc.qt.io/qtforpython/>`_ desktop application with the same split-panel layout as the TUI.

.. code-block:: bash

   flync-converter --gui
   # or
   flync-converter gui
   # or
   flync-converter-gui

The GUI mirrors the TUI feature-for-feature:

- **Resizable split panels** - drag the divider to adjust the source/destination ratio.
- **Dynamic config fields** - text inputs for scalar fields, dropdowns for enum fields. Required fields are marked ``*`` in red.
- **Real-time log output** - Python log records from the library appear in the log panel. The log level selector controls verbosity.
- **Threaded conversion** - the Convert button is disabled during conversion; output streams live into the log panel. Errors are displayed inline on the relevant panel.

----

Format auto-detection
---------------------

When ``--source-format`` is not supplied to ``convert``, the registry's ``pick()`` method inspects the source path and returns the best-matching registered converter. The detected name is printed before conversion starts.

----

Exit codes
----------

.. list-table::
   :header-rows: 1

   * - Code
     - Meaning
   * - ``0``
     - Success
   * - Non-zero
     - Conversion error or unhandled exception (message printed to stderr)
