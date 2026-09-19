"""
Utilities for exporting the FLYNC model as JSON Schema.

Splits the schema of a root Pydantic model class (usually ``FLYNCModel``) into one JSON Schema document
per class. Every Pydantic model class reachable from the root, and every enum or named type Pydantic
emits a definition for, gets its own document.
Cross references point at sibling files (``"$ref": "ECU.schema.json"``) instead of the ``#/$defs``
section of a single bundled document.

Field descriptions are taken from ``Field(description=...)`` when set, and otherwise from the numpydoc
``Parameters`` section of the class docstring.
"""

import inspect
import json
import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel
from pydantic.json_schema import GenerateJsonSchema, JsonSchemaValue
from pydantic_core import core_schema

# The draft Pydantic generates for, stamped as ``$schema`` on every document.
JSON_SCHEMA_DIALECT = GenerateJsonSchema.schema_dialect
DEFAULT_SCHEMA_SUFFIX = ".schema.json"

_SECTION_HEADER = re.compile(r"^(?P<title>\S[^\n]*)\n-{3,}[ \t]*$", re.MULTILINE)
_PARAMETER_ENTRY = re.compile(r"^(?P<names>\w+(?:\s*,\s*\w+)*)\s*(?::|$)")
_RST_ROLE = re.compile(r":\w+(?::\w+)?:`(?P<target>[^`]+)`")
_DOCSTRING_ONLY_SECTIONS = ("Parameters", "Private Attributes")


def _plain_text(text: str) -> str:
    """
    Turn the reStructuredText markup of a docstring into Markdown friendly text.

    Roles such as ``:class:`~flync.model.flync_4_ecu.port.ECUPort``` become the short target name, and double
    backtick literals become single backtick code spans.

    Args:
        text (str): Docstring text.

    Returns:
        str: The text without reStructuredText roles.
    """

    def _role(match: re.Match[str]) -> str:
        """
        Return the plain text shown for one reStructuredText role.

        ``:ref:`text <target>``` yields ``text``, ``:class:`~pkg.module.Name``` yields ``Name``, and any other
        target is returned unchanged.

        Args:
            match (re.Match[str]): A match of ``_RST_ROLE``.

        Returns:
            str: The text replacing the role.
        """

        target = match.group("target")
        if "<" in target:
            return target.split("<", 1)[0].strip()
        if target.startswith("~"):
            return target.rsplit(".", 1)[-1]
        return target

    return _RST_ROLE.sub(_role, text).replace("``", "`")


def _docstring_sections(docstring: str) -> tuple[str, dict[str, str]]:
    """
    Split a numpydoc docstring into its introduction and its underlined sections.

    Args:
        docstring (str): The cleaned docstring.

    Returns:
        tuple[str, dict[str, str]]: The text before the first section, and each section body keyed by its title.
    """

    headers = list(_SECTION_HEADER.finditer(docstring))
    if not headers:
        return docstring, {}
    sections = {}
    for index, header in enumerate(headers):
        end = headers[index + 1].start() if index + 1 < len(headers) else len(docstring)
        sections[header.group("title").strip()] = docstring[header.end() : end]
    return docstring[: headers[0].start()], sections


def _parameter_descriptions(section: str) -> dict[str, str]:
    """
    Parse the body of a numpydoc ``Parameters`` section.

    An entry starts with an unindented ``name : type`` line and its description is the indented block below it.
    Unindented lines that do not start an entry continue the type and are skipped.

    Args:
        section (str): The section body.

    Returns:
        dict[str, str]: Description per parameter name, with paragraphs separated by a blank line.
    """

    blocks: dict[str, list[str]] = {}
    current: list[str] = []
    for line in section.splitlines():
        entry = _PARAMETER_ENTRY.match(line)
        if entry:
            current = []
            for name in entry.group("names").split(","):
                blocks[name.strip()] = current
        elif line.strip() and line[0].isspace():
            current.append(line.strip())
        elif not line.strip():
            current.append("")

    descriptions = {}
    for name, block in blocks.items():
        paragraphs = "\n".join(block).split("\n\n")
        text = "\n\n".join(" ".join(paragraph.split()) for paragraph in paragraphs if paragraph.strip())
        if text:
            descriptions[name] = _plain_text(text)
    return descriptions


