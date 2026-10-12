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
- **Avoid `Any` in type hints** — prefer a concrete, narrow type (including a `X | Y` union, a `Protocol`, a `TypeVar`, or a forward-declared model type under `TYPE_CHECKING`) over `typing.Any`. Reserve `Any` for the cases where it is genuinely unavoidable.
- **No untyped code** — every function definition **must** carry full type hints on its parameters *and* return type (except `@property` setters, which should not annotate the set value). Do not add new functions whose parameters or return value are left annotated as implicit `Any` (e.g. `def foo(x):` with no `->`), and do not annotate local variables with bare, unparameterized containers (`x: list`, `d: dict`, `s: set`) instead of `x: list[...]`, `d: dict[...]`, `s: set[...]`. Untyped/barely-typed function bodies are invisible to mypy's default checking (it emits `annotation-unchecked` notes for them), so they escape type checking entirely — annotate them fully so they are actually checked.
- **Enforced for `flync.core` and `flync.model`** — `[[tool.mypy.overrides]]` in `pyproject.toml` turns on `disallow_untyped_defs`, `disallow_incomplete_defs`, `disallow_any_generics` and `warn_unreachable` for both packages, so `uv run mypy src` fails on an untyped function, a bare `list`/`dict`/`set`, or a branch the annotations make dead (a `None` check on a non-Optional value, an `isinstance` check on input already typed as validated). Fix the annotation rather than the check. Do not narrow with `assert` in validation code — a failing assert becomes an uncatalogued `assertion_error`; tighten the field type instead. Input that has not been validated yet (a `mode="before"` validator, raw YAML) is `object`, not `Any`; narrow it with `isinstance`.

For per-package structure see `src/flync/core/AGENTS.md`, `src/flync/model/AGENTS.md`, and `src/flync/sdk/AGENTS.md`.
