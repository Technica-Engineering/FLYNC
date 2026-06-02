"""System-level tests for the PDU forwarder feature."""

import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError

from flync.model.flync_4_signal.forwarder import (
    CANFrameEgress,
    EthSocketEgress,
)
from flync.sdk.workspace.flync_workspace import FLYNCWorkspace

CANONICAL_PATH = Path(__file__).parents[3] / "examples" / "flync_example"


# Canonical-example coverage: all four gateway scenarios resolve from the baked-in YAML.


@pytest.fixture(scope="module")
def loaded_canonical_workspace() -> FLYNCWorkspace:
    return FLYNCWorkspace.load_workspace("flync_example", CANONICAL_PATH)


def test_canonical_workspace_loads_with_forwarder_content(loaded_canonical_workspace):
    ws = loaded_canonical_workspace
    assert ws is not None
    assert ws.flync_model is not None


def test_canonical_workspace_exposes_can_frame_forwarder(loaded_canonical_workspace):
    forwarders = loaded_canonical_workspace.flync_model.get_all_can_frame_forwarders()
    assert len(forwarders) == 1
    fwd = forwarders[0]
    assert fwd.frame_ref == "Frame_EngineStatus"
    assert len(fwd.egresses) == 2


def test_canonical_scenario_1_can_to_can_egress_present(loaded_canonical_workspace):
    """Forward Frame_EngineStatus to Frame_EngineDiagResponse on DiagCAN."""

    fwd = loaded_canonical_workspace.flync_model.get_all_can_frame_forwarders()[0]
    can_sinks = [s.root for s in fwd.egresses if isinstance(s.root, CANFrameEgress)]
    assert any(s.bus_ref == "DiagCAN" and s.frame_ref == "Frame_EngineDiagResponse" for s in can_sinks)


def test_canonical_scenario_2_can_to_eth_sink_present(loaded_canonical_workspace):
    """The same forwarder fans out to the pdu_engine_status_tx Ethernet socket."""

    fwd = loaded_canonical_workspace.flync_model.get_all_can_frame_forwarders()[0]
    socket_sinks = [s.root for s in fwd.egresses if isinstance(s.root, EthSocketEgress)]
    assert any(s.socket_ref == "pdu_engine_status_tx" for s in socket_sinks)


def test_canonical_workspace_exposes_pdu_forwarder(loaded_canonical_workspace):
    """Canonical example carries one PDUForwarder on pdu_powertrain_rx (drives scenarios 3 + 4)."""

    forwarders = loaded_canonical_workspace.flync_model.get_all_pdu_forwarders()
    assert len(forwarders) == 1
    fwd = forwarders[0]
    assert fwd.pdu_ref == "EthPowertrainContainer"
    assert len(fwd.egresses) == 2


def test_canonical_scenario_3_eth_to_can_with_extraction(loaded_canonical_workspace):
    """The PDU forwarder extracts PDU_EngineStatus from EthPowertrainContainer and re-emits on DiagCAN."""

    fwd = loaded_canonical_workspace.flync_model.get_all_pdu_forwarders()[0]
    can_sinks = [s.root for s in fwd.egresses if isinstance(s.root, CANFrameEgress)]
    assert any(s.bus_ref == "DiagCAN" and s.frame_ref == "Frame_EngineDiagResponse" and s.extract_pdu_ref == "PDU_EngineStatus" for s in can_sinks)


def test_canonical_scenario_4_eth_to_eth_rebridge(loaded_canonical_workspace):
    """The PDU forwarder also re-bridges the whole container to pdu_powertrain_rebridge_tx."""

    fwd = loaded_canonical_workspace.flync_model.get_all_pdu_forwarders()[0]
    socket_sinks = [s.root for s in fwd.egresses if isinstance(s.root, EthSocketEgress)]
    rebridge = next((s for s in socket_sinks if s.socket_ref == "pdu_powertrain_rebridge_tx"), None)
    assert rebridge is not None
    assert rebridge.extract_pdu_ref is None


# Tmpdir helpers for the workspace-level validator tests below (each test copies the canonical workspace and mutates one or two YAMLs).