def _model_docstring(cls: type[BaseModel]) -> tuple[str | None, dict[str, str]]:
    """
    Read the model description and the field descriptions from the docstrings of a model and its bases.

    Args:
        cls (type[BaseModel]): The model class.

    Returns:
        tuple[str | None, dict[str, str]]: The model description without its ``Parameters`` and ``Private Attributes``
        sections (``None`` when the class has no docstring of its own), and the description per field name.
    """

    fields: dict[str, str] = {}
    for base in reversed(cls.__mro__):
        docstring = base.__dict__.get("__doc__")
        if issubclass(base, BaseModel) and docstring:
            _, sections = _docstring_sections(inspect.cleandoc(docstring))
            fields.update(_parameter_descriptions(sections.get("Parameters", "")))

    docstring = cls.__dict__.get("__doc__")
    if not docstring:
        return None, fields
    intro, sections = _docstring_sections(inspect.cleandoc(docstring))
    kept = [f"{title}\n{'-' * len(title)}\n{body.strip()}" for title, body in sections.items() if title not in _DOCSTRING_ONLY_SECTIONS]
    description = "\n\n".join(part for part in [intro.strip(), *kept] if part)
    return _plain_text(description), fields


class DocstringJsonSchema(GenerateJsonSchema):
    """JSON Schema generator that documents model fields from the numpydoc ``Parameters`` section of the class docstring."""

    def model_schema(self, schema: core_schema.ModelSchema) -> JsonSchemaValue:
        """
        Generate the schema of a model and fill in its descriptions from the docstring.

        Args:
            schema (core_schema.ModelSchema): The core schema of the model.

        Returns:
            JsonSchemaValue: The model schema with the model description and the field descriptions.
        """

        json_schema = super().model_schema(schema)
        cls = schema["cls"]
        description, field_descriptions = _model_docstring(cls)
        if description:
            json_schema["description"] = description
        elif description == "":
            json_schema.pop("description", None)

        properties = json_schema.get("properties", {})
        for name, field in cls.model_fields.items():
            if field.description or name not in field_descriptions:
                continue
            keys = [name, field.alias, field.serialization_alias, field.validation_alias]
            key = next((key for key in keys if isinstance(key, str) and key in properties), None)
            if key is not None:
                properties[key].setdefault("description", field_descriptions[name])
        return json_schema


def schema_file_name(model_name: str, suffix: str = DEFAULT_SCHEMA_SUFFIX) -> str:
    """
    Return the file name of the schema document for a definition.

    Args:
        model_name (str): The definition name, as Pydantic uses it in ``$defs``.
        suffix (str): The file name suffix.

    Returns:
        str: The file name, e.g. ``"ECU.schema.json"``.
    """

    return f"{model_name}{suffix}"


def _stamp(schema: dict[str, Any], file_name: str, base_uri: str | None) -> dict[str, Any]:
    """
    Prepend the ``$schema`` dialect and, when a base URI is given, the ``$id`` to a schema.

    Args:
        schema (dict[str, Any]): The schema document body.
        file_name (str): The file name the document is written to.
        base_uri (str | None): URI the schema files are published under.

    Returns:
        dict[str, Any]: The stamped schema document.
    """

    header: dict[str, Any] = {"$schema": JSON_SCHEMA_DIALECT}
    if base_uri is not None:
        header["$id"] = f"{base_uri.rstrip('/')}/{file_name}"
    return {**header, **schema}


