# AGENTS.md — flync_converter

`src/flync_converter/` — pluggy-based converter framework with multiple interface modes:

| Subpackage / Module | Description |
|---|---|
| `base/` | ABC (`BaseConverter`) with `decode()`/`encode()` contract + `ConverterConfig` |
| `converters/` | 4 built-in converters: `flync` (workspace), `json`, `yaml`, `dbc` (CAN via cantools) |

The `dbc` converter supports J1939 in both directions. It detects J1939 databases through cantools'
`Message.protocol == "j1939"` (the `VFrameFormat=J1939PG` DBC attribute), decomposes the 29-bit ID into the
`J1939Frame` fields with `cantools.j1939`, and builds one J1939 ECU per source node plus a synthesized sender
(``Vector__XXX``, matching the placeholder the source attributes every message to), each with a synthetic
`j1939_name`, no `source_address`, and PGN-keyed `j1939_sender_frames`/`j1939_receiver_frames`. Encoding rebuilds
the 29-bit ID and emits `VFrameFormat=J1939PG`, preserving the source `BU_:` node names. A message's payload
length is mapped onto `J1939Frame.length` (1–1785), so Transport Protocol / multiframe messages are recovered
rather than dropped. Files that fail cantools' strict load (overlapping J1939 SPNs) are retried
non-strictly and noted under the `dbc_strict_fallback` report group.
| `registry.py` | `ConverterFactoryRegistry` — pluggy-based plugin loading and name-to-converter mapping |
| `cli/` | 3 interface modes: **Click CLI** (`flync-converter`), **Textual TUI** (`flync-converter-interactive`), **PySide6 GUI** (`flync-converter-gui`) |
| `hookspec.py` | Pluggy hook specification (`register_converters`) for external plugin discovery |

The TUI/GUI packages (`cli/tui/`, `cli/gui/`) import textual/PySide6 at module level — they need the `tui`/`gui` extras to type-check (see the mypy note in the root `AGENTS.md`).
