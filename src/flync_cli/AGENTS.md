# AGENTS.md — flync_cli

`src/flync_cli/` — CLI application built on **Typer + Rich**:

| Module | Description |
|---|---|
| `main.py` | Root Typer app that wires up commands from `commands/` via `add_typer`. `info`, `config`, and `errors` are registered as named subcommand groups; `validate`, `filetree`, `schema`, and `generate-system-uml` attach at the top level. Also hosts the hidden, deprecated top-level aliases (`display-vlan-info`, `display-service-info`, `display-repo-structure`, `debug`) |
| `commands/validate.py` | Workspace validation (semantic checks, reference resolution); `--verbose` runs the layered debug checks from `flync.sdk.helpers.debug_layers` |
| `commands/info.py` | The `info` command group: `ecus`, `controllers`, `switches`, `ports`, `ip`, `sockets`, `services`, `instances`, `vlans` — plus their hidden `list-*` aliases |
| `commands/config.py` | The `config` command group: `set`/`show`/`clear` the session-persisted workspace path |
| `commands/filetree.py` | Exports the expected filetree of a FLYNC configuration (or a model sub-tree) to a txt file |
| `commands/schema.py` | Exports the FLYNC model as JSON Schema files, one per Pydantic model class, linked with `$ref` |
| `commands/generate_system_uml.py` | PlantUML system diagram generation from workspace |
| `commands/errors.py` | FLYNC error catalog inspection and maintenance (`get-next-number`, `validate-catalog`, `generate-catalog`, `fix-numbers`, `sync`) |
| `utils/workspace.py` | Session-persisted workspace path (backing `config`) and `load_workspace()`, the shared "resolve path, validate, hand back the workspace" used by every command |
| `utils/model_views.py` | Shared model-traversal generators (sockets, IP assignments, VLAN membership, SOME/IP deployments) behind the `info` reports |
| `utils/console.py` | The one shared Rich `Console` instance used across the CLI |
| `utils/deprecation.py` | `warn_deprecated()`, printed by every hidden deprecated alias |
| `utils/` (remaining) | Error table rendering, error catalog scanning, connection mapping |

For the error catalog workflow (`flync errors ...`), see the Error Catalog section in the root `AGENTS.md`.
