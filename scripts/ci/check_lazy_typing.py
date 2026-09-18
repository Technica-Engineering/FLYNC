#!/usr/bin/env python3
"""AST guard that flags unnecessary string-quoted (lazy) type annotations.

FLYNC uses explicit (unquoted) type annotations and ``typing.Self`` for self-referencing
method returns. A quoted annotation is only justified for a genuine forward or cyclic
reference: a name imported solely under ``if TYPE_CHECKING:``, a name defined later in the
same module, or the enclosing class itself (unbound while its own body executes).

The script scans the source tree and exits non-zero on three findings:

``redundant``
    Every name referenced inside the quotes is already legally in module scope at that
    line, so the quotes buy nothing and should be dropped.

``whole-quote``
    The whole annotation is quoted rather than just the forward-referenced name -
    ``"Optional[ECU]"`` instead of ``Optional["ECU"]``. Quoting the single name that is
    not yet bound keeps the rest of the annotation visible to readers and to ``grep``.

``self-return``
    A method returns its own quoted class name. The quotes are load-bearing (the class is
    unbound inside its own body), but ``typing.Self`` says it better and keeps working in
    subclasses.

Quoted annotations that reference a name which is genuinely not yet in scope are allowed,
so no allow-list is needed for the common cases. For the rare unavoidable exception, put
``# lazy-typing: allow`` on the annotation's line.

Exit codes:
    0  - no findings
    1  - one or more findings
"""

from __future__ import annotations

import argparse
import ast
import builtins
import collections.abc
import sys
import typing
from pathlib import Path
from typing import Iterator, NamedTuple

DEFAULT_ROOTS = ["src/flync", "src/flync_cli", "src/flync_converter", "scripts", "tests"]

# Identifiers that are always considered in scope: builtins plus everything the typing and
# collections.abc modules export, which is what an annotation normally reaches for.
ALWAYS_KNOWN = set(dir(builtins)) | set(dir(typing)) | set(dir(collections.abc))

# Inline escape hatch, placed on the line carrying the annotation.
PRAGMA = "# lazy-typing: allow"


class Finding(NamedTuple):
    """One reported annotation site."""

    path: Path
    line: int
    kind: str
    text: str
    detail: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.kind}: {self.detail}"


class ModuleScope(NamedTuple):
    """What a module binds at run time, and where."""

    imported: set[str]
    """Names bound by an import that actually executes."""

    defined: dict[str, int]
    """``{name: line}`` for module-level classes, functions and assignments."""

    has_future_annotations: bool
    """``from __future__ import annotations`` makes every quote redundant."""


def _dotted_name(node: ast.expr) -> str:
    """Return ``a.b.c`` for a Name/Attribute chain, or ``""`` for anything else."""

    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _dotted_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def _leaf_name(node: ast.expr) -> str:
    """Return the last segment of a dotted name, so ``typing.Literal`` matches ``Literal``."""

    return _dotted_name(node).rsplit(".", 1)[-1]


def _is_type_checking_test(test: ast.expr) -> bool:
    """True for ``if TYPE_CHECKING:`` / ``if typing.TYPE_CHECKING:`` and their negations."""

    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        return _is_type_checking_test(test.operand)
    return _leaf_name(test) == "TYPE_CHECKING"


def _target_names(target: ast.expr) -> Iterator[str]:
    """Yield the simple ``Name`` targets of an assignment, skipping attribute/subscript targets."""

    if isinstance(target, ast.Name):
        yield target.id
    elif isinstance(target, (ast.Tuple, ast.List)):
        for element in target.elts:
            yield from _target_names(element)


def _collect_scope(tree: ast.Module) -> ModuleScope:
    """Collect the module-level bindings that exist at run time.

    Imports inside an ``if TYPE_CHECKING:`` block are deliberately *not* collected: a name
    that only exists for the type checker is exactly the case a quoted annotation is for.
    Other module-level ``if`` / ``try`` blocks do execute, so their imports are collected.
    """

    imported: set[str] = set()
    defined: dict[str, int] = {}
    has_future = False

    def visit(body: list[ast.stmt]) -> None:
        nonlocal has_future
        for node in body:
            if isinstance(node, ast.ImportFrom) and node.module == "__future__":
                has_future = has_future or any(a.name == "annotations" for a in node.names)
                continue
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    if alias.name != "*":
                        imported.add(alias.asname or alias.name.split(".", 1)[0])
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                defined.setdefault(node.name, node.lineno)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    for name in _target_names(target):
                        defined.setdefault(name, node.lineno)
            elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
                for name in _target_names(node.target):
                    defined.setdefault(name, node.lineno)
            elif isinstance(node, ast.If):
                if not _is_type_checking_test(node.test):
                    visit(node.body)
                visit(node.orelse)
            elif isinstance(node, (ast.Try, ast.TryStar)):
                visit(node.body)
                visit(node.orelse)
                visit(node.finalbody)
                for handler in node.handlers:
                    visit(handler.body)

    visit(tree.body)
    return ModuleScope(imported, defined, has_future)


