"""Base class that ensures instance names are unique."""

import pydantic
from pydantic import PrivateAttr

from .base_model import FLYNCBaseModel
from .instances_registery import Registry, get_registry


class UniqueName(FLYNCBaseModel):
    """Base class that ensures instance names are unique."""

    name: str
    _unique_name_validated: bool = PrivateAttr(False)

    @pydantic.model_validator(mode="after")
    def ensure_unique_name(val: "UniqueName"):
        if val._unique_name_validated:
            return val
        if val is None:
            return val
        name = val.get_key()
        # if this object already exists, then something is wrong.
        tracked_reg: Registry = get_registry()
        assert name not in tracked_reg.names
        tracked_reg.names.add(name)
        val._unique_name_validated = True
        return val

    def get_key(self):
        return f"{self.__class__.__name__}.{self.name}"
