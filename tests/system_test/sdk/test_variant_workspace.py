"""
System tests for variant management: one 150 % workspace resolved, validated and exported per product variant.

They run against ``examples/flync_4_variability/02_architecture_alternatives``, which has both kinds of variation point:
ECUs whose presence a condition at the root of their ``ecu_metadata`` decides (the domain and the zone controllers, and
the two generations of the central compute ECU, which are alternatives), and conditional entries of the system topology
(the links of each architecture, and the coordinator nodes of the door segment both architectures share).
"""

import shutil
from pathlib import Path

import pytest
import yaml

from flync.sdk.helpers.generation_helpers import dump_flync_workspace, export_variant
from flync.sdk.helpers.validation_helpers import validate_external_node, validate_variants
from flync.sdk.utils.model_dumper import dump_model_with_discriminators
from flync.sdk.workspace.flync_workspace import FLYNCWorkspace, VariantWorkspaceWriteError, WorkspaceConfiguration
from flync.sdk.workspace.ids import ObjectId
from tests.example_paths import FLYNC_EXAMPLE, FLYNC_VARIANTS_EXAMPLE
from tests.system_test.sdk.helper import patch_yaml

VARIANTS = ["domain_gen1", "domain_gen2", "zonal_gen2"]
DOMAIN_ECUS = ["body_domain_controller", "central_compute_gen1", "chassis_domain_controller", "door_module_left", "door_module_right"]
DOMAIN_GEN2_ECUS = [name.replace("gen1", "gen2") for name in DOMAIN_ECUS]
ZONAL_ECUS = ["central_compute_gen2", "door_module_left", "door_module_right", "zone_controller_front", "zone_controller_rear"]
DOMAIN_LINKS = ["link_body_domain", "link_chassis_domain", "DoorSegment"]
ZONAL_LINKS = ["link_zone_front", "link_zone_rear", "DoorSegment"]
TOPOLOGY = "topology/ethernet_topology.flync.yaml"
REAR_ZONE = "ecus/zone_controller_rear"


@pytest.fixture(scope="module")
def example():
    """The example parsed once; tests switch between its variants with ``select_variant``."""
    return FLYNCWorkspace.safe_load_workspace("variants", FLYNC_VARIANTS_EXAMPLE)


@pytest.fixture
def workspace_copy(tmp_path) -> Path:
    """A writable copy of the example."""
    root = tmp_path / "ws"
    shutil.copytree(FLYNC_VARIANTS_EXAMPLE, root)
    return root


def _error_ids(ws) -> list[str]:
    return sorted(str((err.get("ctx") or {}).get("error_id")) for errs in ws.documents_diags.values() for err in errs)


def _ids_of(result) -> list[str]:
    return sorted(str((err.get("ctx") or {}).get("error_id")) for errs in result.errors.values() for err in errs)


def _with_id(entries: list, entry_id: str) -> dict:
    """The one connection of a parsed system topology whose ``id`` is ``entry_id``."""
    (entry,) = [entry for entry in entries if entry.get("id") == entry_id]
    return entry


def _line_of(path: Path, text: str) -> int:
    """The 1-based number of the first line of ``path`` that contains ``text``."""
    return next(number for number, line in enumerate(path.read_text().splitlines(), 1) if text in line)


@pytest.mark.parametrize(
    "variant, ecus, links, segment",
    [
        pytest.param("domain_gen1", DOMAIN_ECUS, DOMAIN_LINKS, ["bdc_p2", "dml_p1", "dmr_p1"], id="domain_gen1"),
        pytest.param("domain_gen2", DOMAIN_GEN2_ECUS, DOMAIN_LINKS, ["bdc_p2", "dml_p1", "dmr_p1"], id="domain_gen2"),
        pytest.param("zonal_gen2", ZONAL_ECUS, ZONAL_LINKS, ["zcf_p2", "dml_p1", "dmr_p1"], id="zonal_gen2"),
    ],
)
def test_resolves_each_variant(example, variant, ecus, links, segment):
    example.select_variant(variant)
    model = example.flync_model

    assert example.load_errors == []
    assert model.active_variant.name == variant
    assert [ecu.name for ecu in model.ecus] == ecus
    connections = model.topology.ethernet_topology.connections
    assert [c.id for c in connections] == links
    assert [node.ecu_port_name for node in connections[-1].nodes] == segment


