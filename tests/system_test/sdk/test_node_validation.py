"""
Test the validation API of an external node using its file
to ensure it reports node problems and states accurately.
"""

from pathlib import Path

import pytest
import yaml

from flync.model.flync_4_bus.can_bus import CANBus
from flync.model.flync_4_bus.lin_bus import LINBus
from flync.model.flync_4_communication.flync_communication import TCPOption
from flync.model.flync_4_ecu.controller import ControllerInterface, VirtualSwitch
from flync.model.flync_4_ecu.ecu import ECU, Socket, Switch
from flync.model.flync_4_ecu.socket_container import SocketContainer
from flync.model.flync_4_metadata.metadata import EmbeddedMetadata, SystemMetadata
from flync.model.flync_4_signal.pdu import PDU, ContainerPDU
from flync.model.flync_4_someip import SDConfig
from flync.model.flync_4_someip.service_interface import SDTimings, SOMEIPServiceInterface
from flync.model.flync_4_topology.system_topology import SystemTopology
from flync.sdk.context.diagnostics_result import WorkspaceState
from flync.sdk.helpers.validation_helpers import validate_external_node

from .helper import (
    absolute_path,
    assert_broken_result,
    assert_not_broken_result,
    assert_valid_or_warning_result,
    assert_valid_result,
)


def test_validate_valid_external_ecu_switch():
    """Validates each ECU's switch."""
    switch_paths = list(absolute_path.glob("ecus/*/switches/*.flync.yaml"))
    for switch_path in switch_paths:
        result = validate_external_node(Switch, switch_path)
        assert_valid_result(result)


def test_validate_valid_external_controller_metadata():
    """Validates each ECU's controller metadata."""
    controller_metadata_paths = list(absolute_path.glob("ecus/*/controllers/*/controller_metadata.flync.yaml"))
    for controller_metadata_path in controller_metadata_paths:
        result = validate_external_node(EmbeddedMetadata, controller_metadata_path)
        assert_not_broken_result(result)


def test_validate_valid_external_ecu_socket():
    """Validates the SOMEIP socket file that exists for the listed ECUs."""
    socket_paths = list(absolute_path.glob("ecus/*/controllers/*/ethernet_interfaces/*/sockets/socket_*.flync.yaml"))
    for socket_path in socket_paths:
        result = validate_external_node(SocketContainer, socket_path)
        assert_valid_or_warning_result(result)


def test_validate_valid_socket_entries_in_socket_container_files():
    """Validates each socket entry inside the example socket container files."""
    socket_container_paths = list(absolute_path.glob("ecus/*/controllers/*/ethernet_interfaces/*/sockets/socket_*.flync.yaml"))
    assert socket_container_paths, "Expected socket container files in the example workspace"
    for socket_container_path in socket_container_paths:
        result = validate_external_node(SocketContainer, socket_container_path)
        assert_valid_or_warning_result(result)
        assert result.model is not None, f"Expected a model for {socket_container_path}"
        for socket in result.model.sockets or []:
            assert isinstance(socket, Socket), f"Expected a FLYNC Socket instance for {socket_container_path}, got {type(socket).__name__}"


def test_validate_valid_external_someip_service():
    """Validates the example SOMEIP service interface file."""
    services_path = absolute_path / "communication" / "someip" / "services" / "ets.flync.yaml"
    result = validate_external_node(SOMEIPServiceInterface, services_path)
    assert_valid_result(result)


def test_validate_valid_external_sd_config():
    """Validates the SOMEIP Service Discovery configuration file."""
    sd_config_path = absolute_path / "communication" / "someip" / "sd_config.flync.yaml"
    result = validate_external_node(SDConfig, sd_config_path)
    assert_valid_result(result)


def test_validate_valid_external_tcp_profiles():
    """Validates the TCP profile definitions file."""
    tcp_profiles_path = absolute_path / "communication" / "tcp_profiles.flync.yaml"
    result = validate_external_node(TCPOption, tcp_profiles_path)
    assert_not_broken_result(result)


@pytest.mark.parametrize(
    "node_type,path_glob",
    [
        (SystemMetadata, "system_metadata.flync.yaml"),
        (SystemTopology, "topology/system_topology.flync.yaml"),
        (ControllerInterface, "ecus/*/controllers/*/ethernet_interfaces/*/interface_config.flync.yaml"),
        (VirtualSwitch, "ecus/*/controllers/*/virtual_switch.flync.yaml"),
        (CANBus, "communication/channels/can/*.flync.yaml"),
        (LINBus, "communication/channels/lin/*.flync.yaml"),
        (PDU, "communication/channels/pdus/*.flync.yaml"),
        (ContainerPDU, "communication/channels/ethernet_pdu_containers/*.flync.yaml"),
        (SDTimings, "communication/someip/someip_timings.flync.yaml"),
    ],
    ids=[
        "system_metadata",
        "system_topology",
        "controller_interface",
        "virtual_switch",
        "can_bus",
        "lin_bus",
        "pdu",
        "container_pdu",
        "someip_timings",
    ],
)
def test_validate_valid_external_example_node_files(node_type, path_glob):
    """Validates all supported external example files for the given FLYNC node type."""

    node_paths = list(absolute_path.glob(path_glob))
    assert node_paths, f"Expected files for path pattern '{path_glob}'"
    for node_path in node_paths:
        result = validate_external_node(node_type, node_path)
        assert_not_broken_result(result)


@pytest.mark.parametrize(
    "rel_path",
    [
        Path("ecus") / "nonexistent_ecu",
        Path("ecus") / "zonal_platform1" / "missing_file.flync.yaml",
    ],
    ids=["missing_folder", "missing_file"],
)
def test_validate_external_node_missing_path(rel_path: Path):
    """
    A non-existent path must produce an 'BROKEN' workspace result.

    Args:
        rel_path: A relative path that does not exist."""
    full_path = absolute_path / rel_path
    result = validate_external_node(ECU, full_path)
    assert_broken_result(result)


@pytest.mark.parametrize(
    "wrong_type",
    [dict],
)
def test_validate_external_node_unsupported_type(wrong_type):
    """
    Using a completely unsupported Python type should produce a BROKEN result.
    """
    ecu_path = absolute_path / "ecus" / "eth_ecu"
    result = validate_external_node(wrong_type, ecu_path)
    assert_broken_result(result)


@pytest.mark.parametrize(
    "node_type",
    [SDConfig, Switch, TCPOption],
)
def test_validate_external_node_supported_but_invalid_type(node_type):
    """
    Using a valid FLYNC model type with an incompatible node should produce INVALID.
    """
    ecu_path = absolute_path / "ecus" / "eth_ecu"

    result = validate_external_node(node_type, ecu_path)

    assert result.workspace is not None
    assert result.state == WorkspaceState.INVALID
    assert result.model is None


@pytest.mark.parametrize(
    "node_type_str, rel_path",
    [
        pytest.param(
            "SystemTopology",
            Path("topology") / "system_topology.flync.yaml",
            id="system_topology_by_string",
        ),
        pytest.param(
            "SystemMetadata",
            Path("system_metadata.flync.yaml"),
            id="system_metadata_by_string",
        ),
    ],
)
def test_validate_external_node_by_string(node_type_str, rel_path):
    """Validates external nodes using their string name.

    Args:
        node_type_str: A string identifier of the model.
        rel_path: The relative path to the node file or folder."""
    full_path = absolute_path / rel_path
    result = validate_external_node(node_type_str, full_path)
    assert_valid_result(result)
