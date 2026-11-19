"""Unit tests for configuration completion (assigned, inherited, default) and the variant analyses."""

import copy

import pytest

from flync.core.utils.exceptions_handling import validate_with_policy
from flync.model.flync_4_variability import FeatureModel, ValueSource, Variability, configure
from flync.model.flync_4_variability.analysis import collect_variation_points, compare_variants, trace_features
from tests.error_assertions import assert_no_findings

FEATURES = [
    {"name": "park_assist", "category": "product", "attributes": {"option_code": "PA01"}},
    {"name": "architecture", "category": "solution", "values": ["domain", "zonal"]},
    {"name": "generation", "category": "element", "values": ["gen1", "gen2"], "ordered": True, "default": "gen1"},
    {"name": "heated_mirrors", "default": True},
]

VARIANTS = [
    {"name": "base", "features": {"architecture": "domain"}},
    {"name": "zonal", "features": {"architecture": "zonal", "generation": "gen2", "park_assist": True}},
    {"name": "domain_gen2", "extends": "base", "features": {"generation": "gen2"}},
]


def model(features=None, variants=None, **feature_model) -> dict:
    """A valid variability model with a boolean option and two architecture alternatives."""

    return {
        "feature_model": {"features": copy.deepcopy(FEATURES if features is None else features), **feature_model},
        "variants": copy.deepcopy(VARIANTS if variants is None else variants),
    }


# region configuration


def test_valid_model_has_no_findings():
    data = model(
        constraints=[{"expression": "architecture != zonal or generation >= gen2"}],
        qualifiers={"zonal_arch": "architecture == zonal", "gen2": "generation == gen2"},
        default_variant="base",
    )
    assert_no_findings(validate_with_policy(Variability, data, "variability"))


def test_undecided_features_take_their_default():
    context = Variability.model_validate(model()).context("base")
    assert dict(context.assignment) == {"park_assist": False, "architecture": "domain", "generation": "gen1", "heated_mirrors": True}
    assert dict(context.sources) == {
        "park_assist": ValueSource.DEFAULT,
        "architecture": ValueSource.ASSIGNED,
        "generation": ValueSource.DEFAULT,
        "heated_mirrors": ValueSource.DEFAULT,
    }


def test_inherited_decisions_are_marked_and_own_decisions_override():
    context = Variability.model_validate(model()).context("domain_gen2")
    assert (context.value("architecture"), context.source("architecture")) == ("domain", ValueSource.INHERITED)
    assert (context.value("generation"), context.source("generation")) == ("gen2", ValueSource.ASSIGNED)


def test_inheritance_reaches_through_a_chain_nearer_variants_winning():
    variants = copy.deepcopy(VARIANTS) + [{"name": "far", "extends": "domain_gen2", "features": {"heated_mirrors": False}}]
    variants[0]["features"]["park_assist"] = True
    context = Variability.model_validate(model(variants=variants)).context("far")
    assert dict(context.assignment) == {"park_assist": True, "architecture": "domain", "generation": "gen2", "heated_mirrors": False}
    assert context.source("park_assist") is ValueSource.INHERITED


def test_configure_works_on_a_feature_model_directly():
    feature_model = FeatureModel.model_validate({"features": copy.deepcopy(FEATURES)})
    configuration = configure(feature_model, {"park_assist": True, "generation": 7}, {"architecture": "zonal", "park_assist": False})
    assert configuration.values == {"park_assist": True, "architecture": "zonal", "generation": "7", "heated_mirrors": True}
    assert configuration.sources["architecture"] is ValueSource.INHERITED
    assert configuration.open_decisions == []


def test_configure_records_enumerated_features_without_value_or_default():
    feature_model = FeatureModel.model_validate({"features": copy.deepcopy(FEATURES)})
    configuration = configure(feature_model, {"architecture": True})  # a boolean does not fit an enumerated feature
    assert configuration.open_decisions == ["architecture"]
    assert "architecture" not in configuration.values


@pytest.mark.parametrize(
    "condition, holds_in",
    [
        pytest.param("generation >= gen2", {"zonal", "domain_gen2"}, id="ordered"),
        pytest.param("architecture in [zonal]", {"zonal"}, id="membership"),
        pytest.param("park_assist or generation == gen2", {"zonal", "domain_gen2"}, id="boolean-or-enumeration"),
    ],
)
def test_conditions_follow_the_completed_configuration(condition, holds_in):
    variability = Variability.model_validate(model())
    assert {context.name for context in variability.contexts() if context.evaluate(condition)} == holds_in


# endregion

# region analyses

DOCUMENTS = {
    "topology/ethernet_topology.flync.yaml": {"connections": [{"id": "link_1"}, {"id": "link_2", "variant_condition": "park_assist"}]},
    "ecus/zone_controller/ecu_metadata.flync.yaml": {"variant_condition": "zonal_arch", "author": "Dev"},
    "ecus/gateway_gen2/ecu_metadata.flync.yaml": {"variant_condition": "generation >= gen2", "author": "Dev"},
    "ecus/gateway_gen2/ports.flync.yaml": {"ports": [{"name": "p1"}]},
    "variability/feature_model.flync.yaml": {"features": []},
}


def test_collect_variation_points():
    points = collect_variation_points(DOCUMENTS)
    assert [(point.describe(), point.condition) for point in points] == [
        ("ecus/gateway_gen2/ecu_metadata.flync.yaml", "generation >= gen2"),
        ("ecus/zone_controller/ecu_metadata.flync.yaml", "zonal_arch"),
        ("topology/ethernet_topology.flync.yaml: connections[1] (link_2)", "park_assist"),
    ]


def test_trace_features_follows_qualifiers():
    variability = Variability.model_validate(model(qualifiers={"zonal_arch": "architecture == zonal"}))
    traced = trace_features(variability, collect_variation_points(DOCUMENTS))
    assert list(traced) == ["park_assist", "architecture", "generation", "heated_mirrors"]
    assert [point.document for point in traced["architecture"]] == ["ecus/zone_controller/ecu_metadata.flync.yaml"]
    assert [point.location for point in traced["architecture"]] == [()]
    assert [point.label for point in traced["park_assist"]] == ["link_2"]
    assert [point.document for point in traced["generation"]] == ["ecus/gateway_gen2/ecu_metadata.flync.yaml"]
    assert traced["heated_mirrors"] == []


def test_compare_variants():
    variability = Variability.model_validate(model(qualifiers={"zonal_arch": "architecture == zonal"}))
    comparison = compare_variants(variability, collect_variation_points(DOCUMENTS), "base", "zonal")
    assert comparison.features == [("park_assist", False, True), ("architecture", "domain", "zonal"), ("generation", "gen1", "gen2")]
    assert [(point.describe(), left, right) for point, left, right in comparison.elements] == [
        ("ecus/gateway_gen2/ecu_metadata.flync.yaml", False, True),
        ("ecus/zone_controller/ecu_metadata.flync.yaml", False, True),
        ("topology/ethernet_topology.flync.yaml: connections[1] (link_2)", False, True),
    ]
    assert not comparison.identical
    assert compare_variants(variability, [], "base", "base").identical


# endregion
