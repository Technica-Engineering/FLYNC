"""
Configuration module for FLYNC SDK.

Provides a simple configuration object.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkspaceConfiguration:
    """
    Configuration object for the FLYNC SDK.
    """

    flync_file_extension: str = ".flync.yaml"
    exclude_unset: bool = True
