import pytest
from pathlib import Path
from flync.sdk.workspace.flync_workspace import FLYNCWorkspace
from flync.model.flync_4_ecu import (
    SocketContainer,
    Switch,
    SwitchPort,
    Controller,
    ControllerInterface,
    ECUPort,
    ECU,
)
from flync.core.utils.base_utils import read_yaml
import shutil
from pydantic import ValidationError
from .helper import update_yaml_content

absolute_path = Path(__file__).parents[2] / "examples" / "flync_example"


def reset(class_name):

    for item in class_name.NAMES.copy():
        if item.startswith(class_name.__name__):
            class_name.NAMES.remove(item)


def reset_unique_name_cache():
    reset(SwitchPort)
    reset(Switch)
    reset(Controller)
    reset(ControllerInterface)
    reset(ECUPort)
    reset(ECU)


def test_multicast_paths_no_tx(tmpdir):
    destination_folder = Path(tmpdir) / "copie"
    shutil.copytree(absolute_path, destination_folder)
    file_to_update = (
        destination_folder
        / "ecus"
        / "high_processing_core"
        / "sockets"
        / "socket_nm.flync.yaml"
    )
    update_yaml_content(file_to_update, "multicast_tx:", "")
    update_yaml_content(file_to_update, "- 224.0.0.1", "")

    data = read_yaml(file_to_update)
    data["name"] = "socket_nm"
    SocketContainer.model_validate(data)

    with pytest.raises(ValidationError) as exc_info:
        FLYNCWorkspace.load_workspace("flync_example", destination_folder)
    assert (
        "Invalid Multicast Configuration"
        and "224.0.0.1"
        and "no tx" in str(exc_info.value)
    )
    if destination_folder.exists():
        shutil.rmtree(destination_folder)


def test_multicast_paths_no_path_from_rx_to_tx(tmpdir):
    destination_folder = Path(tmpdir) / "copie2"
    shutil.copytree(absolute_path, destination_folder)
    file_to_update = (
        destination_folder
        / "ecus"
        / "high_processing_core"
        / "switches"
        / "hpc_switch1.flync.yaml"
    )
    update_yaml_content(file_to_update, "    - hpc_s1_p3", "")

    data = read_yaml(file_to_update)
    Switch.model_validate(data)
    reset_unique_name_cache()
    with pytest.raises(ValidationError) as exc_info:
        FLYNCWorkspace.load_workspace("flync_example", destination_folder)
    assert (
        "Invalid Multicast Configuration"
        and "224.0.0.1"
        and "eth_ecu_c1_iface1"
        and "cannot be reached by the TX" in str(exc_info.value)
    )
    if destination_folder.exists():
        shutil.rmtree(destination_folder)


def test_switch_flooded(tmpdir):
    destination_folder = Path(tmpdir) / "copie2"
    shutil.copytree(absolute_path, destination_folder)
    loaded_ws = FLYNCWorkspace.load_workspace(
        "flync_example", destination_folder
    )
    ecus = loaded_ws.flync_model.ecus
    switch = None
    for ecu in ecus:
        if ecu.name == "high_processing_core":
            switch = ecu.get_switch_by_name("hpc_switch1")

    for v in switch.vlans:
        if v.id == 40:
            mcast_addresses = [str(m.address) for m in v.multicast]
            assert "224.0.0.1" in mcast_addresses
