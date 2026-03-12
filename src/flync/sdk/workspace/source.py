from dataclasses import dataclass


@dataclass(frozen=True)
class Position:
    """Represents a position in a text document.

    Attributes:
        line (int): Zero-based line number.
        character (int): Zero-based character offset.
    """

    line: int
    character: int


@dataclass(frozen=True)
class Range:
    """Represents a range between two positions in a document.

    Attributes:
        start (Position): The start position of the range.
        end (Position): The end position of the range.
    """

    start: Position
    end: Position


@dataclass(frozen=True)
class SourceRef:
    """Reference to the source location of a semantic object.

    Attributes:
        uri (str): Document URI where the object is defined.
        range (Range): The range within the document.
    """

    uri: str
    range: Range
