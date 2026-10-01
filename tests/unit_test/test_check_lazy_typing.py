"""Tests for the ``check_lazy_typing`` CI guard.

The guard is the thing that keeps redundant quoted annotations out of the tree, so its
blind spots matter more than its hit rate: a rule it cannot see is a rule nobody enforces.
Each case below is the smallest module that exercises one rule.
"""

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "ci" / "check_lazy_typing.py"


def _load_guard():
    """Import the guard script, which lives outside the installed packages."""

    spec = importlib.util.spec_from_file_location("check_lazy_typing", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard = _load_guard()


def kinds(source: str) -> list[str]:
    """Return the finding kinds the guard reports for *source*."""

    return [finding.kind for finding in guard.check_module(Path("sample.py"), source)]


FLAGGED = [
    pytest.param('from x import Foo\n\n\ndef f(a: "Foo") -> None: ...\n', "redundant", id="param-in-scope"),
    pytest.param('from x import Foo\n\n\ndef f() -> "Foo": ...\n', "redundant", id="return-in-scope"),
    pytest.param('from typing import Optional\nfrom x import Foo\n\n\na: Optional["Foo"] = None\n', "redundant", id="nested-in-subscript"),
    pytest.param(
        'from typing import Annotated, List, Optional\nfrom x import Foo, Meta\n\n\na: Annotated[Optional[List["Foo"]], Meta()] = None\n',
        "redundant",
        id="nested-under-annotated",
    ),
    pytest.param('from x import Foo\n\n\ndef f(*args: "Foo") -> None: ...\n', "redundant", id="vararg"),
    pytest.param('from x import Foo\n\n\ndef f(**kw: "Foo") -> None: ...\n', "redundant", id="kwarg"),
    pytest.param('from typing import cast\nfrom x import Foo\n\n\ny = cast("Foo", 1)\n', "redundant", id="cast"),
    pytest.param('from typing import TypeAlias\nfrom x import Foo\n\n\nY: TypeAlias = "Foo"\n', "redundant", id="type-alias"),
    pytest.param(
        'from __future__ import annotations\n\nfrom typing import TYPE_CHECKING\n\nif TYPE_CHECKING:\n    from x import Foo\n\n\na: "Foo" = None\n',
        "redundant",
        id="future-annotations-never-needs-quotes",
    ),
    pytest.param(
        'from typing import TYPE_CHECKING, Optional\n\nif TYPE_CHECKING:\n    from x import Foo\n\n\na: "Optional[Foo]" = None\n',
        "whole-quote",
        id="whole-annotation-quoted",
    ),
    pytest.param(
        'from typing import TYPE_CHECKING\n\nif TYPE_CHECKING:\n    from x import Foo\n\n\nclass C:\n    def f(self) -> "C": ...\n',
        "self-return",
        id="self-return-should-use-Self",
    ),
    pytest.param(
        'import sys\n\nif sys.version_info >= (3, 13):\n    from x import Foo\nelse:\n    from y import Foo\n\n\na: "Foo" = None\n',
        "redundant",
        id="conditional-runtime-import-still-binds-the-name",
    ),
]

ALLOWED = [
    pytest.param(
        'from typing import TYPE_CHECKING, Optional\n\nif TYPE_CHECKING:\n    from x import Foo\n\n\na: Optional["Foo"] = None\n',
        id="type-checking-only-import",
    ),
    pytest.param('def f() -> "Later": ...\n\n\nclass Later: ...\n', id="defined-later-in-module"),
    pytest.param(
        'from typing import List, Optional\n\n\nclass C:\n    children: Optional[List["C"]] = None\n',
        id="field-self-reference-is-load-bearing",
    ),
    pytest.param('from typing import Literal\n\n\na: Literal["drop", "mirror"] = "drop"\n', id="literal-payload-is-not-a-type"),
    pytest.param(
        'from typing import Annotated\nfrom x import Field\n\n\na: Annotated[int, Field(description="a note")] = 1\n',
        id="annotated-metadata-is-not-a-type",
    ),
    pytest.param('from x import Foo\n\n\ndef f(a: "Foo") -> None: ...  # lazy-typing: allow\n', id="inline-pragma"),
]


@pytest.mark.parametrize(("source", "expected"), FLAGGED)
def test_flagged(source: str, expected: str) -> None:
    assert kinds(source) == [expected]


@pytest.mark.parametrize("source", ALLOWED)
def test_allowed(source: str) -> None:
    assert kinds(source) == []


def test_repo_is_clean() -> None:
    """The guard must pass on the tree it ships with, or it is not enforcing anything."""

    assert guard.main([]) == 0
