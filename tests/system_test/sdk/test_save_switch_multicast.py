"""
Tests that saving a model writes the multicast groups of a switch VLAN as authored. The root model provisions further
groups and ports from the multicast paths; those are rebuilt on each load and never written to the switch file.
"""

import shutil

import yaml

from flync.sdk.workspace.flync_workspace import FLYNCWorkspace
from tests.example_paths import FLYNC_EXAMPLE_EXPERIMENTAL as absolute_path

Z1_SWITCH = "ecus/zonal_platform1/switches/z1_switch1/switch.flync.yaml"
VLAN20 = "- name: VLAN20\n  id: 20\n  default_priority: 0\n  ports:\n    - z1_s1_p0\n    - z1_s1_p2\n"
AUTHORED = "  multicast:\n    - address: 224.244.224.245\n      ports: [z1_s1_p2]\n"


def test_saving_writes_only_the_authored_switch_multicast(tmp_path):
    root = tmp_path / "ws"
    shutil.copytree(absolute_path, root)
    path = root / Z1_SWITCH
    text = path.read_text()
    assert VLAN20 in text
    path.write_text(text.replace(VLAN20, VLAN20 + AUTHORED))

    model = FLYNCWorkspace.load_workspace("authored", root).flync_model
    switch = next(sw for ecu in model.ecus for sw in ecu.switches or [] if sw.name == "z1_switch1")
    provisioned = {str(group.address): sorted(group.ports) for group in next(v for v in switch.vlans if v.id == 20).multicast}
    assert provisioned == {"224.244.224.245": ["z1_s1_p0", "z1_s1_p2"], "224.0.0.15": ["z1_s1_p0", "z1_s1_p2"]}

    out = FLYNCWorkspace("saved", tmp_path / "out")
    out.load_flync_model(model)
    out.generate_configs(persist_config=False)

    saved = yaml.safe_load((tmp_path / "out" / Z1_SWITCH).read_text())
    vlan20 = next(v_entry for v_entry in saved["vlans"] if v_entry["id"] == 20)
    assert vlan20["multicast"] == [{"address": "224.244.224.245", "ports": ["z1_s1_p2"]}]
