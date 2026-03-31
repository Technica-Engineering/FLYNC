"""Base classes that automatically store created model instances."""

from abc import abstractmethod
from typing import Any, ClassVar, Dict, Generic, TypeVar

import pydantic
from pydantic import PrivateAttr

from .base_model import FLYNCBaseModel
from .resettable_model import BaseRegistry
from .unique_name import UniqueName

T = TypeVar("T", bound="FLYNCBaseModel")


class DictInstances(FLYNCBaseModel, Generic[T], BaseRegistry):
    """Base class that registers validated instances in a
    class-level dictionary."""

    INSTANCES: ClassVar[Dict[Any, T]] = {}
    _added_to_instances: bool = PrivateAttr(False)

    @abstractmethod
    def get_dict_key(self):
        pass

    @pydantic.model_validator(mode="after")
    def ensure_unique_instances(self: "DictInstances"):
        if self._added_to_instances:
            return self
        self.__class__.INSTANCES[self.get_dict_key()] = self
        self._added_to_instances = True
        return self

    @classmethod
    def reset(cls):
        cls.INSTANCES.clear()
        return super().reset()


class NamedDictInstances(UniqueName, Generic[T]):
    """Base class for named models registered in a class-level dictionary."""

    INSTANCES: ClassVar[Dict[str, T]] = {}
    _added_to_instances: bool = PrivateAttr(False)

    @pydantic.model_validator(mode="after")
    def ensure_unique_instances(self: "NamedDictInstances"):
        if self._added_to_instances:
            return self
        self.__class__.INSTANCES[self.get_instance_key()] = self
        self._added_to_instances = True
        return self

    def get_instance_key(self):
        return self.name

    @classmethod
    def reset(cls):
        cls.INSTANCES.clear()
        return super().reset()