@pytest.fixture
def workspace_copy(tmpdir) -> Path:
    """Copy the canonical workspace into a tmpdir for safe mutation."""

    destination = Path(tmpdir) / "ws"
    shutil.copytree(CANONICAL_PATH, destination)
    return destination


def _mutate_file(path: Path, replacements: dict[str, str]) -> None:
    """Replace every (old, new) string pair in *path*."""

    text = path.read_text(encoding="utf-8")
    for old, new in replacements.items():
        if old not in text:
            raise AssertionError(f"Text {old!r} not found in {path}")
        text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")


def _load_or_capture(workspace_copy: Path) -> tuple[FLYNCWorkspace | None, Exception | None]:
    """Load the workspace; return (workspace, None) on success or (None, exc) on failure."""

    try:
        return FLYNCWorkspace.load_workspace("flync_example", workspace_copy), None
    except (ValidationError, Exception) as exc:  # noqa BLE001
        return None, exc


def _assert_message_contains(load_result: tuple, substrings: list[str]) -> None:
    """Assert at least one load error / exception text contains every substring."""

    ws, exc = load_result
    combined = ""
    if exc is not None:
        combined = str(exc)
    elif ws is not None:
        combined = str(getattr(ws, "load_errors", []))
    for needle in substrings:
        assert needle in combined, f"Expected {needle!r} in load output, got: {combined[:1500]}"


def _pwrtr_ifc(ws: Path) -> Path:
    return ws / "ecus" / "high_performance_compute" / "controllers" / "hpc_controller1" / "can_interfaces" / "powertrain_can_interface.flync.yaml"


def _diag_ifc(ws: Path) -> Path:
    return ws / "ecus" / "high_performance_compute" / "controllers" / "hpc_controller1" / "can_interfaces" / "diag_can_interface.flync.yaml"


def _hpc_eth_socket_pdu(ws: Path) -> Path:
    return (
        ws
        / "ecus"
        / "high_performance_compute"
        / "controllers"
        / "hpc_controller1"
        / "ethernet_interfaces"
        / "hpc_c1_iface1"
        / "sockets"
        / "socket_pdu.flync.yaml"
    )


# Workspace-level: locality and direction safety.


def test_negative_can_egress_not_in_sender_frames(workspace_copy):
    """Drop Frame_EngineDiagResponse from DiagCAN sender_frames -> locality check fires."""

    _mutate_file(_diag_ifc(workspace_copy), {"- frame_ref: Frame_EngineDiagResponse\n": ""})
    _assert_message_contains(
        _load_or_capture(workspace_copy),
        ["Frame_EngineDiagResponse", "sender_frames"],
    )


def test_negative_eth_socket_egress_unknown_target(workspace_copy):
    """Rename the egress socket the forwarder targets -> err_major (unknown socket on controller)."""

    _mutate_file(
        _hpc_eth_socket_pdu(workspace_copy),
        {"- name: pdu_engine_status_tx": "- name: pdu_engine_status_renamed"},
    )
    _assert_message_contains(
        _load_or_capture(workspace_copy),
        ["pdu_engine_status_tx", "does not exist on controller"],
    )


def test_negative_eth_socket_egress_target_has_no_pdu_sender(workspace_copy):
    """Change the egress socket's deployment so it no longer sends PDU_EngineStatus."""

    _mutate_file(
        _hpc_eth_socket_pdu(workspace_copy),
        {
            "  - name: pdu_engine_status_tx\n    endpoint_address: 10.0.20.5\n    endpoint_type: unicast\n    port_no: 30802\n    protocol: udp\n    deployments:\n      - deployment_type: pdu_sender\n        pdu_ref: PDU_EngineStatus": "  - name: pdu_engine_status_tx\n    endpoint_address: 10.0.20.5\n    endpoint_type: unicast\n    port_no: 30802\n    protocol: udp\n    deployments:\n      - deployment_type: pdu_receiver\n        pdu_ref: PDU_EngineStatus",
        },
    )
    _assert_message_contains(
        _load_or_capture(workspace_copy),
        ["pdu_engine_status_tx", "no pdu_sender deployment"],
    )


