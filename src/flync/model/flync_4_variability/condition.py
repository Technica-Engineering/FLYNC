"""
The variant condition language.

A variant condition (a *presence condition* in product-line engineering terms) is a boolean expression
over the features of the feature model, for example
``remote_access and region in [eu, us] and not (release < r2)``. It decides whether a variation point
of the workspace is part of a product variant.

The text is parsed with :func:`ast.parse` in ``eval`` mode and the resulting tree is walked
against a strict whitelist, so nothing is ever evaluated by Python itself. The accepted grammar is:

- ``and``, ``or``, ``not``, and parentheses
- a boolean feature or a qualifier on its own: ``remote_access``
- a comparison of a feature with a value: ``region == eu``, ``region != cn``
- a membership test: ``region in [eu, us]``, ``region not in [cn]``
- an ordering test on an ``ordered`` feature: ``release >= r2``
- the literals ``true`` and ``false``

Values that are not identifiers (e.g. ``"r-2"``) must be quoted. Numbers are compared as text, so
``release >= 2027`` works when the feature declares ``values: [2026, 2027, 2028]``.
"""

import ast
import keyword
import operator
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Iterator, Mapping, Protocol

RESERVED_NAMES = frozenset({"true", "false"})
"""Identifiers that cannot be used as feature or qualifier names."""

_TRUE_NAMES = frozenset({"true", "True"})
_FALSE_NAMES = frozenset({"false", "False"})

_COMPARE_OPS: dict[type, str] = {
    ast.Eq: "==",
    ast.NotEq: "!=",
    ast.Lt: "<",
    ast.LtE: "<=",
    ast.Gt: ">",
    ast.GtE: ">=",
    ast.In: "in",
    ast.NotIn: "not in",
}
_EQUALITY_OPS = frozenset({"==", "!="})
_RANK_OPS = {"<": operator.lt, "<=": operator.le, ">": operator.gt, ">=": operator.ge}
_MEMBERSHIP_OPS = frozenset({"in", "not in"})
_ORDERING_OPS = frozenset({"<", "<=", ">", ">="})

ConditionValue = str | bool
"""A value a feature can hold: the text of an enumerated value, or ``True``/``False``."""


class ConditionSyntaxError(ValueError):
    """Raised for a condition that does not parse or uses a construct outside the condition language."""

    def __init__(self, expression: object, reason: str):
        self.expression = expression
        self.reason = reason
        super().__init__(f"invalid variant condition {expression!r}: {reason}")


def is_identifier(name: object) -> bool:
    """Return ``True`` when ``name`` can be used as a feature or qualifier name inside a condition."""

    return isinstance(name, str) and name.isidentifier() and not keyword.iskeyword(name) and name not in RESERVED_NAMES


# region expression tree


class Resolver(Protocol):
    """What a condition needs from its evaluation environment."""

    def truth(self, name: str) -> bool:
        """Truth value of a boolean feature or a qualifier."""

    def value_of(self, name: str) -> ConditionValue:
        """Current value of a feature."""

    def rank(self, name: str, value: ConditionValue) -> int:
        """Position of ``value`` in the declared order of the ordered feature ``name``."""


@dataclass(frozen=True)
class BoolConst:
    """The constant ``true`` or ``false``."""

    value: bool

    def evaluate(self, _resolver: Resolver) -> bool:
        """Return the constant."""
        return self.value


@dataclass(frozen=True)
class Ref:
    """A boolean feature or a qualifier used on its own."""

    name: str

    def evaluate(self, resolver: Resolver) -> bool:
        """Return the truth value of the referenced boolean feature or qualifier."""
        return resolver.truth(self.name)


@dataclass(frozen=True)
class Compare:
    """A comparison of a feature with one or more values."""

    name: str
    op: str
    values: tuple[ConditionValue, ...]

    def evaluate(self, resolver: Resolver) -> bool:
        """Compare the current value of :attr:`name` with :attr:`values`."""
        return self._compare(resolver.value_of(self.name), resolver)

    def _compare(self, current: ConditionValue, resolver: Resolver) -> bool:
        """Apply the operator to ``current`` and :attr:`values`; ordering operators compare the declared ranks."""

        if self.op in _MEMBERSHIP_OPS:
            return any(_same(current, value) for value in self.values) == (self.op == "in")
        if self.op in _EQUALITY_OPS:
            return _same(current, self.values[0]) == (self.op == "==")
        return _RANK_OPS[self.op](resolver.rank(self.name, current), resolver.rank(self.name, self.values[0]))


@dataclass(frozen=True)
class Not:
    """Negation of an operand."""

    operand: "Node"

    def evaluate(self, resolver: Resolver) -> bool:
        """Return the negated operand."""
        return not self.operand.evaluate(resolver)


