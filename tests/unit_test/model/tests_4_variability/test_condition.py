"""Unit tests for the variant condition language: parsing, evaluation, and the checks against a feature model."""

import pytest

from flync.model.flync_4_variability.condition import ConditionSyntaxError, FeatureSymbol, SymbolTable, compile_condition, is_identifier
from flync.model.flync_4_variability.context import VariantContext

SYMBOLS = SymbolTable(
    features={
        "trailer_hitch": FeatureSymbol("trailer_hitch"),
        "market": FeatureSymbol("market", ("eu", "us", "cn")),
        "model_year": FeatureSymbol("model_year", ("my26", "my27", "my28"), ordered=True),
        "body": FeatureSymbol("body", ("sedan", "suv")),
    },
    qualifiers={"premium": compile_condition("trailer_hitch and market != cn")},
)

SUV_EU = VariantContext(
    name="suv_eu",
    assignment={"trailer_hitch": True, "market": "eu", "model_year": "my27", "body": "suv"},
    symbols=SYMBOLS,
)


@pytest.mark.parametrize(
    "expression, expected",
    [
        pytest.param("trailer_hitch", True, id="boolean-feature"),
        pytest.param("not trailer_hitch", False, id="not"),
        pytest.param("trailer_hitch == true", True, id="boolean-equals-literal"),
        pytest.param("market == eu", True, id="equals"),
        pytest.param("market != eu", False, id="not-equals"),
        pytest.param('market == "eu"', True, id="quoted-value"),
        pytest.param("market in [us, cn]", False, id="in"),
        pytest.param("market not in [cn]", True, id="not-in"),
        pytest.param("model_year >= my27", True, id="ordered-boundary-included"),
        pytest.param("model_year > my27", False, id="ordered-boundary-excluded"),
        pytest.param("model_year < my28 and model_year >= my26", True, id="ordered-range"),
        pytest.param("premium", True, id="qualifier"),
        pytest.param("premium == false", False, id="qualifier-compared"),
        pytest.param("(market == us or body == suv) and not model_year > my27", True, id="nested"),
        pytest.param("false or trailer_hitch", True, id="literal"),
        pytest.param(True, True, id="yaml-boolean"),
    ],
)
def test_evaluate(expression, expected):
    assert compile_condition(expression).evaluate(SUV_EU) is expected


@pytest.mark.parametrize(
    "expression, reason",
    [
        pytest.param("", "empty", id="empty"),
        pytest.param("market ==", "invalid syntax", id="incomplete"),
        pytest.param("enabled()", "unsupported syntax", id="call"),
        pytest.param("market.eu", "unsupported syntax", id="attribute"),
        pytest.param("model_year < my27 < my28", "chained comparisons", id="chained"),
        pytest.param("market == [eu]", "unsupported value", id="list-without-in"),
        pytest.param("true == market", "left side of a comparison", id="literal-on-the-left"),
        pytest.param("market in eu", "non-empty list", id="in-without-list"),
        pytest.param("market in []", "non-empty list", id="in-empty-list"),
        pytest.param("model_year + 1", "unsupported syntax", id="arithmetic"),
        pytest.param(42, "must be a string", id="not-a-string"),
    ],
)
def test_rejects_syntax(expression, reason):
    with pytest.raises(ConditionSyntaxError) as exc_info:
        compile_condition(expression)
    assert reason in exc_info.value.reason


@pytest.mark.parametrize(
    "expression, problem",
    [
        pytest.param("sunroof", "unknown feature or qualifier 'sunroof'", id="unknown-name"),
        pytest.param("market", "must be compared", id="enumerated-feature-alone"),
        pytest.param("market == de", "'de' is not a value of feature 'market'", id="unknown-value"),
        pytest.param("market < us", "needs an ordered feature", id="ordering-unordered"),
        pytest.param("trailer_hitch == eu", "can only be compared with true or false", id="boolean-with-value"),
        pytest.param("trailer_hitch in [true]", "cannot be used with boolean feature", id="boolean-membership"),
        pytest.param("variant == suv_eu", "unknown feature 'variant'", id="no-variant-symbol"),
        pytest.param("color == red", "unknown feature 'color'", id="unknown-compared-feature"),
        pytest.param("eu == market", "unknown feature 'eu'", id="value-on-the-left"),
    ],
)
def test_reports_misuse(expression, problem):
    problems = SYMBOLS.problems(compile_condition(expression))
    assert len(problems) == 1, problems
    assert problem in problems[0]


@pytest.mark.parametrize(
    "expression",
    [
        pytest.param("trailer_hitch and market in [eu, us]", id="feature-and-membership"),
        pytest.param("model_year >= my27 or body not in [sedan]", id="ordering-and-not-in"),
        pytest.param("premium", id="qualifier"),
    ],
)
def test_accepts_declared_names(expression):
    assert SYMBOLS.problems(compile_condition(expression)) == []


def test_names_and_refs():
    condition = compile_condition("premium and (market == eu or not trailer_hitch)")
    assert condition.names() == {"premium", "market", "trailer_hitch"}
    assert condition.refs() == {"premium", "trailer_hitch"}


@pytest.mark.parametrize(
    "name, expected",
    [
        pytest.param("trailer_hitch", True, id="identifier"),
        pytest.param("_internal2", True, id="leading-underscore"),
        pytest.param("2door", False, id="leading-digit"),
        pytest.param("class", False, id="python-keyword"),
        pytest.param("variant", True, id="variant-is-not-reserved"),
        pytest.param("true", False, id="reserved-literal"),
        pytest.param("rear-camera", False, id="hyphen"),
    ],
)
def test_is_identifier(name, expected):
    assert is_identifier(name) is expected
