"""
Test the validation API of an external node using its folder
to ensure it reports the errors and states accurately.
"""

import pytest

from flync.model.flync_4_ecu.controller import Controller, EthernetInterface
from flync.model.flync_4_ecu.ecu import ECU
from flync.sdk.helpers.validation_helpers import validate_external_node

from .helper import absolute_path, assert_not_broken_result, assert_valid_or_warning_result, assert_valid_result

ECU_LIST = ["high_performance_compute", "zonal_platform1", "zonal_platform2"]


@pytest.mark.parametrize("ecu", ECU_LIST)
def test_validate_valid_external_ecu(ecu):
    """Validates an ECU by its folder."""
    ecu_path = absolute_path / "ecus" / ecu
    result = validate_external_node(ECU, ecu_path)
    assert_valid_result(result)


def test_validate_valid_external_controller():
    """Validates an Controller by its folder."""
    controller_paths = list(absolute_path.glob("ecus/*/controllers/*"))
    for controller_path in controller_paths:
        result = validate_external_node(Controller, controller_path)
        assert_valid_or_warning_result(result)


def test_validate_valid_external_ethernet_interface():
    """Validates each ethernet interface by its folder."""
    ethernet_interface_paths = [path for path in absolute_path.glob("ecus/*/controllers/*/ethernet_interfaces/*") if path.is_dir()]
    assert ethernet_interface_paths, "Expected ethernet interface folders in the example workspace"
    for ethernet_interface_path in ethernet_interface_paths:
        result = validate_external_node(EthernetInterface, ethernet_interface_path)
        assert_not_broken_result(result)
