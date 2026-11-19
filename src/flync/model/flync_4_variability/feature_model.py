"""
The feature model: the features product variants are configured by, and the rules between them.

It is stored in ``variability/feature_model.flync.yaml``. A feature is a characteristic in which the products of a
product line differ. It is either a boolean feature (an optional component that a product has or does not have) or an
enumerated feature from which every variant selects exactly one value (an E/E architecture, a hardware generation).
The features form a flat list.

``constraints`` restrict which combinations of feature values a variant may have. Qualifiers give reusable names to
conditions that several variation points share, so the alternatives of an element read ``zonal`` / ``domain`` instead
of repeating ``architecture == zonal`` everywhere.
"""

from enum import StrEnum
from typing import Annotated, Dict, List, Optional, Self

from pydantic import AfterValidator, BeforeValidator, Field, field_validator, model_validator

from flync.core.base_models import FLYNCBaseModel
from flync.core.utils.exceptions import Category, err_major
from flync.core.validators.generic import validate_list_items_unique
from flync.model.flync_4_variability.condition import (
    RESERVED_NAMES,
    ConditionSyntaxError,
    FeatureSymbol,
    SymbolTable,
    compile_condition,
    is_identifier,
)


def _condition_to_text(value: object) -> object:
    """Accept a YAML boolean (``expression: true``) as the literal condition text."""

    if isinstance(value, bool):
        return str(value).lower()
    return value


def _check_condition_syntax(value: str) -> str:
    """Reject a condition that does not parse, so a typo is reported where it was written."""

    try:
        compile_condition(value)
    except ConditionSyntaxError as exc:
        raise err_major(
            "Invalid variant condition '{expression}': {reason}.",
            category=Category.FORMAT,
            error_number="362",
            expression=value,
            reason=exc.reason,
        ) from None
    return value


VariantCondition = Annotated[str, BeforeValidator(_condition_to_text), AfterValidator(_check_condition_syntax)]
"""A variant condition written as text, checked for syntax when it is loaded."""


def _stringify_number(value: object) -> object:
    """Read a value written as a YAML number (``2027``) as text."""

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return value


def _stringify_values(values: object) -> object:
    """Read enumerated values written as YAML numbers (``values: [2026, 2027]``) as text."""

    if isinstance(values, list):
        return [_stringify_number(value) for value in values]
    return values


AttributeValue = bool | int | float | str
"""The value of a free-form attribute of a feature."""

Attributes = Dict[str, AttributeValue]
"""Free-form, domain-specific data attached to a feature (an option code, a cost class, ...)."""


class FeatureType(StrEnum):
    """
    The kind of value a feature holds.

    - ``boolean``: the feature is present or absent in a variant (an optional component). It has no ``values``.
    - ``enumeration``: every variant selects exactly one of the declared ``values`` (an architecture, a generation).
    """

    BOOLEAN = "boolean"
    ENUMERATION = "enumeration"


class FeatureCategory(StrEnum):
    """
    What a feature stands for. Documents the role of the feature; it does not change how the feature is configured.

    - ``product``: a capability of the product that a customer or product manager chooses (an option, an edition).
    - ``context``: a condition outside the system: a region, a customer, a market, a legal frame.
    - ``requirement``: a high-level requirement that only some variants have (e.g. "redundant actuation needed").
    - ``solution``: one technical solution that fulfills a requirement (e.g. a domain or a zonal architecture).
    - ``element``: a technical element that a solution is made of (e.g. a hardware generation of an ECU).
    """

    PRODUCT = "product"
    CONTEXT = "context"
    REQUIREMENT = "requirement"
    SOLUTION = "solution"
    ELEMENT = "element"


