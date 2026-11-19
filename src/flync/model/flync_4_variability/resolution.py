"""
Resolution of the variation points of a 150 % workspace for one product variant.

Everything here works on the raw (safe-loaded) YAML data and on workspace paths, before any model is
validated, so every FLYNC model sees an ordinary, variant-free configuration. The workspace loader calls
these functions; they never touch the disk.

Variation points
----------------
A product variant is a selection of ECUs and of the links between them. An ECU is the same in every variant it is
part of: an ECU that differs between variants - one port more, another controller, other software - is a separate
ECU. Both variation points are therefore a ``variant_condition``:

- **ECU presence** - a ``variant_condition`` at the root of an ECU's ``ecu_metadata.flync.yaml`` decides which
  variants the whole ECU folder is part of (see :data:`PRESENCE_DOCUMENT_ATTR`).
- **System topology entries** - an entry of a list in a document of the system topology (``topology/``), such as a
  connection or a node of a multidrop segment, may carry a ``variant_condition``; it is removed from the variants the
  condition does not hold in.

Every other document is the same in every variant, and a variation point in it is reported by :func:`lint_document`
(:class:`DocumentRole` says what each document may contain).
"""

from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pydantic_core import ErrorDetails, PydanticCustomError

from flync.core.utils.exceptions import Category, collect_warnings, err_fatal, err_major, error_details_from, warn
from flync.model.flync_4_variability.condition import ConditionSyntaxError, SymbolTable, compile_condition
from flync.model.flync_4_variability.context import VariantContext

VARIABILITY_FOLDER = "variability"
"""Workspace folder holding the variability model."""

ECUS_FOLDER = "ecus"
"""Workspace folder holding one folder per ECU."""

TOPOLOGY_FOLDER = "topology"
"""Workspace folder holding the system topology."""

FEATURE_MODEL_DOCUMENT = f"{VARIABILITY_FOLDER}/feature_model.flync.yaml"
"""Document id of the feature model, where workspace-level variability findings are reported."""

VARIANT_CONDITION_KEY = "variant_condition"
"""Reserved mapping key holding the presence condition of an ECU or of a system topology entry."""

VARIANT_VALUES_KEY = "variant_values"
"""Mapping key of the value variation of earlier drafts; it is not supported, and :func:`lint_document` reports it."""

PRESENCE_DOCUMENT_ATTR = "PRESENCE_DOCUMENT"
"""
Class attribute a folder-based model declares to name the field whose document decides the folder's presence.

Only the ECU declares one, ``PRESENCE_DOCUMENT = "ecu_metadata"``: a ``variant_condition`` at the root of
``ecu_metadata.flync.yaml`` removes the whole ECU folder from the variants it does not hold in.
"""

YamlPath = tuple[str | int, ...]
"""Path to a value inside a document: mapping keys and list indices."""


class DocumentRole(Enum):
    """What a document of the workspace may contain in the way of variation points."""

    ECU_PRESENCE = "ecu_presence"
    """The presence document of an ECU (``ecus/<ecu>/ecu_metadata.flync.yaml``): a ``variant_condition`` at its root only."""

    ECU = "ecu"
    """Any other document of an ECU: none, the ECU is the same in every variant it is part of."""

    SYSTEM_TOPOLOGY = "system_topology"
    """A document of the system topology (``topology/``): a ``variant_condition`` on entries of its lists."""

    VARIABILITY = "variability"
    """A document of the variability model itself: none."""

    OTHER = "other"
    """Any other document (communication, applications, metadata, ...): none, it is the same in every variant."""


def document_role(path: str, presence_file: str) -> DocumentRole:
    """
    Return the role of a document from its location in the workspace.

    Args:
        path (str): Path of the document relative to the root of the workspace, with ``/`` separators, e.g.
            ``ecus/gateway/ecu_metadata.flync.yaml``.
        presence_file (str): File name of the presence document of an ECU, e.g. ``ecu_metadata.flync.yaml``.

    Returns:
        DocumentRole: What the document may contain in the way of variation points.
    """

    parts = path.split("/")
    role = DocumentRole.OTHER
    if parts[0] == VARIABILITY_FOLDER:
        role = DocumentRole.VARIABILITY
    elif parts[0] == TOPOLOGY_FOLDER and len(parts) > 1:
        role = DocumentRole.SYSTEM_TOPOLOGY
    elif parts[0] == ECUS_FOLDER and len(parts) > 2:
        role = DocumentRole.ECU_PRESENCE if len(parts) == 3 and parts[2] == presence_file else DocumentRole.ECU
    return role


class _Absent(object):
    """Marker for a value removed by variant resolution; compare with ``is ABSENT``."""

    def __repr__(self) -> str:
        return "ABSENT"

    def __bool__(self) -> bool:
        return False


