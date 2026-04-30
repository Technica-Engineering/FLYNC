"""Base Model that is used by FLYNC Model classes."""

import logging
from typing import Optional

import pydantic
from pydantic import PrivateAttr  # noqa F401
from pydantic import BaseModel, ConfigDict

from .instances_registery import Registry, _active_registry


class FLYNCBaseModel(BaseModel):
    """Base Model that is used by FLYNC Model classes."""

    _logger: Optional[logging.Logger] = pydantic.PrivateAttr(default=None)
    model_config = ConfigDict(extra="forbid")

    @property
    def logger(self):
        return self._logger

    def model_post_init(self, __context):
        registry = _active_registry.get()
        if registry is None:
            # orphan registery used globally by any object outside the context
            # avoid this as much as possible.
            registry = Registry()
            _active_registry.set(registry)

        return super().model_post_init(__context)

    def model_dump(self, **kwargs):
        """Override pydantics model_dump to dump with defaults."""

        kwargs.setdefault("exclude_none", True)
        kwargs.setdefault("by_alias", True)
        return super().model_dump(**kwargs)