@dataclass(frozen=True)
class AllOf:
    """Conjunction (``and``) of its operands."""

    operands: tuple["Node", ...]

    def evaluate(self, resolver: Resolver) -> bool:
        """Return ``True`` when every operand is true."""
        return all(operand.evaluate(resolver) for operand in self.operands)


@dataclass(frozen=True)
class AnyOf:
    """Disjunction (``or``) of its operands."""

    operands: tuple["Node", ...]

    def evaluate(self, resolver: Resolver) -> bool:
        """Return ``True`` when at least one operand is true."""
        return any(operand.evaluate(resolver) for operand in self.operands)


Node = BoolConst | Ref | Compare | Not | AllOf | AnyOf


def _same(current: ConditionValue, value: ConditionValue) -> bool:
    """Compare a feature value with a condition value, booleans by identity and everything else as text."""

    if isinstance(current, bool) or isinstance(value, bool):
        return isinstance(current, bool) and isinstance(value, bool) and current is value
    return str(current) == str(value)


def _iter_nodes(node: Node) -> Iterator[Node]:
    """Yield ``node`` and every node below it."""

    yield node
    if isinstance(node, Not):
        yield from _iter_nodes(node.operand)
    elif isinstance(node, (AllOf, AnyOf)):
        for operand in node.operands:
            yield from _iter_nodes(operand)


@dataclass(frozen=True)
class Condition:
    """
    A compiled variant condition.

    Attributes:
        expression (str): The source text of the condition.
        root (Node): The parsed expression tree.
    """

    expression: str
    root: Node = field(compare=False)

    def evaluate(self, resolver: Resolver) -> bool:
        """Evaluate the condition against ``resolver`` (normally a :class:`~flync.model.flync_4_variability.context.VariantContext`)."""
        return self.root.evaluate(resolver)

    def names(self) -> frozenset[str]:
        """Every feature or qualifier the condition refers to."""
        return frozenset(node.name for node in _iter_nodes(self.root) if isinstance(node, (Ref, Compare)))

    def refs(self) -> frozenset[str]:
        """The names used on their own (boolean features and qualifiers)."""
        return frozenset(node.name for node in _iter_nodes(self.root) if isinstance(node, Ref))


# endregion

# region parsing


def _value_atom(node: ast.expr, expression: str) -> ConditionValue:
    """Turn the right-hand side of a comparison into a value."""

    if isinstance(node, ast.Name):
        if node.id in _TRUE_NAMES:
            return True
        return False if node.id in _FALSE_NAMES else node.id
    if isinstance(node, ast.Constant) and isinstance(node.value, (bool, str, int, float)):
        return node.value if isinstance(node.value, bool) else str(node.value)
    raise ConditionSyntaxError(expression, f"unsupported value at column {node.col_offset + 1}")


def _walk_compare(node: ast.Compare, expression: str) -> Compare:
    """Translate a single (non-chained) comparison."""

    if len(node.ops) != 1 or len(node.comparators) != 1:
        raise ConditionSyntaxError(expression, f"chained comparisons are not supported (column {node.col_offset + 1})")
    op = _COMPARE_OPS.get(type(node.ops[0]))
    if op is None:
        raise ConditionSyntaxError(expression, f"unsupported comparison operator at column {node.col_offset + 1}")
    if not isinstance(node.left, ast.Name) or node.left.id in _TRUE_NAMES | _FALSE_NAMES:
        raise ConditionSyntaxError(expression, f"the left side of a comparison must be a feature name (column {node.col_offset + 1})")
    comparator = node.comparators[0]
    if op in _MEMBERSHIP_OPS:
        if not isinstance(comparator, (ast.List, ast.Tuple, ast.Set)) or not comparator.elts:
            raise ConditionSyntaxError(expression, f"'{op}' needs a non-empty list of values, e.g. [a, b] (column {comparator.col_offset + 1})")
        values = tuple(_value_atom(element, expression) for element in comparator.elts)
    else:
        values = (_value_atom(comparator, expression),)
    return Compare(node.left.id, op, values)


def _walk(node: ast.expr, expression: str) -> Node:
    """Translate a whitelisted Python expression node into the condition tree."""

    if isinstance(node, ast.BoolOp):
        operands = tuple(_walk(value, expression) for value in node.values)
        return AllOf(operands) if isinstance(node.op, ast.And) else AnyOf(operands)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return Not(_walk(node.operand, expression))
    return _walk_atom(node, expression)


def _walk_atom(node: ast.expr, expression: str) -> Node:
    """Translate a comparison, a name, or a boolean literal."""

    if isinstance(node, ast.Compare):
        return _walk_compare(node, expression)
    if isinstance(node, ast.Name):
        return BoolConst(node.id in _TRUE_NAMES) if node.id in _TRUE_NAMES | _FALSE_NAMES else Ref(node.id)
    if isinstance(node, ast.Constant) and isinstance(node.value, bool):
        return BoolConst(node.value)
    raise ConditionSyntaxError(expression, f"unsupported syntax at column {getattr(node, 'col_offset', 0) + 1}")