ABSENT = _Absent()
"""The resolved value of something that is not part of the active variant."""


@dataclass
class ResolutionTrace:
    """
    What resolving one document removed, keyed by paths into the **original** document.

    The workspace uses it to build a filtered copy of the composed YAML tree whose nodes keep their original
    line and column marks, so error positions and the object map stay correct for the resolved data.

    Attributes:
        removed (set[YamlPath]): Paths of removed list items and mapping keys (including stripped ``variant_condition`` keys).
    """

    removed: set[YamlPath] = field(default_factory=set)
    _prefixes: frozenset[YamlPath] | None = field(default=None, repr=False, compare=False)

    def __bool__(self) -> bool:
        return bool(self.removed)

    def touched_prefixes(self) -> frozenset[YamlPath]:
        """Every path that is, or contains, a removed path."""

        if self._prefixes is None:
            found: set[YamlPath] = set()
            for path in self.removed:
                for end in range(len(path) + 1):
                    found.add(path[:end])
            self._prefixes = frozenset(found)
        return self._prefixes


def has_variation_points(text: object) -> bool:
    """Cheap test whether a document's text can contain variation points (including the unsupported ``variant_values``)."""

    return isinstance(text, str) and (VARIANT_CONDITION_KEY in text or VARIANT_VALUES_KEY in text)


def copy_tree(data: Any) -> Any:
    """Copy the mappings and lists of a safe-loaded document, so validation can prune the copy without touching the cache."""

    if isinstance(data, dict):
        return {key: copy_tree(value) for key, value in data.items()}
    if isinstance(data, list):
        return [copy_tree(item) for item in data]
    return data


def is_in_variability(uri: str) -> bool:
    """Whether a document or folder id lies inside the ``variability/`` folder."""

    return uri == VARIABILITY_FOLDER or uri.startswith(f"{VARIABILITY_FOLDER}/")


# region resolution


def _holds(context: VariantContext | None, condition: object) -> bool:
    """Evaluate a condition; without variability, and for a broken condition, it is false."""

    return context is not None and context.holds(condition)


def _resolve(value: Any, path: YamlPath, context: VariantContext | None, trace: ResolutionTrace) -> Any:
    """Resolve a parsed YAML node, recording what is removed in ``trace``."""

    if isinstance(value, dict):
        return _resolve_mapping(value, path, context, trace)
    if isinstance(value, list):
        return _resolve_sequence(value, path, context, trace)
    return value


def _resolve_mapping(value: dict[Any, Any], path: YamlPath, context: VariantContext | None, trace: ResolutionTrace) -> Any:
    """Resolve a mapping: its presence condition, then its children, dropping absent ones."""

    if VARIANT_CONDITION_KEY in value:
        trace.removed.add(path + (VARIANT_CONDITION_KEY,))
        # at the document root the condition decides the presence of the whole document
        if not _holds(context, value[VARIANT_CONDITION_KEY]):
            return ABSENT
        value = {key: item for key, item in value.items() if key != VARIANT_CONDITION_KEY}
    resolved: dict[Any, Any] = {}
    for key, item in value.items():
        child = _resolve(item, path + (key,), context, trace)
        if child is ABSENT:
            trace.removed.add(path + (key,))
            continue
        resolved[key] = child
    return resolved


def _resolve_sequence(value: list[Any], path: YamlPath, context: VariantContext | None, trace: ResolutionTrace) -> list[Any]:
    """Resolve the items of a sequence, dropping the absent ones."""

    items = []
    for index, item in enumerate(value):
        child = _resolve(item, path + (index,), context, trace)
        if child is ABSENT:
            trace.removed.add(path + (index,))
            continue
        items.append(child)
    return items


def resolve_document(data: Any, context: VariantContext | None, *, root_presence: bool = True) -> tuple[Any, ResolutionTrace]:
    """
    Resolve the ``variant_condition`` entries of one document for a variant.

    Args:
        data: The safe-loaded document content. It is never modified.
        context (VariantContext | None): The active variant, or ``None`` when the workspace has no variability, in
            which case every condition is false.
        root_presence (bool): Whether a condition at the root decides the presence of the document. ``False`` for the
            presence document of an ECU: its condition decides the presence of the ECU folder, which the loader checks
            before it reads the folder, so here it is only stripped.

    Returns:
        tuple: The resolved copy of the content (or :data:`ABSENT`) and the :class:`ResolutionTrace`.
    """

    trace = ResolutionTrace()
    if not root_presence and isinstance(data, dict) and VARIANT_CONDITION_KEY in data:
        trace.removed.add((VARIANT_CONDITION_KEY,))
        data = {key: value for key, value in data.items() if key != VARIANT_CONDITION_KEY}
    return _resolve(data, (), context, trace), trace


