from dataclasses import dataclass


@dataclass(frozen=True)
class Position:
    """Represents a position in a text document.

    For objects backed by a YAML file both ``line`` and ``character`` are
    **1-based**, derived from ruamel.yaml ``start_mark`` / ``end_mark`` by
    adding 1 to the 0-based mark offsets.

    For objects that have no YAML source (e.g. implied or externally loaded
    objects without a resolved file) both fields are **0**, acting as a
    sentinel meaning *"no location available"*.

    Attributes:
        line (int): 1-based line number, or 0 when no source is available.
        character (int): 1-based character offset, or 0 when no source is
            available.
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
