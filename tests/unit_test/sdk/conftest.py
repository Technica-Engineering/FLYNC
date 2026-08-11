import pytest
from approvaltests import set_default_reporter
from approvaltests.reporters.diff_reporter import DiffReporter

from flync.sdk.context.workspace_config import ListObjectsMode
from flync.sdk.workspace.flync_workspace import FLYNCWorkspace, WorkspaceConfiguration


# These fixtures load the example workspace, which is comparatively expensive
# (especially ``map_objects=True``). All consumers use the workspace read-only,
# so they are session-scoped and loaded once per worker instead of once per test.
# Do NOT mutate the workspace/model in tests that use these fixtures.
@pytest.fixture(scope="session")
def get_flync_example_path(pytestconfig):
    project_root = pytestconfig.rootpath
    return str((project_root / "examples" / "flync_example"))


@pytest.fixture
def get_flync_workspace_minimal_config():
    return WorkspaceConfiguration(map_objects=True, list_objects_mode=ListObjectsMode.INDEX)


@pytest.fixture(scope="session")
def loaded_workspace_with_object_map(get_flync_example_path):
    return FLYNCWorkspace.load_workspace("test_workspace", get_flync_example_path, WorkspaceConfiguration(map_objects=True))


@pytest.fixture(scope="session")
def loaded_workspace_index_only(get_flync_example_path):
    return FLYNCWorkspace.load_workspace(
        "test_workspace",
        get_flync_example_path,
        WorkspaceConfiguration(map_objects=True, list_objects_mode=ListObjectsMode.INDEX),
    )


@pytest.fixture(scope="session")
def loaded_workspace_without_object_map(get_flync_example_path):
    return FLYNCWorkspace.load_workspace("test_workspace", get_flync_example_path, WorkspaceConfiguration(map_objects=False))


@pytest.fixture
def get_relative_flync_example_path():
    return "examples/flync_example"


def configure_approvaltests():
    set_default_reporter(DiffReporter())


@pytest.fixture(scope="session", autouse=True)
def set_default_reporter_for_all_tests() -> None:
    configure_approvaltests()