# Workspace-level: reference resolution.


def test_negative_unknown_pdu_ref(workspace_copy):
    """A CANFrameForwarder targeting an unknown frame triggers err_major."""

    _mutate_file(
        _pwrtr_ifc(workspace_copy),
        {"frame_ref: Frame_EngineDiagResponse": "frame_ref: Frame_DoesNotExist"},
    )
    _assert_message_contains(
        _load_or_capture(workspace_copy),
        ["Frame_DoesNotExist"],
    )


# Workspace-level: payload-fit between forwarded PDU and egress CAN frame.


def test_negative_payload_does_not_fit_can_frame(workspace_copy):
    """Forward an 8-byte PDU to a 4-byte frame: workspace-level payload-fit check fires.

    The frame is also cleared of its statically packed PDU so the new bus-level
    'packed PDU fits frame length' check stays silent — the test isolates the
    workspace-level forwarder payload-fit path.
    """

    can_path = workspace_copy / "communication" / "channels" / "can" / "diag_can.flync.yaml"
    _mutate_file(
        can_path,
        {
            (
                "  - name: Frame_EngineDiagResponse\n"
                "    type: can_fd\n"
                "    description: Diagnostic response from HPC, CAN FD 64-byte payload.\n"
                "    length: 64\n"
                "    can_id: 2024         # 0x7E8\n"
                "    id_format: standard_11bit\n"
                "    bit_rate_switch: true\n"
                "    error_state_indicator: false\n"
                "    packed_pdus:\n"
                "      - pdu_ref: PDU_EngineStatus\n"
                "        bit_position: 0"
            ): (
                "  - name: Frame_EngineDiagResponse\n"
                "    type: can_fd\n"
                "    description: Diagnostic response from HPC, CAN FD 64-byte payload.\n"
                "    length: 4\n"
                "    can_id: 2024         # 0x7E8\n"
                "    id_format: standard_11bit\n"
                "    bit_rate_switch: true\n"
                "    error_state_indicator: false\n"
                "    packed_pdus: []"
            ),
        },
    )
    _assert_message_contains(
        _load_or_capture(workspace_copy),
        ["does not fit"],
    )


# Workspace-level: cycle detection.


def test_negative_two_bus_cycle(workspace_copy):
    """Add a return-leg forwarder DiagCAN -> PowertrainCAN so the gateway loops back."""

    _mutate_file(
        _pwrtr_ifc(workspace_copy),
        {"sender_frames: []": "sender_frames:\n  - frame_ref: Frame_EngineStatus"},
    )
    _mutate_file(
        _diag_ifc(workspace_copy),
        {
            "receiver_frames:\n  - frame_ref: Frame_LightDiagRequest": "receiver_frames:\n  - frame_ref: Frame_LightDiagRequest\nforwarder_frames:\n  - frame_ref: Frame_EngineDiagResponse\n    egresses:\n      - egress_type: can_frame\n        bus_ref: PowertrainCAN\n        frame_ref: Frame_EngineStatus",
        },
    )
    _assert_message_contains(
        _load_or_capture(workspace_copy),
        ["cycle"],
    )


# Alternate gateway topologies exercised through tmpdir mutation (independent of the canonical-example coverage above).


