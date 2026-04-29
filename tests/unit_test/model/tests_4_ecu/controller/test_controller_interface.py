import pytest
from pydantic import ValidationError

from flync.model.flync_4_ecu.controller import (
    Controller,
    ControllerInterface,
    VirtualControllerInterface,
)


def test_positive_controller_interface_config(
    virtual_controller_interface: VirtualControllerInterface,embedded_metadata_entry
):
    ctrl_interface = {
        "name": "interface_test",
        "mac_address": "aa:bb:cc:dd:ee:ff",
        "virtual_interfaces": [virtual_controller_interface],
        "ptp_config": None,
    }
    ctrl = Controller.model_validate(
        {   "controller_metadata": embedded_metadata_entry,
            "name": "controller_test",
            "ethernet_interfaces": [{"interface_config": ctrl_interface}],
        }
    )
    assert isinstance(ctrl.ethernet_interfaces[0].interface_config, ControllerInterface)


def test_negative_controller_interface_wrong_mac(
    virtual_controller_interface: VirtualControllerInterface,
    embedded_metadata_entry,
):
    ctrl_interface = {
        "name": "interface_test",
        "mac_address": "aaa-bb-cc-dd-ee-ff",
        "virtual_interfaces": [virtual_controller_interface],
    }

    with pytest.raises(ValidationError):
        Controller.model_validate(
            {
                "controller_metadata": embedded_metadata_entry,
                "name": "controller_test",
                "ethernet_interfaces": [{"interface_config": ctrl_interface}],
            }
        )


def test_negative_controller_interface_missing_vifaces(embedded_metadata_entry):
    ctrl_interface = {
        "name": "interface_test",
        "mac_address": "aa:bb:cc:dd:ee:ff",
    }

    with pytest.raises(ValidationError):
        Controller.model_validate(
            {
                "controller_metadata": embedded_metadata_entry,
                "name": "controller_test",
                "ethernet_interfaces": [{"interface_config": ctrl_interface}],
            }
        )


def test_negative_controller_interface_empty_vifaces(embedded_metadata_entry):
    ctrl_interface = {
        "name": "interface_test",
        "mac_address": "aa:bb:cc:dd:ee:ff",
        "virtual_interfaces": [],
    }

    with pytest.raises(ValidationError):
        Controller.model_validate(
            {
                "controller_metadata": embedded_metadata_entry,
                "name": "controller_test",
                "ethernet_interfaces": [{"interface_config": ctrl_interface}],
            }
        )
