"""Unit tests for the resolution of variation points on raw workspace data, and for the variant-independent lint."""

import copy

import pytest

from flync.model.flync_4_variability import Variability
from flync.model.flync_4_variability.resolution import (
    ABSENT,
    DocumentRole,
    copy_tree,
    document_condition,
    document_present,
    document_role,
    lint_document,
    resolve_document,
)

MODEL = Variability.model_validate(
    {
        "feature_model": {
            "features": [{"name": "body", "values": ["sedan", "suv"]}, {"name": "trailer_hitch"}, {"name": "unused"}],
            "qualifiers": {"suv": "body == suv", "sedan": "body == sedan", "big": "body == suv or trailer_hitch"},
        },
        "variants": [
            {"name": "sedan_base", "features": {"body": "sedan"}},
            {"name": "suv_trailer", "features": {"body": "suv", "trailer_hitch": True}},
        ],
    }
)
SEDAN = MODEL.context("sedan_base")
SUV = MODEL.context("suv_trailer")
SYMBOLS = MODEL.feature_model.symbol_table()
CONTEXTS = MODEL.contexts()

PRESENCE_FILE = "ecu_metadata.flync.yaml"

TOPOLOGY = {
    "connections": [
        {"type": "ecu_port_to_ecu_port", "id": "link_front", "ecu1_port": "p1", "ecu2_port": "q1"},
        {"type": "ecu_port_to_ecu_port", "id": "link_trailer", "variant_condition": "trailer_hitch", "ecu1_port": "p2", "ecu2_port": "t1"},
        {
            "type": "ethernet_multidrop",
            "id": "segment",
            "nodes": [
                {"ecu_port": "s_suv", "node_id": 0, "variant_condition": "suv"},
                {"ecu_port": "s_sedan", "node_id": 0, "variant_condition": "sedan"},
                {"ecu_port": "s_all", "node_id": 1},
            ],
        },
    ]
}


def _ids(connections) -> list[str]:
    return [connection["id"] for connection in connections]


def _node_ports(connection) -> list[str]:
    return [node["ecu_port"] for node in connection["nodes"]]


def test_resolves_for_each_variant():
    sedan, sedan_trace = resolve_document(TOPOLOGY, SEDAN)
    suv, _ = resolve_document(TOPOLOGY, SUV)

    assert _ids(sedan["connections"]) == ["link_front", "segment"]
    assert _node_ports(sedan["connections"][1]) == ["s_sedan", "s_all"]
    assert _ids(suv["connections"]) == ["link_front", "link_trailer", "segment"]
    assert _node_ports(suv["connections"][2]) == ["s_suv", "s_all"]
    assert "variant_condition" not in suv["connections"][1]
    assert {("connections", 1), ("connections", 2, "nodes", 0), ("connections", 2, "nodes", 1, "variant_condition")} <= sedan_trace.removed


def test_resolution_never_mutates_its_input():
    original = copy.deepcopy(TOPOLOGY)
    resolved, _ = resolve_document(TOPOLOGY, SUV)
    resolved["connections"].clear()
    assert TOPOLOGY == original


def test_without_variability_every_condition_is_false():
    resolved, _ = resolve_document(TOPOLOGY, None)
    assert _ids(resolved["connections"]) == ["link_front", "segment"]
    assert _node_ports(resolved["connections"][1]) == ["s_all"]


@pytest.mark.parametrize(
    "context, expected",
    [
        pytest.param(SUV, {"name": "x"}, id="holds"),
        pytest.param(SEDAN, ABSENT, id="false"),
        pytest.param(None, ABSENT, id="no-variability"),
    ],
)
def test_root_condition_decides_the_presence_of_the_document(context, expected):
    resolved, trace = resolve_document({"variant_condition": "trailer_hitch", "name": "x"}, context)
    assert resolved == expected if expected is not ABSENT else resolved is ABSENT
    assert ("variant_condition",) in trace.removed


