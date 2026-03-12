"""
Shared type variables for the FLYNC SDK.

Provides common type aliases used across SDK modules.
"""

from pathlib import Path
from typing import TypeAlias

PathType: TypeAlias = Path | str
"""A type alias that accepts either a :class:`pathlib.Path` or a plain
:class:`str`."""
