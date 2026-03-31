"""Base class for registries that require a reset method."""

from abc import ABC, abstractmethod


class BaseRegistry(ABC):
    """Base for FLYNC model registries requiring a reset mechanism."""

    @classmethod
    @abstractmethod
    def reset(cls):
        """Reset function to clear the registry."""