@pytest.mark.parametrize("context", [pytest.param(SEDAN, id="false"), pytest.param(None, id="no-variability")])
def test_the_presence_condition_of_an_ecu_is_only_stripped(context):
    # the loader decides the presence of the ECU folder before it reads the folder, e.g. not at all for a validated ECU
    resolved, trace = resolve_document({"variant_condition": "trailer_hitch", "author": "Dev"}, context, root_presence=False)
    assert resolved == {"author": "Dev"}
    assert trace.removed == {("variant_condition",)}


def test_document_presence_helpers():
    data = {"variant_condition": "body == suv", "name": "x"}
    assert document_condition(data) == "body == suv"
    assert document_condition({"name": "x"}) is None
    assert document_condition(["not", "a", "mapping"]) is None
    assert document_present(data, SUV)
    assert not document_present(data, SEDAN)
    assert not document_present(data, None)
    assert document_present({"name": "x"}, None)


def test_variant_values_are_not_interpreted():
    # no value is chosen: the lint reports the mapping, and the model rejects it
    data = {"version": {"variant_values": [{"value": 2}, {"value": 1}]}}
    resolved, trace = resolve_document(data, SUV)
    assert resolved == data
    assert not trace


def test_copy_tree_is_independent():
    data = {"a": [{"b": 1}]}
    copied = copy_tree(data)
    copied["a"][0]["b"] = 2
    assert data == {"a": [{"b": 1}]}


@pytest.mark.parametrize(
    "path, role",
    [
        pytest.param("ecus/gateway/ecu_metadata.flync.yaml", DocumentRole.ECU_PRESENCE, id="ecu-presence"),
        pytest.param("ecus/gateway/ports.flync.yaml", DocumentRole.ECU, id="ecu-ports"),
        pytest.param("ecus/gateway/controllers/c1/controller_metadata.flync.yaml", DocumentRole.ECU, id="ecu-controller"),
        pytest.param("ecus/gateway/controllers/c1/ecu_metadata.flync.yaml", DocumentRole.ECU, id="deeper-same-name"),
        pytest.param("topology/ethernet_topology.flync.yaml", DocumentRole.SYSTEM_TOPOLOGY, id="topology"),
        pytest.param("variability/variants/base.flync.yaml", DocumentRole.VARIABILITY, id="variability"),
        pytest.param("communication/channels/pdus/PDU_A.flync.yaml", DocumentRole.OTHER, id="communication"),
        pytest.param("system_metadata.flync.yaml", DocumentRole.OTHER, id="metadata"),
    ],
)
def test_document_role(path, role):
    assert document_role(path, PRESENCE_FILE) is role


def _error_ids(findings):
    return [finding["ctx"]["error_id"] for finding in findings]


ENTRY = "topology/ethernet_topology.flync.yaml"
PRESENCE = "ecus/gateway/ecu_metadata.flync.yaml"