def build_model_schemas(
    root: type[BaseModel],
    *,
    suffix: str = DEFAULT_SCHEMA_SUFFIX,
    mode: Literal["validation", "serialization"] = "validation",
    by_alias: bool = True,
    base_uri: str | None = None,
) -> dict[str, dict[str, Any]]:
    """
    Build one JSON Schema document per Pydantic model class reachable from ``root``.

    Each document is self-contained apart from its ``$ref`` entries, which name the sibling file of
    the referenced definition. The documents therefore resolve correctly only when all of them are
    stored in the same directory (or published under the same ``base_uri``). Model and field descriptions are
    generated by :class:`DocstringJsonSchema`.

    Args:
        root (type[BaseModel]): The root model, e.g. ``FLYNCModel``.
        suffix (str): File name suffix of every schema document.
        mode (Literal["validation", "serialization"]): Whether the schemas describe validation input or serialization output.
        by_alias (bool): Whether field aliases are used as property names.
        base_uri (str | None): URI the schema files are published under. Sets an absolute ``$id`` of ``<base_uri>/<file name>``.

    Returns:
        dict[str, dict[str, Any]]: Schema documents keyed by file name. The root document comes first.

    Raises:
        ValueError: If the root model's name clashes with a different definition of the same name.
    """

    schema = root.model_json_schema(
        by_alias=by_alias, mode=mode, ref_template=schema_file_name("{model}", suffix), schema_generator=DocstringJsonSchema
    )
    definitions: dict[str, dict[str, Any]] = schema.pop("$defs", {})

    documents: dict[str, dict[str, Any]] = {}
    if set(schema) == {"$ref"}:
        # A recursive root is emitted as a definition itself, with the top level only pointing at it.
        root_file = schema["$ref"]
        documents[root_file] = _stamp(definitions.pop(root_file.removesuffix(suffix)), root_file, base_uri)
    else:
        if root.__name__ in definitions:
            raise ValueError(f"Root model name '{root.__name__}' clashes with another schema definition of the same name")
        root_file = schema_file_name(root.__name__, suffix)
        documents[root_file] = _stamp(schema, root_file, base_uri)

    for name, definition in definitions.items():
        file_name = schema_file_name(name, suffix)
        documents[file_name] = _stamp(definition, file_name, base_uri)
    return documents


def dump_model_schemas(
    root: type[BaseModel],
    output_dir: str | Path,
    *,
    suffix: str = DEFAULT_SCHEMA_SUFFIX,
    mode: Literal["validation", "serialization"] = "validation",
    by_alias: bool = True,
    base_uri: str | None = None,
    indent: int = 2,
) -> list[Path]:
    """
    Write one JSON Schema file per Pydantic model class reachable from ``root`` into ``output_dir``.

    See :func:`build_model_schemas` for the layout of the documents. Existing files with the same
    names are overwritten; other files in ``output_dir`` are left untouched.

    Example:
        .. code-block:: python

            from flync.model import FLYNCModel
            from flync.sdk.utils.model_schema import dump_model_schemas

            paths = dump_model_schemas(FLYNCModel, "schemas")
            print(paths[0])  # schemas/FLYNCModel.schema.json

    Args:
        root (type[BaseModel]): The root model, e.g. ``FLYNCModel``.
        output_dir (str | Path): Directory the schema files are written to. Created if missing.
        suffix (str): File name suffix of every schema file.
        mode (Literal["validation", "serialization"]): Whether the schemas describe validation input or serialization output.
        by_alias (bool): Whether field aliases are used as property names.
        base_uri (str | None): URI the schema files are published under, used for ``$id``.
        indent (int): JSON indentation.

    Returns:
        list[Path]: The written files, root schema first.
    """

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    documents = build_model_schemas(root, suffix=suffix, mode=mode, by_alias=by_alias, base_uri=base_uri)

    paths = []
    for file_name, document in documents.items():
        path = output / file_name
        path.write_text(json.dumps(document, indent=indent, ensure_ascii=False) + "\n", encoding="utf-8")
        paths.append(path)
    return paths
