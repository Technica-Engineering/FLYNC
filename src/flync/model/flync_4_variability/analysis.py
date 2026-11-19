"""
Analyses over the variation points of a 150 % workspace: traceability and variant comparison.

The functions here take the raw (safe-loaded) documents of a workspace, keyed by their workspace-relative ids,
and never touch the disk.

- :func:`collect_variation_points` lists every ``variant_condition``: at the root of an ECU's ``ecu_metadata`` it
  decides which variants the ECU is part of, on an entry of the system topology which variants the entry is part of.
- :func:`trace_features` answers "which elements of the workspace does this feature decide?" - the link from a
  feature down to the realizing elements.
- :func:`compare_variants` answers "what is different between these two variants?" - in feature values and in
  the elements of the workspace.
"""

from dataclasses import dataclass, field
from typing import Any, Iterator, Mapping

from flync.model.flync_4_variability.condition import ConditionSyntaxError, compile_condition
from flync.model.flync_4_variability.context import VariantContext
from flync.model.flync_4_variability.resolution import VARIANT_CONDITION_KEY, YamlPath, is_in_variability
from flync.model.flync_4_variability.variant import Variability

LABEL_KEYS = ("id", "name", "ecu_port")
"""Keys of a mapping whose value names the element in :meth:`VariationPoint.describe`, in order of preference."""


@dataclass(frozen=True)
class VariationPoint:
    """
    One variation point of the workspace: a ``variant_condition`` and the element it decides the presence of.

    Attributes:
        document (str): Workspace-relative id of the document.
        location (YamlPath): Path to the element inside the document; empty for a condition at the document root, which
        decides the presence of the whole document (for an ECU's ``ecu_metadata``, of the whole ECU).
        condition (str | None): The condition, ``None`` when what is written is not a condition.
        label (str | None): The name of the element (its ``id``, ``name``, or ``ecu_port``), when it has one.
    """

    document: str
    location: YamlPath
    condition: str | None
    label: str | None = None

    def describe(self) -> str:
        """A short human-readable reference, e.g. ``topology/ethernet_topology.flync.yaml: connections[1] (link_rear)``."""

        where = _format_location(self.location)
        text = f"{self.document}: {where}" if where else self.document
        return f"{text} ({self.label})" if self.label and where else text

    def outcome(self, context: VariantContext) -> bool:
        """Whether the element is part of a variant."""

        return context.holds(self.condition)


def _format_location(location: YamlPath) -> str:
    """Render a YAML path as ``a.b[0].c``."""

    text = ""
    for part in location:
        if isinstance(part, int):
            text += f"[{part}]"
        else:
            text += f".{part}" if text else str(part)
    return text


def _condition_text(value: object) -> str | None:
    """The text of a condition, ``None`` when the value is not one (YAML booleans become ``true``/``false``)."""

    if isinstance(value, bool):
        return str(value).lower()
    return value if isinstance(value, str) else None


def _label(data: dict[Any, Any]) -> str | None:
    """The name of the element a mapping stands for, see :data:`LABEL_KEYS`."""

    for key in LABEL_KEYS:
        value = data.get(key)
        if isinstance(value, (str, int)) and not isinstance(value, bool):
            return str(value)
    return None


def _walk(document: str, data: Any, path: YamlPath) -> Iterator[VariationPoint]:
    """Yield the variation points of a parsed YAML node: a mapping's own condition first, then those nested in it."""

    if isinstance(data, dict):
        if VARIANT_CONDITION_KEY in data:
            yield VariationPoint(document, path, _condition_text(data[VARIANT_CONDITION_KEY]), _label(data))
        for key, value in data.items():
            if key != VARIANT_CONDITION_KEY:
                yield from _walk(document, value, path + (key,))
    elif isinstance(data, list):
        for index, item in enumerate(data):
            yield from _walk(document, item, path + (index,))


def collect_variation_points(documents: Mapping[str, Any]) -> list[VariationPoint]:
    """
    List every variation point of a workspace.

    Args:
        documents (Mapping[str, Any]): The safe-loaded content of every document, by workspace-relative id. Documents in
            ``variability/`` are skipped.

    Returns:
        list[VariationPoint]: The variation points in document order, a document's root condition first.
    """

    points: list[VariationPoint] = []
    for uri in sorted(documents):
        if not is_in_variability(uri):
            points.extend(_walk(uri, documents[uri], ()))
    return points


def _names(variability: Variability, condition: str | None) -> set[str]:
    """The features that ``condition`` refers to, qualifiers expanded; an unparsable condition refers to none."""

    if condition is None:
        return set()
    feature_model = variability.feature_model
    try:
        names = compile_condition(condition).names()
    except ConditionSyntaxError:
        return set()
    declared = {feature.name for feature in feature_model.features}
    return {name for name in feature_model.expand(names) if name in declared}


def trace_features(variability: Variability, points: list[VariationPoint]) -> dict[str, list[VariationPoint]]:
    """
    Find the variation points every feature decides, directly or through qualifiers.

    Args:
        variability (Variability): The variability model.
        points (list[VariationPoint]): The variation points of the workspace, see :func:`collect_variation_points`.

    Returns:
        dict[str, list[VariationPoint]]: For every feature (in declaration order), the variation points whose
        condition refers to it; features no variation point refers to map to an empty list.
    """

    traced: dict[str, list[VariationPoint]] = {feature.name: [] for feature in variability.feature_model.features}
    for point in points:
        for name in _names(variability, point.condition):
            traced[name].append(point)
    return traced


@dataclass
class VariantComparison:
    """
    The differences between two variants.

    Attributes:
        left (str): Name of the first variant.
        right (str): Name of the second variant.
        features (list[tuple[str, object, object]]): ``(feature, left value, right value)`` for every feature that differs.
        elements (list[tuple[VariationPoint, bool, bool]]): ``(point, part of left, part of right)`` for every element that
        is part of one of the variants only.
    """

    left: str
    right: str
    features: list[tuple[str, object, object]] = field(default_factory=list)
    elements: list[tuple[VariationPoint, bool, bool]] = field(default_factory=list)

    @property
    def identical(self) -> bool:
        """Whether the two variants resolve to the same workspace and feature values."""

        return not self.features and not self.elements


def compare_variants(variability: Variability, points: list[VariationPoint], left: str, right: str) -> VariantComparison:
    """
    Compare two variants: their feature values and the elements of the workspace that differ.

    Args:
        variability (Variability): The variability model.
        points (list[VariationPoint]): The variation points of the workspace, see :func:`collect_variation_points`.
        left (str): Name of the first variant.
        right (str): Name of the second variant.

    Returns:
        VariantComparison: The differences, in feature declaration order and document order.

    Raises:
        KeyError: If one of the variants is not declared.
    """

    left_context, right_context = variability.context(left), variability.context(right)
    comparison = VariantComparison(left, right)
    for name in (feature.name for feature in variability.feature_model.features):
        left_value, right_value = left_context.assignment.get(name), right_context.assignment.get(name)
        if left_value != right_value:
            comparison.features.append((name, left_value, right_value))
    for point in points:
        left_outcome, right_outcome = point.outcome(left_context), point.outcome(right_context)
        if left_outcome != right_outcome:
            comparison.elements.append((point, left_outcome, right_outcome))
    return comparison
