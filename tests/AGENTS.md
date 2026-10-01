# AGENTS.md — tests

This file covers writing and running the test suite. Shared helpers live at the repo root of `tests/`: `tests/error_assertions.py` (see below), `tests/model_builders.py`, `tests/multidrop_workspace.py`, `tests/example_paths.py`, and `tests/conftest.py` (pre-loads the `flync_example` workspace for xdist workers).

## Testing

```bash
uv run pytest                                         # all tests (auto: -n auto, coverage, junitxml)
uv run pytest tests/unit_test/core/                   # single test directory
uv run pytest -k "test_unique"                        # keyword filter
uv run pytest --no-header -v --tb=short               # verbose, short tracebacks
```

Pytest config lives **only** in `pyproject.toml` under `[tool.pytest.ini_options]` — `addopts` (`-n auto --cov=flync --cov=flync_cli --cov=flync_converter --cov-report=term --cov-report=xml --junitxml=report.xml`), `testpaths = ["tests"]`, the 5-minute per-test `timeout`, and the `markers` list (`performance`, `critical_api`, `no_xdist`). Do **not** add a `pytest.ini` / `tox.ini` / `setup.cfg` `[pytest]` section: any of those takes precedence over `pyproject.toml` and silently disables all of the above (pytest prints `WARNING: ignoring pytest config in pyproject.toml!`).

**Benchmarks need `-n 0`.** pytest-benchmark disables itself whenever xdist distributes, so the
`performance`-marked tests must override the `-n auto` from `addopts`:

```bash
uv run pytest -m performance -n 0
```

`tests/converter_tests/test_gui.py` skips on a default `uv sync`. To run it:

```bash
uv sync --group test --group qt --extra gui --extra tui
uv run pytest tests/converter_tests/test_gui.py
```

## Writing tests

Tests must be **useful and concise** — rigorous about what they pin down, lightweight in the lines it takes.

- **Pin the exact error with the shared helper.** Negative tests use `tests/error_assertions.py` — never a bare `assert "..." in str(exc_info.value)`, which passes on any error
  that happens to contain the fragment:

  ```python
  from tests.error_assertions import assert_single_error

  with pytest.raises(ValidationError) as exc_info:
      Bitfield(name="corrupt_bitfield", length=8, fields=nine_fields)
  assert_single_error(exc_info, "FLYNC-SOM-MIN-CONS-138", "exceeds the bitfield length (8)")
  ```

  It asserts *exactly one* error, pins the `FLYNC-<MODULE>-<SEVERITY>-<CATEGORY>-<NUMBER>` id, and matches a
  substring of `"<location>: <message>"` — so the fragment may name the offending field path instead of the
  message. Pass `expected_error_id=None` for the few errors raised by plain Pydantic (union tag, literal,
  `extra_forbidden`, a bare `ValueError` in a validator), which carry no id.
- **One defect per fixture.** `assert_single_error` fails when a fixture grows a second, unrelated error —
  that is the point. Build the minimum input that triggers the one rule under test.
- **Parameterize aggressively.** Collapse variants of the same rule into one `@pytest.mark.parametrize` with
  `pytest.param(..., id="...")` per case; put the expected error id and message fragment in the params rather
  than duplicating the test body. Prefer plain dicts for the input so a case is one readable line.
- **Cover both directions.** Every rule gets the accepted cases (boundary included: last valid bit, exactly-full,
  maximum length) next to the rejected ones — a validator with an inverted condition passes a negative-only suite.
- Keep helper builders module-level and named for what they produce, so `parametrize` can call them directly.

## Validate examples

```bash
uv run python scripts/ci/validate_examples.py   # validates bundled example workspaces (alongside scripts/ci/fetch_pr_data.py)
```

**`flync_example_experimental` must always be a superset of `flync_example`.** The
experimental example is a mutable sandbox copy of the canonical one plus its own
experimental additions. Whenever you add, remove, or change a file in
`examples/flync_example`, mirror the change into `examples/flync_example_experimental`
unless the difference is a deliberate experimental restructure. A CI gate enforces
this:

```bash
uv run python scripts/ci/check_example_superset.py   # exits 1 if any standard-example file is missing/wrong in experimental
```