def test_alternative_ecus_are_complete_and_interchangeable(example):
    example.select_variant("domain_gen1")
    gen1 = example.flync_model.get_ecu_by_name("central_compute_gen1")
    assert example.flync_model.get_ecu_by_name("central_compute_gen2") is None

    example.select_variant("domain_gen2")
    gen2 = example.flync_model.get_ecu_by_name("central_compute_gen2")
    assert example.flync_model.get_ecu_by_name("central_compute_gen1") is None

    assert (str(gen1.ecu_metadata.hardware.version), str(gen2.ecu_metadata.hardware.version)) == ("1.0.0", "2.0.0")
    assert [c.name for c in gen2.controllers] == ["cc_main", "cc_safety"]
    # the same ports outside, so the links of the system topology fit both of them
    assert [p.name for p in gen2.ports] == [p.name for p in gen1.ports] == ["cc_p1", "cc_p2"]


def test_default_variant_is_loaded_without_selection():
    ws = FLYNCWorkspace.load_workspace("variants", FLYNC_VARIANTS_EXAMPLE)
    assert ws.active_variant.name == "domain_gen1"
    assert ws.variants == VARIANTS
    inactive = ws.inactive_documents()
    # exactly the documents of the ECUs that are not part of the variant
    assert {uri.split("/")[1] for uri in inactive} == {"central_compute_gen2", "zone_controller_front", "zone_controller_rear"}
    assert all(uri.startswith("ecus/") for uri in inactive)
    assert f"{REAR_ZONE}/ecu_metadata.flync.yaml" in inactive


def test_validate_variants_passes_for_every_variant():
    result = validate_variants(FLYNC_VARIANTS_EXAMPLE)
    assert result.passed, result.failed_variants()
    assert list(result.variants) == VARIANTS
    assert all(r.variant == name for name, r in result.variants.items())


def test_workspace_without_variability_is_unchanged():
    result = validate_variants(FLYNC_EXAMPLE)
    assert list(result.variants) == [""]
    assert result.variants[""].workspace.variability is None
    assert result.variants[""].model.active_variant is None


def test_defect_is_reported_for_the_variants_it_occurs_in(workspace_copy):
    # forget the condition of the zonal coordinator of the door segment: the domain variants have no front zone controller
    with patch_yaml(workspace_copy / TOPOLOGY) as topology:
        del _with_id(topology["connections"], "DoorSegment")["nodes"][1]["variant_condition"]

    result = validate_variants(workspace_copy)

    assert result.failed_variants() == ["domain_gen1", "domain_gen2"]
    assert "FLYNC-TOP-MAJ-REF-329" in _ids_of(result.variants["domain_gen1"])


def test_error_position_after_a_filtered_item(workspace_copy):
    topology_file = workspace_copy / TOPOLOGY
    with patch_yaml(topology_file) as topology:
        # after the two coordinator nodes, one of which every variant drops
        _with_id(topology["connections"], "DoorSegment")["nodes"].append({"ecu_port": "dmr_p1", "node_id": 300})
    line = _line_of(topology_file, "node_id: 300")

    for variant in ("domain_gen1", "zonal_gen2"):
        ws = FLYNCWorkspace.safe_load_workspace("ws", workspace_copy, variant=variant)
        lines = [(err.get("ctx") or {}).get("line") for err in ws.documents_diags.get(TOPOLOGY, [])]
        assert line in lines, f"{variant}: node_id error not located at line {line}: {lines}"


def test_object_map_follows_the_resolved_documents():
    ws = FLYNCWorkspace.load_workspace("ws", FLYNC_VARIANTS_EXAMPLE, WorkspaceConfiguration(map_objects=True), variant="zonal_gen2")
    topology_file = FLYNC_VARIANTS_EXAMPLE / TOPOLOGY

    # the two domain links (the first connections in the file) are dropped in this variant: the ids stay dense and the
    # connection after them maps to its own source lines
    link = ObjectId("topology.ethernet_topology.connections.0")
    assert ws.get_object(link).model.id == "link_zone_front"
    assert ws.get_source(link).range.start.line <= _line_of(topology_file, "id: link_zone_front") <= ws.get_source(link).range.end.line
    assert not ws.has_object(ObjectId("topology.ethernet_topology.connections.3"))
    # the same for the coordinator node of the door segment, after the dropped one of the domain architecture
    node = ObjectId("topology.ethernet_topology.connections.2.nodes.0")
    assert ws.get_object(node).model.ecu_port_name == "zcf_p2"
    assert ws.get_source(node).range.start.line <= _line_of(topology_file, "ecu_port: zcf_p2") <= ws.get_source(node).range.end.line
    # the ECUs of the active alternative are registered under their own names
    assert ws.get_source(ObjectId("ecus.zone_controller_front")).uri == "ecus/zone_controller_front"
    assert not ws.has_object(ObjectId("ecus.body_domain_controller"))


