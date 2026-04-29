import pytest
from pydantic import ValidationError

from flync.model.flync_4_ecu import ControllerInterface, Switch, SwitchPort


def test_unique_silicon_port_number(
    embedded_metadata_entry, vlan_entry, switch_host_controller_example
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
                "meta": embedded_metadata_entry,
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
    switch_host_controller_example,
):
    switch_example = Switch.model_validate(
        {
            "meta": embedded_metadata_entry,
            "name": "switch_example",
            "vlans": [vlan_entry],
            "ports": [switch_port],
            "host_controller": switch_host_controller_example,
        }
    )

    assert isinstance(switch_example.host_controller, ControllerInterface)


def test_get_mac_returns_host_controller_mac(
    embedded_metadata_entry,
    vlan_entry,
    switch_port,
    switch_host_controller_example,
):
    """Switch.get_mac proxies to host_controller.mac_address."""
    switch = Switch.model_validate(
        {
            "meta": embedded_metadata_entry,
            "name": "switch_example",
            "vlans": [vlan_entry],
            "ports": [switch_port],
            "host_controller": switch_host_controller_example,
        }
    )

    assert switch.get_mac() == "10:10:10:22:22:22"


@pytest.mark.parametrize("invalid_vlan_id", [-1, 4096])
def test_switch_port_default_vlan_id_out_of_range_rejected(invalid_vlan_id):
    with pytest.raises(ValidationError):
        SwitchPort(
            name="port_x",
            default_vlan_id=invalid_vlan_id,
            silicon_port_no=1,
        )


def test_switch_port_silicon_port_no_negative_rejected():
    with pytest.raises(ValidationError):
        SwitchPort(
            name="port_x",
            default_vlan_id=1,
            silicon_port_no=-1,
        )


def test_validate_ipv_mapping_positive(
    embedded_metadata_entry, vlan_entry
):
    """A traffic class with internal_priority_values must find a matching
    stream ipv on some port of the same switch."""
    port = SwitchPort.model_validate(
        {
            "name": "port1",
            "default_vlan_id": 1,
            "silicon_port_no": 1,
            "ingress_streams": [
                {
                    "name": "stream1",
                    "ipv": 3,
                }
            ],
            "traffic_classes": [
                {
                    "name": "tc1",
                    "priority": 0,
                    "internal_priority_values": [3],
                }
            ],
        }
    )

    switch = Switch.model_validate(
        {
            "meta": embedded_metadata_entry,
            "name": "switch_example",
            "vlans": [vlan_entry],
            "ports": [port],
        }
    )

    assert switch.ports[0].traffic_classes[0].internal_priority_values == [3]


def test_validate_ipv_mapping_negative(
    embedded_metadata_entry, vlan_entry
):
    """A traffic class internal_priority_value with no matching stream ipv
    must raise."""
    port = SwitchPort.model_validate(
        {
            "name": "port1",
            "default_vlan_id": 1,
            "silicon_port_no": 1,
            "traffic_classes": [
                {
                    "name": "tc1",
                    "priority": 0,
                    "internal_priority_values": [5],
                }
            ],
        }
    )

    with pytest.raises(ValidationError) as e:
        Switch.model_validate(
            {
                "meta": embedded_metadata_entry,
                "name": "switch_example",
                "vlans": [vlan_entry],
                "ports": [port],
            }
        )

    assert "internal priority values 5" in str(e.value)


def test_validate_ats_instances_positive(
    embedded_metadata_entry, vlan_entry
):
    """An ATS shaper traffic class is valid when at least one ingress stream
    on the switch has an ATS instance configured."""
    ats_instance = {
        "committed_information_rate": 100,
        "committed_burst_size": 100,
        "max_residence_time": 1,
    }
    port = SwitchPort.model_validate(
        {
            "name": "port1",
            "default_vlan_id": 1,
            "silicon_port_no": 1,
            "ingress_streams": [
                {
                    "name": "stream1",
                    "ipv": 3,
                    "ats": ats_instance,
                }
            ],
            "traffic_classes": [
                {
                    "name": "tc_ats",
                    "priority": 0,
                    "internal_priority_values": [3],
                    "selection_mechanisms": {"type": "ats"},
                }
            ],
        }
    )

    switch = Switch.model_validate(
        {
            "meta": embedded_metadata_entry,
            "name": "switch_example",
            "vlans": [vlan_entry],
            "ports": [port],
        }
    )

    shaper = switch.ports[0].traffic_classes[0].selection_mechanisms
    assert shaper.type == "ats"


def test_validate_ats_instances_negative(
    embedded_metadata_entry, vlan_entry
):
    """An ATS shaper traffic class without any ingress stream ATS instance
    must raise even though the ipv mapping is satisfied."""
    port = SwitchPort.model_validate(
        {
            "name": "port1",
            "default_vlan_id": 1,
            "silicon_port_no": 1,
            "ingress_streams": [
                {
                    "name": "stream1",
                    "ipv": 3,
                }
            ],
            "traffic_classes": [
                {
                    "name": "tc_ats",
                    "priority": 0,
                    "internal_priority_values": [3],
                    "selection_mechanisms": {"type": "ats"},
                }
            ],
        }
    )

    with pytest.raises(ValidationError) as e:
        Switch.model_validate(
            {
                "meta": embedded_metadata_entry,
                "name": "switch_example",
                "vlans": [vlan_entry],
                "ports": [port],
            }
        )

    assert "No ATS Instance found for traffic class tc_ats" in str(e.value)
