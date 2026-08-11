"""
Tests for :meth:`FLYNCWorkspace.update_document`, the incremental single-document
reload path. Every scenario asserts that a partial update leaves the workspace in
the same state a full reload would produce, so partial loading can never diverge
from the authoritative load.
"""

import shutil
from pathlib import Path

import pytest

from flync.sdk.context.workspace_config import WorkspaceConfiguration
from flync.sdk.workspace.flync_workspace import FLYNCWorkspace

from .helper import absolute_path

PORTS = "ecus/zonal_platform1/ports.flync.yaml"


def _snapshot(ws: FLYNCWorkspace) -> dict:
    """Comparable view of everything a reload derives from disk."""
    for id in ws.list_objects():
        ws.has_object(id)
    return {
        "ecus": [e.name for e in (ws.flync_model.ecus or [])] if ws.flync_model else None,
        "diags": {k: len(v) for k, v in ws.documents_diags.items() if v},
        "objects": {str(oid): type(so.model).__name__ for oid, so in ws.objects.items()},
        "sources": {str(oid): (s.uri, s.range.start.line) for oid, s in ws.sources.items()},
        "children": {k: sorted(v) for k, v in ws._children_by_parent.items()},
    }


@pytest.fixture
def workspace(tmp_path):
    """A fresh, writable copy of the example workspace with object mapping enabled."""
    root = tmp_path / "ws"
    shutil.copytree(absolute_path, root)
    config = WorkspaceConfiguration(map_objects=True)
    ws = FLYNCWorkspace.load_workspace("update_ws", root, workspace_config=config)
    return ws, root, config


def _edit(root: Path, rel: str, old: str, new: str):
    path = root / rel
    path.write_text(path.read_text().replace(old, new))


def _assert_matches_full_reload(ws, root, config, rel):
    partial = _snapshot(ws)
    full = _snapshot(FLYNCWorkspace.safe_load_workspace("full", root, workspace_config=config))
    assert partial == full, f"partial update of {rel} diverged from a full reload"


def test_benign_edit_updates_model_without_full_reload(workspace):
    ws, root, config = workspace
    _edit(root, PORTS, "speed: 100", "speed: 1000")

    affected = ws.update_document(PORTS)

    zonal = next(e for e in ws.flync_model.ecus if e.name == "zonal_platform1")
    assert zonal.ports[0].mdi_config.speed == 1000
    # the changed file, its owning ECU and the root are recomputed
    assert PORTS in affected
    assert "ecus/zonal_platform1" in affected
    assert "." in affected
    _assert_matches_full_reload(ws, root, config, PORTS)


def test_breaking_a_reference_matches_full_reload(workspace):
    ws, root, config = workspace
    # a topology connection references port "z1_p1"; renaming it dangles that reference
    _edit(root, PORTS, "name: z1_p1", "name: z1_renamed")

    ws.update_document(PORTS)

    ecu_diags = ws.documents_diags.get("ecus/zonal_platform1", [])
    assert any(d.get("type") == "major" for d in ecu_diags)
    _assert_matches_full_reload(ws, root, config, PORTS)


def test_adding_a_port_matches_full_reload(workspace):
    ws, root, config = workspace
    (root / PORTS).write_text(
        (root / PORTS).read_text()
        + "\n"
        + "  - name: z1_extra\n"
        + "    mdi_config:\n"
        + "      mode: base_t1\n"
        + "      speed: 100\n"
        + "      duplex: full\n"
        + "      role: slave\n"
        + "      autonegotiation: false\n"
    )

    ws.update_document(PORTS)

    zonal = next(e for e in ws.flync_model.ecus if e.name == "zonal_platform1")
    assert "z1_extra" in [p.name for p in zonal.ports]
    _assert_matches_full_reload(ws, root, config, PORTS)


@pytest.mark.parametrize(
    "rel",
    [
        "ecus/zonal_platform1/switches/z1_switch1.flync.yaml",
        "ecus/eth_ecu/controllers/eth_ecu_controller1/controller_metadata.flync.yaml",
        "communication/tcp_profiles.flync.yaml",
        "system_metadata.flync.yaml",
    ],
)
def test_touch_various_documents_matches_full_reload(workspace, rel):
    ws, root, config = workspace

    affected = ws.update_document(rel)

    assert rel in affected
    _assert_matches_full_reload(ws, root, config, rel)


def test_unknown_document_falls_back_to_full_reload(workspace):
    ws, root, config = workspace
    # a path that is not an indexed load-node still leaves a consistent workspace
    ws.update_document("ecus/zonal_platform1/ecu_metadata.flync.yaml")
    _assert_matches_full_reload(ws, root, config, "ecu_metadata")


def test_update_document_cleans_duplicated_object_ids(workspace):
    """
    After a partial document update, ``_duplicated_objects_ids`` keys must
    all exist in ``self.objects`` and none of the removed object ids
    may linger as keys or values.  This guards against a gap where
    ``_purge_object_subtree`` purges ``self.objects`` but leaves stale
    entries in ``_duplicated_objects_ids``.
    """
    import yaml

    ws, root, _ = workspace
    rel = "ecus/zonal_platform1/switches/z1_switch1.flync.yaml"
    file = root / rel

    with open(file, "r") as f:
        data = yaml.safe_load(f)
    assert "host_controller" in data
    del data["host_controller"]

    with open(file, "w") as f:
        yaml.safe_dump(data, f, sort_keys=False)

    hc_obj_id = "ecus.zonal_platform1.switches.z1_switch1.host_controller"
    ids = [hc_obj_id, f"{hc_obj_id}.mac_address", f"{hc_obj_id}.virtual_interfaces"]
    for id in ids:
        assert ws.has_object(id), f"{id} not found"

    # Collect the state of _duplicated_objects_ids before the update
    pre_dup = {k: list(v) for k, v in ws._duplicated_objects_ids.items()}

    ws.update_document(rel)

    for id in ids:
        assert not ws.has_object(id), f"{id} should be removed since the host_controller was removed from the document"

    # After update, the purged ids must not appear as keys or values
    all_dup_values = {v for vals in ws._duplicated_objects_ids.values() for v in vals}
    for removed_id in ids:
        assert removed_id not in ws._duplicated_objects_ids, f"stale key {removed_id} in _duplicated_objects_ids"
        assert removed_id not in all_dup_values, f"stale value {removed_id} in _duplicated_objects_ids"
