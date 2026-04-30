import pytest, yaml
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
    InternalTopology,
)
from flync.core.utils.base_utils import read_yaml, write_to_file
import shutil
from pydantic import ValidationError
from flync.model.flync_4_someip.service_interface import SOMEIPServiceInterface


def test_consumed_services():
    example_path = Path(__file__).parents[4] / "examples/flync_example"
    loaded_ws = FLYNCWorkspace.load_workspace(
        "flync_example", example_path
    )
    ecus = loaded_ws.flync_model.ecus
    consumed_services = None
    for ecu in ecus:
        if ecu.name == "high_performance_compute":
            consumed_services = ecu.get_consumed_services()
    assert consumed_services[0].service.name ==  "Enhanced Testability Services"
    assert consumed_services[0].instance_id == int("0xf4", 16)


def test_provided_services():
    example_path = Path(__file__).parents[4] / "examples/flync_example"
    loaded_ws = FLYNCWorkspace.load_workspace(
        "flync_example", example_path
    )
    ecus = loaded_ws.flync_model.ecus
    provided_services = None
    for ecu in ecus:
        if ecu.name == "high_performance_compute":
            provided_services = ecu.get_provided_services()

    assert provided_services[0].service.name ==  "Enhanced Testability Services"
    assert provided_services[0].instance_id == int("1", 16)
