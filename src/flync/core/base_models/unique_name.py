"""Base class that ensures instance names are unique."""

import typing

import pydantic
from pydantic import PrivateAttr

from .base_model import FLYNCBaseModel
from .resettable_model import BaseRegistry


class UniqueName(FLYNCBaseModel, BaseRegistry):
    """Base class that ensures instance names are unique."""

    NAMES: typing.ClassVar[typing.Set[str]] = set()
    name: str
    _unique_name_validated: bool = PrivateAttr(False)

    @pydantic.model_validator(mode="after")
    def ensure_unique_name(val: "UniqueName"):
        if val._unique_name_validated:
            return val
        if val is None:
            return val
        name = val.get_key()
        assert name not in UniqueName.NAMES
        UniqueName.NAMES.add(name)
        val._unique_name_validated = True
        return val

    def get_key(self):
        return f"{self.__class__.__name__}.{self.name}"

    @classmethod
    def reset(cls):
        cls.NAMES.clear()
        return super().reset()
