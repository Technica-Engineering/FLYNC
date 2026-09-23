# AGENTS.md

## Project Overview

FLYNC (FLexible Yaml-based Network Configuration) — Python library for automotive E/E network configuration as code. Requires **Python 3.12+** (`requires-python = ">=3.12,<3.15"`). Uses **uv** for dependency management and **hatchling** as build backend.

## Quick Start

```bash
uv sync    # creates .venv and installs all dependencies (core + test + static-analysis)
```

Prefix commands with `uv run` (e.g. `uv run pytest`) — uv resolves `.venv` itself, so
there is no need to activate it.

### Dependency Groups

uv dependency groups are defined via PEP 735 `[dependency-groups]` in `pyproject.toml`:

| Group | Purpose | Install with |
|---|---|---|
| (main) | Runtime dependencies (pydantic, pyyaml, etc.) | `uv sync` |
| `dev` | Pre-commit + test + static-analysis (default) | `uv sync` |
| `test` | Testing (pytest, pytest-xdist, pytest-cov, etc.) | `uv sync --group test` |
| `qt` | `pytest-qt`, for the GUI tests only | `uv sync --group qt --extra gui` |
| `static-analysis` | Linting & formatting (black, flake8, isort, mypy, colorama) | `uv sync --group static-analysis` |
| `docs` | Documentation (Sphinx, furo, sphinx-needs) | `uv sync --group docs` |
| `deploy` | Publishing (twine) | `uv sync --group deploy` |

**Tip:** `uv sync` installs `dev` (which includes `test` and `static-analysis`) by default. For docs: `uv sync --group docs`.

**`qt` is deliberately outside `dev`.** `pytest-qt` aborts collection when no Qt binding is importable, so installing it without the `gui` extra would break every `uv run pytest` on a core install. Always pair them: `uv sync --group test --group qt --extra gui --extra tui`.

### Documentation

Documentation can be found in `docs` and should be updated by every significant change:

* Update Release Notes in `docs/source/release_notes.rst` for significant changes
* Update the Model Change History in `docs/source/model_change_history.rst` for model changes
* Model development conventions live in `docs/source/development/` (Model Development Guide) — when a significant change adds or alters a modelling pattern, update the guide and its examples

### Entry Points

The project registers these CLI commands via `[project.scripts]`:

| Command | Entry Point | Description |
|---|---|---|
| `flync` | `flync_cli:app` | Main CLI (Typer) — validate, info, UML generation, etc. |
| `puml-to-html` | `flync_cli.convert_puml:main` | Convert PlantUML diagrams to HTML |
| `flync-converter` | `flync_converter.cli:main` | Click-based converter CLI |
| `flync-converter-interactive` | `flync_converter.cli:main_interactive` | Textual TUI for conversions (requires `tui` extra) |
| `flync-converter-gui` | `flync_converter.cli:main_gui` | PySide6 GUI for conversions (requires `gui` extra) |

### Optional Extras

The TUI and GUI front-ends are optional extras — they are **not** installed by default:

| Extra | Dependency | Install with |
|---|---|---|
| `tui` | `textual>=0.80.0` | `pip install 'flync[tui]'` or `uv sync --extra tui` |
| `gui` | `PySide6>=6.6.0` | `pip install 'flync[gui]'` or `uv sync --extra gui` |
| `all` | Both of the above | `pip install 'flync[all]'` or `uv sync --extra gui --extra tui` |

`flync-converter-interactive` requires the `tui` extra; `flync-converter-gui` requires the `gui` extra. All other commands work without any extras.

## Source Layout

```
src/flync/
├── __init__.py, py.typed
├── core/          # Base models (Pydantic v2), annotations, datatypes, utilities
├── model/         # Domain models (ECU, topology, SOME/IP, TSN, security, signal, safety, metadata, instrumentation)
└── sdk/           # Workspace management, helpers, context
src/flync_cli/     # CLI application
src/flync_converter/  # Converter tools
tests/
├── unit_test/     # Unit tests (mirrors src/flync/ structure)
│   ├── core/      #   Core unit tests
│   ├── model/     #   Model unit tests
│   └── sdk/       #   SDK unit tests
├── system_test/   # System/integration tests (model + sdk)
├── cli_tests/     # CLI tests
├── converter_tests/ # Converter tests (includes test_plugin/ for plugin integration)
├── test_workspace_config/ # Workspace-config fixtures
├── error_assertions.py  # assert_single_error — mandatory for negative tests (see tests/AGENTS.md)
├── model_builders.py    # Shared model fixtures/builders
├── example_paths.py     # Paths to the bundled example workspaces
├── multidrop_workspace.py # Shared multidrop workspace builder
└── conftest.py    # Root conftest — pre-loads flync_example workspace for xdist workers
```

