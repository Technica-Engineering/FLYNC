from pathlib import Path
from typing import Any

import pytest

from flync.sdk.workspace.document import Document, parse_document

# --- Fixtures / Helpers ---


@pytest.fixture
def sample_yaml_text():
    return "foo: bar\nbaz:\n  - 1\n  - 2"


@pytest.fixture
def sample_file(tmp_path, sample_yaml_text):
    """Create a sample YAML file inside a temporary workspace root."""
    file_path = tmp_path / "config.yaml"
    file_path.write_text(sample_yaml_text)
    return file_path, tmp_path, sample_yaml_text


def __assert_compose_ast(needs_compose: bool, compose_ast: Any) -> bool:
    return (needs_compose and compose_ast is not None) or (not needs_compose and compose_ast is None)


# --- Tests ---


@pytest.mark.parametrize("needs_compose", [True, False])
def test_document_parse_and_update(needs_compose, sample_yaml_text):
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
    yaml_instance_first = doc._yaml

    doc.parse()
    yaml_instance_second = doc._yaml

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


@pytest.mark.parametrize("needs_compose", [True, False])
def test_parse_document(sample_file, needs_compose):
    file_path, ws_root, yaml_text = sample_file

    normalized_uri, ast, compose_ast, text = parse_document(
        path=file_path,
        text=yaml_text,
        ws_root=ws_root,
        needs_compose=needs_compose,
    )

    assert normalized_uri == "config.yaml"
    assert ast["foo"] == "bar"
    assert ast["baz"] == [1, 2]
    assert __assert_compose_ast(needs_compose, compose_ast)
    assert text == yaml_text