def document_condition(data: Any) -> object | None:
    """
    Return the presence condition written at the root of a document, or ``None`` when it has none.

    Args:
        data: The safe-loaded document content.
    """

    if isinstance(data, dict) and VARIANT_CONDITION_KEY in data:
        return data[VARIANT_CONDITION_KEY]
    return None


def document_present(data: Any, context: VariantContext | None) -> bool:
    """
    Whether a document is part of a variant: its root ``variant_condition`` holds, or it has none.

    Args:
        data: The safe-loaded document content.
        context (VariantContext | None): The active variant; ``None`` makes every condition false.
    """

    condition = document_condition(data)
    return condition is None or _holds(context, condition)


# endregion

# region findings

_CONDITION = "condition"
"""Kind of a ``variant_condition`` found by :func:`_variation_points`."""

_VALUES = "values"
"""Kind of an (unsupported) ``variant_values`` found by :func:`_variation_points`."""


def _detail(error: PydanticCustomError, loc: YamlPath, uri: str) -> ErrorDetails:
    """Locate ``error`` at ``loc`` in the document ``uri``."""

    return error_details_from(error, loc=loc, yaml_path=uri)


def _variation_points(data: Any, path: YamlPath = ()) -> Iterator[tuple[str, YamlPath, Any]]:
    """
    Yield every variation point of a document as ``(kind, path, payload)``, in document order.

    ``kind`` is ``"condition"`` (payload: the condition) or ``"values"`` (payload: the ``variant_values`` content, which
    is not looked into).
    """

    if isinstance(data, dict):
        yield from _mapping_variation_points(data, path)
    elif isinstance(data, list):
        for index, item in enumerate(data):
            yield from _variation_points(item, path + (index,))


def _mapping_variation_points(data: dict[Any, Any], path: YamlPath) -> Iterator[tuple[str, YamlPath, Any]]:
    """Yield the variation points of a mapping: its own condition or ``variant_values`` keys, and those nested in its values."""

    kinds = {VARIANT_CONDITION_KEY: _CONDITION, VARIANT_VALUES_KEY: _VALUES}
    for key, value in data.items():
        if key in kinds:
            yield kinds[key], path + (key,), value
        else:
            yield from _variation_points(value, path + (key,))


def _condition_problem(text: object, symbols: SymbolTable) -> str | None:
    """Why ``text`` is not a valid condition for ``symbols``, or ``None`` when it is."""

    try:
        condition = compile_condition(text)
    except ConditionSyntaxError as exc:
        return exc.reason
    problems = symbols.problems(condition)
    return "; ".join(problems) if problems else None


def lint_document(uri: str, data: Any, symbols: SymbolTable | None, contexts: Sequence[VariantContext], role: DocumentRole) -> list[ErrorDetails]:
    """
    Check the variation points of a document, independently of the active variant.

    Args:
        uri (str): Workspace-relative document id.
        data: The safe-loaded document content.
        symbols (SymbolTable | None): Names declared by the feature model, or ``None`` when the workspace has no variability.
        contexts (Sequence[VariantContext]): Every declared variant, used to find conditions that never hold.
        role (DocumentRole): Where the document lies in the workspace, which decides the variation points it may have.

    Returns:
        list[ErrorDetails]: The findings, located by their path in the original document.
    """

    points = list(_variation_points(data))
    if not points:
        return []
    document_finding = _document_finding(uri, points[0][1], symbols, role)
    if document_finding is not None:
        return [document_finding]
    assert symbols is not None  # a document without a symbol table was reported by _document_finding
    found: list[ErrorDetails] = []
    for kind, path, payload in points:
        misplaced = _placement_error(kind, path, role)
        if misplaced is not None:
            found.append(_detail(misplaced, path, uri))
        else:
            found.extend(_lint_condition(uri, path, payload, symbols, contexts))
    return found


def _document_finding(uri: str, first: YamlPath, symbols: SymbolTable | None, role: DocumentRole) -> ErrorDetails | None:
    """The finding for a document that must not have variation points at all, located at its first one (``first``)."""

    if role is DocumentRole.VARIABILITY or is_in_variability(uri):
        error = err_major(
            "The variability model itself cannot contain variation points ('{key}').",
            category=Category.STRUCTURAL,
            error_number="445",
            key=first[-1],
        )
        return _detail(error, first, uri)
    if symbols is None:
        error = err_major(
            "This document uses variation points ('{key}') but the workspace has no variability/ folder; "
            "they are resolved as if every condition were false.",
            category=Category.REQUIRED,
            error_number="444",
            key=first[-1],
        )
        return _detail(error, first, uri)
    return None


