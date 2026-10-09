import pytest
from pydantic import ValidationError

from flync.model.flync_4_ecu.controller import Controller, EthernetInterface, EthernetInterfaceConfig
from flync.model.flync_4_security.firewall import Firewall
from tests.error_assertions import assert_single_error

_ACCEPT_SRC_IPV4 = {"name": "allow_someip_vlan_multicast", "action": "accept", "pattern": {"src_ipv4": "10.0.0.1"}}
_DROP_SRC_IPV4 = {"name": "allow_someip_vlan_multicast", "action": "drop", "pattern": {"src_ipv4": "10.0.0.2"}}
_ACCEPT_DST_IPV4 = {"name": "allow_someip_vlan_multicast", "action": "accept", "pattern": {"dst_ipv4": "10.0.0.1"}}
_ACCEPT_DST_IPV6 = {"name": "allow_someip_vlan_multicast", "action": "accept", "pattern": {"dst_ipv6": "2001:0db8:85a3:0000:0000:8a2e:0370:7334"}}


def _interface_config(virtual_controller_interface, firewall):
    """Build the interface_config payload that carries ``firewall``."""
    return {
        "mac_address": "00:11:22:33:44:55",
        "mii_config": None,
        "virtual_interfaces": [virtual_controller_interface],
        "firewall": {"default_action": "drop", **firewall},
    }


@pytest.mark.parametrize(
    "firewall",
    [
        pytest.param({"input_rules": [_ACCEPT_SRC_IPV4]}, id="single_input_rule"),
        pytest.param({"forward_rules": [_ACCEPT_SRC_IPV4, _DROP_SRC_IPV4]}, id="multiple_forward_rules"),
        pytest.param({"input_rules": [_ACCEPT_DST_IPV4, _DROP_SRC_IPV4]}, id="only_dst_ipv4_in_frame_filter"),
        pytest.param({"output_rules": [_ACCEPT_DST_IPV6, _DROP_SRC_IPV4]}, id="only_dst_ipv6_in_frame_filter"),
    ],
)
def test_positive_firewall_config(firewall, virtual_controller_interface):
    """A rule set naming a single address family per direction is accepted."""
    iface_config = EthernetInterfaceConfig.model_validate(_interface_config(virtual_controller_interface, firewall))

    assert isinstance(iface_config.firewall, Firewall)


@pytest.mark.parametrize(
    "firewall",
    [
        pytest.param({"output_rules": [_ACCEPT_SRC_IPV4, dict(_ACCEPT_SRC_IPV4, action="drop")]}, id="two_rules_same_filter"),
        pytest.param(
            {
                "input_rules": [
                    {"name": "allow_someip_vlan_multicast", "action": "accept", "pattern": {"dst_ipv6": "2001:db8::1", "dst_ipv4": "10.0.0.1"}}
                ]
            },
            id="both_dst_ipv4_and_dst_ipv6",
        ),
    ],
)
def test_negative_firewall_config(firewall, virtual_controller_interface):
    """The firewall is rejected while the interface config is built, so no Controller is ever assembled."""
    with pytest.raises(ValidationError) as exc_info:
        EthernetInterfaceConfig.model_validate(_interface_config(virtual_controller_interface, firewall))

    assert_single_error(exc_info, "FLYNC-CMN-MIN-UNC-000", "while validating firewall")


def test_positive_firewall_reachable_through_the_controller(virtual_controller_interface, embedded_metadata_entry):
    """A validated firewall is still reachable once the interface is nested in a Controller."""
    iface_config = EthernetInterfaceConfig.model_validate(
        _interface_config(virtual_controller_interface, {"forward_rules": [_ACCEPT_SRC_IPV4, _DROP_SRC_IPV4]})
    )
    controller = Controller.model_validate(
        {
            "controller_metadata": embedded_metadata_entry,
            "name": "controller_example",
            "ethernet_interfaces": [{"name": "eth0", "interface_config": iface_config}],
        }
    )

    assert isinstance(controller.ethernet_interfaces[0].interface_config.firewall, Firewall)


def test_positive_firewall_reachable_through_the_ethernet_interface(virtual_controller_interface):
    """The firewall validates when the interface config is built inline by EthernetInterface."""
    eth_iface = EthernetInterface.model_validate(
        {
            "name": "iface1",
            "interface_config": _interface_config(virtual_controller_interface, {"input_rules": [_ACCEPT_SRC_IPV4]}),
        }
    )

    assert isinstance(eth_iface.interface_config.firewall, Firewall)
