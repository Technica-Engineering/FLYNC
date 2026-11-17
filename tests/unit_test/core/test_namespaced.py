"""Tests for the ``Namespaced`` annotation helpers in ``flync.core.base_models.namespace``."""

import pytest

from flync.core.annotations import Namespaced
from flync.core.base_models import qualify_name, split_qualified_name

NS = Namespaced()


@pytest.mark.parametrize(
    "namespace, data, expected_name",
    [
        pytest.param(("abc",), {"name": "ets", "id": 1}, "abc::ets", id="one-segment"),
        pytest.param(("abc", "def"), {"name": "ets"}, "abc::def::ets", id="nested"),
        pytest.param((), {"name": "ets"}, "ets", id="no-namespace-keeps-name"),
        pytest.param(("abc",), {"name": "Enhanced Testability Services"}, "abc::Enhanced Testability Services", id="name-with-spaces"),
    ],
)
def test_qualify_name(namespace, data, expected_name):
    original = dict(data)
    result = qualify_name(data, namespace, NS)
    assert result["name"] == expected_name
    assert {k: v for k, v in result.items() if k != "name"} == {k: v for k, v in original.items() if k != "name"}
    assert data == original, "the input (a cached document tree) must never be mutated"


@pytest.mark.parametrize("data", [{"id": 1}, {"name": 5}, {"name": None}], ids=["missing", "int", "none"])
def test_qualify_name_leaves_an_invalid_name_for_validation_to_report(data):
    assert qualify_name(data, ("abc",), NS) == data


def test_qualify_name_honours_separator_and_key():
    custom = Namespaced(separator="/", name_key="title")
    assert qualify_name({"title": "t"}, ("a", "b"), custom) == {"title": "a/b/t"}


@pytest.mark.parametrize(
    "qualified, segments, name",
    [
        pytest.param("ets", (), "ets", id="plain"),
        pytest.param("abc::ets", ("abc",), "ets", id="one-segment"),
        pytest.param("abc::def::ets", ("abc", "def"), "ets", id="nested"),
    ],
)
def test_split_qualified_name_inverts_qualify_name(qualified, segments, name):
    assert split_qualified_name(qualified, NS) == (segments, name)
    assert qualify_name({"name": name}, segments, NS)["name"] == qualified
