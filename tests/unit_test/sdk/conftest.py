import pytest
from approvaltests import set_default_reporter
from approvaltests.reporters.diff_reporter import DiffReporter

from flync.sdk.workspace.flync_workspace import FLYNCWorkspace


@pytest.fixture
def get_flync_example_path(pytestconfig):
    project_root = pytestconfig.rootpath
    return str((project_root / "examples" / "flync_example"))


@pytest.fixture
def loaded_workspace(get_flync_example_path):
    return FLYNCWorkspace.load_workspace(
        "test_workspace", get_flync_example_path
    )


@pytest.fixture
def get_relative_flync_example_path():
    return "examples/flync_example"


def configure_approvaltests():
    set_default_reporter(DiffReporter)


@pytest.fixture(scope="session", autouse=True)
def set_default_reporter_for_all_tests() -> None:
    configure_approvaltests()
