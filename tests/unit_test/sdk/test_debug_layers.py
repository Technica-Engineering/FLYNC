"""Tests for the debug-layer list/dict type-mismatch detection.

When a YAML field that expects a list receives a single mapping (a dict — i.e. the
user forgot the leading "- "), the validator chain raises a clear Layer 4 error.

Three distinct error pathways are covered:

  A  validate_list_items_and_remove  (BeforeValidator raises err_minor directly for dict input)
  B  none_to_empty_list inside a parent validate_or_remove  (dict buried in sub_errors string)
  C  plain List[T] with no BeforeValidator  (native Pydantic list_type wrapped by _wrap_native_error)

Each scenario copies the example workspace to a temp directory, applies ONE targeted
mutation, then asserts that run_workspace_validation produces the expected Layer 4
message. Related scenarios are grouped into a single test function (rather than one
test per scenario) to keep the suite easy to scan and maintain; each still asserts on
its own isolated fixture/workspace copy.
"""

import re
import shutil
from pathlib import Path
from types import SimpleNamespace
from typing import Annotated, List, Optional

import pytest
import yaml
from pydantic import BaseModel

import flync.sdk.helpers.debug_layers.layer1_structure as layer1_mod
import flync.sdk.helpers.debug_layers.layer2_yaml as layer2_mod
import flync.sdk.helpers.debug_layers.layer3_4_5_workspace as layer345_mod
from flync.core.annotations.external import External, NamingStrategy, OutputStrategy
from flync.sdk.helpers import debug as debug_mod
from flync.sdk.helpers.debug_layers.layer1_structure import StructureIssue, check_structure
from flync.sdk.helpers.debug_layers.layer2_yaml import YAMLIssue, check_yaml_syntax
from flync.sdk.helpers.debug_layers.layer3_4_5_workspace import run_workspace_validation
from flync.sdk.helpers.debug_layers.runner import run_debug

EXAMPLES = Path(__file__).parents[3] / "examples" / "flync_example"

# Paths relative to the workspace root
_IFACE_CFG = "ecus/eth_ecu/controllers/eth_ecu_controller1" "/ethernet_interfaces/eth_ecu_c1_iface1/interface_config.flync.yaml"
_DIAG_CAN = "communication/channels/can/diag_can.flync.yaml"
_SOCKET_PDU = "ecus/zonal_platform1/controllers/z1_controller2" "/ethernet_interfaces/z1_c2_iface1/sockets/socket_pdu.flync.yaml"
_TOPOLOGY = "topology/system_topology.flync.yaml"
_CAN_IFACE = "ecus/high_performance_compute/controllers/hpc_controller1" "/can_interfaces/diag_can_interface.flync.yaml"
_POWERTRAIN_CAN_IFACE = "ecus/high_performance_compute/controllers/hpc_controller1" "/can_interfaces/powertrain_can_interface.flync.yaml"
_LIN_BUS = "communication/channels/lin/body_lin.flync.yaml"
_ETH_CONTAINER = "communication/channels/ethernet_pdu_containers" "/eth_powertrain_container.flync.yaml"
_HPC_SWITCH = "ecus/high_performance_compute/switches/hpc_switch1.flync.yaml"


