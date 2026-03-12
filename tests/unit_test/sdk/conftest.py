import pytest
from approvaltests import set_default_reporter
from approvaltests.reporters.diff_reporter import DiffReporter


@pytest.fixture
def get_flync_example_path(pytestconfig):
    project_root = pytestconfig.rootpath
    return str((project_root / "examples" / "flync_example"))


@pytest.fixture
def get_relative_flync_example_path():
    return "examples/flync_example"


def configure_approvaltests():
    set_default_reporter(DiffReporter)


@pytest.fixture(scope="session", autouse=True)
def set_default_reporter_for_all_tests() -> None:
    configure_approvaltests()
