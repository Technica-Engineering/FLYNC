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
        "name": "interface_test",
        "mac_address": "aa:bb:cc:dd:ee:ff",
        "virtual_interfaces": [virtual_controller_interface],
        "ptp_config": None,
    }
    ctrl = Controller.model_validate(
        {
            "meta": embedded_metadata_entry,
            "name": "controller_test",
            "interfaces": [ctrl_interface],
        }
    )
    assert isinstance(ctrl.interfaces[0], ControllerInterface)


def test_negative_controller_interface_wrong_mac(
    virtual_controller_interface: VirtualControllerInterface,
):
    ctrl_interface = {
        "name": "interface_test",
        "mac_address": "aaa-bb-cc-dd-ee-ff",
        "virtual_interfaces": [virtual_controller_interface],
    }

    with pytest.raises(ValidationError) as e:
        ctrl = Controller.model_validate(
            {
                "name": "controller_test",
                "interfaces": [ctrl_interface],
            }
        )


def test_negative_controller_interface_missing_vifaces():
    ctrl_interface = {
        "name": "interface_test",
        "mac_address": "aa:bb:cc:dd:ee:ff",
    }

    with pytest.raises(ValidationError) as e:
        ctrl = Controller.model_validate(
            {
                "name": "controller_test",
                "interfaces": [ctrl_interface],
            }
        )


def test_negative_controller_interface_empty_vifaces():
    ctrl_interface = {
        "name": "interface_test",
        "mac_address": "aa:bb:cc:dd:ee:ff",
        "virtual_interfaces": [],
    }

    with pytest.raises(ValidationError) as e:
        ctrl = Controller.model_validate(
            {
                "name": "controller_test",
                "interfaces": [ctrl_interface],
            }
        )
