import pytest

from flync.sdk.workspace.flync_workspace import FLYNCWorkspace

from .test_helpers import EXAMPLE_DIR


@pytest.fixture(scope="session")
def flync_object():
    ws = FLYNCWorkspace.load_workspace("example_workspace", EXAMPLE_DIR)
    return ws.flync_model
