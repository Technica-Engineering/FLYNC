from pathlib import Path
from typing import Any

import pytest

from flync.sdk.workspace.document import Document, parse_documents

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


def test_parse_reuses_yaml_instance(sample_yaml_text):
    doc = Document(uri=Path("config.yaml"), text=sample_yaml_text, needs_compose=False)

    doc.parse()
    yaml_instance_first = Document._get_safe_yaml()

    doc.parse()
    yaml_instance_second = Document._get_safe_yaml()

    assert yaml_instance_first is yaml_instance_second


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


# --- parse_documents ---


def _make_yaml(tmp_path: Path, name: str, content: str) -> tuple[Path, Path]:
    """Create a YAML file under tmp_path and return (file_path, ws_root)."""
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path, tmp_path


@pytest.mark.parametrize("needs_compose", [True, False])
def test_parse_documents_single_file(needs_compose, tmp_path):
    file_path, ws_root = _make_yaml(tmp_path, "config.yaml", "foo: bar\nbaz: 42")
    results = parse_documents([file_path], ws_root, needs_compose)
    assert len(results) == 1
    uri, ast, compose_ast = results[0]
    assert uri == "config.yaml"
    assert ast == {"foo": "bar", "baz": 42}
    if needs_compose:
        assert compose_ast is not None
    else:
        assert compose_ast is None


def test_parse_documents_multiple_files(tmp_path):
    files = [
        _make_yaml(tmp_path, "a.yaml", "x: 1"),
        _make_yaml(tmp_path, "sub/b.yaml", "y: 2"),
    ]
    results = parse_documents([f for f, _ in files], tmp_path, False)
    assert len(results) == 2
    assert results[0] == ("a.yaml", {"x": 1}, None)
    assert results[1] == ("sub/b.yaml", {"y": 2}, None)


def test_parse_documents_compose_ast_preserves_structure(tmp_path):
    file_path, ws_root = _make_yaml(tmp_path, "data.yaml", "items:\n  - a\n  - b")
    results = parse_documents([file_path], ws_root, True)
    _, ast, compose_ast = results[0]
    assert ast == {"items": ["a", "b"]}
    assert compose_ast is not None
    # Verify compose_ast is a ruamel.yaml node tree
    assert hasattr(compose_ast, "start_mark")
    assert compose_ast.start_mark.line == 0
