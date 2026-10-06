"""Base converter abstractions.

This module defines the abstract BaseConverter class used by concrete
converters to encode/decode between FLYNCModel and other representations.

The BaseConverter methods are documented in Google docstring style so that
IDE help and generated docs show parameter and return contracts clearly.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar, Optional

from flync.model import FLYNCModel

from .converter_config import ConverterConfig

"""Base classes for converters between :class:`FLYNCModel` and other
representations.

Provides abstract base class :class:`BaseConverter` defining the required
``encode`` and ``decode`` methods for concrete converter implementations.
"""


class BaseConverter(ABC):
    """Abstract base class defining the interface for converters.

    Converters convert between FLYNCModel instances and other representations.
    Concrete implementations must implement decode/encode and indicate whether
    they can decode a given source.

    Attributes:
        config (Optional[ConverterConfig]): Optional configuration for the
            converter.
        report_loggers (tuple[str, ...]): Loggers whose records belong to this
            converter: its own logger(s) and those of the libraries it
            delegates to. For every conversion the converter takes part in, as
            source or destination, they are written to
            ``<destination>/.flync/reports/<name>/logs.txt`` and to the shared
            ``reports/logs.txt``, and their level is adjusted for the duration
            of the conversion. Empty by default: the converter's records then
            reach the shared log only.
        report_dir (Optional[Path]): The converter's report folder,
            ``<destination>/.flync/reports/<name>``, set for the duration of a
            conversion so the converter can write its own report files there.
            ``None`` outside a conversion and when reporting is disabled.
    """

    name: str = ""
    uses_directory: bool = False
    source_extensions: tuple[str, ...] = ()
    destination_extensions: tuple[str, ...] = ()

    report_loggers: ClassVar[tuple[str, ...]] = ()

    report_dir: Optional[Path] = None

    @classmethod
    def get_source_extensions(cls) -> tuple[str, ...]:
        """Return source extensions, defaulting to the converter name."""
        return cls.source_extensions or ((cls.name,) if cls.name else ())

    @classmethod
    def get_destination_extensions(cls) -> tuple[str, ...]:
        """Return destination extensions, defaulting to the converter name."""
        return cls.destination_extensions or ((cls.name,) if cls.name else ())

    @classmethod
    def build_file_filter(cls, extensions: tuple[str, ...]) -> str:
        """Build a QFileDialog filter from converter metadata."""
        patterns = " ".join(f"*.{extension.lstrip('.')}" for extension in extensions)
        return f"{cls.name.upper()} files ({patterns})"

    def __init__(self, config: Optional[ConverterConfig] = None):
        """Initializes the converter.

        Args:
            config: Optional converter-specific configuration.
        """
        self.config = config

    @abstractmethod
    def can_decode(self) -> bool:
        """Determine whether this converter can decode the configured source.

        Returns:
            bool: True if decoding is possible from the configured location.
        """

    @abstractmethod
    def encode(self, source: FLYNCModel):
        """Encode a FLYNCModel into the target representation.

        Args:
            source: The FLYNCModel instance to encode.

        Raises:
            ConverterError: If encoding fails (implementation specific).
        """

    @abstractmethod
    def decode(self) -> FLYNCModel:
        """Decode the configured source into a FLYNCModel.

        Returns:
            FLYNCModel: The decoded model.

        Raises:
            ConverterError: If decoding fails (implementation specific).
        """
