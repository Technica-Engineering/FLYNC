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

Non-interactive conversion from one or many sources to one or many destinations. Each endpoint is one ``source`` or ``destination`` subcommand, and both can be repeated:

.. code-block:: bash

   flync-converter convert [--on-conflict first|last|error] [--fail-fast] [--dry-run] [--no-preview] \
     source -p <path> -f <format> [--config <file>] [--<field> <value> ...] \
     [source ...] \
     destination -p <path> -f <format> [--config <file>] [--<field> <value> ...] \
     [destination ...]

Every source is decoded to a FLYNC model, the models are merged in the order the sources are given, and the merged model is encoded to every destination. With a single source the model is passed on unchanged. Sources must come before destinations, and at least one of each is required.

Options of ``source`` and ``destination``:

.. list-table::
   :header-rows: 1

   * - Option
     - Short
     - Description
   * - ``--path``
     - ``-p``
     - Folder (or file) to read from or write to. Required.
   * - ``--format``
     - ``-f``
     - Converter name, as listed by ``list-converters``. Required; an unregistered name is rejected before anything runs.
   * - ``--config``
     - N/A
     - Converter configuration YAML, used instead of the configuration stored in the endpoint. ``--<field>`` options override the values in it.
   * - ``--<field>``
     - N/A
     - Config field of the endpoint's converter (see below).

Options of ``convert``, given before the first subcommand:

.. list-table::
   :header-rows: 1

   * - Option
     - Description
     - Default
   * - ``--on-conflict``
     - What to do when two sources disagree on the same value: keep the ``first``, keep the ``last``, or fail with an ``error``.
     - ``first``
   * - ``--fail-fast``
     - Stop at the first destination that fails. Without it the remaining destinations are still written and the failures are reported together at the end.
     - off
   * - ``--dry-run``
     - Check the conversion and print its preview, without reading or writing any endpoint (see below).
     - off
   * - ``--no-preview``
     - Hide the conversion preview (see below).
     - off

Examples:

.. code-block:: bash

   # One source, one destination
   flync-converter convert source -p workspace/ -f flync destination -p out/ -f yaml

   # Two sources merged into one FLYNC workspace, also exported as JSON
   flync-converter convert \
     source -p workspace/ -f flync \
     source -p buses/ -f dbc --baud-rate-default 500000 \
     destination -p merged/ -f flync \
     destination -p merged_json/ -f json

   # Fail on any value the sources disagree on
   flync-converter convert --on-conflict error \
     source -p a/ -f flync source -p b/ -f yaml destination -p out/ -f flync

Dry run
^^^^^^^

``--dry-run`` checks a conversion without running it, then prints the preview and exits with code ``0``:

- the command line: subcommands, options, option values and registered formats;
- the request: no endpoint listed twice, no destination inside a source or the other way round;
- every ``--config`` file: it exists and is a valid configuration of its converter.

The sources are not read, so a source that cannot be decoded only fails in a real run. ``--dry-run`` applies to the ``source`` / ``destination`` form only.

.. code-block:: bash

   flync-converter convert --dry-run      source -p workspace/ -f flync source -p buses/ -f dbc      destination -p merged/ -f flync

Conversion preview
^^^^^^^^^^^^^^^^^^

Before running, the CLI prints a preview: each source and destination with the converter options that differ from their defaults, and the command line that runs the same conversion.

.. code-block:: text

   Conversion preview
   ------------------
   - Source            : flync -> workspace/
   - Destination       : yaml -> out/
   - Destination option: persist_config = False
   - Command           : flync-converter convert source -p workspace/ -f flync destination -p out/ -f yaml --persist-config False
   Converting workspace/ (flync) -> out/ (yaml)

The scripted ``convert`` command, ``convert-interactive``, the Textual TUI and the GUI all print the same preview.
The command line is quoted for the shell of the running platform (POSIX quoting, or Windows quoting on Windows).
Option values that cannot be given on the command line, such as lists, are listed in the preview but left out of the command.

.. list-table::
   :header-rows: 1

   * - Flag
     - Where
     - Effect
   * - ``--no-preview``
     - Main command, ``convert`` or ``convert-interactive``
     - Hide the conversion preview. The ``Converting ...`` line is still printed. The Textual TUI (command palette) and the GUI (checkbox) have their own preview toggle.

Examples:

.. code-block:: bash

   # Hide the preview for a fully automated run
   flync-converter convert --no-preview source -p workspace/ -f flync destination -p out/ -f yaml
   flync-converter --no-preview convert source -p workspace/ -f flync destination -p out/ -f yaml

Converter config options (``--<field>``)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Each converter can declare its own Pydantic config model with extra fields beyond the base ``config_path``. Every such field is an option of the ``source`` or ``destination`` subcommand that uses the converter, and applies only to that endpoint. Field names use hyphens (e.g. a field named ``output_type`` becomes ``--output-type``). The ``report_enabled``, ``report_min_log_level`` and ``persist_config`` fields are offered on destinations only.

**Discovering available fields**

Pass ``-f`` together with ``--help`` to see the options of that converter:

.. code-block:: bash

   flync-converter convert source -f yaml --help
   flync-converter convert destination -f dbc --help

.. note::

   ``--help`` must appear *after* ``-f`` on the command line. If ``--help`` comes first, Click processes it before the format is read, so the converter's options will not yet be listed.

**Examples:**

