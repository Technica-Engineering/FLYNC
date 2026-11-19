"""
Product variants and the ``variability/`` folder that holds them together with the feature model.

Every file in ``variability/variants/`` declares one product variant (a product configuration that is
actually built, sold, or deployed) by stating its decisions. A variant may ``extends`` another one and
only state what differs; features it leaves undecided take their default. The variants are the closed
set FLYNC resolves and validates the workspace for.
"""

from typing import Annotated, Dict, List, Optional, Self

from pydantic import Field, model_validator

from flync.core.annotations import External, Implied, ImpliedStrategy, NamingStrategy, OutputStrategy
from flync.core.base_models import FLYNCBaseModel
from flync.core.utils.exceptions import Category, err_major, warn
from flync.model.flync_4_variability.condition import SymbolTable, compile_condition
from flync.model.flync_4_variability.context import (
    Configuration,
    VariantContext,
    all_contexts,
    build_context,
    extends_chain,
    normalize_value,
    raw_assignment,
    variant_configuration,
)
from flync.model.flync_4_variability.feature_model import Feature, FeatureModel


class VariantDefinition(FLYNCBaseModel):
    """
    One product variant: a named set of decisions about features.

    Stored as ``variability/variants/<name>.flync.yaml``; the name is the file name.

    Parameters
    ----------
    name : str
        Name of the variant, implied from the file name.
    description : str, optional
        Human-readable description of the variant. Defaults to ``None``.
    extends : str, optional
        Name of a variant whose decisions this variant inherits; its own entries override inherited ones.
        Defaults to ``None``.
    features : dict of str to bool | str | int | float, optional
        Feature decisions: ``true``/``false`` for a boolean feature, one of the declared values for an
        enumerated feature. Features the variant does not decide take their default. Defaults to an empty mapping.
    """

    name: Annotated[str, Implied(strategy=ImpliedStrategy.FILE_NAME)] = Field()
    description: Optional[str] = Field(default=None)
    extends: Optional[str] = Field(default=None)
    features: Dict[str, bool | str | int | float] = Field(default_factory=dict)


