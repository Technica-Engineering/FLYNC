import shutil
import subprocess
from pathlib import Path

from tests.example_paths import FLYNC_EXAMPLE_EXPERIMENTAL as absolute_path
from tests.system_test.sdk.helper import update_yaml_content

VALIDATE_WORKSPACE_SCRIPT = Path(__file__).resolve().parents[5] / "src" / "flync" / "sdk" / "helpers" / "validate_workspace.py"


def test_htb(tmpdir):
    destination_folder = Path(tmpdir) / "copy"
    shutil.copytree(absolute_path, destination_folder)
    file_to_update = (
        destination_folder
        / "ecus"
        / "eth_ecu"
        / "controllers"
        / "eth_ecu_controller1"
        / "ethernet_interfaces"
        / "eth_ecu_c1_iface1"
        / "interface_config.flync.yaml"
    )
    update_yaml_content(
        file_to_update,
        "        default_class: 12",
        "        default_class: 12a",
    )

    result = subprocess.run(
        [
            "flync",
            "validate",
            str(destination_folder),
            "--config",
            "flync_example",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
