"""Regression tests for the model dependency graph utilities."""

from typing import Annotated, List

from pydantic import BaseModel

from flync.core.annotations import External, OutputStrategy
from flync.sdk.utils.model_dependencies import ModelDependencyGraph


class _Widget(BaseModel):
    name: str = ""


class _ExternalHost(BaseModel):
    # same field name as the inline host, but externally serialized
    widgets: Annotated[List[_Widget], External(output_structure=OutputStrategy.SINGLE_FILE)] = []


class _InlineHost(BaseModel):
    # same field name, plain inline
    widgets: List[_Widget] = []


class _Root(BaseModel):
    external: _ExternalHost = _ExternalHost()
    inline: _InlineHost = _InlineHost()


def test_parent_from_child_prefers_external_parent():
    """A field name shared by an external and an inline parent must resolve to
    the external-carrying parent deterministically.

    parent_from_child feeds rebuild_type_from_parent, which reconstructs the
    on-disk wrapper for external fields; if the inline parent won instead, the
    external files would be validated against the bare element type and
    silently dropped. reverse_tree values are sets, so the pre-fix plain
    iteration order varied with class allocation order — this locks it in.
    """

    graph = ModelDependencyGraph(_Root)
    assert _Widget in graph.reverse_tree
    assert {_ExternalHost, _InlineHost} <= graph.reverse_tree[_Widget]  # both are genuine candidates
    assert graph.parent_from_child(_Widget, "widgets") is _ExternalHost
