"""Unit tests for the variability model: the feature model rules, the variant rules, and the variant contexts."""

import copy

import pytest
from pydantic import ValidationError

from flync.core.utils.exceptions_handling import validate_with_policy
from flync.model.flync_4_variability import FeatureType, Variability
from tests.error_assertions import assert_no_findings, assert_single_error, assert_single_warning

FEATURES = [
    {"name": "architecture", "values": ["domain", "zonal"]},
    {"name": "market", "values": ["eu", "us", "cn"], "default": "eu"},
    {"name": "model_year", "values": [2026, 2027], "ordered": True, "default": 2026},
    {"name": "trailer_hitch"},
    {"name": "level3_adas"},
    {"name": "coding", "default": True},
]

VARIANTS = [
    {"name": "domain_eu", "features": {"architecture": "domain"}},
    {"name": "zonal_us", "extends": "domain_eu", "features": {"architecture": "zonal", "market": "us", "level3_adas": True}},
    {"name": "zonal_cn", "extends": "zonal_us", "features": {"market": "cn", "level3_adas": False, "model_year": 2027}},
]


def variability(features=None, variants=None, **feature_model) -> dict:
    """A valid variability model, optionally with parts replaced."""

    return {
        "feature_model": {"features": copy.deepcopy(FEATURES if features is None else features), **feature_model},
        "variants": copy.deepcopy(VARIANTS if variants is None else variants),
    }


def with_variant(variant: str, **changes) -> list:
    """The default variants with one of them changed."""

    variants = copy.deepcopy(VARIANTS)
    next(v for v in variants if v["name"] == variant).update(changes)
    return variants


def with_feature(feature: str, **changes) -> list:
    """The default features with one of them changed."""

    features = copy.deepcopy(FEATURES)
    next(f for f in features if f["name"] == feature).update(changes)
    return features


def test_valid_model_has_no_findings():
    data = variability(
        constraints=[{"expression": "not (market == cn and trailer_hitch)", "description": "not offered in CN"}],
        qualifiers={"zonal": "architecture == zonal", "late": "model_year >= 2027 and zonal"},
        default_variant="domain_eu",
    )
    assert_no_findings(validate_with_policy(Variability, data, "variability"))


@pytest.mark.parametrize(
    "data, error_id, fragment",
    [
        pytest.param(
            variability(with_feature("trailer_hitch", name="2hitch")), "FLYNC-VAR-MAJ-FMT-470", "not a valid feature name", id="feature-name"
        ),
        pytest.param(variability(constraints=[{"expression": "zonal =="}]), "FLYNC-VAR-MAJ-FMT-362", "invalid syntax", id="constraint-syntax"),
        pytest.param(variability(with_feature("market", values=["eu", ""])), "FLYNC-VAR-MAJ-VAL-363", "empty value", id="empty-value"),
        pytest.param(
            variability(with_feature("market", values=["eu", "eu"])), "FLYNC-CMN-MAJ-UNIQ-009", "values of feature 'market'", id="duplicate-values"
        ),
        pytest.param(variability(with_feature("trailer_hitch", ordered=True)), "FLYNC-VAR-MAJ-CONS-364", "declared 'ordered'", id="ordered-boolean"),
        pytest.param(variability(with_feature("trailer_hitch", default="yes")), "FLYNC-VAR-MAJ-VAL-366", "use true or false", id="boolean-default"),
        pytest.param(
            variability(with_feature("market", type="boolean")),
            "FLYNC-VAR-MAJ-CONS-453",
            "declared 'type: boolean' but has values",
            id="boolean-with-values",
        ),
        pytest.param(
            variability(with_feature("trailer_hitch", type="enumeration")),
            "FLYNC-VAR-MAJ-REQ-454",
            "declared 'type: enumeration' but has no values",
            id="enumeration-without-values",
        ),
        pytest.param(
            variability(with_feature("trailer_hitch", type="integer")), None, "Input should be 'boolean' or 'enumeration'", id="unknown-type"
        ),
        pytest.param(variability(with_feature("trailer_hitch", children=[{"name": "x"}])), None, "Extra inputs", id="no-feature-trees"),
        pytest.param(variability(with_feature("trailer_hitch", implies={"coding": True})), None, "Extra inputs", id="no-implies"),
        pytest.param(variability(with_feature("trailer_hitch", requires="coding")), None, "Extra inputs", id="no-requires"),
        pytest.param(variability(with_feature("coding", binding_time="deployment")), None, "Extra inputs", id="no-binding-time"),
        pytest.param(variability(with_feature("coding", trace_links=["REQ-1"])), None, "Extra inputs", id="no-trace-links"),
        pytest.param(variability(derivations=[{"when": "coding", "assign": {"trailer_hitch": True}}]), None, "Extra inputs", id="no-derivations"),
        pytest.param(variability() | {"feature_models": []}, None, "Extra inputs", id="no-feature-modules"),
        pytest.param(
            variability(variants=with_variant("domain_eu", attributes={"ordering_code": "A"})), None, "Extra inputs", id="no-variant-attributes"
        ),
        pytest.param(variability(with_feature("market", default="de")), "FLYNC-VAR-MAJ-VAL-471", "is not one of its values", id="enum-default"),
        pytest.param(variability(qualifiers={"2x": "trailer_hitch"}), "FLYNC-VAR-MAJ-FMT-472", "not a valid qualifier name", id="qualifier-name"),
        pytest.param(variability(qualifiers={"market": "trailer_hitch"}), "FLYNC-VAR-MAJ-UNIQ-473", "same name as a feature", id="qualifier-clash"),
        pytest.param(
            variability(constraints=[{"expression": "sunroof"}]), "FLYNC-VAR-MAJ-REF-477", "unknown feature or qualifier", id="unknown-name"
        ),
        pytest.param(variability(qualifiers={"a": "b", "b": "a"}), "FLYNC-VAR-MAJ-CONS-474", "Qualifier cycle", id="qualifier-cycle"),
        pytest.param(variability(variants=[]), "FLYNC-VAR-MAJ-REQ-475", "declares no variants", id="no-variants"),
        pytest.param(variability(default_variant="nobody"), "FLYNC-VAR-MAJ-REF-476", "default_variant 'nobody'", id="default-variant"),
        pytest.param(
            variability(qualifiers={"special": "variant == domain_eu"}), "FLYNC-VAR-MAJ-REF-477", "unknown feature 'variant'", id="no-variant-symbol"
        ),
        pytest.param(
            variability(variants=with_variant("zonal_us", extends="nobody")), "FLYNC-VAR-MAJ-REF-478", "extends unknown", id="extends-unknown"
        ),
        pytest.param(
            variability(variants=with_variant("domain_eu", extends="zonal_cn")), "FLYNC-VAR-MAJ-CONS-479", "inheritance cycle", id="extends-cycle"
        ),
        pytest.param(
            variability(variants=with_variant("domain_eu", features={"architecture": "domain", "sunroof": True})),
            "FLYNC-VAR-MAJ-REF-480",
            "unknown feature 'sunroof'",
            id="unknown-feature",
        ),
        pytest.param(
            variability(variants=with_variant("domain_eu", features={"architecture": "hybrid"})),
            "FLYNC-VAR-MAJ-VAL-481",
            "assigns 'hybrid' to feature 'architecture'",
            id="bad-value",
        ),
        pytest.param(
            variability(variants=with_variant("domain_eu", features={"architecture": "domain", "trailer_hitch": "yes"})),
            "FLYNC-VAR-MAJ-VAL-481",
            "allowed: true or false",
            id="bad-boolean",
        ),
        pytest.param(
            variability(variants=with_variant("domain_eu", features={})),
            "FLYNC-VAR-MAJ-REQ-482",
            "does not assign enumerated feature",
            id="unassigned",
        ),
        pytest.param(
            variability(constraints=[{"expression": "market != cn", "description": "no CN"}]),
            "FLYNC-VAR-MAJ-CONS-436",
            "violates constraint 'market != cn' (no CN)",
            id="constraint-violated",
        ),
    ],
)
def test_rejects(data, error_id, fragment):
    with pytest.raises(ValidationError) as exc_info:
        Variability.model_validate(data)
    assert_single_error(exc_info, error_id, fragment)