class Feature(FLYNCBaseModel):
    """
    One feature of the feature model: a characteristic in which the products of the product line differ.

    A feature without ``values`` is a boolean (present/absent) feature such as an optional component. A feature with
    ``values`` is an enumerated feature, from which every variant selects exactly one value. ``type`` states the kind
    explicitly; when it is omitted, it is inferred from whether ``values`` is given.

    Parameters
    ----------
    name : str
        Identifier of the feature used in variant conditions (non-empty). Letters, digits, and underscores,
        not starting with a digit; ``true`` and ``false`` are reserved. Unique across the feature model.
    description : str, optional
        Human-readable description of the feature. Defaults to ``None``.
    type : :class:`FeatureType`, optional
        The kind of feature: ``boolean`` or ``enumeration``. Must agree with ``values``: a boolean feature has
        no values, an enumerated feature has them. Defaults to ``None`` (inferred from ``values``).
    category : :class:`FeatureCategory`, optional
        What the feature stands for: ``product``, ``context``, ``requirement``, ``solution``, or ``element``.
        Documents the role of the feature; it does not change how the feature is configured. Defaults to ``None``.
    values : list of str, optional
        The values of an enumerated feature (at least one, all unique). Omit it for a boolean feature.
        Numbers are read as text. Defaults to ``None``.
    ordered : bool, optional
        Whether the order of ``values`` is meaningful, which enables ``<``, ``<=``, ``>`` and ``>=`` in
        conditions (e.g. hardware generations). Only allowed together with ``values``. Defaults to ``False``.
    default : str | bool, optional
        Value a variant gets when neither it nor a variant it extends decides the feature: one of ``values`` for an
        enumerated feature, ``true`` or ``false`` for a boolean feature. A boolean feature without a default is
        ``false`` when undecided; an enumerated feature without a default must be decided by every variant.
        Defaults to ``None``.
    attributes : dict of str to bool | int | float | str, optional
        Free-form, domain-specific data about the feature (an option code, a cost class). FLYNC does not interpret
        it; generators and reports read it. Defaults to an empty mapping.
    """

    name: str = Field(min_length=1)
    description: Optional[str] = Field(default=None)
    type: Optional[FeatureType] = Field(default=None)
    category: Optional[FeatureCategory] = Field(default=None)
    values: Annotated[Optional[List[str]], BeforeValidator(_stringify_values)] = Field(default=None, min_length=1)
    ordered: bool = Field(default=False)
    default: Annotated[Optional[bool | str], BeforeValidator(_stringify_number)] = Field(default=None)
    attributes: Attributes = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        """A feature name must be usable inside a variant condition."""

        if not is_identifier(value):
            raise err_major(
                "'{name}' is not a valid feature name: use letters, digits, and underscores, do not start with a digit, "
                "and do not use a Python keyword or one of {reserved}.",
                category=Category.FORMAT,
                error_number="470",
                name=value,
                reserved=sorted(RESERVED_NAMES),
            )
        return value

    @model_validator(mode="after")
    def validate_type(self) -> Self:
        """An explicit ``type`` agrees with ``values``."""

        if self.type is FeatureType.BOOLEAN and self.values is not None:
            raise err_major(
                "Feature '{feature}' is declared 'type: boolean' but has values; remove the values or declare it 'type: enumeration'.",
                category=Category.CONSISTENCY,
                error_number="453",
                feature=self.name,
            )
        if self.type is FeatureType.ENUMERATION and self.values is None:
            raise err_major(
                "Feature '{feature}' is declared 'type: enumeration' but has no values; list them under 'values'.",
                category=Category.REQUIRED,
                error_number="454",
                feature=self.name,
            )
        return self

    @model_validator(mode="after")
    def validate_values(self) -> Self:
        """The values of an enumerated feature are non-empty and unique; ``ordered`` needs values."""

        if self.values is None:
            if self.ordered:
                raise err_major(
                    "Feature '{feature}' is declared 'ordered' but has no values.",
                    category=Category.CONSISTENCY,
                    error_number="364",
                    feature=self.name,
                )
            return self
        if any(not value for value in self.values):
            raise err_major(
                "Feature '{feature}' declares an empty value.",
                category=Category.VALUE_RANGE,
                error_number="363",
                feature=self.name,
            )
        validate_list_items_unique(self.values, f"values of feature '{self.name}'")
        return self

    @model_validator(mode="after")
    def validate_default(self) -> Self:
        """The default of an enumerated feature is one of its values; a boolean feature defaults to a boolean."""

        if self.default is None:
            return self
        if self.values is None and not isinstance(self.default, bool):
            raise err_major(
                "Boolean feature '{feature}' has default '{default}'; use true or false.",
                category=Category.VALUE_RANGE,
                error_number="366",
                feature=self.name,
                default=self.default,
            )
        if self.values is not None and (isinstance(self.default, bool) or self.default not in self.values):
            raise err_major(
                "Default '{default}' of feature '{feature}' is not one of its values {values}.",
                category=Category.VALUE_RANGE,
                error_number="471",
                feature=self.name,
                default=self.default,
                values=self.values,
            )
        return self

    @property
    def feature_type(self) -> FeatureType:
        """The kind of feature: the declared ``type``, or the one implied by ``values``."""

        if self.type is not None:
            return self.type
        return FeatureType.BOOLEAN if self.values is None else FeatureType.ENUMERATION

    @property
    def is_boolean(self) -> bool:
        """Whether this is a boolean (present/absent) feature."""

        return self.values is None

    def symbol(self) -> FeatureSymbol:
        """Return what a variant condition may do with this feature."""

        return FeatureSymbol(self.name, tuple(self.values) if self.values is not None else None, self.ordered)


