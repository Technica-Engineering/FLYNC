"""
The configuration of one product variant and its evaluation context.

A variant states only its own decisions. :func:`configure` completes them into a full configuration:

1. The decisions written for the variant itself.
2. The decisions it inherits through ``extends``, nearer variants overriding farther ones.
3. The default of every feature that is still undecided (``false`` for a boolean feature without a default).

An enumerated feature without a value and without a default is recorded as an open decision;
:class:`~flync.model.flync_4_variability.variant.Variability` reports it.

A :class:`VariantContext` holds the completed configuration of a variant and evaluates variant conditions against
it. The workspace loader uses it to resolve the variation points of the 150 % workspace, and a loaded
:class:`~flync.model.flync_model.FLYNCModel` exposes it as ``active_variant`` so generators can tell which variant
they hold, where each value comes from, and read the attributes of its features.

The functions here only read the variability model, so they work on a partially valid model too.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING, Mapping

from flync.model.flync_4_variability.condition import Condition, ConditionValue, SymbolTable, compile_condition
from flync.model.flync_4_variability.feature_model import AttributeValue, Feature, FeatureModel

if TYPE_CHECKING:
    from flync.model.flync_4_variability.variant import Variability, VariantDefinition


class ValueSource(StrEnum):
    """
    Where the value of a feature in a variant comes from.

    - ``assigned``: written in the variant itself.
    - ``inherited``: written in a variant it ``extends``.
    - ``default``: the feature's default, or ``false`` for an undecided boolean feature.
    """

    ASSIGNED = "assigned"
    INHERITED = "inherited"
    DEFAULT = "default"


@dataclass
class Configuration:
    """
    The completed configuration of a variant.

    Attributes:
        values (dict[str, ConditionValue]): The value of every decided feature.
        sources (dict[str, ValueSource]): Where each value comes from.
        open_decisions (list[str]): Enumerated features that have neither a value nor a default.
    """

    values: dict[str, ConditionValue] = field(default_factory=dict)
    sources: dict[str, ValueSource] = field(default_factory=dict)
    open_decisions: list[str] = field(default_factory=list)


def normalize_value(value: object, is_boolean: bool) -> ConditionValue | None:
    """Read an assigned value the way conditions compare it, or return ``None`` when it does not fit the feature."""

    if is_boolean:
        return value if isinstance(value, bool) else None
    if isinstance(value, (str, int, float)) and not isinstance(value, bool):
        return str(value)
    return None


def configure(
    feature_model: FeatureModel,
    assigned: Mapping[str, object],
    inherited: Mapping[str, object] | None = None,
) -> Configuration:
    """
    Complete the decisions of a variant into a full configuration.

    Decisions that name an undeclared feature or do not fit its type are skipped here; the variability model reports them.

    Args:
        feature_model (FeatureModel): The features of the product line.
        assigned (Mapping[str, object]): The values written in the variant itself.
        inherited (Mapping[str, object] | None): The values it inherits through ``extends`` (nearer variants already merged).

    Returns:
        Configuration: The values with their sources, and the enumerated features left undecided.
    """

    config = Configuration()
    layers = ((assigned, ValueSource.ASSIGNED), (inherited or {}, ValueSource.INHERITED))
    for feature in feature_model.features:
        decided = _decided_value(feature, layers)
        if decided is None:
            decided = _default_value(feature)
        if decided is None:
            config.open_decisions.append(feature.name)
        else:
            config.values[feature.name], config.sources[feature.name] = decided
    return config


def _decided_value(feature: Feature, layers: tuple[tuple[Mapping[str, object], ValueSource], ...]) -> tuple[ConditionValue, ValueSource] | None:
    """The first decision for ``feature`` that fits it, searching the variant's own decisions before inherited ones."""

    for decisions, source in layers:
        if feature.name in decisions:
            value = normalize_value(decisions[feature.name], feature.is_boolean)
            if value is not None:
                return value, source
    return None


def _default_value(feature: Feature) -> tuple[ConditionValue, ValueSource] | None:
    """The default of ``feature`` (``false`` for a boolean feature without one), or ``None`` when it has none."""

    if feature.default is not None:
        value = normalize_value(feature.default, feature.is_boolean)
        if value is not None:
            return value, ValueSource.DEFAULT
    return (False, ValueSource.DEFAULT) if feature.is_boolean else None