Directory-specific context lives in nested `AGENTS.md` files — see the [Context Index](#context-index).

## Error Catalog

FLYNC uses a structured, globally-unique error ID system for all validation errors and warnings. The code is the source of truth — the documentation catalog is generated from it.

This section is the operational quick reference. The reasoning — which validator to put a rule in, which severity to choose and what each one does to the load — is in `docs/source/development/validators_and_errors.rst`.

### Error ID Format

```
FLYNC-<MODULE>-<SEVERITY>-<CATEGORY>-<NUMBER>
```

Example: `FLYNC-ECU-MAJ-VAL-001`

| Segment | Values |
|---|---|
| **Module** | Auto-resolved from the `KEY` variable in each domain package's `__init__.py`. Declared today: `ECU`, `SIG`, `SOM`, `DIA`, `TOP`, `TSN`, `SEC`, `MET`, `BUS`, `INS`. Packages without a `KEY` fall through to `CMN`; `flync.model.flync_model` and `version_migrators` resolve to `GEN` |
| **Severity** | `WARN` (warning), `MIN` (minor), `MAJ` (major), `FAT` (fatal) |
| **Category** | The id carries a code; you pass the enum member: `VAL` ← `Category.VALUE_RANGE`, `REQ` ← `REQUIRED`, `CONS` ← `CONSISTENCY`, `UNIQ` ← `UNIQUENESS`, `REF` ← `REFERENCE`, `FMT` ← `FORMAT`, `COMP` ← `COMPATIBILITY`, `STRUCT` ← `STRUCTURAL`, `LIFE` ← `LIFECYCLE` |
| **Number** | Zero-padded 3-digit number, globally unique across the entire codebase (monotonically increasing, never reused). |

### Raising Errors in Validators

Findings come from the factories in `flync.core.utils.exceptions` — never a bare `ValueError` or `assert`.

- `err_minor` / `err_major` / `err_fatal` return a `PydanticCustomError` — **raise** the result
- `warn` appends to the active warning list — **do not raise** (call it like a side-effect)
- `category` and `error_number` are keyword-only and mandatory; pass the message's values as ctx keyword arguments rather than building an f-string, so they reach the catalog entry
- The module code is auto-resolved from the calling module's package `KEY` — never specify it manually
- Severity selects loader behaviour, not tone: minor drops the component and continues, major additionally suppresses the returned model, fatal aborts the load. Default to major over fatal. Worked examples of all four factories are in `docs/source/development/validators_and_errors.rst`.

### Adding a New Error

1. Get the next free number: `flync errors get-next-number`
2. Use it in your factory call with the appropriate `category=Category.<NAME>` and `error_number="<NNN>"`
3. Bring the tree back in step: `flync errors sync`

`sync` is the one command that does everything: it renumbers any error number your branch has
collided with (keeping the number for the call site that already exists on the base branch, and
rewriting the `FLYNC-...` ids your tests pin), regenerates `error_catalog.rst` from the code, and
so drops entries for errors that no longer exist. `generate-catalog`
and `validate-catalog` remain for the narrower jobs of rendering only and checking only.

### CLI Commands

```bash
flync errors get-next-number     # Print the next free globally-unique error number
flync errors validate-catalog    # Check code ↔ docs/source/error_catalog.rst drift (exits 1 on mismatch)
flync errors generate-catalog    # (Re)generate error_catalog.rst from code
flync errors fix-numbers         # Renumber duplicate error numbers introduced by this branch
flync errors sync                # fix-numbers + generate-catalog in one step (the pipeline entry point)
flync errors sync --check        # Same, but writes nothing and exits 1 if anything would change
```

`fix-numbers` and `sync` accept `--base <ref>` to name the branch a duplicate is judged against;
without it they use `CI_MERGE_REQUEST_TARGET_BRANCH_NAME` / `GITHUB_BASE_REF`, then `origin/main`.
CI needs an unshallow checkout (`fetch-depth: 0`) for that lookup to work; with no base resolvable
the keeper is picked by file order instead, which may renumber the older error.

### Key Files

| File | Role |
|---|---|
| `src/flync/core/utils/exceptions.py` | `Severity`, `Category` enums, `err_minor`/`err_major`/`err_fatal`/`warn` factories, `compose_error_id` |
| `src/flync_cli/commands/errors.py` | CLI commands (`get-next-number`, `validate-catalog`, `generate-catalog`, `fix-numbers`, `sync`) |
| `src/flync_cli/utils/errors.py` | AST-based static scanner (`scan_error_calls`), catalog renderer, drift validator |
| `src/flync_cli/utils/error_renumber.py` | Duplicate-number fixer: git base-branch lookup, renumber plan, id propagation, `sync_catalog` |
| `docs/source/error_catalog.rst` | Generated Sphinx-Needs catalog (do not edit by hand) |

## Commands

### Quality checks (run before pushing)

```bash
bash scripts/helpers/local_checkers.sh           # run all checkers: isort + flake8 + mypy + black + lazy-typing (isort/black cover src, scripts & tests; flake8/mypy cover src & scripts only)
bash scripts/helpers/local_autoformat.sh         # auto-fix isort & black issues (src + tests)
```

### Individual checks

```bash
uv run black --check --diff --color src                            # formatting (line-length: 149)
uv run isort --check --diff --color --line-length 149 src          # import sorting (profile=black)
uv run flake8 src                                                  # linting (config in .flake8: max-line-length=149, extend-ignore=E203)
uv run mypy src --show-error-codes --pretty --install-types --non-interactive  # type checking
```

**mypy needs the optional extras.** `src/flync_converter/cli/gui/` and `cli/tui/` import PySide6 and textual at module level, so a core-only env produces `import-not-found` errors. Run `uv sync --group static-analysis --extra gui --extra tui` first; CI does the same.

### Auto-format a single file

```bash
uv run isort --line-length 149 path/to/file.py
uv run black --line-length 149 path/to/file.py
uv run flake8 path/to/file.py
```

### Pre-commit hooks

Defined in `.pre-commit-config.yaml` with `default_install_hook_types: [pre-commit, commit-msg]`:
- `end-of-file-fixer`, `trailing-whitespace` (pre-commit-hooks v6.0.0)
- `autoflake` — removes unused imports/variables, expands star imports
- `black` (line-length=149)
- `mypy` and `check-lazy-typing` (`local` hooks, run through `uv run`) — the mypy hook passes
  `--extra gui --extra tui` so PySide6/textual resolve; see the extras caveat under
  [Individual checks](#individual-checks). CI's `pre-commit` job syncs the same extras

```bash
pre-commit install              # install hooks (both pre-commit and commit-msg)
pre-commit run --all-files      # run on all files
```

### Build docs

```bash
cd docs && make html    # Sphinx, generates mermaid diagrams + CLI docs
```

## Context Index

High-level and cross-cutting rules live here. Per-package and per-directory context lives in nested `AGENTS.md` files that load when you work in those directories:

| Location | Covers |
|---|---|
| `src/flync/AGENTS.md` | Library-wide conventions: mandatory docstrings, key architecture patterns (applies to `core` + `model`) |
| `src/flync/core/AGENTS.md` | Structure of `flync.core` (base models, annotations, datatypes, utils, validators) |
| `src/flync/model/AGENTS.md` | Domain model packages, some of `FLYNCModel` |
| `src/flync/sdk/AGENTS.md` | Structure of `flync.sdk` (workspace, helpers, context) |
| `src/flync_cli/AGENTS.md` | CLI commands and utils; error catalog maintenance |
| `src/flync_converter/AGENTS.md` | Converter framework, plugins, TUI/GUI modes |
| `tests/AGENTS.md` | Running tests, writing tests, validate examples |

## CI

- **GitHub Actions** (primary) — workflows in `.github/workflows/`:
  - `push_and_pr.yaml` — main test/lint pipeline on push and PR
    - Static checks: `format-check` (Black), `isort`, `lint` (flake8), `type-check` (mypy), `pre-commit`, `error-catalog-check` (`flync errors sync`), `model-docstring-check`
    - Test splits (all gated on the static checks): `unit-tests`, `system-tests`, `cli-tests` (core env), `converter-tests` and `performance-tests` (Qt/PySide6 apt libs + `--group qt --extra gui --extra tui`); `performance-tests` is `continue-on-error`
    - `tests-summary` — runs with `if: always()`, combines the per-split `.coverage.*` / `report_*.xml` into `coverage.xml` + `report.xml` and posts the PR coverage comment; missing splits produce warnings, only a total absence of artifacts fails the job
    - Plus `example-validation` and `build-documentation`
    - Triggers on push/PR to `main` and `release-*` branches
    - Posts coverage comment on PRs
  - `pr_sonar_and_coverage_reports.yaml` — SonarQube analysis + coverage reporting
  - `build_and_deploy_docs.yaml` — Sphinx docs build/deploy
- **GitLab CI** (`.gitlab-ci.yml`) — stages `static-analysis` → `tests` → `sonar` → `code_review` → `docs` → `deploy`; key jobs `quality` (lint/format/isort/pre_commit_check/type_check matrix), `integrity` (error-catalog/model-docstrings/lazy-typing matrix), `unit_tests`, `performance_tests` (allow-failure), `test-summary`, `sonar:scan`, `docs-build`, `pages`, `build`; also installs converter test plugin (`tests/converter_tests/test_plugin/`)
- All CI targets **Python 3.12**, uses **uv** with **hatchling** + `uv-dynamic-versioning` (semver, `release-*` tag pattern)
- Renovate for dependency updates (`renovate.json`)
- SonarQube (`sonar-project.properties`)
