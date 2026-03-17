from typing import Any

from ruamel.yaml import YAML

from flync.sdk.utils.sdk_types import PathType

yaml = YAML(typ="rt")
yaml.preserve_quotes = True


class Document(object):
    """Represents a YAML document with parsing capabilities.

    Attributes:
        uri (str): The unique identifier for the document.

        text (str): The raw YAML content.

        ast (Any | None): The parsed abstract syntax tree, or \
        None if not parsed.

        compose_ast (Any | None): The composed ruamel.yaml AST used for
        source-position tracking, or None if not parsed.
    """

    def __init__(self, uri: PathType, text: str, needs_compose: bool):
        """Initialize a Document instance.

        Args:
            uri (str): The document's URI.
            text (str): The raw YAML text.
        """
        self.uri: PathType = uri
        self.text = text
        self.needs_compose = needs_compose
        self.ast: Any | None = None
        self.compose_ast = None

    def parse(self):
        """Parse the YAML text into an abstract syntax tree.

        Sets :attr:`ast` via ``yaml.load`` and :attr:`compose_ast` via
        ``yaml.compose``, both derived from :attr:`text`.

        Returns: None
        """
        self.ast = yaml.load(self.text)
        # only needed for object maps, so can be ignored otherwise
        if self.needs_compose:
            self.compose_ast = yaml.compose(self.text)

    def update_text(self, text: str):
        """Update the document's text and re-parse it.

        Args:
            text (str): The new YAML content.

        Returns: None
        """
        self.text = text
        self.parse()
