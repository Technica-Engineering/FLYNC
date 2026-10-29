"""
YAML loading, composing and dumping on top of ``PyYAML`` (with libyaml when available).

PyYAML implements YAML 1.1, whose implicit typing is hostile to configuration data: ``yes``/``no``/``on``/``off`` become booleans,
``0875`` an octal number and ``00:11:22:33:44:55`` a base-60 integer. The loader and dumper below therefore use the YAML 1.2 core
schema, raise on duplicate mapping keys and keep the mapping order. Every YAML access in the project goes through this module.
"""

import re
from collections.abc import Hashable
from typing import IO, Any

import yaml
from yaml.constructor import ConstructorError
from yaml.error import MarkedYAMLError, YAMLError
from yaml.nodes import MappingNode, Node
from yaml.parser import ParserError
from yaml.scanner import ScannerError

__all__ = ["YAMLError", "MarkedYAMLError", "ParserError", "ScannerError", "safe_load", "safe_dump", "compose"]

_BOOL_TAG = "tag:yaml.org,2002:bool"
_INT_TAG = "tag:yaml.org,2002:int"
_FLOAT_TAG = "tag:yaml.org,2002:float"
_MERGE_TAG = "tag:yaml.org,2002:merge"

_BOOL_RE = re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$")
_INT_RE = re.compile(r"^(?:[-+]?\d+|0o[0-7]+|0x[0-9a-fA-F]+)$", re.ASCII)
# The float rule is split into small expressions (all ASCII-only, so ``\d`` means 0-9); PyYAML tries them in order.
_FLOAT_RES = tuple(
    re.compile(pattern, re.ASCII)
    for pattern in (
        r"^[-+]?\d+\.\d*(?:[eE][-+]?\d+)?$",
        r"^[-+]?\d+[eE][-+]?\d+$",
        r"^\.\d+(?:[eE][-+]?\d+)?$",
        r"^(?:[-+]?\.(?:inf|Inf|INF)|\.(?:nan|NaN|NAN))$",
    )
)


def _implicit_resolvers() -> dict[str, list[tuple[str, re.Pattern[str]]]]:
    """PyYAML's implicit resolvers with the bool/int/float rules replaced by their YAML 1.2 core schema versions."""
    replaced = {_BOOL_TAG, _INT_TAG, _FLOAT_TAG}
    resolvers: dict[str, list[tuple[str, re.Pattern[str]]]] = {}
    for first, entries in yaml.resolver.Resolver.yaml_implicit_resolvers.items():
        kept = [(tag, regexp) for tag, regexp in entries if tag not in replaced]
        if kept:
            resolvers[first] = kept
    for first, tag, regexp in (
        ("tTfF", _BOOL_TAG, _BOOL_RE),
        ("-+0123456789", _INT_TAG, _INT_RE),
        *(("-+0123456789.", _FLOAT_TAG, float_re) for float_re in _FLOAT_RES),
    ):
        for char in first:
            resolvers.setdefault(char, []).append((tag, regexp))
    return resolvers


_IMPLICIT_RESOLVERS = _implicit_resolvers()

_BaseLoader: type = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
_BaseDumper: type = getattr(yaml, "CSafeDumper", yaml.SafeDumper)


class _Loader(_BaseLoader):
    """Safe loader: YAML 1.2 core schema, duplicate keys are an error."""

    yaml_implicit_resolvers = _IMPLICIT_RESOLVERS

    def construct_mapping(self, node: MappingNode, deep: bool = False) -> dict[Any, Any]:
        """Build the mapping, raising :class:`ConstructorError` when a key occurs twice (merge keys excluded)."""
        seen: set[Hashable] = set()
        for key_node, _ in node.value:
            if key_node.tag == _MERGE_TAG:
                continue
            key = self.construct_object(key_node, deep=True)
            if not isinstance(key, Hashable):
                continue
            if key in seen:
                raise ConstructorError("while constructing a mapping", node.start_mark, f"found duplicate key {key!r}", key_node.start_mark)
            seen.add(key)
        return super().construct_mapping(node, deep=deep)


def _construct_int(loader: _Loader, node: Node) -> int:
    """Construct a YAML 1.2 integer: decimal (leading zeros allowed), ``0o`` octal or ``0x`` hexadecimal."""
    value = str(loader.construct_scalar(node))
    digits = value.lstrip("+-")
    sign = -1 if value.startswith("-") else 1
    if digits.startswith("0o"):
        return sign * int(digits[2:], 8)
    if digits.startswith("0x"):
        return sign * int(digits[2:], 16)
    return sign * int(digits, 10)


_Loader.add_constructor(_INT_TAG, _construct_int)


class _Dumper(_BaseDumper):
    """Safe dumper sharing the loader's resolvers, so strings the loader would not read back as ``str`` get quoted."""

    yaml_implicit_resolvers = _IMPLICIT_RESOLVERS


def safe_load(stream: str | IO[str]) -> Any:
    """Parse ``stream`` (text or an open file) into plain Python data. An empty document yields ``None``."""
    return yaml.load(stream, Loader=_Loader)  # nosec B506 - _Loader is a safe loader


def compose(text: str) -> Node | None:
    """Compose ``text`` into a node tree whose ``start_mark`` / ``end_mark`` carry source positions (``None`` for an empty document)."""
    return yaml.compose(text, Loader=_Loader)


def safe_dump(data: Any, stream: IO[str] | None = None) -> str | None:
    """
    Serialize ``data`` as block-style YAML, keeping mapping order and non-ASCII characters.

    Writes to ``stream`` when given; otherwise returns the YAML text.
    """
    return yaml.dump(data, stream, Dumper=_Dumper, default_flow_style=False, allow_unicode=True, sort_keys=False)