def _load(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _dump(path: Path, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True)


def _run(workspace: Path):
    _, issues = run_workspace_validation(workspace)
    return issues


def _l4(issues) -> list:
    return [i for i in issues if i.layer == 4]


def _list_type_errors(workspace: Path) -> list:
    return [i for i in _l4(_run(workspace)) if "must be a list" in i.message]


def _new_workspace(dest: Path) -> Path:
    """Fresh copy of the example workspace with any user-introduced dict-as-list
    mutations reverted so every scenario starts from a known-clean baseline."""
    shutil.copytree(EXAMPLES, dest)

    # Revert interface_config: fix filter at child_classes[1] (dict → list)
    iface_path = dest / _IFACE_CFG
    iface_data = _load(iface_path)
    cc = iface_data["compute_nodes"][0]["htb"]["child_classes"]
    if isinstance(cc[1]["filter"], dict):
        cc[1]["filter"] = [cc[1]["filter"]]
    # Revert interface_config: fix eth_ecu_vm2.virtual_interfaces (dict → list)
    vi = iface_data["compute_nodes"][1]["virtual_interfaces"]
    if isinstance(vi, dict):
        iface_data["compute_nodes"][1]["virtual_interfaces"] = [vi]
    _dump(iface_path, iface_data)

    # Revert diag_can: fix frames[0].packed_pdus (dict → list)
    can_path = dest / _DIAG_CAN
    can_data = _load(can_path)
    pdus = can_data["frames"][0].get("packed_pdus")
    if isinstance(pdus, dict):
        can_data["frames"][0]["packed_pdus"] = [pdus]
    _dump(can_path, can_data)

    return dest


@pytest.fixture
def workspace(tmp_path):
    return _new_workspace(tmp_path / "ws")


def test_clean_workspace_has_no_list_type_errors(workspace):
    """Unmodified example workspace must produce zero 'must be a list' errors."""
    errs = _list_type_errors(workspace)
    assert errs == [], "Unexpected list-type errors in clean workspace:\n" + "\n".join(
        f"  layer={e.layer} field={e.field} msg={e.message}" for e in errs
    )


# ---------------------------------------------------------------------------
# Pathways A/B/C — every list-typed field that can receive a lone dict instead
# of a list must be caught as a Layer 4 "must be a list" error, regardless of
# which validator mechanism guards it:
#
#   A  validate_list_items_and_remove  (BeforeValidator raises err_minor directly)
#   B  none_to_empty_list inside a parent validate_or_remove (dict in sub_errors)
#   C  plain List[T] with no BeforeValidator (native Pydantic list_type, wrapped)
#
# One mutator per field drives the same load -> mutate -> dump -> assert flow;
# only the mutation and the expected field name vary. All cases are checked
# inside a single test so failures across every field are reported together.
# ---------------------------------------------------------------------------


def _mutate_virtual_interfaces(data: dict) -> bool:
    data["compute_nodes"][1]["virtual_interfaces"] = data["compute_nodes"][1]["virtual_interfaces"][0]
    return True


def _mutate_sockets(data: dict) -> bool:
    data["sockets"] = data["sockets"][0]
    return True


def _mutate_htb_filter(data: dict) -> bool:
    cc = data["compute_nodes"][0]["htb"]["child_classes"]
    cc[0]["filter"] = cc[0]["filter"][0]
    return True


def _mutate_htb_child_classes(data: dict) -> bool:
    htb = data["compute_nodes"][0]["htb"]
    htb["child_classes"] = htb["child_classes"][0]
    return True


def _mutate_packed_pdus(data: dict) -> bool:
    data["frames"][0]["packed_pdus"] = data["frames"][0]["packed_pdus"][0]
    return True


def _mutate_can_frames(data: dict) -> bool:
    data["frames"] = data["frames"][0]
    return True


def _mutate_ptp_ports(data: dict) -> bool:
    ptp_ports = data.get("ptp_config", {}).get("ptp_ports")
    if not ptp_ports:
        return False
    data["ptp_config"]["ptp_ports"] = ptp_ports[0]
    return True


def _mutate_receiver_frames(data: dict) -> bool:
    data["receiver_frames"] = data["receiver_frames"][0]
    return True


def _mutate_sender_frames(data: dict) -> bool:
    data["sender_frames"] = data["sender_frames"][0]
    return True


def _mutate_forwarder_egresses(data: dict) -> bool:
    data["forwarder_frames"][0]["egresses"] = data["forwarder_frames"][0]["egresses"][0]
    return True


def _mutate_lin_schedule_entries(data: dict) -> bool:
    data["schedule_tables"][0]["entries"] = data["schedule_tables"][0]["entries"][0]
    return True


def _mutate_lin_frames(data: dict) -> bool:
    data["frames"] = data["frames"][0]
    return True


def _mutate_contained_pdus(data: dict) -> bool:
    data["contained_pdus"] = data["contained_pdus"][0]
    return True


def _mutate_traffic_classes(data: dict) -> bool:
    data["ports"][0]["traffic_classes"] = data["ports"][0]["traffic_classes"][0]
    return True


def _mutate_stream_identification(data: dict) -> bool:
    port = data["ports"][0]["ingress_streams"][0]
    port["stream_identification"] = port["stream_identification"][0]
    return True


def _mutate_vlans(data: dict) -> bool:
    data["vlans"] = data["vlans"][0]
    return True


def _mutate_ingress_streams(data: dict) -> bool:
    data["ports"][0]["ingress_streams"] = data["ports"][0]["ingress_streams"][0]
    return True


# (pathway, file, mutator, field-name substring expected in message)
_LIST_TYPE_CASES = [
    ("A", _IFACE_CFG, _mutate_virtual_interfaces, "virtual interface"),
    ("A", _SOCKET_PDU, _mutate_sockets, "socket"),
    ("B", _IFACE_CFG, _mutate_htb_filter, "filter"),
    ("B", _IFACE_CFG, _mutate_htb_child_classes, "child_classes"),
    ("C", _DIAG_CAN, _mutate_packed_pdus, "packed_pdus"),
    ("C", _DIAG_CAN, _mutate_can_frames, "frames"),
    ("C", _IFACE_CFG, _mutate_ptp_ports, "ptp_ports"),
    ("C", _CAN_IFACE, _mutate_receiver_frames, "receiver_frames"),
    ("C", _CAN_IFACE, _mutate_sender_frames, "sender_frames"),
    ("C", _POWERTRAIN_CAN_IFACE, _mutate_forwarder_egresses, "egresses"),
    ("C", _LIN_BUS, _mutate_lin_schedule_entries, "entries"),
    ("C", _LIN_BUS, _mutate_lin_frames, "frames"),
    ("C", _ETH_CONTAINER, _mutate_contained_pdus, "contained_pdus"),
    ("C", _HPC_SWITCH, _mutate_traffic_classes, "traffic_classes"),
    ("C", _HPC_SWITCH, _mutate_stream_identification, "stream_identification"),
    ("C", _HPC_SWITCH, _mutate_vlans, "vlans"),
    ("C", _HPC_SWITCH, _mutate_ingress_streams, "ingress_streams"),
]


def test_dict_instead_of_list_detected_across_all_pathways(tmp_path):
    """Every list-typed field, across all three validator pathways, must be
    reported as a Layer 4 'must be a list' error naming the offending field."""
    failures = []
    for idx, (pathway, rel_path, mutate, expected) in enumerate(_LIST_TYPE_CASES):
        ws = _new_workspace(tmp_path / f"case_{idx}")
        path = ws / rel_path
        data = _load(path)
        if not mutate(data):
            continue  # optional fixture field not present in this example workspace
        _dump(path, data)

        errs = _list_type_errors(ws)
        label = f"{pathway}:{expected}"
        if not errs:
            failures.append(f"{label} - no list-type Layer 4 error produced")
        elif not all(e.layer == 4 for e in errs):
            failures.append(f"{label} - error(s) not on layer 4: {[e.layer for e in errs]}")
        elif not any(expected in e.message for e in errs):
            failures.append(f"{label} - message did not mention field: {[e.message for e in errs]}")

    assert not failures, "List-as-dict detection failed for:\n" + "\n".join(failures)


# ---------------------------------------------------------------------------
# Layer isolation — dict-as-list must land in Layer 4, not Layer 3, must name
# the field, must keep its full nested field path, and must not swallow an
# independent real Layer 3 error.
# ---------------------------------------------------------------------------


def test_layer_isolation(tmp_path):
    # A dict-as-list mutation must produce a Layer 4 error (not Layer 3) that
    # names the field, not a generic placeholder.
    ws1 = _new_workspace(tmp_path / "ws1")
    data = _load(ws1 / _DIAG_CAN)
    data["frames"][0]["packed_pdus"] = data["frames"][0]["packed_pdus"][0]
    _dump(ws1 / _DIAG_CAN, data)

    issues = _run(ws1)
    l3_for_field = [i for i in issues if i.layer == 3 and "packed_pdus" in (i.field or "")]
    l4_list_type = [i for i in issues if i.layer == 4 and "must be a list" in i.message]
    assert l4_list_type, "list-type error must appear in Layer 4"
    assert not l3_for_field, "list-type error must NOT appear as a Layer 3 structural error"
    assert not any("list field" in e.message for e in l4_list_type), "message must not use the generic placeholder 'list field'"
    assert any("packed_pdus" in e.message for e in l4_list_type)

    # A nested list-type error's field path must drill down to the actual field.
    ws2 = _new_workspace(tmp_path / "ws2")
    iface_data = _load(ws2 / _IFACE_CFG)
    cc = iface_data["compute_nodes"][0]["htb"]["child_classes"]
    cc[0]["filter"] = cc[0]["filter"][0]
    _dump(ws2 / _IFACE_CFG, iface_data)

    errs = _list_type_errors(ws2)
    assert errs
    assert any("filter" in e.field for e in errs), f"Expected 'filter' in field path, got: {[e.field for e in errs]}"

    # A separate, real missing-field error must still surface as Layer 3
    # alongside the list-type error above.
    del iface_data["compute_nodes"][0]["htb"]["child_classes"][0]["classid"]
    _dump(ws2 / _IFACE_CFG, iface_data)

    issues2 = _run(ws2)
    l3 = [i for i in issues2 if i.layer == 3]
    assert any(
        "classid" in (i.field or "").lower() or "classid" in i.message.lower() for i in l3
    ), f"Missing classid should appear as a Layer 3 error, got: {[(i.layer, i.field, i.message) for i in l3]}"


# ---------------------------------------------------------------------------
# Fixture models for debug.py / layer1_structure.py unit tests
#
# Small standalone pydantic models (instead of the full FLYNCModel tree) keep
# these tests fast and independent of the example workspace's actual shape.
# ---------------------------------------------------------------------------


class Detail(BaseModel):
    id: str = "d1"


class ItemWithSub(BaseModel):
    """List item whose type has an External sub-field -> serialises to a subfolder."""

    detail: Annotated[Detail, External(output_structure=OutputStrategy.SINGLE_FILE)]


class LeafOnly(BaseModel):
    """List item with no External fields -> serialises to a flat file."""

    id: str = "leaf"


class Root(BaseModel):
    items: Annotated[
        List[ItemWithSub],
        External(output_structure=OutputStrategy.FOLDER, naming_strategy=NamingStrategy.FIELD_NAME),
    ]
    leaves: Annotated[
        List[LeafOnly],
        External(output_structure=OutputStrategy.FOLDER, naming_strategy=NamingStrategy.FIELD_NAME),
    ]
    solo: Annotated[
        Optional[Detail],
        External(
            output_structure=OutputStrategy.SINGLE_FILE,
            naming_strategy=NamingStrategy.FIXED_PATH,
            path="config",
        ),
    ] = None


def _populate_valid_root(root_dir: Path) -> None:
    """Build a filesystem tree that fully satisfies the Root model above."""
    (root_dir / "items" / "item1").mkdir(parents=True)
    (root_dir / "items" / "item1" / "detail.flync.yaml").write_text("id: d1\n", encoding="utf-8")
    (root_dir / "leaves").mkdir(parents=True)
    (root_dir / "leaves" / "leaf1.flync.yaml").write_text("id: leaf\n", encoding="utf-8")


def test_debug_type_helpers():
    """_unwrap_type / _is_optional / _is_pydantic_model / _has_external_fields."""
    assert debug_mod._unwrap_type(Detail) == (False, Detail)
    assert debug_mod._unwrap_type(Optional[Detail]) == (False, Detail)
    assert debug_mod._unwrap_type(List[Detail]) == (True, Detail)
    assert debug_mod._unwrap_type(Optional[List[Detail]]) == (True, Detail)

    assert debug_mod._is_optional(Optional[Detail]) is True
    assert debug_mod._is_optional(Detail) is False
    assert debug_mod._is_optional(List[Detail]) is False

    assert debug_mod._is_pydantic_model(Detail) is True
    assert debug_mod._is_pydantic_model(str) is False
    # get_origin(List[int]) returns list, which isn't a class issubclass can use directly
    assert debug_mod._is_pydantic_model(List[int]) is False

    assert debug_mod._has_external_fields(ItemWithSub) is True
    assert debug_mod._has_external_fields(LeafOnly) is False


def test_display_name_and_collect_ext_fields():
    folder_ext = External(output_structure=OutputStrategy.FOLDER)
    assert debug_mod._display_name("items", folder_ext, is_file=False) == "items"

    file_ext = External(output_structure=OutputStrategy.SINGLE_FILE)
    assert debug_mod._display_name("detail", file_ext, is_file=True) == "detail.flync.yaml"

    fixed_path_ext = External(
        output_structure=OutputStrategy.SINGLE_FILE,
        naming_strategy=NamingStrategy.FIXED_PATH,
        path="config",
    )
    assert debug_mod._display_name("solo", fixed_path_ext, is_file=True) == "config.flync.yaml"

    fields = debug_mod._collect_ext_fields(Root)
    names = {name for name, _, _ in fields}
    assert names == {"items", "leaves", "solo"}
    assert debug_mod._collect_ext_fields(LeafOnly) == []


def test_print_structure_and_subtree(tmp_path, monkeypatch):
    monkeypatch.setattr(debug_mod, "_EXPORTS_DIR", tmp_path)

    out = debug_mod.print_flync_structure(Root)
    assert out == tmp_path / "Root_structure.txt"
    content = out.read_text(encoding="utf-8")
    assert "!! required" in content
    assert "Root/" in content
    assert "!! items/" in content
    assert "!! leaves/" in content
    assert "   config.flync.yaml" in content
    # List-item placeholders and the trailing "..." row
    assert "<items_item>" in content
    assert "<leaves_item>" in content
    assert content.count("...") == 2

    sub_out = debug_mod.print_field_subtree(Root, "leaves")
    assert sub_out == tmp_path / "leaves_structure.txt"
    sub_content = sub_out.read_text(encoding="utf-8")
    assert sub_content.startswith("!! required\n\nleaves/")
    assert "<leaves_item>.flync.yaml" in sub_content

    with pytest.raises(ValueError):
        debug_mod.print_field_subtree(LeafOnly, "id")


def test_check_structure_scenarios(tmp_path):
    # Missing required folders are reported as errors.
    missing_dir = tmp_path / "missing"
    missing_dir.mkdir()
    errors = [i for i in check_structure(Root, missing_dir, missing_dir) if i.severity == "error"]
    assert {"items", "leaves"} <= {name for i in errors for name in [i.message.split("'")[1]] if "Required" in i.message}

    # A fully valid tree has no issues.
    valid_dir = tmp_path / "valid"
    valid_dir.mkdir()
    _populate_valid_root(valid_dir)
    assert check_structure(Root, valid_dir, valid_dir) == []

    # A stray file directly inside a substructure folder is a warning.
    stray_dir = tmp_path / "stray"
    stray_dir.mkdir()
    _populate_valid_root(stray_dir)
    (stray_dir / "items" / "stray.flync.yaml").write_text("id: x\n", encoding="utf-8")
    warnings = [i for i in check_structure(Root, stray_dir, stray_dir) if i.severity == "warning"]
    assert any("stray.flync.yaml" in w.message and "directly inside" in w.message for w in warnings)

    # An unexpected subfolder inside a flat list folder is a warning.
    unexpected_dir = tmp_path / "unexpected"
    unexpected_dir.mkdir()
    _populate_valid_root(unexpected_dir)
    (unexpected_dir / "leaves" / "unexpected_dir").mkdir()
    warnings = [i for i in check_structure(Root, unexpected_dir, unexpected_dir) if i.severity == "warning"]
    assert any("unexpected_dir" in w.message and "Unexpected folder" in w.message for w in warnings)

    # A file placed at the wrong location is an error.
    # 'detail.flync.yaml' is only ever expected inside items/<item>/, not at the root.
    wrong_dir = tmp_path / "wrong"
    wrong_dir.mkdir()
    _populate_valid_root(wrong_dir)
    (wrong_dir / "detail.flync.yaml").write_text("id: d1\n", encoding="utf-8")
    errors = [i for i in check_structure(Root, wrong_dir, wrong_dir) if i.severity == "error"]
    assert any("detail.flync.yaml" in e.message and "wrong location" in e.message for e in errors)

    # A typo'd folder name gets a "did you mean" hint.
    typo_dir = tmp_path / "typo"
    typo_dir.mkdir()
    _populate_valid_root(typo_dir)
    (typo_dir / "item").mkdir()  # typo of "items"
    warnings = [i for i in check_structure(Root, typo_dir, typo_dir) if i.severity == "warning"]
    assert any("Did you mean 'items'" in w.hint for w in warnings)

    # An unrecognised entry with no typo match still warns.
    unknown_dir = tmp_path / "unknown"
    unknown_dir.mkdir()
    _populate_valid_root(unknown_dir)
    (unknown_dir / "totally_unknown.flync.yaml").write_text("id: x\n", encoding="utf-8")
    warnings = [i for i in check_structure(Root, unknown_dir, unknown_dir) if i.severity == "warning"]
    assert any("totally_unknown.flync.yaml" in w.message for w in warnings)

    # readme/hidden files are ignored entirely.
    ignored_dir = tmp_path / "ignored"
    ignored_dir.mkdir()
    _populate_valid_root(ignored_dir)
    (ignored_dir / "readme.md").write_text("docs\n", encoding="utf-8")
    (ignored_dir / ".hidden").write_text("x\n", encoding="utf-8")
    assert check_structure(Root, ignored_dir, ignored_dir) == []

    # A missing directory path produces no issues (nothing to check yet).
    assert check_structure(Root, tmp_path / "does_not_exist", tmp_path) == []

    # StructureIssue dataclass defaults.
    issue = StructureIssue(severity="warning", message="msg")
    assert issue.hint == ""
    assert issue.path == ""


_VALID_YAML = "id: value\nlist:\n  - a\n  - b\n"
_INVALID_YAML = "id: [1, 2\nother: 3\n"


def test_yaml_syntax_scenarios(tmp_path):
    valid_dir = tmp_path / "valid"
    valid_dir.mkdir()
    (valid_dir / "good.flync.yaml").write_text(_VALID_YAML, encoding="utf-8")
    assert check_yaml_syntax(valid_dir) == []

    invalid_dir = tmp_path / "invalid"
    invalid_dir.mkdir()
    (invalid_dir / "bad.flync.yaml").write_text(_INVALID_YAML, encoding="utf-8")
    issues = check_yaml_syntax(invalid_dir)
    assert len(issues) == 1
    assert issues[0].path == "bad.flync.yaml"
    assert issues[0].message

    ignored_dir = tmp_path / "ignored"
    ignored_dir.mkdir()
    (ignored_dir / "not_flync.yaml").write_text(_INVALID_YAML, encoding="utf-8")
    assert check_yaml_syntax(ignored_dir) == []

    nested_root = tmp_path / "nested"
    nested = nested_root / "a" / "b"
    nested.mkdir(parents=True)
    (nested / "bad.flync.yaml").write_text(_INVALID_YAML, encoding="utf-8")
    nested_issues = check_yaml_syntax(nested_root)
    assert len(nested_issues) == 1
    assert "bad.flync.yaml" in nested_issues[0].path

    # Directly exercise the PyYAML fallback path used when ruamel.yaml is unavailable.
    fallback_valid: list = []
    layer2_mod._check_with_pyyaml(valid_dir, fallback_valid)
    assert fallback_valid == []

    fallback_invalid: list = []
    layer2_mod._check_with_pyyaml(invalid_dir, fallback_invalid)
    assert len(fallback_invalid) == 1
    assert fallback_invalid[0].path == "bad.flync.yaml"

    # YAMLIssue dataclass defaults.
    issue = YAMLIssue(message="m", path="p")
    assert issue.line is None
    assert issue.col is None


def _plain(captured: str) -> str:
    """Strip rich's ANSI escape codes/highlighter splits and collapse whitespace."""
    return " ".join(re.sub(r"\x1b\[[0-9;]*m", "", captured).split())


def test_run_debug_scenarios(tmp_path, capsys, monkeypatch):
    # Nonexistent path is reported and stops immediately.
    run_debug(tmp_path / "nope")
    assert "Path does not exist" in capsys.readouterr().out

    # Stops at Layer 1 on a structure error.
    with monkeypatch.context() as m:
        m.setattr(
            layer1_mod,
            "check_structure",
            lambda model_cls, dir_path, root_path: [StructureIssue(severity="error", message="Required folder missing: 'ecus'")],
        )
        run_debug(tmp_path)
        assert "Stopped at Layer 1." in _plain(capsys.readouterr().out)

    # Stops at Layer 2 on a YAML syntax error.
    with monkeypatch.context() as m:
        m.setattr(layer1_mod, "check_structure", lambda model_cls, dir_path, root_path: [])
        m.setattr(
            layer2_mod,
            "check_yaml_syntax",
            lambda dir_path: [YAMLIssue(message="bad syntax", path="ecus/x.flync.yaml", line=3)],
        )
        run_debug(tmp_path)
        assert "Stopped at Layer 2." in _plain(capsys.readouterr().out)

    # Reports "Model is valid" when no issues are found at any layer.
    with monkeypatch.context() as m:
        m.setattr(layer1_mod, "check_structure", lambda model_cls, dir_path, root_path: [])
        m.setattr(layer2_mod, "check_yaml_syntax", lambda dir_path: [])
        m.setattr(
            layer345_mod,
            "run_workspace_validation",
            lambda dir_path: (SimpleNamespace(model=object()), []),
        )
        run_debug(tmp_path)
        assert "Model is valid" in capsys.readouterr().out

    # Layer 4 and Layer 5 issues are reported without stopping the run.
    from flync.sdk.helpers.debug_layers.layer3_4_5_workspace import WorkspaceIssue

    with monkeypatch.context() as m:
        m.setattr(layer1_mod, "check_structure", lambda model_cls, dir_path, root_path: [])
        m.setattr(layer2_mod, "check_yaml_syntax", lambda dir_path: [])
        m.setattr(
            layer345_mod,
            "run_workspace_validation",
            lambda dir_path: (
                SimpleNamespace(model=object()),
                [
                    WorkspaceIssue(layer=4, severity="error", message="bad value", field="x"),
                    WorkspaceIssue(layer=5, severity="warning", message="system warning", field="y"),
                ],
            ),
        )
        run_debug(tmp_path)
        out = _plain(capsys.readouterr().out)
        assert "Layer 4 - Field Value Errors" in out
        assert "bad value" in out
        assert "Layer 5 - System-Wide Validation" in out
        assert "system warning" in out
        assert "Stopped at Layer 3." not in out
