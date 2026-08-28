import shutil
from pathlib import Path

from flync.core.utils.base_utils import read_yaml
from flync.model.flync_4_ecu import SocketContainer, Switch
from flync.sdk.workspace.flync_workspace import FLYNCWorkspace
from tests.system_test.sdk.helper import entry_named, patch_yaml


def test_multicast_paths_no_tx(tmpdir, example_workspace_path):
    destination_folder = Path(tmpdir) / "copy"
    shutil.copytree(example_workspace_path, destination_folder)
    file_to_update = (
        destination_folder
        / "ecus"
        / "high_performance_compute"
        / "controllers"
        / "hpc_controller2"
        / "ethernet_interfaces"
        / "hpc_c2_iface1"
        / "sockets"
        / "socket_nm.flync.yaml"
    )
    with patch_yaml(file_to_update) as socket_container:
        del entry_named(socket_container["sockets"], "network_management_socket")["multicast_tx"]

    # The zonal gateway bridges the NM PDU onto the backbone and therefore
    # also transmits to 224.0.0.1 — strip its multicast_tx as well so the
    # group really has no transmitter left.
    gateway_file = (
        destination_folder
        / "ecus"
        / "zonal_gateway"
        / "controllers"
        / "zgw_controller1"
        / "ethernet_interfaces"
        / "zgw_c1_iface1"
        / "sockets"
        / "socket_nm.flync.yaml"
    )
    with patch_yaml(gateway_file) as gateway_container:
        del entry_named(gateway_container["sockets"], "nm_rx_socket")["multicast_tx"]

    data = read_yaml(file_to_update)
    data["name"] = "socket_nm"
    SocketContainer.model_validate(data)

    loaded_ws = FLYNCWorkspace.load_workspace("flync_example", destination_folder)
    assert "Invalid Multicast Configuration" in str(loaded_ws.load_errors)
    assert "224.0.0.1" in str(loaded_ws.load_errors)
    assert "no tx" in str(loaded_ws.load_errors)
    if destination_folder.exists():
        shutil.rmtree(destination_folder)


def test_multicast_paths_no_path_from_rx_to_tx(tmpdir, example_workspace_path):
    destination_folder = Path(tmpdir) / "copie2"
    shutil.copytree(example_workspace_path, destination_folder)
    file_to_update = destination_folder / "ecus" / "high_performance_compute" / "switches" / "hpc_switch1" / "switch.flync.yaml"
    with patch_yaml(file_to_update) as switch_config:
        entry_named(switch_config["vlans"], "VLAN40")["ports"].remove("hpc_s1_p3")

    data = read_yaml(file_to_update)
    Switch.model_validate({"name": "hpc_switch1", "switch_config": data})
    loaded_ws = FLYNCWorkspace.load_workspace("flync_example", destination_folder)
    assert "Invalid Multicast Address Configuration" in str(loaded_ws.load_errors)
    assert "eth_ecu_c1_iface1" in str(loaded_ws.load_errors)
    assert "cannot be reached by the TX" in str(loaded_ws.load_errors)
    if destination_folder.exists():
        shutil.rmtree(destination_folder)


def test_switch_flooded(tmpdir, example_workspace_path):
    destination_folder = Path(tmpdir) / "copie2"
    shutil.copytree(example_workspace_path, destination_folder)
    loaded_ws = FLYNCWorkspace.load_workspace("flync_example", destination_folder)
    ecus = loaded_ws.flync_model.ecus
    switch = None
    for ecu in ecus:
        if ecu.name == "high_performance_compute":
            switch = ecu.get_switch_by_name("hpc_switch1")

    for v in switch.vlans:
        if v.id == 40:
            mcast_addresses = [str(m.address) for m in v.multicast]
            assert "224.0.0.1" in mcast_addresses
