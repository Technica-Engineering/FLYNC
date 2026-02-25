"""
Configuration module for FLYNC SDK.

Provides a simple configuration object.
"""

from dataclasses import dataclass, field

DEFAULT_EXTENSION = ".flync.yaml"


@dataclass(frozen=True)
class WorkspaceConfiguration:
    """
    Configuration object for the FLYNC SDK.
    """

    flync_file_extension: str = DEFAULT_EXTENSION
    allowed_extensions: set[str] = field(
        default_factory=lambda: {DEFAULT_EXTENSION, ".flync.yml"}
    )
    exclude_unset: bool = True
