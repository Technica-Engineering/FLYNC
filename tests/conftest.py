import pytest

from flync.core.base_models import (
    DictInstances,
    ListInstances,
    NamedDictInstances,
    NamedListInstances,
    UniqueName,
    Registry,
)
from flync.core.base_models.instances_registery import registry_context

CENTRAL_REGISTRIES = [
    UniqueName,
    ListInstances,
    NamedListInstances,
    NamedDictInstances,
    DictInstances,
]

from flync.sdk.utils.model_dependencies import cleanup_old_caches


@pytest.fixture(autouse=True)
def reset_global_registery():
    cleanup_old_caches()
    with registry_context(Registry()):
        yield