def _quoted_in_type_position(node: ast.expr | None) -> Iterator[tuple[ast.Constant, str]]:
    """Yield every ``(node, text)`` string constant sitting in a *type* position inside an annotation.

    Two positions are skipped on purpose, because the strings there are ordinary values
    rather than deferred types:

    * ``Literal["can_node", "lin_master"]`` - the payload is the set of allowed values;
    * ``Annotated[T, External(...), Field(description="...")]`` - only index 0 is a type,
      everything after it is metadata full of plain strings.
    """

    if node is None:
        return
    if isinstance(node, ast.Constant):
        if isinstance(node.value, str):
            yield node, node.value
        return
    if isinstance(node, ast.Subscript):
        leaf = _leaf_name(node.value)
        if leaf == "Literal":
            return
        if leaf == "Annotated":
            elements = node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
            if elements:
                yield from _quoted_in_type_position(elements[0])
            return
        yield from _quoted_in_type_position(node.slice)
        return
    if isinstance(node, (ast.Tuple, ast.List)):
        for element in node.elts:
            yield from _quoted_in_type_position(element)
        return
    if isinstance(node, ast.BinOp):
        yield from _quoted_in_type_position(node.left)
        yield from _quoted_in_type_position(node.right)


def _annotation_sites(tree: ast.Module) -> Iterator[tuple[ast.expr, bool]]:
    """Yield ``(annotation_expression, is_function_return)`` for every annotation in a module.

    Covers parameters (positional-only, regular, keyword-only, ``*args`` and ``**kwargs``),
    return types, annotated assignments, the right-hand side of a ``TypeAlias`` and the
    first argument of ``typing.cast``.
    """

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = node.args
            parameters = [*args.posonlyargs, *args.args, *args.kwonlyargs, args.vararg, args.kwarg]
            for parameter in parameters:
                if parameter is not None and parameter.annotation is not None:
                    yield parameter.annotation, False
            if node.returns is not None:
                yield node.returns, True
        elif isinstance(node, ast.AnnAssign):
            yield node.annotation, False
            # ``X: TypeAlias = "Foo"`` defers the alias itself, not the annotation.
            if _leaf_name(node.annotation) == "TypeAlias" and node.value is not None:
                yield node.value, False
        elif isinstance(node, ast.Call) and _leaf_name(node.func) == "cast" and node.args:
            yield node.args[0], False


def _enclosing_classes(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> list[str]:
    """Return the names of the ClassDefs surrounding *node*, innermost first."""

    names: list[str] = []
    parent = parents.get(node)
    while parent is not None:
        if isinstance(parent, ast.ClassDef):
            names.append(parent.name)
        parent = parents.get(parent)
    return names


def _referenced_names(text: str) -> tuple[set[str], ast.expr | None]:
    """Parse a quoted annotation, returning its referenced names and its expression."""

    try:
        expression = ast.parse(text.strip(), mode="eval").body
    except SyntaxError:
        return set(), None
    names = {node.id for node in ast.walk(expression) if isinstance(node, ast.Name)}
    return names, expression


def check_module(path: Path, source: str) -> list[Finding]:
    """Return every lazy-typing finding for a single module."""

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    scope = _collect_scope(tree)
    lines = source.splitlines()
    parents: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node

    findings: list[Finding] = []
    for annotation, is_return in _annotation_sites(tree):
        for constant, text in _quoted_in_type_position(annotation):
            line = constant.lineno
            if PRAGMA in (lines[line - 1] if 0 < line <= len(lines) else ""):
                continue

            names, expression = _referenced_names(text)
            if not names or expression is None:
                continue

            # A module with deferred annotations never needs a quote anywhere.
            if scope.has_future_annotations:
                findings.append(Finding(path, line, "redundant", text, f"module defers annotations, drop the quotes around {text!r}"))
                continue

            enclosing = _enclosing_classes(constant, parents)
            in_scope = {
                name
                for name in names
                if name not in enclosing and (name in ALWAYS_KNOWN or name in scope.imported or scope.defined.get(name, sys.maxsize) < line)
            }

            if in_scope == names:
                findings.append(
                    Finding(path, line, "redundant", text, f"{', '.join(sorted(names))} already in scope, drop the quotes around {text!r}")
                )
            elif is_return and enclosing and names == {enclosing[0]}:
                findings.append(Finding(path, line, "self-return", text, f"returns its own class {text!r}, use typing.Self"))
            elif not isinstance(expression, (ast.Name, ast.Attribute)):
                deferred = ", ".join(sorted(names - in_scope))
                findings.append(Finding(path, line, "whole-quote", text, f"quote only the forward reference ({deferred}), not the whole {text!r}"))

    return findings


def iter_python_files(roots: list[str]) -> Iterator[Path]:
    """Yield every ``.py`` file under *roots*, in a stable order."""

    for root in roots:
        for path in sorted(Path(root).rglob("*.py")):
            yield path


def main(argv: list[str] | None = None) -> int:
    """Scan the configured roots and report every lazy-typing finding."""

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("roots", nargs="*", default=DEFAULT_ROOTS, help="directories to scan (default: the FLYNC source, scripts and tests)")
    parser.add_argument("--quiet", action="store_true", help="print findings only, without the summary line")
    options = parser.parse_args(argv)

    findings: list[Finding] = []
    file_count = 0
    for path in iter_python_files(options.roots or DEFAULT_ROOTS):
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        file_count += 1
        findings.extend(check_module(path, source))

    for finding in findings:
        print(f"[lazy-typing] {finding}")
    if not options.quiet:
        print(f"Checked {file_count} files; {len(findings)} finding(s).")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