def test_resolved_model_is_not_written_over_the_workspace(workspace_copy):
    ws = FLYNCWorkspace.load_workspace("ws", workspace_copy, variant="zonal_gen2")
    with pytest.raises(VariantWorkspaceWriteError, match="zonal_gen2"):
        dump_flync_workspace(ws.flync_model, workspace_copy, "ws")
    with pytest.raises(VariantWorkspaceWriteError):
        ws.load_flync_model(ws.flync_model, workspace_copy)


@pytest.mark.parametrize("variant", ["domain_gen1", "zonal_gen2"])
def test_export_round_trip(example, tmp_path, variant):
    example.select_variant(variant)
    export_variant(example.flync_model, tmp_path / variant)

    exported = FLYNCWorkspace.load_workspace("exported", tmp_path / variant)

    assert exported.load_errors == []
    assert exported.variability is None
    assert exported.flync_model.active_variant is None
    assert not any("variant_condition" in path.read_text(encoding="utf-8") for path in (tmp_path / variant).rglob("*.flync.yaml"))
    assert (tmp_path / variant / "ecus/zone_controller_front").is_dir() == (variant == "zonal_gen2")
    resolved = example.flync_model.model_copy(update={"variability": None})
    # a list that resolves to empty is not written, so it reloads as unset
    assert _without_empty_lists(dump_model_with_discriminators(exported.flync_model, mode="json")) == _without_empty_lists(
        dump_model_with_discriminators(resolved, mode="json")
    )


def _without_empty_lists(data):
    """Drop mapping entries holding an empty list, recursively."""
    if isinstance(data, dict):
        return {key: _without_empty_lists(value) for key, value in data.items() if value != []}
    if isinstance(data, list):
        return [_without_empty_lists(item) for item in data]
    return data


def test_export_refuses_a_variant_workspace(example, workspace_copy):
    with pytest.raises(VariantWorkspaceWriteError):
        export_variant(example.flync_model, workspace_copy)


@pytest.mark.parametrize(
    "variant, error_id",
    [
        pytest.param("nobody", "FLYNC-VAR-FAT-REF-449", id="unknown-variant"),
    ],
)
def test_selection_errors(variant, error_id):
    ws = FLYNCWorkspace.safe_load_workspace("ws", FLYNC_VARIANTS_EXAMPLE, variant=variant)
    assert ws.flync_model is None
    assert error_id in _error_ids(ws)


def test_no_variant_selected(workspace_copy):
    with patch_yaml(workspace_copy / "variability/feature_model.flync.yaml") as feature_model:
        del feature_model["default_variant"]
    ws = FLYNCWorkspace.safe_load_workspace("ws", workspace_copy)
    assert ws.flync_model is None
    assert _error_ids(ws) == ["FLYNC-VAR-FAT-REQ-448"]


def test_invalid_variability_stops_the_load(workspace_copy):
    with patch_yaml(workspace_copy / "variability/variants/zonal_gen2.flync.yaml") as variant:
        variant["features"]["architecture"] = "mars"
    result = validate_variants(workspace_copy)
    assert not result.passed
    assert result.variants == {}
    assert sorted(_ids_of(result)) == ["FLYNC-VAR-FAT-STRUCT-450", "FLYNC-VAR-MAJ-VAL-481"]


def test_variant_for_a_workspace_without_variability():
    ws = FLYNCWorkspace.safe_load_workspace("ws", FLYNC_EXAMPLE, variant="suv")
    assert ws.flync_model is None
    assert _error_ids(ws) == ["FLYNC-VAR-FAT-REF-449"]


def test_variation_points_without_variability(tmp_path):
    root = tmp_path / "ws"
    shutil.copytree(FLYNC_VARIANTS_EXAMPLE, root)
    shutil.rmtree(root / "variability")
    ws = FLYNCWorkspace.safe_load_workspace("ws", root)
    assert {i for i in _error_ids(ws) if i.startswith("FLYNC-VAR-")} == {"FLYNC-VAR-MAJ-REQ-444"}
    # every condition is false: only the ECUs without a presence condition remain
    assert [ecu.name for ecu in ws.flync_model.ecus] == ["door_module_left", "door_module_right"]


def _set_port_condition(data):
    data["ports"][0]["variant_condition"] = "zonal"


def _set_root_condition(data):
    data["variant_condition"] = "zonal"


def _set_value_variation(data):
    _with_id(data["connections"], "DoorSegment")["plca"]["to_timer"] = {
        "variant_values": [{"variant_condition": "zonal", "value": 64}, {"value": 32}]
    }


