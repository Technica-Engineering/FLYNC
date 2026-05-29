from pathlib import Path

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


def pytest_configure(config):
    # Build the on-disk dependency graph cache once in the xdist master so that
    # workers start with a warm cache and don't serialise on the FileLock.
    if hasattr(config, "workerinput"):
        return
    cleanup_old_caches()
    from flync.sdk.workspace.flync_workspace import FLYNCWorkspace

    example_path = Path(__file__).parent.parent / "examples" / "flync_example"
    FLYNCWorkspace.load_workspace("flync_example", example_path)


@pytest.fixture(autouse=True)
def reset_global_registery():
    with registry_context(Registry()):
        yield
