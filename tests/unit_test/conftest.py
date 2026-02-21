import pytest
from flync.core.base_models import (
    UniqueName,
    ListInstances,
    DictInstances,
    NamedDictInstances,
    NamedListInstances,
    BaseRegistry,
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


@pytest.fixture(autouse=True)
def reset_global_registery():
    for cls in CENTRAL_REGISTRIES:
        reset_all_registries(cls)