@pytest.mark.parametrize(
    "document, patch, error_id",
    [
        pytest.param(f"{REAR_ZONE}/ports.flync.yaml", _set_port_condition, "FLYNC-VAR-MAJ-STRUCT-483", id="inside-an-ecu"),
        pytest.param(
            "ecus/central_compute_gen2/controllers/cc_safety/controller_metadata.flync.yaml",
            _set_root_condition,
            "FLYNC-VAR-MAJ-STRUCT-483",
            id="root-of-a-controller",
        ),
        pytest.param(TOPOLOGY, _set_root_condition, "FLYNC-VAR-MAJ-STRUCT-484", id="root-of-the-system-topology"),
        pytest.param(
            "communication/channels/pdus/PDU_DoorLeftStatus.flync.yaml", _set_root_condition, "FLYNC-VAR-MAJ-STRUCT-485", id="communication"
        ),
        pytest.param(TOPOLOGY, _set_value_variation, "FLYNC-VAR-MAJ-STRUCT-486", id="variant-values"),
    ],
)
def test_misplaced_variation_points_fail_every_variant(workspace_copy, document, patch, error_id):
    with patch_yaml(workspace_copy / document) as data:
        patch(data)

    result = validate_variants(workspace_copy)

    assert result.failed_variants() == VARIANTS
    for name, variant in result.variants.items():
        assert error_id in [str((err.get("ctx") or {}).get("error_id")) for err in variant.errors.get(document, [])], name


def test_findings_in_inactive_documents_are_reported(workspace_copy):
    metadata = workspace_copy / f"{REAR_ZONE}/ecu_metadata.flync.yaml"
    with patch_yaml(metadata) as data:
        data["variant_condition"] = "zonal and sunroof"
    ws = FLYNCWorkspace.safe_load_workspace("ws", workspace_copy, variant="domain_gen1")
    (finding,) = ws.documents_diags[f"{REAR_ZONE}/ecu_metadata.flync.yaml"]
    assert finding["ctx"]["error_id"] == "FLYNC-VAR-MAJ-FMT-438"
    assert finding["ctx"]["line"] == _line_of(metadata, "sunroof")


def test_dead_condition_is_a_warning(workspace_copy):
    # the constraint of the feature model rules out the zonal architecture on the first generation
    with patch_yaml(workspace_copy / TOPOLOGY) as topology:
        _with_id(topology["connections"], "link_zone_rear")["variant_condition"] = "zonal and compute_generation == gen1"
    result = validate_variants(workspace_copy, variants=["domain_gen1"])
    assert result.passed
    assert _ids_of(result.variants["domain_gen1"]) == ["FLYNC-VAR-WARN-CONS-446"]


def test_broken_presence_condition_removes_the_ecu_and_is_reported(workspace_copy):
    with patch_yaml(workspace_copy / f"{REAR_ZONE}/ecu_metadata.flync.yaml") as metadata:
        metadata["variant_condition"] = "sunroof"
    ws = FLYNCWorkspace.safe_load_workspace("ws", workspace_copy, variant="zonal_gen2")
    assert "zone_controller_rear" not in [ecu.name for ecu in ws.flync_model.ecus]
    assert "FLYNC-VAR-MAJ-FMT-438" in _error_ids(ws)


@pytest.mark.parametrize("variant", [None, "domain_gen1", "zonal_gen2"])
def test_a_validated_ecu_is_the_same_in_every_variant(variant):
    # the presence condition decides about the ECU in a workspace; validated on its own, the ECU is loaded as written
    result = validate_external_node("ECU", FLYNC_VARIANTS_EXAMPLE / REAR_ZONE, variant=variant)
    assert result.errors == {}
    assert [p.name for p in result.model.ports] == ["zcr_p1"]


def test_a_validated_ecu_is_checked_against_the_enclosing_variability(workspace_copy):
    with patch_yaml(workspace_copy / f"{REAR_ZONE}/ecu_metadata.flync.yaml") as metadata:
        metadata["variant_condition"] = "sunroof"
    with patch_yaml(workspace_copy / f"{REAR_ZONE}/ports.flync.yaml") as ports:
        ports["ports"][0]["variant_condition"] = "domain or zonal"  # holds in every variant, so only its place is wrong

    result = validate_external_node("ECU", workspace_copy / REAR_ZONE)

    assert _ids_of(result) == ["FLYNC-VAR-MAJ-FMT-438", "FLYNC-VAR-MAJ-STRUCT-483"]


