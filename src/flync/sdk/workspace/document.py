from typing import Any

from ruamel.yaml import YAML

from flync.sdk.utils.sdk_types import PathType

yaml = YAML(typ="rt")
yaml.preserve_quotes = True


class Document:
    """Represents a YAML document with parsing capabilities.

    Attributes:
        uri (str): The unique identifier for the document.

        text (str): The raw YAML content.

        ast (Any | None): The parsed abstract syntax tree, or \
        None if not parsed.
    """

    def __init__(self, uri: PathType, text: str):
        """Initialize a Document instance.

        Args:
            uri (str): The document's URI.
            text (str): The raw YAML text.
        """
        self.uri = uri
        self.text = text
        self.ast: Any | None = None

    def parse(self):
        """Parse the YAML text into an abstract syntax tree.

        Returns: None
        """
        self.ast = yaml.load(self.text)

    def update_text(self, text: str):
        """Update the document's text and re-parse it.

        Args:
            text (str): The new YAML content.

        Returns: None
        """
        self.text = text
        self.parse()
