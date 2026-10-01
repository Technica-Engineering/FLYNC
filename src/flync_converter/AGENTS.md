# AGENTS.md — flync_converter

`src/flync_converter/` — pluggy-based converter framework with multiple interface modes:

| Subpackage / Module | Description |
|---|---|
| `base/` | ABC (`BaseConverter`) with `decode()`/`encode()` contract + `ConverterConfig` |
| `converters/` | 4 built-in converters: `flync` (workspace), `json`, `yaml`, `dbc` (CAN via cantools) |
| `registry.py` | `ConverterFactoryRegistry` — pluggy-based plugin loading and name-to-converter mapping |
| `cli/` | 3 interface modes: **Click CLI** (`flync-converter`), **Textual TUI** (`flync-converter-interactive`), **PySide6 GUI** (`flync-converter-gui`) |
| `hookspec.py` | Pluggy hook specification (`register_converters`) for external plugin discovery |

The TUI/GUI packages (`cli/tui/`, `cli/gui/`) import textual/PySide6 at module level — they need the `tui`/`gui` extras to type-check (see the mypy note in the root `AGENTS.md`).
