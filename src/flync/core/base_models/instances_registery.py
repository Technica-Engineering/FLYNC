"""Base class for registries that require a reset method."""

import typing
from contextlib import contextmanager
from contextvars import ContextVar

_active_registry: ContextVar["Registry | None"] = ContextVar(
    "active_registry", default=None
)


class Registry(object):
    """Base for FLYNC model registries requiring a reset mechanism.

    Attributes:
        names: Set of registered names for this registry instance.
        dict_by_class: Mapping from type to a dict of id-keyed instances.
        list_by_class: Mapping from type to an ordered list of instances.
    """

    CONTEXT_NAME = "registry"
    names: typing.Set[str] = set()
    dict_by_class: typing.ClassVar[typing.Dict[type, dict]] = {}
    list_by_class: typing.ClassVar[typing.Dict[type, list]] = {}

    def __init__(self):
        self.names = set()
        self.dict_by_class = {}
        self.list_by_class = {}

    def register_dict_item(self, instance, instance_id):
        """Register an instance ID in the dict store for its type.

        Args:
            instance: The object to register.
            instance_id: The key for the instance within its type bucket.
        """
        instances_dict = self.dict_by_class.setdefault(type(instance), {})
        if (
            hasattr(instance, "_allow_duplicate")
            and not getattr(instance, "_allow_duplicate")
            and instance_id in instances_dict
        ):
            raise ValueError(
                "Id {} already exists for instance {}", instance_id, instance
            )
        instances_dict[instance_id] = instance

    def register_list_item(self, instance):
        """Append an instance to the list store for its type.

        Args:
            instance: The object to register.
        """
        self.list_by_class.setdefault(type(instance), []).append(instance)

    def get_dict(self, cls: type) -> dict:
        """Return the registered dict for a given class.

        Args:
            cls: The type whose dict store should be returned.

        Returns:
            A dict of instances, or an empty dict if none
            have been registered for the given class.
        """
        return self.dict_by_class.get(cls, {})

    def get_list(self, cls: type) -> list:
        """Return the registered list for a given class.

        Args:
            cls: The type whose list store should be returned.

        Returns:
            A list of registered instances, or an empty list if none have been
            registered for the given class.
        """
        return self.list_by_class.get(cls, [])


@contextmanager
def registry_context(registry: Registry):
    """Context manager that activates a registry for the current context.

    Args:
        registry: The Registry instance to set as active.

    Yields:
        The provided registry while the context is active.
    """
    token = _active_registry.set(registry)
    try:
        yield registry
    finally:
        _active_registry.reset(token)


def get_registry() -> Registry:
    """Return the currently active registry.

    Returns:
        The active Registry instance.

    Raises:
        RuntimeError: If no registry is active in the current context.
    """
    registry = _active_registry.get()
    if registry is None:
        raise RuntimeError(
            "No active registry. "
            "Wrap model construction in registry_context()."
        )
    return registry


@contextmanager
def ensure_registry():
    """Yield the active registry, creating a temporary one if none exists.

    Yields:
        The existing active Registry if one is set, otherwise a newly created
        Registry that is cleaned up on exit.
    """
    existing = _active_registry.get()
    if existing is not None:
        yield existing  # already active, just use it
    else:
        with registry_context(Registry()) as reg:
            yield reg  # create, yield, and clean up on exit
