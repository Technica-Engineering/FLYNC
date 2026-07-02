"""Helper for working with YAML documents."""

import threading
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from flync.sdk.utils.sdk_types import PathType


class Document(object):
    """
    Represents a YAML document with parsing capabilities.

    Attributes:
        uri (str): The unique identifier for the document.

        text (str): The raw YAML content.

        ast (Any | None): The parsed abstract syntax tree, or None if not parsed.

        compose_ast (Any | None): The composed ruamel.yaml AST used for source-position tracking, or None if not parsed.
    """

    _yaml_local = threading.local()

    def __init__(self, uri: PathType, text: str, needs_compose: bool):
        """
        Initialize a Document instance.

        Args:
            uri (str): The document's URI.
            text (str): The raw YAML text.
        """

        self.uri: PathType = uri
        self.text = text
        self.needs_compose = needs_compose
        self.ast: Any | None = None
        self.compose_ast = None
        # ruamel.yaml YAML instances are not thread-safe: they store
        # per-parse composer state on the instance itself. Each Document
        # owns its own instance so concurrent parses in different threads
        # never share state.
        self._yaml = None

    def parse(self):
        """
        Parse the YAML text into an abstract syntax tree.

        Sets :attr:`ast` via ``yaml.load`` and :attr:`compose_ast` via ``yaml.compose``, both derived from :attr:`text`.

        Returns: None
        """
        if self._yaml is None:
            self._yaml = self.get_yaml(self.needs_compose)

        self.ast, self.compose_ast = self.parse_text(self._yaml, self.text, self.needs_compose)

    def update_text(self, text: str):
        """
        Update the document's text and re-parse it.

        Args:
            text (str): The new YAML content.

        Returns: None
        """

        self.text = text
        self.parse()

    def assign_ast(self, ast, compose_ast):
        """
        Assign parsed YAML structures to the Document instance.

        Args:
            ast: Parsed YAML object tree.
            compose_ast: Composed YAML node tree (optional, used for object maps).
        """
        self.ast = ast
        self.compose_ast = compose_ast

    @classmethod
    def parse_text(cls, yaml: YAML, text: str, needs_compose: bool):
        """
        Parse YAML text into AST and optionally a composed AST.

        Args:
            yaml (YAML): ruamel.yaml parser instance.
            text (str): YAML source text.
            needs_compose (bool): Whether to also produce a composed AST.

        Returns:
            tuple: (ast, compose_ast) where compose_ast may be None.
        """
        ast = yaml.load(text)
        compose_ast = yaml.compose(text) if needs_compose else None
        return ast, compose_ast

    @classmethod
    def _get_yaml_safe(cls):
        """
        Get or initialize a thread-local safe YAML parser.

        Returns:
            YAML: A ruamel.yaml safe parser instance.
        """
        if not hasattr(cls._yaml_local, "yaml"):
            cls._yaml_local.yaml = YAML(typ="safe")
        return cls._yaml_local.yaml

    @classmethod
    def get_yaml(cls, needs_compose: bool):
        """
        Create a YAML parser instance appropriate for parsing.

        Args:
            needs_compose (bool): If True, use 'rt' type for composer state.
                                  Otherwise, use a thread-local safe parser.

        Returns:
            YAML: Configured ruamel.yaml parser with preserved quotes.
        """
        yaml = YAML(typ="rt") if needs_compose else Document._get_yaml_safe()
        yaml.preserve_quotes = True
        return yaml

    @classmethod
    def normalize_uri(cls, uri: PathType, ws_root: Path | None) -> str:
        """
        Normalize a file URI relative to the workspace root.

        Args:
            uri (Path): File path to normalize.
            ws_root (Path): Workspace root path.

        Returns:
            str: Normalized URI as POSIX-style string.
        """
        if isinstance(uri, str):
            uri = Path(uri)
        if uri.is_absolute():
            uri = uri.relative_to(ws_root)  # type: ignore[arg-type]
        return uri.as_posix()


def read_file(path: PathType) -> tuple[Path, str] | None:
    """
    Read a file as UTF-8 text.

    Args:
        path (PathType): Path to the file.

    Returns:
        tuple[Path, str] | None: (Path, file contents) if successful, None if file cannot be read.
    """
    try:
        with open(path, "r", encoding="utf-8") as direct_data:
            text = direct_data.read()
            return Path(path), text
    except:  # noqa: E722  # NOSONAR
        pass
    return None


def parse_document(path: Path, text: str, ws_root: Path, needs_compose: bool) -> tuple:
    """
    Worker function to parse a YAML document.

    Args:
        path (Path): Path to the YAML file.
        text (str): YAML source text.
        ws_root (Path): Workspace root for URI normalization.
        needs_compose (bool): Whether to produce a composed AST.

    Returns:
        tuple: (normalized_uri, ast, compose_ast, text)
    """
    _yaml = Document.get_yaml(needs_compose)
    ast, compose_ast = Document.parse_text(_yaml, text, needs_compose)
    return Document.normalize_uri(path, ws_root), ast, compose_ast, text
