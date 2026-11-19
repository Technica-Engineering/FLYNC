"""Tests for the variant management CLI: ``flync variants``, ``flync validate`` on a 150 % workspace, and ``--variant``."""

import json
import shutil

import pytest
from typer.testing import CliRunner

from flync.sdk.workspace.flync_workspace import FLYNCWorkspace
from flync_cli.commands import info, validate, variants
from flync_cli.main import app
from flync_cli.utils import error_table
from tests.cli_tests.cli_assertions import assert_cli_error, assert_cli_ok
from tests.cli_tests.rich_output import capture
from tests.example_paths import FLYNC_EXAMPLE, FLYNC_VARIANTS_EXAMPLE
from tests.system_test.sdk.helper import patch_yaml

runner = CliRunner()
EXAMPLE = str(FLYNC_VARIANTS_EXAMPLE)
VARIANTS = ["domain_gen1", "domain_gen2", "zonal_gen2"]
TOPOLOGY = "topology/ethernet_topology.flync.yaml"


@pytest.fixture
def workspace_copy(tmp_path):
    root = tmp_path / "ws"
    shutil.copytree(FLYNC_VARIANTS_EXAMPLE, root)
    return root


class TestValidate:
    def test_validates_every_variant_by_default(self):
        with capture(validate, error_table) as out:
            result = runner.invoke(app, ["validate", EXAMPLE])
        assert_cli_ok(result)
        summary = out.tables[0]
        assert summary[0] == ["Variant", "State", "Errors", "Warnings"]
        assert summary[1:] == [[name, "VALID", "0", "0"] for name in VARIANTS]

    def test_validates_one_variant(self):
        with capture(validate, error_table) as out:
            result = runner.invoke(app, ["validate", EXAMPLE, "--variant", "zonal_gen2"])
        assert_cli_ok(result)
        assert "Resolved for variant zonal_gen2" in out.text

    def test_reports_each_finding_with_its_variants(self, workspace_copy):
        # the zonal coordinator of the door segment without its condition: the domain variants have no front zone controller
        with patch_yaml(workspace_copy / TOPOLOGY) as topology:
            del next(c for c in topology["connections"] if c["id"] == "DoorSegment")["nodes"][1]["variant_condition"]
        with capture(validate, error_table) as out:
            result = runner.invoke(app, ["validate", str(workspace_copy)])
        assert result.exit_code == 1
        failed = [row for row in out.tables[0][1:] if row[2] != "0"]
        assert [row[0] for row in failed] == ["domain_gen1", "domain_gen2"]
        rows = [row for table in out.tables[1:] for row in table if "zcf_p2" in " ".join(row)]
        assert rows
        assert all("domain_gen1, domain_gen2" in " ".join(row) for row in rows)

    def test_variant_and_all_variants_exclude_each_other(self):
        result = runner.invoke(app, ["validate", EXAMPLE, "--variant", "zonal_gen2", "--all-variants"])
        assert_cli_error(result, 1, "cannot be combined")

    def test_unknown_variant_fails(self):
        result = runner.invoke(app, ["validate", EXAMPLE, "--variant", "nobody"])
        assert_cli_error(result, 1, "INVALID")


