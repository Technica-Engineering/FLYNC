"""Variability (product-line variant management) of a FLYNC workspace."""

from flync.model.flync_4_variability.condition import (
    Condition,
    ConditionSyntaxError,
    FeatureSymbol,
    SymbolTable,
    compile_condition,
    is_identifier,
)
from flync.model.flync_4_variability.context import Configuration, ValueSource, VariantContext, build_context, configure
from flync.model.flync_4_variability.feature_model import (
    AttributeValue,
    Feature,
    FeatureCategory,
    FeatureConstraint,
    FeatureModel,
    FeatureType,
    VariantCondition,
)
from flync.model.flync_4_variability.variant import Variability, VariantDefinition

# Module code for this package's error ids (``FLYNC-VAR-<SEVERITY>-<CATEGORY>-<NUMBER>``).
KEY = "VAR"

__all__ = [
    "KEY",
    "AttributeValue",
    "Condition",
    "ConditionSyntaxError",
    "Configuration",
    "Feature",
    "FeatureCategory",
    "FeatureConstraint",
    "FeatureModel",
    "FeatureSymbol",
    "FeatureType",
    "SymbolTable",
    "ValueSource",
    "Variability",
    "VariantCondition",
    "VariantContext",
    "VariantDefinition",
    "build_context",
    "compile_condition",
    "configure",
    "is_identifier",
]
