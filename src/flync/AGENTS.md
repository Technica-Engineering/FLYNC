# AGENTS.md — flync library package

Library-wide conventions covering the model and core subpackages under `src/flync/`.

## Docstrings are mandatory

Every Pydantic model in `flync.core` and `flync.model` **must** have a NumPy-style docstring with a `Parameters` section documenting every field — name, type, and `, optional` where the field has a default. This is not optional polish: it is the source the Sphinx API reference and the generated docs are built from.

```bash
uv run python scripts/ci/check_model_docstrings.py
```

This scans every model in those packages and reports, per class, any field that's `[missing]` from the docstring or whose documented `[type]` doesn't match its annotation. Run it after adding or changing a model and fix every finding it reports before considering the change done — do not leave warnings for a future pass. It also runs in CI (`model-docstring-check` in `push_and_pr.yaml`), currently non-gating (reports warnings without failing the build), but treat it as gating in your own work regardless.

## Key Architecture Patterns

- All models extend `FLYNCBaseModel` (Pydantic v2) — set `model_config = {'extra': 'forbid'}`
- **`External` / `Reference` / `Implied`** annotations on fields control YAML load/resolve behavior
- **Discriminated unions** for polymorphic types (e.g., PHY types)
- Field annotations use `Annotated[str, External(output_structure=OutputStrategy.SINGLE_FILE)]`
- Validators use `@field_validator` / `@model_validator` / `BeforeValidator` / `AfterValidator` patterns
- **Avoid `PrivateAttr(default=...)`** — it trips SonarQube's `S5890` (the `PrivateAttr` value never matches the `Optional[T]` annotation). Pydantic v2 already treats a leading-underscore, typed class attribute as a private attr, so write `_some_attr: Optional[T] = None` instead (kept out of fields/`model_dump`, copied by `model_copy`).
- **Avoid `typing.Union` / `typing.Optional` in type hints** — use the `X | Y` and `X | None` union expressions (PEP 604), which SonarQube's `S6546` requires. `Optional`/`Union` are still fine for annotations that must stay strings, but prefer the `|` syntax wherever it parses.
- **Avoid redundant quoting for lazy typing** — under `from __future__ import annotations` and for names imported under `TYPE_CHECKING`, do not wrap type hints in quotes; the guard `scripts/ci/check_lazy_typing.py` enforces this. `Self` (not a quoted self-return string) is required for `@model_validator(mode="after")` methods.

For per-package structure see `src/flync/core/AGENTS.md`, `src/flync/model/AGENTS.md`, and `src/flync/sdk/AGENTS.md`.
