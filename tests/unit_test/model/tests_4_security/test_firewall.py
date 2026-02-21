import pytest
from pydantic import ValidationError

from flync.model.flync_4_ecu.controller import Controller, ControllerInterface
from flync.model.flync_4_security.firewall import *


def test_firewall_config_positive_(virtual_controller_interface):

    firewall_example = {
        "default_action": "drop",
        "input_rules": [
            {
                "name": "allow_someip_vlan_multicast",
                "action": "accept",
                "pattern": {"src_ipv4": "10.0.0.1"},
            }
        ],
    }

    controller_iface = ControllerInterface.model_validate(
        {
            "name": "iface1",
            "mac_address": "00:11:22:33:44:55",
            "mii_config": None,
            "virtual_interfaces": [virtual_controller_interface],
            "firewall": firewall_example,
        }
    )

    assert isinstance(controller_iface.firewall, Firewall)


def test_firewall_config_positive_multiple_rules(
    embedded_metadata_entry, virtual_controller_interface
):

    firewall_example = {
        "default_action": "drop",
        "forward_rules": [
            {
                "name": "allow_someip_vlan_multicast",
                "action": "accept",
                "pattern": {"src_ipv4": "10.0.0.1"},
            },
            {
                "name": "allow_someip_vlan_multicast",
                "action": "drop",
                "pattern": {"src_ipv4": "10.0.0.2"},
            },
        ],
    }

    controller_iface = ControllerInterface.model_validate(
        {
            "name": "iface1",
            "mac_address": "00:11:22:33:44:55",
            "mii_config": None,
            "virtual_interfaces": [virtual_controller_interface],
            "firewall": firewall_example,
        }
    )

    controller = Controller.model_validate(
        {
            "meta": embedded_metadata_entry,
            "name": "controller_example",
            "interfaces": [controller_iface],
        }
    )
    assert isinstance(controller.interfaces[0].firewall, Firewall)


def test_negative_firewall_config_multiple_rules_same_filter(
    virtual_controller_interface,
):

    firewall_example = {
        "default_action": "drop",
        "output_rules": [
            {
                "name": "allow_someip_vlan_multicast",
                "action": "accept",
                "pattern": {"src_ipv4": "10.0.0.1"},
            },
            {
                "name": "allow_someip_vlan_multicast",
                "action": "drop",
                "pattern": {"src_ipv4": "10.0.0.1"},
            },
        ],
    }

    with pytest.raises(ValidationError):
        Controller.model_validate(
            {
                "name": "controller_example",
                "interfaces": [
                    ControllerInterface.model_validate(
                        {
                            "name": "iface1",
                            "mac_address": "00:11:22:33:44:55",
                            "mii_config": None,
                            "virtual_interfaces": [
                                virtual_controller_interface
                            ],
                            "firewall": firewall_example,
                        }
                    )
                ],
            }
        )


def test_positive_only_dst_ipv4_in_frame_filter(
    embedded_metadata_entry, virtual_controller_interface
):

    firewall_example = {
        "default_action": "drop",
        "input_rules": [
            {
                "name": "allow_someip_vlan_multicast",
                "action": "accept",
                "pattern": {"dst_ipv4": "10.0.0.1"},
            },
            {
                "name": "allow_someip_vlan_multicast",
                "action": "drop",
                "pattern": {"src_ipv4": "10.0.0.2"},
            },
        ],
    }

    controller_iface = ControllerInterface.model_validate(
        {
            "name": "iface1",
            "mac_address": "00:11:22:33:44:55",
            "mii_config": None,
            "virtual_interfaces": [virtual_controller_interface],
            "firewall": firewall_example,
        }
    )

    controller = Controller.model_validate(
        {
            "meta": embedded_metadata_entry,
            "name": "controller_example",
            "interfaces": [controller_iface],
        }
    )
    assert isinstance(controller.interfaces[0].firewall, Firewall)


def test_positive_only_dst_ipv6_in_frame_filter(
    embedded_metadata_entry, virtual_controller_interface
):

    firewall_example = {
        "default_action": "drop",
        "output_rules": [
            {
                "name": "allow_someip_vlan_multicast",
                "action": "accept",
                "pattern": {
                    "dst_ipv6": "2001:0db8:85a3:0000:0000:8a2e:0370:7334"
                },
            },
            {
                "name": "allow_someip_vlan_multicast",
                "action": "drop",
                "pattern": {"src_ipv4": "10.0.0.2"},
            },
        ],
    }

    controller_iface = ControllerInterface.model_validate(
        {
            "name": "iface1",
            "mac_address": "00:11:22:33:44:55",
            "mii_config": None,
            "virtual_interfaces": [virtual_controller_interface],
            "firewall": firewall_example,
        }
    )

    controller = Controller.model_validate(
        {
            "meta": embedded_metadata_entry,
            "name": "controller_example",
            "interfaces": [controller_iface],
        }
    )
    assert isinstance(controller.interfaces[0].firewall, Firewall)


def test_negative_both_dst_ipv4_and_dst_ipv6_in_frame_filter(
    virtual_controller_interface,
):

    firewall_example = {
        "default_action": "drop",
        "input_rules": [
            {
                "name": "allow_someip_vlan_multicast",
                "action": "accept",
                "pattern": {
                    "dst_ipv6": "2001:0db8:85a3:0000:0000:8a2e:0370:7334",
                    "dst_ipv4": "10.0.0.1",
                },
            }
        ],
    }

    with pytest.raises(ValidationError):
        Controller.model_validate(
            {
                "name": "controller_example",
                "interfaces": [
                    ControllerInterface.model_validate(
                        {
                            "name": "iface1",
                            "mac_address": "00:11:22:33:44:55",
                            "mii_config": None,
                            "virtual_interfaces": [
                                virtual_controller_interface
                            ],
                            "firewall": firewall_example,
                        }
                    )
                ],
            }
        )
