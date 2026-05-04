"""Base classes that automatically collect model instances in a list."""

from typing import Generic, TypeVar

import pydantic
from pydantic import PrivateAttr

from .base_model import FLYNCBaseModel
from .instances_registery import Registry, get_registry
from .unique_name import UniqueName

T = TypeVar("T", bound="FLYNCBaseModel")


class ListInstances(FLYNCBaseModel, Generic[T]):
    """
    Base class that appends every validated instance to the active :class:`~flync.core.base_models.instances_registery.Registry` list
    for its concrete type.

    After Pydantic validation completes, ``ensure_unique_instances`` calls ``registry.register_list_item(self)``, which appends ``self``
    to ``registry.list_by_class[type(self)]``.  Unlike :class:`~flync.core.base_models.dict_instances.DictInstances`, there
    is no key -- the list is meant for validators that need to *iterate* over all instances of a type and filter by some condition.

    **Looking up instances in a validator**

    Use :func:`~flync.core.base_models.instances_registery.get_registry` to obtain the active registry, then call ``get_list`` with the
    concrete class and iterate::

        from flync.core.base_models import Registry, get_registry
        from pydantic import model_validator

        class MyChild(FLYNCBaseModel):
            name: str

            def get_parent(self):
                registry: Registry = get_registry()
                for parent in registry.get_list(MyParent):
                    if self in parent.children:
                        return parent
                raise ValueError("No parent found for this child")

    This is the pattern used in :mod:`flync.model.flync_4_ecu.controller`, for example in ``ControllerInterface.get_controller``::

        registry: Registry = get_registry()
        controller_instances = registry.get_list(Controller)
        for ctrl in controller_instances:
            for interface in ctrl.interfaces:
                if interface.name == self.name:
                    return ctrl

    **Injecting a parent back-reference into children**

    When a child model needs to navigate back to its parent at runtime (e.g. to call ``get_switch()`` on a port), override
    ``model_post_init`` on the *parent* to set a private attribute on each child.  Always call ``super().model_post_init(__context)`` last
    so that the base-class registration runs::

        class MyParent(ListInstances):
            children: List[MyChild] = Field()

            def model_post_init(self, __context):
                for child in self.children:
                    child._parent = self
                return super().model_post_init(__context)

    See ``Switch.model_post_init`` in
    :mod:`flync.model.flync_4_ecu.switch` for the canonical example::

        def model_post_init(self, __context):
            for port in self.ports:
                port._switch = self
            return super().model_post_init(__context)
    """

    _added_to_instances: bool = PrivateAttr(False)

    @pydantic.model_validator(mode="after")
    def ensure_unique_instances(self: "ListInstances"):
        if self._added_to_instances:
            return self
        tracked_reg: Registry = get_registry()
        tracked_reg.register_list_item(self)
        self._added_to_instances = True
        return self


class NamedListInstances(UniqueName, Generic[T]):
    """
    Base class that appends every validated named instance to the active :class:`~flync.core.base_models.instances_registery.Registry` list,
    keyed by type.

    Identical to :class:`ListInstances` but extends :class:`~flync.core.base_models.unique_name.UniqueName`, so each
    instance carries a ``name`` field that is unique within a registry context.  Use this class when instances need a name *and* are
    typically looked up by iterating all registered instances of a type.

    **Looking up instances in a validator**

    The lookup pattern is the same as for :class:`ListInstances` -- iterate ``registry.get_list(ClassName)`` and filter by ``name`` or any
    other attribute::

        from flync.core.base_models import Registry, get_registry
        from pydantic import model_validator

        class MyConnection(FLYNCBaseModel):
            target_name: str
            _target: Optional[MyNode] = PrivateAttr(default=None)

            @model_validator(mode="after")
            def resolve_target(self):
                registry: Registry = get_registry()
                for node in registry.get_list(MyNode):
                    if node.name == self.target_name:
                        self._target = node
                        return self
                raise ValueError(f"Node '{self.target_name}' not found")

    **Injecting a parent back-reference into children**

    Same as for :class:`ListInstances` -- override ``model_post_init`` on the parent to assign a private back-reference on each child::

        class MyParent(NamedListInstances):
            children: List[MyChild] = Field()

            def model_post_init(self, __context):
                for child in self.children:
                    child._parent = self
                return super().model_post_init(__context)
    """

    _added_to_instances: bool = PrivateAttr(False)

    @pydantic.model_validator(mode="after")
    def ensure_unique_instances(self: "NamedListInstances"):
        if self._added_to_instances:
            return self
        tracked_reg: Registry = get_registry()
        tracked_reg.register_list_item(self)
        self._added_to_instances = True
        return self
