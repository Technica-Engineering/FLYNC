from pathlib import Path

import pytest

from flync.sdk.utils.model_dependencies import cleanup_old_caches


def pytest_configure(config):
    # Build the on-disk dependency graph cache once in the xdist master so that
    # workers start with a warm cache and don't serialise on the FileLock.
    if hasattr(config, "workerinput"):
        return
    cleanup_old_caches(force=True)
    from flync.sdk.workspace.flync_workspace import FLYNCWorkspace

    example_path = Path(__file__).parent.parent / "examples" / "flync_example"
    FLYNCWorkspace.load_workspace("flync_example", example_path)


# ============================================================================
# Shared Fixtures (used across multiple test suites)
# ============================================================================


@pytest.fixture(scope="session")
def example_workspace_path():
    """Return path to standard example FLYNC workspace.

    This fixture is used across multiple test suites (workspace_config, sdk, etc.)
    to load the common example workspace without modifications.
    """
    return (Path(__file__).parent.parent / "examples" / "flync_example").absolute()


@pytest.fixture(scope="session")
def example_experimental_workspace_path():
    """Return path to the experimental example FLYNC workspace.

    ``flync_example_experimental`` is a sandbox copy of ``flync_example`` that
    developers may freely modify without affecting the canonical example that
    most tests depend on. It mirrors ``example_workspace_path`` so tests can
    exercise a workspace they are allowed to mutate.
    """
    return (Path(__file__).parent.parent / "examples" / "flync_example_experimental").absolute()