@lru_cache(maxsize=4096)
def _compile_text(expression: str) -> Condition:
    """Parse and translate ``expression``; cached on the expression text."""

    text = expression.strip()
    if not text:
        raise ConditionSyntaxError(expression, "the condition is empty")
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError as exc:
        raise ConditionSyntaxError(expression, f"invalid syntax at column {exc.offset or 1}") from None
    return Condition(expression, _walk(tree.body, expression))


def compile_condition(expression: object) -> Condition:
    """
    Compile a variant condition.

    Args:
        expression (str | bool): The condition text. A YAML boolean (``variant_condition: true``) is accepted as the literal.

    Returns:
        Condition: The compiled condition.

    Raises:
        ConditionSyntaxError: If the text does not parse or uses a construct outside the condition language.
    """

    if isinstance(expression, bool):
        return Condition(str(expression).lower(), BoolConst(expression))
    if not isinstance(expression, str):
        raise ConditionSyntaxError(expression, "a condition must be a string expression")
    return _compile_text(expression)


# endregion

# region semantic checks


@dataclass(frozen=True)
class FeatureSymbol:
    """
    What a condition may do with one feature.

    Attributes:
        name (str): The feature name.
        values (tuple[str, ...] | None): The declared values of an enumerated feature, or ``None`` for a boolean feature.
        ordered (bool): Whether ordering comparisons are allowed.
    """

    name: str
    values: tuple[str, ...] | None = None
    ordered: bool = False

    @property
    def is_boolean(self) -> bool:
        """Whether the feature is a boolean (on/off) feature."""
        return self.values is None


@dataclass(frozen=True)
class SymbolTable:
    """
    The names a condition may refer to.

    Attributes:
        features (Mapping[str, FeatureSymbol]): The declared features by name.
        qualifiers (Mapping[str, Condition]): The declared qualifiers (named conditions) by name.
    """

    features: Mapping[str, FeatureSymbol]
    qualifiers: Mapping[str, Condition] = field(default_factory=dict)

    def is_boolean_name(self, name: str) -> bool:
        """Whether ``name`` can be used on its own: a boolean feature or a qualifier."""
        feature = self.features.get(name)
        return name in self.qualifiers or (feature is not None and feature.is_boolean)

    def problems(self, condition: Condition) -> list[str]:
        """
        Return a description of every misuse of a name in ``condition``.

        An empty list means the condition only uses declared names, values, and operators that apply to them.
        """

        found: list[str] = []
        for node in _iter_nodes(condition.root):
            if isinstance(node, Ref):
                found.extend(self._ref_problems(node))
            elif isinstance(node, Compare):
                found.extend(self._compare_problems(node))
        return list(dict.fromkeys(found))

    def _ref_problems(self, node: Ref) -> list[str]:
        """The problem of a name used on its own, if it cannot be."""

        return [] if self.is_boolean_name(node.name) else [self._unusable_ref_problem(node.name)]

    def _unusable_ref_problem(self, name: str) -> str:
        """Why ``name`` cannot be used on its own."""

        feature = self.features.get(name)
        if feature is not None and feature.values:
            return f"feature '{name}' has values and must be compared, e.g. {name} == {feature.values[0]}"
        return f"unknown feature or qualifier '{name}'"

    def _compare_problems(self, node: Compare) -> list[str]:
        """The problems of a comparison, by what its left side names."""

        if node.name in self.qualifiers:
            return self._boolean_compare_problems(node, "qualifier")
        return self._feature_compare_problems(node)

    def _feature_compare_problems(self, node: Compare) -> list[str]:
        """The problems of a comparison with a feature."""

        feature = self.features.get(node.name)
        if feature is None:
            return [f"unknown feature '{node.name}'"]
        if feature.is_boolean:
            return self._boolean_compare_problems(node, "boolean feature")
        found = []
        if node.op in _ORDERING_OPS and not feature.ordered:
            found.append(f"'{node.op}' needs an ordered feature, but '{feature.name}' is not declared 'ordered: true'")
        for value in node.values:
            if isinstance(value, bool) or value not in (feature.values or ()):
                found.append(f"'{value}' is not a value of feature '{feature.name}' (values: {', '.join(feature.values or ())})")
        return found

    @staticmethod
    def _boolean_compare_problems(node: Compare, kind: str) -> list[str]:
        """The problems of a comparison with a boolean feature or a qualifier (``kind``)."""

        found = []
        if node.op not in _EQUALITY_OPS:
            found.append(f"'{node.op}' cannot be used with {kind} '{node.name}'; use it on its own or with == true/false")
        if any(not isinstance(value, bool) for value in node.values):
            found.append(f"{kind} '{node.name}' can only be compared with true or false")
        return found


# endregion