class Variability(FLYNCBaseModel):
    """
    The variability of a workspace: its feature model and the product variants it is resolved for.

    Maps to the optional ``variability/`` folder. A workspace without it describes a single configuration and
    loads exactly as before; a workspace with it is a 150 % model whose variation points (a ``variant_condition`` at the
    root of an ECU's metadata or on an entry of the system topology) are resolved for one variant at a time.

    Parameters
    ----------
    feature_model : :class:`~flync.model.flync_4_variability.feature_model.FeatureModel`
        The features, constraints, and qualifiers, stored in ``variability/feature_model.flync.yaml``.
    variants : list of :class:`VariantDefinition`, optional
        The product variants, one file each in ``variability/variants/``. At least one variant is required.
        Defaults to ``None``.
    """

    feature_model: Annotated[
        FeatureModel,
        External(
            output_structure=OutputStrategy.SINGLE_FILE | OutputStrategy.OMMIT_ROOT,
            naming_strategy=NamingStrategy.FIXED_PATH,
            path="feature_model",
        ),
    ] = Field()
    variants: Annotated[
        Optional[List[VariantDefinition]],
        External(
            output_structure=OutputStrategy.FOLDER,
            naming_strategy=NamingStrategy.FIELD_NAME,
        ),
    ] = Field(default=None)

    @model_validator(mode="after")
    def validate_has_variants(self) -> Self:
        """At least one variant is declared."""

        if not self.variants:
            raise err_major(
                "The variability model declares no variants; add one file per variant to variability/variants/.",
                category=Category.REQUIRED,
                error_number="475",
            )
        return self

    @model_validator(mode="after")
    def validate_default_variant(self) -> Self:
        """The default variant, when given, is declared."""

        default = self.feature_model.default_variant
        if default is not None and default not in self.variant_names():
            raise err_major(
                "default_variant '{variant}' is not declared; available variants: {available}.",
                category=Category.REFERENCE,
                error_number="476",
                variant=default,
                available=self.variant_names(),
            )
        return self

    @model_validator(mode="after")
    def validate_extends(self) -> Self:
        """``extends`` names a declared variant and inheritance has no cycles."""

        names = set(self.variant_names())
        for variant in self.variants or []:
            if variant.extends is None:
                continue
            if variant.extends not in names:
                raise err_major(
                    "Variant '{variant}' extends unknown variant '{extends}'.",
                    category=Category.REFERENCE,
                    error_number="478",
                    variant=variant.name,
                    extends=variant.extends,
                )
            chain = extends_chain(self, variant.name)
            last = next(v for v in self.variants or [] if v.name == chain[-1])
            if last.extends is not None and last.extends in chain:
                raise err_major(
                    "Variant inheritance cycle: {chain}.",
                    category=Category.CONSISTENCY,
                    error_number="479",
                    chain=" -> ".join(chain + [last.extends]),
                )
        return self

    @model_validator(mode="after")
    def validate_assignments(self) -> Self:
        """Every variant decides declared features only, with values that fit them."""

        for variant in self.variants or []:
            for name, value in raw_assignment(self, variant.name).items():
                feature = self.feature_model.feature(name)
                if feature is None:
                    raise err_major(
                        "Variant '{variant}' assigns unknown feature '{feature}'.",
                        category=Category.REFERENCE,
                        error_number="480",
                        variant=variant.name,
                        feature=name,
                    )
                if not _fits(feature, value):
                    raise err_major(
                        "Variant '{variant}' assigns '{value}' to feature '{feature}'; allowed: {allowed}.",
                        category=Category.VALUE_RANGE,
                        error_number="481",
                        variant=variant.name,
                        feature=name,
                        value=value,
                        allowed=_allowed_values(feature),
                    )
        return self

    @model_validator(mode="after")
    def validate_configurations(self) -> Self:
        """Every variant decides every enumerated feature that has no default."""

        for variant in self.variants or []:
            for feature in variant_configuration(self, variant.name).open_decisions:
                raise err_major(
                    "Variant '{variant}' does not assign enumerated feature '{feature}' and the feature has no default.",
                    category=Category.REQUIRED,
                    error_number="482",
                    variant=variant.name,
                    feature=feature,
                )
        return self

    @model_validator(mode="after")
    def validate_constraints(self) -> Self:
        """Every variant satisfies every constraint of the feature model."""

        for context in all_contexts(self):
            for constraint in self.feature_model.constraints:
                if not context.holds(constraint.expression):
                    raise err_major(
                        "Variant '{variant}' violates constraint '{expression}'{description}.",
                        category=Category.CONSISTENCY,
                        error_number="436",
                        variant=context.name,
                        expression=constraint.expression,
                        description=f" ({constraint.description})" if constraint.description else "",
                    )
        return self

    @model_validator(mode="after")
    def warn_identical_variants(self) -> Self:
        """Two variants with the same complete configuration are probably a copy-paste mistake."""

        seen: dict[tuple[tuple[str, object], ...], str] = {}
        for context in all_contexts(self):
            key = tuple(sorted(context.assignment.items()))
            if key in seen:
                warn(
                    f"Variants '{seen[key]}' and '{context.name}' assign the same feature values, so they resolve to the same model.",
                    category=Category.UNIQUENESS,
                    error_number="437",
                )
            else:
                seen[key] = context.name
        return self

    def features(self) -> list[Feature]:
        """Every feature of the feature model, in declaration order."""

        return list(self.feature_model.features)

    def symbol_table(self) -> SymbolTable:
        """The names a variant condition may use: every feature and qualifier."""

        return self.feature_model.symbol_table()

    def variant_names(self) -> list[str]:
        """Names of the declared variants, in declaration order."""

        return [variant.name for variant in self.variants or []]

    def variant(self, name: str) -> VariantDefinition | None:
        """Return the variant called ``name``, or ``None``."""

        return next((variant for variant in self.variants or [] if variant.name == name), None)

    def configuration(self, name: str) -> Configuration:
        """
        Return the completed configuration of variant ``name``, with the source of every value.

        Raises:
            KeyError: If the variant is not declared.
        """

        return variant_configuration(self, name)

    def context(self, name: str) -> VariantContext:
        """
        Return the evaluation context of variant ``name``.

        Raises:
            KeyError: If the variant is not declared.
        """

        return build_context(self, name)

    def contexts(self) -> list[VariantContext]:
        """Return the evaluation context of every declared variant."""

        return all_contexts(self)

    def is_dead(self, condition: str | bool) -> bool:
        """Return ``True`` when ``condition`` is false in every declared variant."""

        compiled = compile_condition(condition)
        return not any(context.holds(compiled) for context in all_contexts(self))


def _allowed_values(feature: Feature) -> str:
    """The values ``feature`` accepts, for an error message."""

    return "true or false" if feature.is_boolean else ", ".join(feature.values or [])


def _fits(feature: Feature, value: object) -> bool:
    """Return ``True`` when ``value`` normalizes to a value ``feature`` accepts."""

    normalized = normalize_value(value, feature.is_boolean)
    return normalized is not None and (feature.values is None or normalized in feature.values)