class TestVariantsCommands:
    def test_list(self):
        with capture(variants) as out:
            result = runner.invoke(app, ["variants", "list", EXAMPLE])
        assert_cli_ok(result)
        header, *rows = out.rows
        assert header == ["Variant", "Extends", "Description"]
        assert [row[:2] for row in rows] == [["domain_gen1 (default)", "-"], ["domain_gen2", "domain_gen1"], ["zonal_gen2", "-"]]
        assert "3 of 3 variants shown." in out.plain

    def test_list_filters_and_adds_feature_columns(self):
        with capture(variants) as out:
            result = runner.invoke(app, ["variants", "list", EXAMPLE, "--where", "compute_generation >= gen2", "-f", "architecture"])
        assert_cli_ok(result)
        header, *rows = out.rows
        assert header == ["Variant", "Extends", "Description", "architecture"]
        assert [[row[0], row[3]] for row in rows] == [["domain_gen2", "domain"], ["zonal_gen2", "zonal"]]
        assert "2 of 2 matching variants shown (3 declared)." in out.plain

    def test_list_limit_counts_every_match(self):
        with capture(variants) as out:
            result = runner.invoke(app, ["variants", "list", EXAMPLE, "--where", "compute_generation >= gen2", "--limit", "1"])
        assert_cli_ok(result)
        assert [row[0] for row in out.rows[1:]] == ["domain_gen2"]
        assert "1 of 2 matching variants shown (3 declared); use --limit to see more" in out.plain

    def test_list_without_matches(self):
        with capture(variants) as out:
            result = runner.invoke(app, ["variants", "list", EXAMPLE, "--where", "architecture == zonal and compute_generation == gen1"])
        assert_cli_ok(result)
        assert out.tables == []
        assert "No variant matches the condition (3 declared)." in out.plain

    @pytest.mark.parametrize(
        "args, message",
        [
            pytest.param(["--where", "sunroof"], "unknown feature or qualifier 'sunroof'", id="unknown-name"),
            pytest.param(["--where", "architecture =="], "invalid syntax", id="syntax"),
            pytest.param(["--feature", "sunroof"], "Error: Unknown feature 'sunroof'.", id="feature"),
            pytest.param(["--feature", "sunroof"], "Declared features: architecture, compute_generation.", id="feature-hint"),
            pytest.param(["--limit", "-1"], "", id="negative-limit"),
        ],
    )
    def test_list_rejects_bad_options(self, args, message):
        with capture(variants) as out:
            result = runner.invoke(app, ["variants", "list", EXAMPLE, *args])
        assert result.exit_code != 0
        assert message in out.plain

    def test_list_scales_to_many_variants(self, workspace_copy):
        folder = workspace_copy / "variability/variants"
        for index in range(120):
            generation = "gen1" if index % 2 else "gen2"
            (folder / f"bulk_{index:03d}.flync.yaml").write_text(
                f"features:\n  architecture: domain\n  compute_generation: {generation}\n", encoding="utf-8"
            )
        with capture(variants) as out:
            result = runner.invoke(app, ["variants", "list", str(workspace_copy)])
        assert_cli_ok(result)
        assert len(out.rows) - 1 == 50
        assert "50 of 123 variants shown; use --limit to see more, or --where to narrow the list." in out.plain

        with capture(variants) as out:
            result = runner.invoke(app, ["variants", "list", str(workspace_copy), "--limit", "0"])
        assert len(out.rows) - 1 == 123

        with capture(variants) as out:
            result = runner.invoke(app, ["variants", "show", "nobody", str(workspace_copy)])
        assert result.exit_code == 1
        assert "... (123 in total; see 'flync variants list')" in out.plain
        assert "bulk_119" not in out.plain

    def test_show(self):
        with capture(variants) as out:
            result = runner.invoke(app, ["variants", "show", "domain_gen2", EXAMPLE])
        assert_cli_ok(result)
        assert "extends domain_gen1" in out.text
        assert "active qualifiers: domain, gen2" in out.text
        assert out.rows[1:] == [["architecture", "domain", "inherited", "enumeration"], ["compute_generation", "gen2", "assigned", "enumeration"]]

    def test_show_marks_defaults(self, workspace_copy):
        (workspace_copy / "variability/variants/domain_default.flync.yaml").write_text("features:\n  architecture: domain\n", encoding="utf-8")
        with capture(variants) as out:
            result = runner.invoke(app, ["variants", "show", "domain_default", str(workspace_copy)])
        assert_cli_ok(result)
        assert ["compute_generation", "gen1", "default", "enumeration"] in out.rows

    def test_show_unknown_variant(self):
        with capture(variants) as out:
            result = runner.invoke(app, ["variants", "show", "nobody", EXAMPLE])
        assert result.exit_code == 1
        assert "Unknown variant 'nobody'" in out.text

    def test_check(self):
        with capture(variants, error_table) as out:
            result = runner.invoke(app, ["variants", "check", EXAMPLE])
        assert_cli_ok(result)
        assert "3 variants, 2 features" in out.text

    def test_check_reports_invalid_conditions(self, workspace_copy):
        with patch_yaml(workspace_copy / TOPOLOGY) as topology:
            topology["connections"][0]["variant_condition"] = "sunroof"
        with capture(variants, error_table) as out:
            result = runner.invoke(app, ["variants", "check", str(workspace_copy)])
        assert result.exit_code == 1
        assert "FLYNC-VAR-MAJ-FMT-438" in out.text

    def test_check_reports_variation_points_inside_an_ecu(self, workspace_copy):
        with patch_yaml(workspace_copy / "ecus/central_compute_gen2/ports.flync.yaml") as ports:
            ports["ports"][1]["variant_condition"] = "zonal"
        with capture(variants, error_table) as out:
            result = runner.invoke(app, ["variants", "check", str(workspace_copy)])
        assert result.exit_code == 1
        assert "FLYNC-VAR-MAJ-STRUCT-483" in out.text

    def test_export(self, tmp_path):
        target = tmp_path / "zonal_gen2"
        with capture(variants, error_table):
            result = runner.invoke(app, ["variants", "export", "zonal_gen2", "--out", str(target), EXAMPLE])
        assert_cli_ok(result)
        exported = FLYNCWorkspace.load_workspace("exported", target)
        assert [ecu.name for ecu in exported.flync_model.ecus][-1] == "zone_controller_rear"
        assert exported.variability is None

    def test_export_refuses_the_variant_workspace(self, workspace_copy):
        with capture(variants, error_table) as out:
            result = runner.invoke(app, ["variants", "export", "zonal_gen2", "--out", str(workspace_copy), str(workspace_copy)])
        assert result.exit_code == 1
        assert "holds a variant workspace" in out.text

    def test_tree_is_not_a_command(self):
        result = runner.invoke(app, ["variants", "tree", EXAMPLE])
        assert result.exit_code == 2

    def test_trace(self):
        with capture(variants) as out:
            result = runner.invoke(app, ["variants", "trace", EXAMPLE])
        assert_cli_ok(result)
        assert out.rows[0] == ["Feature", "Category", "Workspace elements"]
        rows = {row[0]: row for row in out.rows[1:] if row[0]}
        assert rows["architecture"][1] == "solution"
        # through the qualifier 'zonal': an ECU, a link, and a node of the door segment
        assert "ecus/zone_controller_front/ecu_metadata.flync.yaml" in out.text
        assert f"{TOPOLOGY}: connections[2] (link_zone_front)" in out.text
        assert f"{TOPOLOGY}: connections[4].nodes[1] (zcf_p2)" in out.text

    def test_trace_one_feature(self):
        with capture(variants) as out:
            result = runner.invoke(app, ["variants", "trace", "--feature", "compute_generation", EXAMPLE])
        assert_cli_ok(result)
        assert [row[0] for row in out.rows[1:] if row[0]] == ["compute_generation"]
        assert "ecus/central_compute_gen1/ecu_metadata.flync.yaml" in out.text
        assert "ecus/central_compute_gen2/ecu_metadata.flync.yaml" in out.text
        assert "zone_controller_front" not in out.text

    def test_trace_unknown_feature(self):
        with capture(variants) as out:
            result = runner.invoke(app, ["variants", "trace", "--feature", "sunroof", EXAMPLE])
        assert result.exit_code == 1
        assert "Unknown feature 'sunroof'" in out.text

    def test_diff(self):
        with capture(variants) as out:
            result = runner.invoke(app, ["variants", "diff", "domain_gen1", "domain_gen2", EXAMPLE])
        assert_cli_ok(result)
        features, elements = out.tables
        assert features[1:] == [["compute_generation", "gen1", "gen2"]]
        assert elements[1:] == [
            ["ecus/central_compute_gen1/ecu_metadata.flync.yaml", "present", "absent"],
            ["ecus/central_compute_gen2/ecu_metadata.flync.yaml", "absent", "present"],
        ]
        assert "1 features and 2 workspace elements differ" in out.plain

    def test_diff_lists_differing_elements(self):
        with capture(variants) as out:
            result = runner.invoke(app, ["variants", "diff", "domain_gen1", "zonal_gen2", EXAMPLE])
        assert_cli_ok(result)
        elements = out.tables[1]
        assert ["ecus/zone_controller_front/ecu_metadata.flync.yaml", "absent", "present"] in elements
        assert [f"{TOPOLOGY}: connections[0] (link_body_domain)", "present", "absent"] in elements
        assert [f"{TOPOLOGY}: connections[4].nodes[0] (bdc_p2)", "present", "absent"] in elements

    def test_diff_identical(self):
        with capture(variants) as out:
            result = runner.invoke(app, ["variants", "diff", "zonal_gen2", "zonal_gen2", EXAMPLE])
        assert_cli_ok(result)
        assert "resolve identically" in out.plain

    def test_diff_unknown_variant(self):
        with capture(variants) as out:
            result = runner.invoke(app, ["variants", "diff", "zonal_gen2", "nobody", EXAMPLE])
        assert result.exit_code == 1
        assert "Unknown variant 'nobody'" in out.text

    def test_workspace_without_variability(self):
        with capture(variants) as out:
            result = runner.invoke(app, ["variants", "list", str(FLYNC_EXAMPLE)])
        assert result.exit_code == 1
        assert "has no variability/ folder" in out.text


