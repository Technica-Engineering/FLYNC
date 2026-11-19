"""
System tests for the variability examples under ``examples/flync_4_variability``.

Every example is a complete workspace that validates for each of its declared variants. The per-example tests pin
the differences between the variants that each example is meant to show, so the examples cannot silently stop
demonstrating them.
"""

import pytest

from flync.sdk.helpers.validation_helpers import validate_variants
from flync.sdk.helpers.variant_helpers import workspace_variation_points
from flync.sdk.workspace.flync_workspace import FLYNCWorkspace
from tests.example_paths import FLYNC_VARIABILITY_EXAMPLES

EXAMPLES = sorted(path.name for path in FLYNC_VARIABILITY_EXAMPLES.iterdir() if path.is_dir())


def _load(example: str, variant: str):
    ws = FLYNCWorkspace.safe_load_workspace(example, FLYNC_VARIABILITY_EXAMPLES / example, variant=variant)
    assert ws.load_errors == [], ws.load_errors
    assert ws.flync_model is not None
    return ws.flync_model


def _interfaces(model, ecu: str, controller: str) -> list[str]:
    ctrl = next(c for c in model.get_ecu_by_name(ecu).controllers if c.name == controller)
    return [iface.name for iface in ctrl.ethernet_interfaces]


def _links(model) -> list[str]:
    return [connection.id for connection in model.topology.ethernet_topology.connections]


def test_the_supported_use_cases_are_present():
    assert EXAMPLES == ["01_optional_component", "02_architecture_alternatives"]


@pytest.mark.parametrize("example", EXAMPLES)
def test_every_variant_is_valid_without_findings(example):
    result = validate_variants(FLYNC_VARIABILITY_EXAMPLES / example)

    assert result.variants, "the example declares no variant"
    assert result.passed, {name: variant.state for name, variant in result.variants.items()}
    for name, variant in result.variants.items():
        assert variant.errors == {}, (name, variant.errors)


@pytest.mark.parametrize("example", EXAMPLES)
def test_variation_points_are_ecu_presence_or_system_topology_entries(example):
    """An ECU varies only in its presence; everything else that varies is an entry of the system topology."""

    points = workspace_variation_points(FLYNC_VARIABILITY_EXAMPLES / example)

    assert points
    for point in points:
        ecu_presence = point.location == () and point.document.startswith("ecus/") and point.document.endswith("/ecu_metadata.flync.yaml")
        topology_entry = point.document.startswith("topology/") and bool(point.location) and isinstance(point.location[-1], int)
        assert ecu_presence or topology_entry, point.describe()


class TestOptionalComponent:
    EXAMPLE = "01_optional_component"

    def test_base_has_the_adas_controller_without_the_rear_camera_port(self):
        ws = FLYNCWorkspace.safe_load_workspace(self.EXAMPLE, FLYNC_VARIABILITY_EXAMPLES / self.EXAMPLE, variant="base")
        model = ws.flync_model

        assert ws.load_errors == []
        assert [ecu.name for ecu in model.ecus] == ["adas_controller", "front_camera"]
        assert {uri.split("/")[1] for uri in ws.inactive_documents() if uri.startswith("ecus/")} == {"adas_controller_pa", "rear_camera"}
        assert [port.name for port in model.get_ecu_by_name("adas_controller").ports] == ["adas_p1"]
        assert _interfaces(model, "adas_controller", "adas_soc") == ["adas_eth0"]
        assert _links(model) == ["link_front_camera"]

    def test_park_assist_swaps_the_adas_controller_and_adds_the_rear_camera(self):
        model = _load(self.EXAMPLE, "park_assist")

        assert [ecu.name for ecu in model.ecus] == ["adas_controller_pa", "front_camera", "rear_camera"]
        assert [port.name for port in model.get_ecu_by_name("adas_controller_pa").ports] == ["adas_p1", "adas_p2"]
        assert _interfaces(model, "adas_controller_pa", "adas_soc") == ["adas_eth0", "adas_eth1"]
        assert _links(model) == ["link_front_camera", "link_rear_camera"]


class TestArchitectureAlternatives:
    EXAMPLE = "02_architecture_alternatives"

    @staticmethod
    def _facts(model) -> dict:
        (compute,) = [ecu for ecu in model.ecus if ecu.name.startswith("central_compute")]
        segment = next(c for c in model.topology.ethernet_topology.connections if c.id == "DoorSegment")
        return {
            "ecus": [ecu.name for ecu in model.ecus],
            "compute": compute.name,
            "product_id": compute.ecu_metadata.hardware.product_id,
            "compute_ports": [port.name for port in compute.ports],
            "compute_controllers": [c.name for c in compute.controllers],
            "switch_ports": [port.name for port in compute.switches[0].switch_config.ports],
            "links": _links(model),
            "door_segment": [node.ecu_port_name for node in segment.nodes],
        }

    def test_domain_gen1(self):
        facts = self._facts(_load(self.EXAMPLE, "domain_gen1"))

        assert facts["ecus"] == [
            "body_domain_controller",
            "central_compute_gen1",
            "chassis_domain_controller",
            "door_module_left",
            "door_module_right",
        ]
        assert facts["compute"] == "central_compute_gen1"
        assert facts["product_id"] == "CC-G1"
        assert facts["compute_ports"] == ["cc_p1", "cc_p2"]
        assert facts["compute_controllers"] == ["cc_main"]
        assert facts["switch_ports"] == ["cc_sw_p0", "cc_sw_p1", "cc_sw_p2"]
        assert facts["links"] == ["link_body_domain", "link_chassis_domain", "DoorSegment"]
        assert facts["door_segment"] == ["bdc_p2", "dml_p1", "dmr_p1"]

    def test_domain_gen2_only_changes_the_compute_ecu(self):
        gen1 = self._facts(_load(self.EXAMPLE, "domain_gen1"))
        gen2 = self._facts(_load(self.EXAMPLE, "domain_gen2"))

        assert gen2["compute"] == "central_compute_gen2"
        assert gen2["product_id"] == "CC-G2"
        assert gen2["compute_controllers"] == ["cc_main", "cc_safety"]
        assert gen2["switch_ports"] == ["cc_sw_p0", "cc_sw_p1", "cc_sw_p2", "cc_sw_p3"]
        # the same outside: the links of the system topology fit both generations
        assert gen2["compute_ports"] == gen1["compute_ports"]
        assert gen2["links"] == gen1["links"]
        assert gen2["door_segment"] == gen1["door_segment"]
        assert [name.replace("gen2", "gen1") for name in gen2["ecus"]] == gen1["ecus"]

    def test_zonal_gen2(self):
        facts = self._facts(_load(self.EXAMPLE, "zonal_gen2"))

        assert facts["ecus"] == ["central_compute_gen2", "door_module_left", "door_module_right", "zone_controller_front", "zone_controller_rear"]
        assert facts["links"] == ["link_zone_front", "link_zone_rear", "DoorSegment"]
        # the door modules are the same ECUs; only the coordinator of their segment changes
        assert facts["door_segment"] == ["zcf_p2", "dml_p1", "dmr_p1"]