@pytest.mark.parametrize(
    "uri, data, symbols, role, error_id",
    [
        pytest.param(
            ENTRY, {"connections": [{"variant_condition": "body =="}]}, SYMBOLS, DocumentRole.SYSTEM_TOPOLOGY, "FLYNC-VAR-MAJ-FMT-438", id="syntax"
        ),
        pytest.param(
            ENTRY,
            {"connections": [{"variant_condition": "sunroof"}]},
            SYMBOLS,
            DocumentRole.SYSTEM_TOPOLOGY,
            "FLYNC-VAR-MAJ-FMT-438",
            id="unknown-name",
        ),
        pytest.param(
            PRESENCE,
            {"variant_condition": "sunroof", "author": "x"},
            SYMBOLS,
            DocumentRole.ECU_PRESENCE,
            "FLYNC-VAR-MAJ-FMT-438",
            id="presence-name",
        ),
        pytest.param(
            "ecus/gateway/ports.flync.yaml",
            {"ports": [{"name": "p", "variant_condition": "suv"}]},
            SYMBOLS,
            DocumentRole.ECU,
            "FLYNC-VAR-MAJ-STRUCT-483",
            id="in-ecu",
        ),
        pytest.param(
            PRESENCE,
            {"hardware": {"variant_condition": "suv"}},
            SYMBOLS,
            DocumentRole.ECU_PRESENCE,
            "FLYNC-VAR-MAJ-STRUCT-483",
            id="nested-in-presence",
        ),
        pytest.param(
            ENTRY,
            {"variant_condition": "suv", "connections": []},
            SYMBOLS,
            DocumentRole.SYSTEM_TOPOLOGY,
            "FLYNC-VAR-MAJ-STRUCT-484",
            id="topology-root",
        ),
        pytest.param(
            ENTRY,
            {"connections": [{"id": "s", "plca": {"variant_condition": "suv", "to_timer": 32}}]},
            SYMBOLS,
            DocumentRole.SYSTEM_TOPOLOGY,
            "FLYNC-VAR-MAJ-STRUCT-484",
            id="topology-not-an-entry",
        ),
        pytest.param(
            "communication/channels/pdus/P.flync.yaml",
            {"variant_condition": "suv"},
            SYMBOLS,
            DocumentRole.OTHER,
            "FLYNC-VAR-MAJ-STRUCT-485",
            id="other",
        ),
        pytest.param(
            ENTRY,
            {"connections": [{"id": {"variant_values": [{"value": "a"}]}}]},
            SYMBOLS,
            DocumentRole.SYSTEM_TOPOLOGY,
            "FLYNC-VAR-MAJ-STRUCT-486",
            id="variant-values",
        ),
        pytest.param(
            ENTRY, {"connections": [{"variant_condition": "suv"}]}, None, DocumentRole.SYSTEM_TOPOLOGY, "FLYNC-VAR-MAJ-REQ-444", id="no-variability"
        ),
        pytest.param(
            "variability/variants/v.flync.yaml",
            {"variant_condition": "suv"},
            SYMBOLS,
            DocumentRole.VARIABILITY,
            "FLYNC-VAR-MAJ-STRUCT-445",
            id="inside-variability",
        ),
        pytest.param(
            ENTRY,
            {"connections": [{"variant_condition": "unused"}]},
            SYMBOLS,
            DocumentRole.SYSTEM_TOPOLOGY,
            "FLYNC-VAR-WARN-CONS-446",
            id="dead-condition",
        ),
    ],
)
def test_lint_document(uri, data, symbols, role, error_id):
    assert _error_ids(lint_document(uri, data, symbols, CONTEXTS, role)) == [error_id]


def test_lint_document_accepts_valid_points():
    assert lint_document(ENTRY, TOPOLOGY, SYMBOLS, CONTEXTS, DocumentRole.SYSTEM_TOPOLOGY) == []
    assert lint_document(PRESENCE, {"variant_condition": "suv", "author": "Dev"}, SYMBOLS, CONTEXTS, DocumentRole.ECU_PRESENCE) == []


def test_lint_reports_every_misplaced_point():
    data = {"ports": [{"name": "p1", "variant_condition": "suv"}, {"name": "p2", "speed": {"variant_values": [{"value": 100}]}}]}
    findings = lint_document("ecus/gateway/ports.flync.yaml", data, SYMBOLS, CONTEXTS, DocumentRole.ECU)
    assert _error_ids(findings) == ["FLYNC-VAR-MAJ-STRUCT-483", "FLYNC-VAR-MAJ-STRUCT-486"]
    assert [finding["loc"] for finding in findings] == [("ports", 0, "variant_condition"), ("ports", 1, "speed", "variant_values")]


def test_lint_locates_findings_by_original_path():
    (finding,) = lint_document(
        ENTRY, {"connections": [{"id": "ok"}, {"variant_condition": "sunroof"}]}, SYMBOLS, CONTEXTS, DocumentRole.SYSTEM_TOPOLOGY
    )
    assert finding["loc"] == ("connections", 1, "variant_condition")
    assert finding["ctx"]["yaml_path"] == ENTRY