def test_positive_scenario_4_eth_to_eth_rebridge(workspace_copy):
    """Inject a second TX socket and convert pdu_engine_status_tx into a forwarder."""

    _mutate_file(
        _hpc_eth_socket_pdu(workspace_copy),
        {
            "  - name: pdu_engine_status_tx\n    endpoint_address: 10.0.20.5\n    endpoint_type: unicast\n    port_no: 30802\n    protocol: udp\n    deployments:\n      - deployment_type: pdu_sender\n        pdu_ref: PDU_EngineStatus": "  - name: pdu_engine_status_tx\n    endpoint_address: 10.0.20.5\n    endpoint_type: unicast\n    port_no: 30802\n    protocol: udp\n    deployments:\n      - deployment_type: pdu_sender\n        pdu_ref: PDU_EngineStatus\n      - deployment_type: pdu_forwarder\n        pdu_ref: PDU_EngineStatus\n        egresses:\n          - egress_type: eth_socket\n            socket_ref: pdu_engine_rebridge_tx\n\n  - name: pdu_engine_rebridge_tx\n    endpoint_address: 10.0.20.5\n    endpoint_type: unicast\n    port_no: 30803\n    protocol: udp\n    deployments:\n      - deployment_type: pdu_sender\n        pdu_ref: PDU_EngineStatus",
        },
    )
    ws = FLYNCWorkspace.load_workspace("flync_example", workspace_copy)
    assert ws.flync_model is not None
    pdu_fwds = ws.flync_model.get_all_pdu_forwarders()

    def _targets_rebridge(f) -> bool:
        if f.pdu_ref != "PDU_EngineStatus":
            return False
        egress = f.egresses[0].root
        return isinstance(egress, EthSocketEgress) and egress.socket_ref == "pdu_engine_rebridge_tx"

    assert any(_targets_rebridge(f) for f in pdu_fwds)


def test_positive_scenario_3_eth_container_extracted_to_can(workspace_copy):
    """Convert pdu_powertrain_tx into a pdu_forwarder + add a peer pdu_sender to keep direction safety."""

    _mutate_file(
        _hpc_eth_socket_pdu(workspace_copy),
        {
            "  - name: pdu_powertrain_tx\n    endpoint_address: 10.0.20.5\n    endpoint_type: unicast\n    port_no: 30800\n    protocol: udp\n    deployments:\n      - deployment_type: pdu_sender\n        pdu_ref: EthPowertrainContainer": "  - name: pdu_powertrain_tx\n    endpoint_address: 10.0.20.5\n    endpoint_type: unicast\n    port_no: 30800\n    protocol: udp\n    deployments:\n      - deployment_type: pdu_sender\n        pdu_ref: EthPowertrainContainer\n      - deployment_type: pdu_forwarder\n        pdu_ref: EthPowertrainContainer\n        egresses:\n          - egress_type: can_frame\n            bus_ref: DiagCAN\n            frame_ref: Frame_EngineDiagResponse\n            extract_pdu_ref: PDU_EngineStatus",
        },
    )
    ws = FLYNCWorkspace.load_workspace("flync_example", workspace_copy)
    assert ws.flync_model is not None
    pdu_fwds = ws.flync_model.get_all_pdu_forwarders()
    fwd = next((f for f in pdu_fwds if f.pdu_ref == "EthPowertrainContainer"), None)
    assert fwd is not None
    egress = fwd.egresses[0].root
    assert isinstance(egress, CANFrameEgress)
    assert egress.extract_pdu_ref == "PDU_EngineStatus"


def test_negative_extract_pdu_ref_not_in_container(workspace_copy):
    """Same scenario but extract a name that's not in EthPowertrainContainer.contained_pdus."""

    _mutate_file(
        _hpc_eth_socket_pdu(workspace_copy),
        {
            "  - name: pdu_powertrain_tx\n    endpoint_address: 10.0.20.5\n    endpoint_type: unicast\n    port_no: 30800\n    protocol: udp\n    deployments:\n      - deployment_type: pdu_sender\n        pdu_ref: EthPowertrainContainer": "  - name: pdu_powertrain_tx\n    endpoint_address: 10.0.20.5\n    endpoint_type: unicast\n    port_no: 30800\n    protocol: udp\n    deployments:\n      - deployment_type: pdu_sender\n        pdu_ref: EthPowertrainContainer\n      - deployment_type: pdu_forwarder\n        pdu_ref: EthPowertrainContainer\n        egresses:\n          - egress_type: can_frame\n            bus_ref: DiagCAN\n            frame_ref: Frame_EngineDiagResponse\n            extract_pdu_ref: PDU_DoesNotExist",
        },
    )
    _assert_message_contains(
        _load_or_capture(workspace_copy),
        ["PDU_DoesNotExist", "not contained in ContainerPDU"],
    )