.. code-block:: bash

   # Pass converter-specific config fields for full automation
   flync-converter convert \
     source -p data/ -f yaml \
     destination -p out/ -f flync --output-type CLASSIC

   # Enum fields accept the enum member name
   flync-converter convert \
     source -p workspace/ -f flync --some-flag true \
     destination -p converted/ -f flync --output-type EXTENDED

Deprecated: the flat one-to-one form
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The earlier one-to-one form still works and prints a deprecation warning on stderr. It will be removed in a later release.

.. code-block:: bash

   flync-converter convert -s <source_path> -o <output_path> [-sf <format>] [-of <format>] \
     [--src-config <file>] [--dst-config <file>] [--src-<field> <value> ...] [--dst-<field> <value> ...]

``-sf`` and ``-of`` default to ``flync``, a missing ``-s`` or ``-o`` is prompted for, and identical source and output formats skip the conversion. The flat options cannot be combined with ``source`` / ``destination`` subcommands. To migrate, move each side into its own subcommand and drop the ``src-`` / ``dst-`` prefix:

.. code-block:: bash

   # Deprecated
   flync-converter convert -s data/ -sf yaml -o out/ -of flync --dst-output-type CLASSIC
   # Equivalent
   flync-converter convert source -p data/ -f yaml destination -p out/ -f flync --output-type CLASSIC

----

``tui``
~~~~~~~

Launches the interactive Textual TUI session. Equivalent to ``flync-converter -i`` and ``flync-converter-interactive``.

**Requires the** ``tui`` **extra** (``pip install "flync[tui]"`` or ``uv sync --extra tui``).

Without the extra installed, the command prints an actionable error and exits with code 1::

   Error: The interactive TUI requires 'textual', which is an optional dependency of flync.
     Install it with:  pip install 'flync[tui]'
     From a checkout:  uv sync --extra tui

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

**Requires the** ``tui`` **extra** (``pip install "flync[tui]"``).

The TUI is built with `Textual <https://textual.textualize.io/>`_ and presents Source endpoints on the left and Destination endpoints on the right. Each endpoint has its own format and converter configuration:

.. code-block:: text

   ┌───────────────────────────────┐ ┌───────────────────────────────┐
   │ ▼ Source 1             Remove │ │ ▼ Destination 1               │
   │ [ flync                   ▼ ] │ │ [ json                    ▼ ] │
   │ * config_path                 │ │ * config_path                 │
   │ [ /models/base              ] │ │ [ /out/system.json          ] │
   └───────────────────────────────┘ └───────────────────────────────┘
   ┌───────────────────────────────┐
   │ ▶ Source 2  dbc · /ca… Remove │
   └───────────────────────────────┘
   [ Add Source                    ] [ Add Destination               ]

   ┌─ Output ────────────────────────────────────────────────────────┐
   │ INFO flync_converter: Starting conversion                       │
   │ Conversion completed successfully.                              │
   └─────────────────────────────────────────────────────────────────┘
   [ WARNING ▼]                                            [ Convert ]

- **Sources (left)** - starts with one ``flync`` Source. **Add Source** creates another independent endpoint directly above the button.
- **Destinations (right)** - starts with one ``flync`` Destination. **Add Destination** creates another independent endpoint.
- **Endpoint management** - **Remove** deletes an endpoint while at least one endpoint of the same role remains. Titles are renumbered automatically.
- **Collapse** - the arrow before the title (or ``Enter`` on it) hides the format selector and config fields and shows the format and path in the title row. Values are kept, and errors stay visible.
- **Scrolling** - each column scrolls on its own; the Add buttons stay at the bottom.
- **Browse** - the button next to ``config_path`` opens a file and folder picker. Folder converters such as ``flync`` pick a folder, Sources list only files with the converter's extensions, and a Destination file name without an extension gets the converter's default one. The path stays editable in the picker and in the panel.
- **Log panel** - displays Python log output from the library in real time. Level is controlled by the selector bottom-left. On short terminals the log shrinks to as little as three rows.
- **Log level selector** - choose DEBUG / INFO / WARNING / ERROR to filter what appears in the log panel. Defaults to WARNING.
- **Convert button** - enabled only when every configured endpoint has a format selected. Validates all endpoints inline, then runs the conversion in a background thread with live output in the log panel.
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

**Requires the** ``gui`` **extra** (``pip install "flync[gui]"``).

Without the extra installed, the command prints an actionable error and exits with code 1::

   Error: The desktop GUI requires 'PySide6', which is an optional dependency of flync.
     Install it with:  pip install 'flync[gui]'
     From a checkout:  uv sync --extra gui

The GUI is a `PySide6 <https://doc.qt.io/qtforpython/>`_ desktop application with the same split-panel layout as the TUI.

.. code-block:: bash

   flync-converter --gui
   # or
   flync-converter gui
   # or
   flync-converter-gui

The GUI provides a native multi-endpoint conversion workflow:

- **Multiple sources and destinations** - use **Add Source** and **Add Destination** to configure one-to-one, one-to-N, N-to-one, or N-to-N conversions.
- **Endpoint management** - remove any endpoint while at least one endpoint of the same role remains; remaining panels are renumbered automatically.
- **Independent configuration** - every source and destination keeps its own format, path, and converter-specific values.
- **Resizable split panels** - drag the divider to adjust the source/destination ratio.
- **Dynamic config fields** - text inputs for scalar fields, dropdowns for enum fields. Required fields are marked ``*`` in red.
- **Real-time log output** - Python log records from the library appear in the log panel. The log level selector controls verbosity.
- **Threaded conversion** - the complete request runs in the background; output streams live into the log panel. Configuration and request errors are shown inline on the affected endpoints.

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