class FeatureConstraint(FLYNCBaseModel):
    """
    A rule every product variant must satisfy.

    Parameters
    ----------
    expression : str
        Variant condition that must hold in every variant, e.g. ``architecture != zonal or compute_generation >= gen2``.
    description : str, optional
        Human-readable explanation of the rule, shown when a variant violates it. Defaults to ``None``.
    """

    expression: VariantCondition = Field()
    description: Optional[str] = Field(default=None)


class FeatureModel(FLYNCBaseModel):
    """
    The features product variants are configured by, the constraints between them, and the named conditions.

    Stored in ``variability/feature_model.flync.yaml``.

    Parameters
    ----------
    features : list of :class:`Feature`, optional
        The features, in the order tools list them. Defaults to an empty list.
    constraints : list of :class:`FeatureConstraint`, optional
        Rules every variant must satisfy. Defaults to an empty list.
    qualifiers : dict of str to str, optional
        Named, reusable variant conditions, e.g. ``zonal: architecture == zonal``. A qualifier is used by name
        inside other conditions, wherever a condition is written. Defaults to an empty mapping.
    default_variant : str, optional
        Variant loaded when no variant is selected explicitly. Defaults to ``None``.
    """

    features: List[Feature] = Field(default_factory=list)
    constraints: List[FeatureConstraint] = Field(default_factory=list)
    qualifiers: Dict[str, VariantCondition] = Field(default_factory=dict)
    default_variant: Optional[str] = Field(default=None)

    @model_validator(mode="after")
    def validate_unique_feature_names(self) -> Self:
        """Feature names are unique."""

        validate_list_items_unique([feature.name for feature in self.features], "feature names")
        return self

    @model_validator(mode="after")
    def validate_qualifier_names(self) -> Self:
        """Qualifier names are identifiers and do not reuse a feature name."""

        features = {feature.name for feature in self.features}
        for name in self.qualifiers:
            if not is_identifier(name):
                raise err_major(
                    "'{name}' is not a valid qualifier name: use letters, digits, and underscores, do not start with a digit, "
                    "and do not use a Python keyword or one of {reserved}.",
                    category=Category.FORMAT,
                    error_number="472",
                    name=name,
                    reserved=sorted(RESERVED_NAMES),
                )
            if name in features:
                raise err_major(
                    "Qualifier '{name}' has the same name as a feature; features and qualifiers share one namespace.",
                    category=Category.UNIQUENESS,
                    error_number="473",
                    name=name,
                )
        return self

    @model_validator(mode="after")
    def validate_qualifier_cycles(self) -> Self:
        """A qualifier does not refer to itself, directly or through other qualifiers."""

        compiled = {name: compile_condition(text) for name, text in self.qualifiers.items()}
        for start in compiled:
            stack: list[tuple[str, tuple[str, ...]]] = [(start, (start,))]
            while stack:
                current, chain = stack.pop()
                for ref in compiled[current].refs() & compiled.keys():
                    if ref == start:
                        raise err_major(
                            "Qualifier cycle: {chain}.",
                            category=Category.CONSISTENCY,
                            error_number="474",
                            chain=" -> ".join(chain + (start,)),
                        )
                    if ref not in chain:
                        stack.append((ref, chain + (ref,)))
        return self

    @model_validator(mode="after")
    def validate_references(self) -> Self:
        """Every constraint and qualifier uses declared names and values only."""

        symbols = self.symbol_table()
        written = [(f"constraint {index} ({constraint.expression})", constraint.expression) for index, constraint in enumerate(self.constraints)]
        written += [(f"qualifier '{name}'", text) for name, text in self.qualifiers.items()]
        for where, text in written:
            problems = symbols.problems(compile_condition(text))
            if problems:
                raise err_major(
                    "{where}: {problems}.",
                    category=Category.REFERENCE,
                    error_number="477",
                    where=where,
                    problems="; ".join(problems),
                )
        return self

    def feature(self, name: str) -> Feature | None:
        """Return the feature called ``name``, or ``None``."""

        return next((feature for feature in self.features if feature.name == name), None)

    def symbol_table(self) -> SymbolTable:
        """Return the names a variant condition may use: every feature and qualifier."""

        return SymbolTable(
            features={feature.name: feature.symbol() for feature in self.features},
            qualifiers={name: compile_condition(text) for name, text in self.qualifiers.items()},
        )

    def expand(self, names: frozenset[str] | set[str]) -> set[str]:
        """``names`` together with every name that the qualifiers among them refer to, transitively."""

        found: set[str] = set()
        stack = list(names)
        while stack:
            name = stack.pop()
            if name in found:
                continue
            found.add(name)
            text = self.qualifiers.get(name)
            if text is not None:
                stack.extend(compile_condition(text).names())
        return found