def test_info_resolves_the_selected_variant():
    with capture(info) as out:
        result = runner.invoke(app, ["info", "ecus", EXAMPLE, "-V", "zonal_gen2"])
    assert_cli_ok(result)
    assert [row[1] for row in out.rows[1:]] == [
        "central_compute_gen2",
        "door_module_left",
        "door_module_right",
        "zone_controller_front",
        "zone_controller_rear",
    ]


def _schema(folder, name: str) -> dict:
    return json.loads((folder / f"{name}.schema.json").read_text(encoding="utf-8"))


def test_schema_with_variation_points(tmp_path):
    result = runner.invoke(app, ["schema", str(tmp_path), "--variants"])
    assert_cli_ok(result)
    # the presence condition of an ECU, and the entries of the system topology
    for name in ("ECUMetadata", "EthernetPointToPointConnection", "EthernetMultidropConnection", "EthernetMultidropNode"):
        assert _schema(tmp_path, name)["properties"]["variant_condition"]["$ref"] == "VariantCondition.schema.json", name
    # nothing else, and no value variation
    for name in ("ECUPort", "EthernetTopology", "Feature", "ContainerPDU"):
        assert "variant_condition" not in _schema(tmp_path, name).get("properties", {}), name
    assert "anyOf" not in _schema(tmp_path, "ECUPort")["properties"]["name"]
    assert (tmp_path / "VariantCondition.schema.json").is_file()
