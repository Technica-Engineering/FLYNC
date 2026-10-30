"""Helper for working with YAML documents."""

from pathlib import Path
from typing import Any

from flync.core.utils import yaml_io
from flync.sdk.utils.sdk_types import PathType


class Document(object):
    """
    Represents a YAML document with parsing capabilities.

    Attributes:
        uri (str): The unique identifier for the document.

        text (str): The raw YAML content.

        ast (Any | None): The parsed abstract syntax tree, or None if not parsed.

        compose_ast (Any | None): The composed YAML node tree used for source-position tracking, or None if not parsed.
        needs_compose (bool): Whether to produce a composed AST.
    """

    def __init__(self, uri: PathType, text: str, needs_compose: bool):
        """
        Initialize a Document instance.

        Args:
            uri (str): The document's URI.
            text (str): The raw YAML text.
            needs_compose (bool): Whether to produce a composed AST for source tracking.
        """

        self.uri: PathType = uri
        self.needs_compose = needs_compose
        self.ast: Any | None = None
        self.compose_ast = None
        self.text: str = text

    def parse(self):
        """
        Parse the YAML text into an abstract syntax tree.

        Sets :attr:`ast` via ``yaml_io.safe_load`` and :attr:`compose_ast` via ``compose``, both derived from :attr:`text`.

        Returns: None
        """
        self.ast, self.compose_ast = self._parse_text(self.text, self.needs_compose)

    def update_text(self, text: str):
        """
        Update the document's text and re-parse it.

        Args:
            text (str): The new YAML content.

        Returns: None
        """

        self.text = text
        self.parse()

    def source_nodes(self):
        """
        Return the composed YAML node tree of the document, composing it from :attr:`text` when it was not produced at parse time.

        Returns:
            The composed YAML node, or None when the text cannot be composed.
        """
        if self.compose_ast is None and self.text:
            try:
                self.compose_ast = yaml_io.compose(self.text)
            except Exception:
                return None
        return self.compose_ast

    @classmethod
    def _parse_text(cls, text: str, needs_compose: bool):
        """
        Parse YAML text into AST and optionally a composed AST.

        Args:
            text (str): YAML source text.
            needs_compose (bool): Whether to also produce a composed AST.

        Returns:
            tuple: (ast, compose_ast) where compose_ast may be None.
        """
        compose_ast = None
        if needs_compose:
            compose_ast = yaml_io.compose(text)
        ast = yaml_io.safe_load(text)
        return ast, compose_ast

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


def read_file(path: PathType) -> str:
    """
    Read a file as UTF-8 text.

    Args:
        path (PathType): Path to the file.

    Returns:
        str: File contents if successful, empty string if file cannot be read.
    """
    try:
        with open(path, "r", encoding="utf-8") as direct_data:
            return direct_data.read()
    except (OSError, UnicodeDecodeError):
        return ""
