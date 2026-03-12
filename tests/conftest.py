import pytest

from flync.core.base_models import (
    BaseRegistry,
    DictInstances,
    ListInstances,
    NamedDictInstances,
    NamedListInstances,
    UniqueName,
)

CENTRAL_REGISTRIES = [
    UniqueName,
    ListInstances,
    NamedListInstances,
    NamedDictInstances,
    DictInstances,
]


def reset_all_registries(base_cls: BaseRegistry):
    for subclass in base_cls.__subclasses__():
        subclass.reset()
        # recursively reset subclasses of subclasses
        reset_all_registries(subclass)


def reset_global_registery_function():
    for cls in CENTRAL_REGISTRIES:
        reset_all_registries(cls)


@pytest.fixture(autouse=True)
def reset_global_registery():
    reset_global_registery_function()