class TestIncrementalUpdate:
    """Partial updates of a variant workspace must match a full reload of the same variant."""

    @staticmethod
    def _snapshot(ws) -> dict:
        model = ws.flync_model
        return {
            "variant": model.active_variant.name if model is not None and model.active_variant else None,
            "ecus": [ecu.name for ecu in model.ecus] if model is not None else None,
            "ports": [p.name for p in model.get_all_ecu_ports()] if model is not None else None,
            "links": [c.id for c in model.topology.ethernet_topology.connections] if model is not None else None,
            "diags": {doc: sorted(str((e.get("ctx") or {}).get("error_id")) for e in errs) for doc, errs in ws.documents_diags.items() if errs},
        }

    def _assert_matches_full_reload(self, ws, root, variant):
        full = FLYNCWorkspace.safe_load_workspace("full", root, variant=variant)
        assert self._snapshot(ws) == self._snapshot(full)

    def test_edit_of_the_system_topology(self, workspace_copy):
        ws = FLYNCWorkspace.safe_load_workspace("ws", workspace_copy, variant="zonal_gen2")
        topology = workspace_copy / TOPOLOGY
        with patch_yaml(topology) as data:
            _with_id(data["connections"], "link_body_domain")["variant_condition"] = "domain and sunroof"
        ws.update_document(topology)
        # the broken condition is reported, and treated as false like the one it replaced
        assert _error_ids(ws) == ["FLYNC-VAR-MAJ-FMT-438"]
        assert self._snapshot(ws)["links"] == ZONAL_LINKS
        self._assert_matches_full_reload(ws, workspace_copy, "zonal_gen2")

        with patch_yaml(topology) as data:
            _with_id(data["connections"], "link_body_domain")["variant_condition"] = "domain"
            _with_id(data["connections"], "link_zone_rear")["variant_condition"] = "zonal and compute_generation == gen1"
        ws.update_document(topology)
        # an entry whose condition no longer holds leaves the active variant
        assert self._snapshot(ws)["links"] == ["link_zone_front", "DoorSegment"]
        assert "FLYNC-VAR-MAJ-FMT-438" not in _error_ids(ws)

    def test_edit_of_an_inactive_document_only_refreshes_it(self, workspace_copy):
        ws = FLYNCWorkspace.safe_load_workspace("ws", workspace_copy, variant="domain_gen1")
        model = ws.flync_model
        ports = workspace_copy / f"{REAR_ZONE}/ports.flync.yaml"
        with patch_yaml(ports) as data:
            data["ports"][0]["name"] = "zcr_p9"
        assert ws.update_document(ports) == [f"{REAR_ZONE}/ports.flync.yaml"]
        assert ws.flync_model is model
        assert "zcr_p9" in ws.documents[f"{REAR_ZONE}/ports.flync.yaml"].text

    def test_edit_of_a_presence_condition_adds_and_removes_the_ecu(self, workspace_copy):
        ws = FLYNCWorkspace.safe_load_workspace("ws", workspace_copy, variant="domain_gen1")
        metadata = workspace_copy / f"{REAR_ZONE}/ecu_metadata.flync.yaml"
        with patch_yaml(metadata) as data:
            data["variant_condition"] = "domain"
        ws.update_document(metadata)
        assert "zone_controller_rear" in [ecu.name for ecu in ws.flync_model.ecus]
        self._assert_matches_full_reload(ws, workspace_copy, "domain_gen1")

        with patch_yaml(metadata) as data:
            data["variant_condition"] = "zonal"
        ws.update_document(metadata)
        assert "zone_controller_rear" not in [ecu.name for ecu in ws.flync_model.ecus]
        self._assert_matches_full_reload(ws, workspace_copy, "domain_gen1")

    def test_edit_of_the_variability_re_resolves(self, workspace_copy):
        ws = FLYNCWorkspace.safe_load_workspace("ws", workspace_copy)
        feature_model = workspace_copy / "variability/feature_model.flync.yaml"
        with patch_yaml(feature_model) as data:
            data["default_variant"] = "zonal_gen2"
        ws.update_document(feature_model)
        assert ws.flync_model.active_variant.name == "zonal_gen2"
        self._assert_matches_full_reload(ws, workspace_copy, None)


def test_select_variant_reuses_the_parsed_documents(example):
    documents = dict(example.documents)
    example.select_variant("zonal_gen2")
    assert all(example.documents[uri] is doc for uri, doc in documents.items())
    assert example.flync_model.active_variant.value("architecture") == "zonal"


def test_example_feature_model_is_documented():
    """The example is the reference for the docs: every feature carries a description."""
    data = yaml.safe_load((FLYNC_VARIANTS_EXAMPLE / "variability/feature_model.flync.yaml").read_text())
    assert all("description" in feature for feature in data["features"])
