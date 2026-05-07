import pytest

from flync.core.base_models import (
    DictInstances,
    ListInstances,
    NamedDictInstances,
    NamedListInstances,
    Registry,
    UniqueName,
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


@pytest.fixture(scope="session", autouse=True)
def _cleanup_old_caches_once():
    cleanup_old_caches()


@pytest.fixture(autouse=True)
def reset_global_registery():
    with registry_context(Registry()):
        yield
