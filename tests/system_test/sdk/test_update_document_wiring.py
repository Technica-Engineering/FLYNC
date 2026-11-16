"""
Tests that :meth:`FLYNCWorkspace.update_document` leaves the derived wiring of the model (component links,
socket bindings and solicited-node multicast groups) exactly as a full load builds it, however often a document
is reloaded. An incremental reload revalidates the changed document's ancestors around the instances of their
unchanged children, so any wiring a validator adds to those instances must be rebuilt, not added again.
"""

import shutil
from pathlib import Path

import pytest

from flync.model.flync_model import FLYNCModel
from flync.sdk.context.workspace_config import WorkspaceConfiguration
from flync.sdk.workspace.flync_workspace import FLYNCWorkspace
from tests.example_paths import FLYNC_EXAMPLE_EXPERIMENTAL as absolute_path

ETHERNET_TOPOLOGY = "topology/ethernet_topology.flync.yaml"
HPC_DOIP_SOCKETS = "ecus/high_performance_compute/controllers/hpc_controller1/ethernet_interfaces/hpc_c1_iface1/sockets/socket_doip.flync.yaml"
Z1_REAR_LAMP_SOCKETS = "ecus/zonal_platform1/controllers/z1_controller1/ethernet_interfaces/z1_c1_iface1/sockets/rear_lamp_sockets.flync.yaml"


@pytest.fixture
def workspace(tmp_path):
    """A fresh, writable copy of the experimental example workspace with object mapping enabled."""
    root = tmp_path / "ws"
    shutil.copytree(absolute_path, root)
    config = WorkspaceConfiguration(map_objects=True)
    ws = FLYNCWorkspace.load_workspace("wiring_ws", root, workspace_config=config)
    return ws, root, config


def _label(component) -> str:
    return f"{type(component).__name__}:{getattr(component, 'qualified_name', component.name)}"


def _switch_port_links(switch_port) -> list:
    return [switch_port._connected_component] if switch_port._connected_component is not None else []


def _wired_components(model: FLYNCModel):
    """Yield ``(label, links)`` for every port, switch port and interface of the model."""
    for ecu in model.ecus:
        for port in ecu.ports or []:
            yield _label(port), port._connected_components
        for switch_port in ecu.get_all_switch_ports():
            yield f"{ecu.name}/{_label(switch_port)}", _switch_port_links(switch_port)
        for ctrl in ecu.iter_controllers_and_switch_hosts():
            for switch in ctrl.iter_subtree_switches():
                for switch_port in switch.ports:
                    yield f"{ecu.name}/{ctrl.name}/{_label(switch_port)}", _switch_port_links(switch_port)
            for iface in ctrl.iter_subtree_interfaces():
                yield f"{ecu.name}/{ctrl.name}/{_label(iface)}", iface._connected_component


def _wiring(model: FLYNCModel) -> dict:
    """Comparable view of everything the model's validators wire onto its components."""
    links = {label: sorted(_label(c) for c in linked) for label, linked in _wired_components(model)}
    groups = {
        ecu.name: sorted(f"{g.mode} {g.group} {g.vlan} {g.src_ip} {g.solicited_node_multicast}" for g in ecu.multicast_groups) for ecu in model.ecus
    }
    sockets = {
        f"{ecu.name}/{ip.address}": sorted(s.name for s in ip.sockets)
        for ecu in model.ecus
        for ctrl in ecu.iter_controllers_and_switch_hosts()
        for iface in ctrl.iter_subtree_interfaces()
        for vi in iface.interface_config.virtual_interfaces or []
        for ip in vi.addresses
        if hasattr(ip, "sockets")
    }
    switch_groups = {
        f"{ecu.name}/{switch.name}/{v_entry.id}": sorted(f"{group.address} {sorted(group.ports)}" for group in v_entry.multicast)
        for ecu in model.ecus
        for switch in _switches(ecu)
        for v_entry in switch.vlans
    }
    return {"links": links, "groups": groups, "sockets": sockets, "switch_groups": switch_groups}


