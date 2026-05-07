"""Base class that ensures instance names are unique."""

import pydantic
from pydantic import PrivateAttr

from flync.core.utils.exceptions import err_major

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
        tracked_reg: Registry = get_registry()
        if name in tracked_reg.names:
            raise err_major(
                f"Duplicate {val.__class__.__name__} name {val.name!r} "
                f"(registry key {name!r}) — names must be unique within the workspace."
            )
        tracked_reg.names.add(name)
        val._unique_name_validated = True
        return val

    def get_key(self):
        return f"{self.__class__.__name__}.{self.name}"