@dataclass(frozen=True)
class VariantContext:
    """
    The complete configuration of one product variant.

    Attributes:
        name (str): Name of the variant.
        assignment (Mapping[str, ConditionValue]): Value of every feature that has one in this variant: ``True``/``False`` for a
        boolean feature, the selected value (text) for an enumerated feature.
        symbols (SymbolTable): Features and qualifiers of the feature model.
        description (str | None): Description of the variant.
        feature_attributes (Mapping[str, Mapping[str, AttributeValue]]): Attributes of every feature that declares some.
        sources (Mapping[str, ValueSource]): Where the value of each feature comes from.
    """

    name: str
    assignment: Mapping[str, ConditionValue]
    symbols: SymbolTable = field(repr=False)
    description: str | None = None
    feature_attributes: Mapping[str, Mapping[str, AttributeValue]] = field(default_factory=dict, repr=False)
    sources: Mapping[str, ValueSource] = field(default_factory=dict, repr=False)

    # region resolver protocol used by conditions

    def truth(self, name: str) -> bool:
        """Truth value of a boolean feature or a qualifier."""

        qualifier = self.symbols.qualifiers.get(name)
        if qualifier is not None:
            return qualifier.evaluate(self)
        return self.assignment[name] is True

    def value_of(self, name: str) -> ConditionValue:
        """Value of a feature, or the truth value of a qualifier."""

        if name in self.symbols.qualifiers:
            return self.truth(name)
        return self.assignment[name]

    def rank(self, name: str, value: ConditionValue) -> int:
        """Position of ``value`` among the declared values of the ordered feature ``name``."""

        values = self.symbols.features[name].values or ()
        return values.index(str(value))

    # endregion

    def value(self, feature: str) -> ConditionValue:
        """
        Return the value of ``feature`` in this variant.

        Raises:
            KeyError: If the feature does not exist or has no value in this variant.
        """

        return self.assignment[feature]

    def source(self, feature: str) -> ValueSource:
        """
        Return where the value of ``feature`` comes from in this variant.

        Raises:
            KeyError: If the feature does not exist or has no value in this variant.
        """

        return self.sources[feature]

    def is_enabled(self, name: str) -> bool:
        """
        Return whether a boolean feature or a qualifier is true in this variant.

        Raises:
            KeyError: If ``name`` is neither a boolean feature nor a qualifier.
        """

        if not self.symbols.is_boolean_name(name):
            raise KeyError(name)
        return self.truth(name)

    def evaluate(self, condition: str | bool | Condition) -> bool:
        """
        Evaluate a variant condition in this variant.

        Raises:
            ConditionSyntaxError: If the condition does not parse.
            KeyError: If the condition uses a name that is not declared.
            ValueError: If the condition compares an ordered feature with a value it does not declare.
        """

        compiled = condition if isinstance(condition, Condition) else compile_condition(condition)
        return compiled.evaluate(self)

    def holds(self, condition: object) -> bool:
        """
        Evaluate a variant condition, treating an invalid condition (or a value that is not a condition at all) as false.

        Used where a broken condition is reported separately, so the element it guards is simply not part of the
        variant instead of failing the whole load.
        """

        try:
            compiled = condition if isinstance(condition, Condition) else compile_condition(condition)
            return compiled.evaluate(self)
        except (ValueError, KeyError, TypeError, IndexError, RecursionError):
            return False


def _variant_by_name(variability: Variability) -> dict[str, VariantDefinition]:
    """Index the variants of ``variability`` by name."""

    return {variant.name: variant for variant in variability.variants or []}


def extends_chain(variability: Variability, name: str) -> list[str]:
    """
    Return ``name`` followed by the variants it inherits from, nearest first.

    The chain stops at a variant that does not exist or that was already visited, so it is safe on an invalid model.
    """

    variants = _variant_by_name(variability)
    chain: list[str] = []
    current: str | None = name
    while current is not None and current in variants and current not in chain:
        chain.append(current)
        current = variants[current].extends
    return chain


def raw_assignment(variability: Variability, name: str) -> dict[str, object]:
    """Return the assignments written for variant ``name`` and its ``extends`` chain, nearer variants overriding."""

    variants = _variant_by_name(variability)
    merged: dict[str, object] = {}
    for current in reversed(extends_chain(variability, name)):
        merged.update(variants[current].features)
    return merged


def inherited_assignment(variability: Variability, name: str) -> dict[str, object]:
    """Return the assignments variant ``name`` inherits through ``extends`` (without its own), nearer variants overriding."""

    variants = _variant_by_name(variability)
    merged: dict[str, object] = {}
    for current in reversed(extends_chain(variability, name)[1:]):
        merged.update(variants[current].features)
    return merged


def variant_configuration(variability: Variability, name: str) -> Configuration:
    """
    Complete the decisions of variant ``name``.

    Raises:
        KeyError: If the variant is not declared.
    """

    variants = _variant_by_name(variability)
    if name not in variants:
        raise KeyError(name)
    return configure(variability.feature_model, variants[name].features, inherited_assignment(variability, name))


def build_context(variability: Variability, name: str) -> VariantContext:
    """
    Build the evaluation context of variant ``name``.

    Args:
        variability (Variability): The variability model of the workspace.
        name (str): Name of the variant.

    Returns:
        VariantContext: The variant with its complete configuration.

    Raises:
        KeyError: If the variant is not declared.
    """

    variants = _variant_by_name(variability)
    if name not in variants:
        raise KeyError(name)
    feature_model = variability.feature_model
    configuration = variant_configuration(variability, name)
    return VariantContext(
        name=name,
        assignment=MappingProxyType(dict(configuration.values)),
        symbols=feature_model.symbol_table(),
        description=variants[name].description,
        feature_attributes=MappingProxyType(
            {feature.name: MappingProxyType(dict(feature.attributes)) for feature in feature_model.features if feature.attributes}
        ),
        sources=MappingProxyType(dict(configuration.sources)),
    )


def all_contexts(variability: Variability) -> list[VariantContext]:
    """Build the context of every declared variant, in declaration order."""

    return [build_context(variability, variant.name) for variant in variability.variants or []]