def test_warns_about_identical_variants():
    variants = VARIANTS + [{"name": "copy", "features": {"architecture": "domain"}}]
    assert_single_warning(
        validate_with_policy(Variability, variability(variants=variants), "variability"), "FLYNC-VAR-WARN-UNIQ-437", "'domain_eu' and 'copy'"
    )


def test_context_flattens_extends_and_applies_defaults():
    model = Variability.model_validate(variability())
    context = model.context("zonal_cn")

    # inherited from zonal_us (architecture), overridden here (market, level3_adas), defaulted (coding), unassigned boolean (trailer_hitch)
    assert dict(context.assignment) == {
        "architecture": "zonal",
        "market": "cn",
        "model_year": "2027",
        "trailer_hitch": False,
        "level3_adas": False,
        "coding": True,
    }
    assert context.is_enabled("coding")
    assert not context.is_enabled("trailer_hitch")
    assert context.value("market") == "cn"
    assert context.evaluate("model_year > 2026 and market in [cn, us]")
    assert dict(context.sources) == {
        "architecture": "inherited",
        "market": "assigned",
        "model_year": "assigned",
        "trailer_hitch": "default",
        "level3_adas": "assigned",
        "coding": "default",
    }


def test_context_holds_treats_broken_conditions_as_false():
    context = Variability.model_validate(variability()).context("domain_eu")
    assert context.holds("sunroof") is False
    assert context.holds("market ==") is False
    with pytest.raises(KeyError):
        context.is_enabled("market")


def test_feature_type_is_explicit_or_inferred():
    features = with_feature("market", type="enumeration") + [{"name": "sunroof", "type": "boolean"}]
    model = Variability.model_validate(variability(features))
    feature_types = {feature.name: feature.feature_type for feature in model.feature_model.features}
    assert feature_types["market"] is FeatureType.ENUMERATION
    assert feature_types["sunroof"] is FeatureType.BOOLEAN
    assert feature_types["trailer_hitch"] is FeatureType.BOOLEAN  # inferred: no values
    assert feature_types["architecture"] is FeatureType.ENUMERATION  # inferred: values


def test_feature_attributes_reach_the_context():
    features = with_feature("trailer_hitch", attributes={"option_code": "TH01", "certified": True, "release": 3, "weight_kg": 12.5})
    context = Variability.model_validate(variability(features)).context("domain_eu")
    assert dict(context.feature_attributes) == {"trailer_hitch": {"option_code": "TH01", "certified": True, "release": 3, "weight_kg": 12.5}}
    attributes = context.feature_attributes["trailer_hitch"]
    assert [type(attributes[key]) for key in ("certified", "release", "weight_kg", "option_code")] == [bool, int, float, str]


def test_is_dead():
    model = Variability.model_validate(variability())
    assert model.is_dead("trailer_hitch")
    assert model.is_dead("architecture == zonal and market == eu")
    assert not model.is_dead("level3_adas")
    with pytest.raises(KeyError):
        model.context("nobody")
