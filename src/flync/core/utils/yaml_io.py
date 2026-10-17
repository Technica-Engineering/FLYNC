"""
Plain-data YAML loading and dumping on top of ``ruamel.yaml``.

ruamel.yaml is the project's single YAML library. These helpers cover the places that only need to turn YAML text into plain Python
data (or back) and do not need round-trip features such as comments, positions or preserved quotes.
"""

from io import StringIO
from typing import IO, Any

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

__all__ = ["YAMLError", "safe_load", "safe_dump"]


def safe_load(stream: str | IO[str]) -> Any:
    """Parse ``stream`` (text or an open file) into plain Python data. An empty document yields ``None``."""
    return YAML(typ="safe").load(stream)


def safe_dump(data: Any, stream: IO[str] | None = None) -> str | None:
    """
    Serialize ``data`` as block-style YAML, keeping mapping order and non-ASCII characters.

    Writes to ``stream`` when given; otherwise returns the YAML text.
    """
    yaml = YAML(typ="safe", pure=True)
    yaml.default_flow_style = False
    yaml.allow_unicode = True
    if stream is not None:
        yaml.dump(data, stream)
        return None
    out = StringIO()
    yaml.dump(data, out)
    return out.getvalue()
