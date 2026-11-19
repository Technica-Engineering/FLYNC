"""Unit tests for the variant view of a composed YAML document: the tree error positions and the object map walk."""

from flync.core.utils import yaml_io
from flync.model.flync_4_variability import Variability
from flync.model.flync_4_variability.resolution import resolve_document
from flync.sdk.workspace.variant_view import project_node

TEXT = """\
connections:
  - id: link_1
    variant_condition: suv
  - id: segment
    nodes:
      - ecu_port: p_suv
        variant_condition: suv
      - ecu_port: p_all
  - id: link_3
"""

CONTEXT = Variability.model_validate(
    {
        "feature_model": {"features": [{"name": "suv"}]},
        "variants": [{"name": "sedan", "features": {"suv": False}}],
    }
).context("sedan")


def _compose_and_resolve():
    data = yaml_io.safe_load(TEXT)
    node = yaml_io.compose(TEXT)
    _, trace = resolve_document(data, CONTEXT)
    return node, trace


def _mapping(node) -> dict:
    return {key.value: value for key, value in node.value}


def test_projection_matches_the_resolved_data_and_keeps_source_marks():
    node, trace = _compose_and_resolve()

    projected = project_node(node, trace)

    connections = _mapping(projected)["connections"].value
    assert [_mapping(connection)["id"].value for connection in connections] == ["segment", "link_3"]
    nodes = _mapping(connections[0])["nodes"].value
    assert [_mapping(entry)["ecu_port"].value for entry in nodes] == ["p_all"]
    assert nodes[0].start_mark.line == 7  # p_all keeps its own line although p_suv before it is gone (0-based)
    assert connections[1].start_mark.line == 8


def test_projection_shares_untouched_nodes_and_leaves_the_original_alone():
    node, trace = _compose_and_resolve()

    projected = project_node(node, trace)

    assert len(_mapping(node)["connections"].value) == 3
    assert _mapping(projected)["connections"].value[1] is _mapping(node)["connections"].value[2]


def test_projection_without_trace_is_the_original():
    node, _ = _compose_and_resolve()
    assert project_node(node, None) is node