def _switches(ecu) -> list:
    controllers = list(ecu.iter_controllers_and_switch_hosts())
    return [*(ecu.switches or []), *(switch for ctrl in controllers for switch in ctrl.iter_subtree_switches())]


def _stale_links(model: FLYNCModel) -> list[str]:
    """Links that point at an instance the model no longer holds, such as a port replaced by a reload."""
    current = {id(obj) for obj in _components(model)}
    return [f"{label} -> {_label(c)}" for label, linked in _wired_components(model) for c in linked if id(c) not in current]


def _components(model: FLYNCModel):
    for ecu in model.ecus:
        yield from ecu.ports or []
        for switch in _switches(ecu):
            yield from switch.ports
            yield from switch.port_extenders
        for ctrl in ecu.iter_controllers_and_switch_hosts():
            yield from ctrl.iter_subtree_interfaces()


def _full_load(root: Path, config: WorkspaceConfiguration) -> FLYNCModel:
    model = FLYNCWorkspace.safe_load_workspace("full", root, workspace_config=config).flync_model
    assert model is not None
    return model


@pytest.mark.parametrize(
    "rel",
    [
        pytest.param("ecus/zonal_platform1/ports.flync.yaml", id="ecu_ports"),
        pytest.param("ecus/zonal_platform1/topology.flync.yaml", id="ecu_topology"),
        pytest.param("ecus/eth_ecu/controllers/eth_ecu_controller1/controller_metadata.flync.yaml", id="controller"),
        pytest.param(ETHERNET_TOPOLOGY, id="ethernet_topology"),
        pytest.param(HPC_DOIP_SOCKETS, id="sockets"),
    ],
)
def test_repeated_reloads_keep_the_wiring_of_a_full_load(workspace, rel):
    ws, root, config = workspace

    for _ in range(3):
        ws.update_document(rel)

    assert _wiring(ws.flync_model) == _wiring(_full_load(root, config))
    assert _stale_links(ws.flync_model) == []


def test_removing_a_connection_unlinks_its_ports(workspace):
    ws, root, config = workspace
    path = root / ETHERNET_TOPOLOGY
    text = path.read_text()
    removed = "  - type: ecu_port_to_ecu_port\n    id: conn1\n    ecu1_port: hpc1_p1\n    ecu2_port: z1_p1\n"
    assert removed in text
    path.write_text(text.replace(removed, ""))

    ws.update_document(ETHERNET_TOPOLOGY)

    hpc1_p1 = next(p for p in ws.flync_model.get_all_ecu_ports_by_name().values() if p.name == "hpc1_p1")
    assert not any(c.name == "z1_p1" for c in hpc1_p1._connected_components)
    assert _wiring(ws.flync_model) == _wiring(_full_load(root, config))


def test_moving_a_socket_unbinds_it_from_its_old_address(workspace):
    ws, root, config = workspace
    path = root / HPC_DOIP_SOCKETS
    text = path.read_text()
    moved = "- name: doip_udp_socket\n  endpoint_address: 10.0.20.5\n"
    assert moved in text
    path.write_text(text.replace(moved, "- name: doip_udp_socket\n  endpoint_address: 10.0.10.5\n"))

    ws.update_document(HPC_DOIP_SOCKETS)

    sockets = _wiring(ws.flync_model)["sockets"]
    assert "doip_udp_socket" not in sockets["high_performance_compute/10.0.20.5"]
    assert "doip_udp_socket" in sockets["high_performance_compute/10.0.10.5"]
    assert _wiring(ws.flync_model) == _wiring(_full_load(root, config))


def test_removing_the_last_sender_of_a_group_drops_it_from_the_switch(workspace):
    ws, root, config = workspace
    path = root / Z1_REAR_LAMP_SOCKETS
    text = path.read_text()
    sender = text[text.index("- name: rear_lamp_command_tx") : text.index("- name: rear_lamp_status_rx")]
    path.write_text(text.replace(sender, ""))

    ws.update_document(Z1_REAR_LAMP_SOCKETS)

    assert _wiring(ws.flync_model)["switch_groups"]["zonal_platform1/z1_switch1/60"] == []
    assert _wiring(ws.flync_model) == _wiring(_full_load(root, config))
