import pytest



@pytest.fixture
def get_flync_example_path(pytestconfig):
    project_root = pytestconfig.rootpath
    return str((project_root / "examples" / "flync_example"))

@pytest.fixture
def get_relative_flync_example_path():
    return "examples/flync_example"
