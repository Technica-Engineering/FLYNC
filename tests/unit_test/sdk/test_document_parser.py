from pathlib import Path
from typing import Any

import pytest

from flync.sdk.context.workspace_config import WorkspaceConfiguration
from flync.sdk.workspace.document import Document
from flync.sdk.workspace.flync_workspace import FLYNCWorkspace

# --- Fixtures / Helpers ---


@pytest.fixture
def sample_yaml_text():
    return "foo: bar\nbaz:\n  - 1\n  - 2"


def __assert_compose_ast(needs_compose: bool, compose_ast: Any) -> bool:
    return (needs_compose and compose_ast is not None) or (not needs_compose and compose_ast is None)


# --- Tests ---


@pytest.mark.parametrize("needs_compose", [True, False])
def test_document_parse_and_update(needs_compose, sample_yaml_text, tmp_path):
    doc = Document(uri=Path("config.yaml"), text=sample_yaml_text, needs_compose=needs_compose)
    doc.parse()
    assert doc.ast["foo"] == "bar"
    assert doc.ast["baz"] == [1, 2]
    assert __assert_compose_ast(needs_compose, doc.compose_ast)

    # Update text and re-parse
    updated_text = sample_yaml_text.replace("2", "3")
    doc.update_text(updated_text)
    assert doc.ast["baz"] == [1, 3]


def test_normalize_uri_absolute_and_relative(tmp_path):
    ws_root = tmp_path
    abs_file = ws_root / "subdir" / "file.yaml"
    abs_file.parent.mkdir()
    abs_file.write_text("foo: bar")

    # Absolute path normalized relative to ws_root
    assert Document.normalize_uri(abs_file, ws_root) == "subdir/file.yaml"

    # Relative path unchanged
    rel_path = Path("another.yaml")
    assert Document.normalize_uri(rel_path, ws_root) == "another.yaml"


# --- _open_documents ---


def _make_yaml(tmp_path: Path, name: str, content: str) -> Path:
    """Create a YAML file under tmp_path and return its path."""
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


@pytest.mark.parametrize("map_objects", [True, False])
def test_open_documents_single_file(map_objects, tmp_path):
    _make_yaml(tmp_path, "config.flync.yaml", "foo: bar\nbaz: 42")
    workspace = FLYNCWorkspace("w", tmp_path, WorkspaceConfiguration(map_objects=map_objects))
    workspace._open_documents()
    assert list(workspace.documents) == ["config.flync.yaml"]
    doc = workspace.documents["config.flync.yaml"]
    assert doc.ast == {"foo": "bar", "baz": 42}
    assert __assert_compose_ast(map_objects, doc.compose_ast)


def test_open_documents_multiple_files_in_sorted_order(tmp_path):
    _make_yaml(tmp_path, "sub/b.flync.yaml", "y: 2")
    _make_yaml(tmp_path, "a.flync.yaml", "x: 1")
    _make_yaml(tmp_path, "ignored.yaml", "z: 3")
    workspace = FLYNCWorkspace("w", tmp_path)
    workspace._open_documents()
    assert list(workspace.documents) == ["a.flync.yaml", "sub/b.flync.yaml"]
    assert workspace.documents["a.flync.yaml"].ast == {"x": 1}
    assert workspace.documents["sub/b.flync.yaml"].ast == {"y": 2}


def test_open_documents_compose_ast_preserves_structure(tmp_path):
    _make_yaml(tmp_path, "data.flync.yaml", "items:\n  - a\n  - b")
    workspace = FLYNCWorkspace("w", tmp_path, WorkspaceConfiguration(map_objects=True))
    workspace._open_documents()
    doc = workspace.documents["data.flync.yaml"]
    assert doc.ast == {"items": ["a", "b"]}
    # Verify compose_ast is a YAML node tree
    assert hasattr(doc.compose_ast, "start_mark")
    assert doc.compose_ast.start_mark.line == 0
