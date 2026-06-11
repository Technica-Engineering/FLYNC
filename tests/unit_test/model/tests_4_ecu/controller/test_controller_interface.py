import pytest
from pydantic import ValidationError

from flync.model.flync_4_ecu.controller import (
    Controller,
    ControllerInterface,
    VirtualControllerInterface,
)


def test_positive_controller_interface_config(
    virtual_controller_interface: VirtualControllerInterface,
    embedded_metadata_entry,
):
    ctrl_interface = {
        "mac_address": "aa:bb:cc:dd:ee:ff",
        "virtual_interfaces": [virtual_controller_interface],
        "ptp_config": None,
    }
    ctrl = Controller.model_validate(
        {
            "controller_metadata": embedded_metadata_entry,
            "name": "controller_test",
            "ethernet_interfaces": [{"name": "interface_test", "interface_config": ctrl_interface}],
        }
    )
    assert isinstance(ctrl.ethernet_interfaces[0].interface_config, ControllerInterface)


def test_interface_name_propagated_from_ethernet_interface(
    virtual_controller_interface: VirtualControllerInterface,
    embedded_metadata_entry,
):
    """The interface name is no longer stored on ControllerInterface; it must be propagated
    from the parent EthernetInterface (implied from the folder name) onto interface_config.name."""
    ctrl_interface = {
        "mac_address": "aa:bb:cc:dd:ee:ff",
        "virtual_interfaces": [virtual_controller_interface],
    }
    ctrl = Controller.model_validate(
        {
            "controller_metadata": embedded_metadata_entry,
            "name": "controller_test",
            "ethernet_interfaces": [{"name": "interface_test", "interface_config": ctrl_interface}],
        }
    )

    eth = ctrl.ethernet_interfaces[0]
    assert eth.name == "interface_test"
    assert eth.interface_config.name == "interface_test"


def test_negative_controller_interface_wrong_mac(
    virtual_controller_interface: VirtualControllerInterface,
    embedded_metadata_entry,
):
    ctrl_interface = {
        "mac_address": "aaa-bb-cc-dd-ee-ff",
        "virtual_interfaces": [virtual_controller_interface],
    }

    with pytest.raises(ValidationError):
        Controller.model_validate(
            {
                "controller_metadata": embedded_metadata_entry,
                "name": "controller_test",
                "ethernet_interfaces": [{"name": "interface_test", "interface_config": ctrl_interface}],
            }
        )


def test_negative_controller_interface_missing_vifaces(
    embedded_metadata_entry,
):
    ctrl_interface = {
        "mac_address": "aa:bb:cc:dd:ee:ff",
    }

    with pytest.raises(ValidationError):
        Controller.model_validate(
            {
                "controller_metadata": embedded_metadata_entry,
                "name": "controller_test",
                "ethernet_interfaces": [{"name": "interface_test", "interface_config": ctrl_interface}],
            }
        )


def test_negative_controller_interface_empty_vifaces(embedded_metadata_entry):
    ctrl_interface = {
        "mac_address": "aa:bb:cc:dd:ee:ff",
        "virtual_interfaces": [],
    }

    with pytest.raises(ValidationError):
        Controller.model_validate(
            {
                "controller_metadata": embedded_metadata_entry,
                "name": "controller_test",
                "ethernet_interfaces": [{"name": "interface_test", "interface_config": ctrl_interface}],
            }
        )
