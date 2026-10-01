"""Tests for exporting a model as one JSON Schema document per Pydantic model class."""

import json
import re
from enum import Enum
from typing import Optional

import pytest
from pydantic import BaseModel, Field

from flync.model import FLYNCModel
from flync.sdk.utils.model_schema import JSON_SCHEMA_DIALECT, build_model_schemas, dump_model_schemas


class _Color(str, Enum):
    RED = "red"
    BLUE = "blue"


class _Leaf(BaseModel):
    color: _Color = _Color.RED


class _Branch(BaseModel):
    leaves: list[_Leaf] = []
    named_leaves: dict[str, _Leaf] = {}


class _Tree(BaseModel):
    trunk: _Branch
    spare: Optional[_Leaf] = None


class _Node(BaseModel):
    children: list["_Node"] = []


class _DocumentedBase(BaseModel):
    """
    Base with a documented field.

    Parameters
    ----------
    inherited : str
        Documented on the base class.
    """

    inherited: str = ""


class _Documented(_DocumentedBase):
    """
    A documented model.

    Parameters
    ----------
    plain : str
        First line
        continues here.

        Second paragraph.
    linked : list of \
    :class:`~tests.unit_test.sdk.test_model_schema._Leaf`
        Refers to ``Leaf`` via :class:`~tests.unit_test.sdk.test_model_schema._Leaf`.
    aliased : int
        Documented under its field name.
    explicit : int
        Overridden by the Field description.

    Private Attributes
    ------------------
    _cache :
        Internal only.

    Notes
    -----
    Kept in the model description.
    """

    plain: str = ""
    linked: list[_Leaf] = []
    aliased: int = Field(default=0, alias="aliasedName")
    explicit: int = Field(default=0, description="From Field.")
    undocumented: int = 0


def _refs(document: dict) -> set[str]:
    """Return every ``$ref`` value used anywhere in a schema document."""

    return set(re.findall(r'"\$ref": "([^"]*)"', json.dumps(document)))


def test_every_model_gets_its_own_document():
    """The root, each nested class and the enum each end up in a separate document, root first."""

    documents = build_model_schemas(_Tree)

    assert list(documents)[0] == "_Tree.schema.json"
    assert set(documents) == {"_Tree.schema.json", "_Branch.schema.json", "_Leaf.schema.json", "_Color.schema.json"}
    assert all("$defs" not in document for document in documents.values())
    assert all(document["$schema"] == JSON_SCHEMA_DIALECT for document in documents.values())


def test_references_point_at_sibling_files():
    """Model fields reference the sibling schema file, including inside lists, dicts and optionals."""

    documents = build_model_schemas(_Tree)

    assert _refs(documents["_Tree.schema.json"]) == {"_Branch.schema.json", "_Leaf.schema.json"}
    assert _refs(documents["_Branch.schema.json"]) == {"_Leaf.schema.json"}
    assert _refs(documents["_Leaf.schema.json"]) == {"_Color.schema.json"}


def test_recursive_root_is_written_once():
    """A self-referencing root becomes a single document that references its own file."""

    documents = build_model_schemas(_Node)

    assert list(documents) == ["_Node.schema.json"]
    assert _refs(documents["_Node.schema.json"]) == {"_Node.schema.json"}
    assert "properties" in documents["_Node.schema.json"]


def test_suffix_and_base_uri():
    """The suffix applies to file names and refs alike; the base URI yields an absolute ``$id``."""

    documents = build_model_schemas(_Branch, suffix=".json", base_uri="https://example.com/schemas/")

    assert set(documents) == {"_Branch.json", "_Leaf.json", "_Color.json"}
    assert _refs(documents["_Branch.json"]) == {"_Leaf.json"}
    assert documents["_Branch.json"]["$id"] == "https://example.com/schemas/_Branch.json"


def test_field_descriptions_come_from_the_parameters_section():
    """Fields are described from the numpydoc Parameters section, with Field(description) taking precedence."""

    properties = build_model_schemas(_Documented)["_Documented.schema.json"]["properties"]

    assert properties["plain"]["description"] == "First line continues here.\n\nSecond paragraph."
    assert properties["linked"]["description"] == "Refers to `Leaf` via _Leaf."
    assert properties["aliasedName"]["description"] == "Documented under its field name."
    assert properties["explicit"]["description"] == "From Field."
    assert properties["inherited"]["description"] == "Documented on the base class."
    assert "description" not in properties["undocumented"]


def test_model_description_drops_the_field_sections():
    """The model description keeps the prose and other sections but not the Parameters or Private Attributes."""

    description = build_model_schemas(_Documented)["_Documented.schema.json"]["description"]

    assert description == "A documented model.\n\nNotes\n-----\nKept in the model description."


def test_flync_model_references_resolve():
    """Every reference in the FLYNC schema set names a document of the same set."""

    documents = build_model_schemas(FLYNCModel)

    assert list(documents)[0] == "FLYNCModel.schema.json"
    dangling = {ref for document in documents.values() for ref in _refs(document)} - set(documents)
    assert not dangling


@pytest.mark.parametrize("root", [_Tree, FLYNCModel])
def test_dump_writes_one_file_per_document(tmp_path, root):
    """Dumping writes every document to the output directory as JSON, root first."""

    documents = build_model_schemas(root)
    paths = dump_model_schemas(root, tmp_path / "schemas")

    assert [path.name for path in paths] == list(documents)
    assert {path.name for path in (tmp_path / "schemas").iterdir()} == set(documents)
    assert json.loads(paths[0].read_text(encoding="utf-8")) == documents[paths[0].name]