def _placement_error(kind: str, path: YamlPath, role: DocumentRole) -> PydanticCustomError | None:
    """The error for a variation point that is not allowed where it is written, or ``None`` when it is allowed there."""

    if kind == _VALUES:
        error = err_major(
            "variant_values is not supported: an element that differs between variants is a separate element. Model each "
            "alternative as its own ECU or system topology entry, with a variant_condition that selects it.",
            category=Category.STRUCTURAL,
            error_number="486",
        )
    elif _condition_allowed(path, role):
        error = None
    else:
        error = _misplaced_condition_error(role)
    return error


def _condition_allowed(path: YamlPath, role: DocumentRole) -> bool:
    """Whether a ``variant_condition`` at ``path`` is in one of its two places: an ECU's presence document root, or a topology entry."""

    if role is DocumentRole.ECU_PRESENCE:
        return path == (VARIANT_CONDITION_KEY,)
    return role is DocumentRole.SYSTEM_TOPOLOGY and len(path) > 1 and isinstance(path[-2], int)


def _misplaced_condition_error(role: DocumentRole) -> PydanticCustomError:
    """The error for a ``variant_condition`` written where the document of ``role`` does not allow it."""

    if role in (DocumentRole.ECU, DocumentRole.ECU_PRESENCE):
        return err_major(
            "An ECU cannot contain a variant_condition here: an ECU is the same in every variant it is part of. Model an ECU "
            "that differs between variants as a separate ECU, and decide which variants each one is part of with a "
            "variant_condition at the root of its ecu_metadata.",
            category=Category.STRUCTURAL,
            error_number="483",
        )
    if role is DocumentRole.SYSTEM_TOPOLOGY:
        return err_major(
            "In the system topology a variant_condition can only be written on an entry of a list, such as a connection or a "
            "node of a multidrop segment.",
            category=Category.STRUCTURAL,
            error_number="484",
        )
    return err_major(
        "This document is the same in every variant and cannot contain a variant_condition. Variants differ only in their "
        "ECUs (a variant_condition at the root of an ECU's ecu_metadata) and in the entries of the system topology (topology/).",
        category=Category.STRUCTURAL,
        error_number="485",
    )


def _lint_condition(uri: str, path: YamlPath, text: object, symbols: SymbolTable, contexts: Sequence[VariantContext]) -> list[ErrorDetails]:
    """Check one condition: its syntax and names, then whether it holds in at least one declared variant."""

    problem = _condition_problem(text, symbols)
    if problem is not None:
        error = err_major(
            "Invalid variant condition '{expression}': {reason}.",
            category=Category.FORMAT,
            error_number="438",
            expression=text,
            reason=problem,
        )
        return [_detail(error, path, uri)]
    if contexts and not any(context.holds(text) for context in contexts):
        with collect_warnings() as warnings:
            warn(
                f"Variant condition '{text}' is false in every declared variant, so this element is never used.",
                category=Category.CONSISTENCY,
                error_number="446",
            )
        return [_locate_warning(warning, path, uri) for warning in warnings]
    return []


def _locate_warning(warning: ErrorDetails, loc: YamlPath, uri: str) -> ErrorDetails:
    """Locate a collected warning at ``loc`` in the document ``uri``."""

    warning["loc"] = loc
    ctx = dict(warning.get("ctx") or {})
    ctx.setdefault("yaml_path", uri)
    warning["ctx"] = ctx
    return warning


def no_variant_selected_error(available: Sequence[str]) -> ErrorDetails:
    """Finding for a variant workspace loaded without a variant and without ``default_variant``."""

    error = err_fatal(
        "The workspace declares variants but none was selected and the feature model has no default_variant; select one of: {available}.",
        category=Category.REQUIRED,
        error_number="448",
        available=", ".join(available),
    )
    return _detail(error, (), FEATURE_MODEL_DOCUMENT)


def unknown_variant_error(variant: str, available: Sequence[str]) -> ErrorDetails:
    """Finding for a selected variant that is not declared."""

    error = err_fatal(
        "Variant '{variant}' is not declared; available variants: {available}.",
        category=Category.REFERENCE,
        error_number="449",
        variant=variant,
        available=", ".join(available) or "none",
    )
    return _detail(error, (), FEATURE_MODEL_DOCUMENT)


def invalid_variability_error() -> ErrorDetails:
    """Finding for a ``variability/`` folder whose model could not be loaded, so no variant can be resolved."""

    error = err_fatal(
        "The variability model could not be loaded, so the workspace cannot be resolved for a variant; fix the errors in variability/ first.",
        category=Category.STRUCTURAL,
        error_number="450",
    )
    return _detail(error, (), FEATURE_MODEL_DOCUMENT)


# endregion
