import subprocess
import pytest, yaml
from pathlib import Path
from sys import executable
from flync.model.flync_4_ecu import (
    SocketContainer,
)
from flync.core.utils.base_utils import read_yaml
import shutil
from tests.system_test.sdk.helper_load_ws import *

absolute_path = Path(__file__).parents[5] / "examples" / "flync_example"
VALIDATE_WORKSPACE_SCRIPT = (
    Path(__file__).resolve().parents[5]
    / "src"
    / "flync"
    / "sdk"
    / "helpers"
    / "validate_workspace.py"
)


def test_htb(tmpdir):
    destination_folder = Path(tmpdir) / "copy"
    shutil.copytree(absolute_path, destination_folder)
    file_to_update = (
        destination_folder
        / "ecus"
        / "eth_ecu"
        / "controllers"
        / "eth_ecu_controller1.flync.yaml"
    )
    update_yaml_content(file_to_update, "        default_class: 12", "        default_class: 12a")

    result = subprocess.run(
        [
            executable,
            VALIDATE_WORKSPACE_SCRIPT,
            str(destination_folder),
            "--name",
            "flync_example",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
