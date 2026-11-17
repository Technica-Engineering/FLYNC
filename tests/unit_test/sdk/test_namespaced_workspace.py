"""Workspace-level tests for ``Namespaced`` lists: SOME/IP services and PDUs stored in sub-folders."""

import shutil
import sys
from pathlib import Path

import pytest

from flync.sdk.context.workspace_config import WorkspaceConfiguration
from flync.sdk.workspace.flync_workspace import FLYNCWorkspace
from tests.example_paths import FLYNC_EXAMPLE

SERVICES = Path("communication/someip/services")
PDUS = Path("communication/channels/pdus")
BODY_CAN = Path("communication/channels/can/body_can.flync.yaml")
SERVICE_NAME = "Enhanced Testability Services"


def _load(root: Path) -> FLYNCWorkspace:
    return FLYNCWorkspace.load_workspace("namespaced", root, WorkspaceConfiguration(map_objects=False))


def _service_names(workspace: FLYNCWorkspace) -> list[str]:
    return [s.name for s in workspace.flync_model.communication.someip_config.services]


def _pdu_names(workspace: FLYNCWorkspace) -> list[str]:
    return [p.name for p in workspace.flync_model.communication.channels.pdus]


def _copy_service(root: Path, folder: str, service_id: int) -> Path:
    """Copy the example service into ``folder`` with a distinct id and E2E data ids (so only the name repeats)."""
    text = (root / SERVICES / "ets.flync.yaml").read_text(encoding="utf-8")
    text = text.replace("id: 0x0101", f"id: {service_id:#06x}").replace("data_id: 0x1234567", f"data_id: 0x{service_id & 0xF}234567")
    target = root / SERVICES / folder / "ets.flync.yaml"
    target.parent.mkdir(parents=True)
    target.write_text(text, encoding="utf-8")
    return target


def _copy_pdu(root: Path, folder: str) -> Path:
    target = root / PDUS / folder / "PDU_NmMessage.flync.yaml"
    target.parent.mkdir(parents=True)
    shutil.copy(root / PDUS / "PDU_NmMessage.flync.yaml", target)
    return target


@pytest.fixture
def workspace_root(tmp_path) -> Path:
    root = tmp_path / "flync_example"
    shutil.copytree(FLYNC_EXAMPLE, root)
    return root


@pytest.fixture
def baseline_errors(workspace_root) -> list[str]:
    return sorted(e["msg"] for e in _load(workspace_root).load_errors)


def test_services_in_folders_get_qualified_names(workspace_root, baseline_errors):
    _copy_service(workspace_root, "abc", 0x0102)
    _copy_service(workspace_root, "abc/def", 0x0103)

    workspace = _load(workspace_root)

    assert sorted(_service_names(workspace)) == sorted([SERVICE_NAME, f"abc::{SERVICE_NAME}", f"abc::def::{SERVICE_NAME}"])
    assert sorted(e["msg"] for e in workspace.load_errors) == baseline_errors


def test_pdus_in_folders_get_qualified_names_and_are_referenced_by_them(workspace_root, baseline_errors):
    _copy_pdu(workspace_root, "abc")
    can = workspace_root / BODY_CAN
    text = can.read_text(encoding="utf-8")
    can.write_text(text.replace("pdu_ref: PDU_NmMessage", "pdu_ref: abc::PDU_NmMessage", 1), encoding="utf-8")

    workspace = _load(workspace_root)

    assert {"PDU_NmMessage", "abc::PDU_NmMessage"} <= set(_pdu_names(workspace))
    assert sorted(e["msg"] for e in workspace.load_errors) == baseline_errors
    refs = [inst.pdu_ref for bus in workspace.flync_model.communication.channels.can_buses for frame in bus.frames for inst in frame.packed_pdus]
    assert refs.count("abc::PDU_NmMessage") == 1


def test_unqualified_reference_does_not_resolve_to_a_namespaced_pdu(workspace_root):
    """A PDU that exists only in a folder is known solely by its qualified name."""
    source = workspace_root / PDUS / "PDU_NmMessage.flync.yaml"
    target = workspace_root / PDUS / "abc" / "PDU_NmMessage.flync.yaml"
    target.parent.mkdir()
    shutil.move(source, target)

    with pytest.raises(ValueError) as exc_info:
        _load(workspace_root)

    assert "CANBus 'BodyCAN' references unknown PDU(s): ['PDU_NmMessage']" in str(exc_info.value)


def test_hidden_entries_in_a_namespace_folder_are_ignored(workspace_root, baseline_errors):
    _copy_service(workspace_root, "abc", 0x0102)
    (workspace_root / SERVICES / "abc" / ".hidden").mkdir()
    (workspace_root / SERVICES / "abc" / ".hidden" / "x.flync.yaml").write_text("name: x\n", encoding="utf-8")

    workspace = _load(workspace_root)

    assert len(_service_names(workspace)) == 2
    assert sorted(e["msg"] for e in workspace.load_errors) == baseline_errors


@pytest.mark.skipif(sys.platform == "win32", reason="':' is not allowed in a Windows folder name")
def test_namespace_folder_containing_the_separator_is_skipped(workspace_root, caplog):
    _copy_service(workspace_root, "a::b", 0x0102)

    workspace = _load(workspace_root)

    assert _service_names(workspace) == [SERVICE_NAME]
    assert "must not contain '::'" in caplog.text


def test_update_document_picks_up_a_new_nested_service_and_keeps_names(workspace_root):
    workspace = _load(workspace_root)
    assert _service_names(workspace) == [SERVICE_NAME]

    target = _copy_service(workspace_root, "abc", 0x0102)
    workspace.update_document(target)
    assert sorted(_service_names(workspace)) == sorted([SERVICE_NAME, f"abc::{SERVICE_NAME}"])

    target.write_text(target.read_text(encoding="utf-8").replace("minor_version: 1", "minor_version: 2", 1), encoding="utf-8")
    workspace.update_document(target)
    by_name = {s.name: s for s in workspace.flync_model.communication.someip_config.services}
    assert by_name[f"abc::{SERVICE_NAME}"].minor_version == 2


def test_save_round_trip_keeps_folders_and_never_writes_the_separator_into_a_path(workspace_root, tmp_path):
    _copy_service(workspace_root, "abc", 0x0102)
    _copy_pdu(workspace_root, "abc")
    loaded = _load(workspace_root)

    out = tmp_path / "saved"
    saved = FLYNCWorkspace("saved", out)
    saved.load_flync_model(loaded.flync_model)
    saved.generate_configs()

    assert (out / SERVICES / "abc" / f"{SERVICE_NAME}.flync.yaml").is_file()
    assert (out / PDUS / "abc" / "PDU_NmMessage.flync.yaml").is_file()
    assert not [p for p in out.rglob("*") if "::" in p.name]
    assert "abc::" not in (out / SERVICES / "abc" / f"{SERVICE_NAME}.flync.yaml").read_text(encoding="utf-8")

    reloaded = _load(out)
    assert sorted(_service_names(reloaded)) == sorted(_service_names(loaded))
    assert sorted(_pdu_names(reloaded)) == sorted(_pdu_names(loaded))


def test_check_structure_accepts_namespace_folders(workspace_root):
    from flync.model import FLYNCModel
    from flync.sdk.helpers.debug_layers.layer1_structure import check_structure

    _copy_service(workspace_root, "abc", 0x0102)
    _copy_pdu(workspace_root, "abc")

    issues = check_structure(FLYNCModel, workspace_root, workspace_root)

    assert not [i for i in issues if "abc" in i.path or "abc" in i.message]
