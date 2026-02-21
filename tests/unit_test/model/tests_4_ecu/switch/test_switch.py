import pytest
from pydantic import ValidationError

from flync.model.flync_4_ecu.controller import ControllerInterface
from flync.model.flync_4_ecu import Switch, SwitchPort


def test_unique_silicon_port_number(
    metadata_entry, vlan_entry, switch_host_controller_example
):
    switch_port1 = SwitchPort(
        name="port1", default_vlan_id=1, silicon_port_no=1
    )
    switch_port2 = SwitchPort(
        name="port2", default_vlan_id=2, silicon_port_no=1
    )

    with pytest.raises(ValidationError) as e:
        Switch.model_validate(
            {
                "meta": metadata_entry,
                "name": "switch_example",
                "vlans": [vlan_entry],
                "ports": [switch_port1, switch_port2],
                "host_controller": switch_host_controller_example,
            }
        )

        assert "Duplicates found in Switch Ports (silicon_port_number)" in str(
            e.value
        )


def test_switch_host(
    vlan_entry,
    embedded_metadata_entry,
    switch_port,
    ipv4_entry,
    virtual_controller_interface,
):

    host_controller_example = {
        "name": "iface1",
        "mac_address": "10:10:10:22:22:22",
        "virtual_interfaces": [virtual_controller_interface],
    }

    switch_example = Switch.model_validate(
        {
            "meta": embedded_metadata_entry,
            "name": "switch_example",
            "vlans": [vlan_entry],
            "ports": [switch_port],
            "host_controller": host_controller_example,
        }
    )

    assert isinstance(switch_example.host_controller, ControllerInterface)
