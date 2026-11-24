"""Click parameter types and field helpers for the flync_converter front-ends."""

import enum
import json
import types
from collections.abc import Mapping, Sequence
from typing import Any, Type, Union, get_args, get_origin

import click
from pydantic_core import PydanticUndefined

from flync_converter.utils import cast_value


class _EnumNameType(click.ParamType):
    """Click param type that accepts an enum member by name."""

    def __init__(self, enum_cls: Type[enum.Enum]) -> None:
        self.enum_cls = enum_cls
        self.name = enum_cls.__name__

    def get_metavar(self, param, ctx=None) -> str:
        """Return the metavar string listing valid enum member names."""
        return "[" + "|".join(m.name for m in self.enum_cls) + "]"

    def convert(self, value, param, ctx):
        """Convert a string value to the corresponding enum member, failing with choices on error."""
        if isinstance(value, self.enum_cls):
            return value
        try:
            return self.enum_cls[value]
        except KeyError:
            choices = [m.name for m in self.enum_cls]
            self.fail(
                f"{value!r} is not one of {choices}",
                param,
                ctx,
            )


class _JsonParamType(click.ParamType):
    """Click param type that parses a JSON object or array from the command line.

    Args:
        kind: ``"object"`` or ``"array"`` to reject the other JSON kind;
            ``None`` accepts both.
    """

    name = "json"

    def __init__(self, kind: str | None = None) -> None:
        self.kind = kind

    def get_metavar(self, param, ctx=None) -> str:
        """Return the metavar matching the expected JSON kind."""
        if self.kind == "object":
            return "{...}"
        if self.kind == "array":
            return "[...]"
        return "JSON"

    def convert(self, value, param, ctx):
        """Parse a JSON string into a dict or list; an empty string means unset."""
        if value is None or not isinstance(value, str):
            return value
        text = value.strip()
        if not text:
            return None
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            self.fail(f"invalid JSON ({exc.msg} at line {exc.lineno} column {exc.colno})", param, ctx)
        if self.kind == "object" and not isinstance(parsed, dict):
            self.fail('expected a JSON object, e.g. \'{"Package": {"Sub": "Name"}}\'', param, ctx)
        if self.kind == "array" and not isinstance(parsed, list):
            self.fail('expected a JSON array, e.g. \'["first", "second"]\'', param, ctx)
        return parsed


def _json_kind(annotation: Any) -> str | None:
    """Return ``"object"`` or ``"array"`` for a mapping or sequence annotation.

    Args:
        annotation: Pydantic field annotation, optionally still wrapped in ``Optional``.

    Returns:
        The JSON kind the annotation maps to, or ``None`` for scalar annotations.
    """
    origin = get_origin(annotation)
    if origin is Union or origin is types.UnionType:
        inner_args = [a for a in get_args(annotation) if a is not type(None)]
        annotation = inner_args[0] if inner_args else str
        origin = get_origin(annotation)
    target = origin if isinstance(origin, type) else annotation
    if not isinstance(target, type) or issubclass(target, (str, bytes, bytearray)):
        kind = None
    elif issubclass(target, Mapping):
        kind = "object"
    elif issubclass(target, (Sequence, set, frozenset)):
        kind = "array"
    else:
        kind = None
    return kind


def field_default(fld: Any) -> Any:
    """Return a config field's default, evaluating ``default_factory``.

    ``PydanticUndefined`` (a required field or a factory that pydantic does not
    evaluate) is mapped to ``None`` so it is never stringified into a prompt,
    label or help text as the literal text ``"PydanticUndefined"``.

    Args:
        fld: Pydantic field info of the config field.

    Returns:
        The default value, or ``None`` when the field has no usable default.
    """
    if fld.is_required():
        return None
    try:
        default = fld.get_default(call_default_factory=True)
    except TypeError:
        default = fld.get_default()
    return None if default is PydanticUndefined else default


def format_default(default: Any) -> str | None:
    """Return the display text of a field default, JSON-encoding containers.

    Args:
        default: Default value of the field.

    Returns:
        The default as text, or ``None`` when there is no default.
    """
    if default is None:
        return None
    if isinstance(default, enum.Enum):
        text = default.name
    elif isinstance(default, (dict, list, tuple)):
        text = json.dumps(default)
    else:
        text = str(default)
    return text


def parse_field_input(name: str, raw: str, field_type: Any) -> Any:
    """Parse the raw text of a structured or scalar config field.

    Args:
        name: Config field name, used in the error message.
        raw: Raw text entered in the form.
        field_type: Field annotation, already unwrapped from ``Optional``.

    Returns:
        A dict or list for JSON fields, a cast scalar otherwise.

    Raises:
        ValueError: The text is not valid JSON for a mapping or sequence field.
    """
    if _json_kind(field_type) is None:
        return cast_value(raw, field_type)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{name}: invalid JSON ({exc.msg} at line {exc.lineno} column {exc.colno})") from exc


def _annotation_to_click_type(annotation):  # NOSONAR
    """Map a pydantic field annotation to a Click param type.

    Args:
        annotation: Pydantic field annotation, possibly ``Optional`` and possibly a
            mapping or sequence.

    Returns:
        A Click param type: ``BOOL``/``INT``/``FLOAT`` for scalars, an enum-name type
        for enums, a JSON type for mappings and sequences, and ``STRING`` otherwise.
    """
    origin = get_origin(annotation)
    if origin is Union or origin is types.UnionType:
        inner_args = [a for a in get_args(annotation) if a is not type(None)]
        annotation = inner_args[0] if inner_args else str
    json_kind = _json_kind(annotation)
    if json_kind is not None:
        return _JsonParamType(json_kind)
    if isinstance(annotation, type):
        if issubclass(annotation, bool):
            return click.BOOL
        if issubclass(annotation, int):
            return click.INT
        if issubclass(annotation, float):
            return click.FLOAT
        if issubclass(annotation, enum.Enum):
            return _EnumNameType(annotation)
    return click.STRING
