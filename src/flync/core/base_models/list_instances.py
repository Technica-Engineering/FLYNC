"""Base classes that automatically collect model instances in a list."""

from typing import ClassVar, Generic, List, TypeVar

import pydantic
from pydantic import PrivateAttr

from .base_model import FLYNCBaseModel
from .resettable_model import BaseRegistry
from .unique_name import UniqueName

T = TypeVar("T", bound="FLYNCBaseModel")


class ListInstances(FLYNCBaseModel, Generic[T], BaseRegistry):
    """
    Base class that collects all validated
    instances into a class-level list.
    """

    INSTANCES: ClassVar[List[T]] = []
    _added_to_instances: bool = PrivateAttr(False)

    @pydantic.model_validator(mode="after")
    def ensure_unique_instances(self: "ListInstances"):
        if self._added_to_instances:
            return self
        self.__class__.INSTANCES.append(self)
        self._added_to_instances = True
        return self

    @classmethod
    def reset(cls):
        cls.INSTANCES.clear()
        return super().reset()


class NamedListInstances(UniqueName, Generic[T]):
    """Base class that registers named instances in a class-level list."""

    INSTANCES: ClassVar[List[T]] = []
    _added_to_instances: bool = PrivateAttr(False)

    @pydantic.model_validator(mode="after")
    def ensure_unique_instances(self: "NamedListInstances"):
        if self._added_to_instances:
            return self
        self.__class__.INSTANCES.append(self)
        self._added_to_instances = True
        return self

    @classmethod
    def reset(cls):
        cls.INSTANCES.clear()
        return super().reset()
