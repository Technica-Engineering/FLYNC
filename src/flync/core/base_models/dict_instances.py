"""Base classes that automatically store created model instances."""

from abc import abstractmethod
from typing import Generic, TypeVar

import pydantic
from pydantic import PrivateAttr

from .base_model import FLYNCBaseModel
from .instances_registery import Registry, get_registry
from .unique_name import UniqueName

T = TypeVar("T", bound="FLYNCBaseModel")


class DictInstances(FLYNCBaseModel, Generic[T]):
    """Base class that registers validated instances in the active
    :class:`~flync.core.base_models.instances_registery.Registry` under
    a caller-supplied key.

    After Pydantic validation completes, ``ensure_unique_instances``
    calls :meth:`get_dict_key` and stores ``self`` in
    ``registry.dict_by_class[type(self)][key]``.  Any later validator
    that holds a *name* reference to an instance of this class can look
    it up without building a separate index.

    Subclasses must implement :meth:`get_dict_key`.

    **Looking up a registered instance in a validator**

    Use :func:`~flync.core.base_models.instances_registery.get_registry`
    to obtain the active registry, then call ``get_dict`` with the
    concrete class::

        from flync.core.base_models import Registry, get_registry
        from pydantic import model_validator

        class MyConnection(FLYNCBaseModel):
            port_name: str
            _port: Optional[MyPort] = PrivateAttr(default=None)

            @model_validator(mode="after")
            def resolve_port(self):
                registry: Registry = get_registry()
                instances = registry.get_dict(MyPort)
                self._port = instances.get(self.port_name)
                if self._port is None:
                    raise ValueError(f"Port '{self.port_name}' not found")
                return self

    This is the pattern used throughout
    :mod:`flync.model.flync_4_ecu.internal_topology`, for example in
    ``ECUPortToXConnection.validate_ecu_port_exists``::

        registry: Registry = get_registry()
        ecu_ports_instances = registry.get_dict(ECUPort)
        self._ecu_port = ecu_ports_instances.get(self.ecu_port_name, None)

    **Injecting a parent back-reference into children**

    When a child model needs to navigate back to its parent at runtime,
    override ``model_post_init`` on the *parent* to set a private
    attribute on each child.  Always call
    ``super().model_post_init(__context)`` last::

        class MyParent(DictInstances):
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
    # temporarily keep the old behavior of this dict
    # until the model referencing is properly resolved
    _allow_duplicate: bool = PrivateAttr(True)

    @abstractmethod
    def get_dict_key(self):
        pass

    @pydantic.model_validator(mode="after")
    def ensure_unique_instances(self: "DictInstances"):
        if self._added_to_instances:
            return self
        tracked_reg: Registry = get_registry()
        tracked_reg.register_dict_item(self, self.get_dict_key())
        self._added_to_instances = True
        return self


class NamedDictInstances(UniqueName, Generic[T]):
    """Base class for named models registered in the active
    :class:`~flync.core.base_models.instances_registery.Registry` keyed
    by their ``name`` field.

    Identical to :class:`DictInstances` but the registry key is always
    ``self.name`` (via :meth:`get_instance_key`), so subclasses do not
    need to implement :meth:`get_dict_key`.

    **Looking up a registered instance in a validator**

    The lookup pattern is the same as for :class:`DictInstances`::

        from flync.core.base_models import Registry, get_registry
        from pydantic import model_validator

        class MyConnection(FLYNCBaseModel):
            iface_name: str
            _iface: Optional[MyIface] = PrivateAttr(default=None)

            @model_validator(mode="after")
            def resolve_iface(self):
                registry: Registry = get_registry()
                instances = registry.get_dict(MyIface)
                self._iface = instances.get(self.iface_name)
                if self._iface is None:
                    raise ValueError(
                        f"Interface '{self.iface_name}' not found"
                    )
                return self

    See ``SwitchPortToControllerInterface.validate_connection_compatibility``
    in :mod:`flync.model.flync_4_ecu.internal_topology` for a real example::

        registry: Registry = get_registry()
        controller_interface_instances = registry.get_dict(ControllerInterface)
        self._iface = controller_interface_instances.get(self.iface_name, None)

    **Injecting a parent back-reference into children**

    Same as for :class:`DictInstances` -- override ``model_post_init``
    on the parent to assign a private back-reference on each child::

        class MyParent(NamedDictInstances):
            children: List[MyChild] = Field()

            def model_post_init(self, __context):
                for child in self.children:
                    child._parent = self
                return super().model_post_init(__context)
    """

    _added_to_instances: bool = PrivateAttr(False)

    @pydantic.model_validator(mode="after")
    def ensure_unique_instances(self: "NamedDictInstances"):
        if self._added_to_instances:
            return self
        tracked_reg: Registry = get_registry()
        tracked_reg.register_dict_item(self, self.get_instance_key())
        self._added_to_instances = True
        return self

    def get_instance_key(self):
        return self.name
