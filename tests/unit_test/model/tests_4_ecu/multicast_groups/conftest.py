"""Fixtures for the MulticastGroupMembership tests.

``MulticastGroupMembership._interface`` is assigned by the loader rather than by a validator, so the
positive tests need a ready-made Ethernet interface to attach a membership to.
"""

from ipaddress import IPv4Address

import pytest
from pydantic_extra_types.mac_address import MacAddress

from flync.model.flync_4_ecu.controller import EthernetInterface, EthernetInterfaceConfig, VirtualControllerInterface
from flync.model.flync_4_ecu.sockets import IPv4AddressEndpoint


@pytest.fixture(scope="session")
def vci():
    vci = VirtualControllerInterface(
        name="vci",
        vlanid=10,
        addresses=[
            IPv4AddressEndpoint(
                address="192.168.1.10",
                ipv4netmask=IPv4Address("255.255.255.0"),
                sockets=[],
            )
        ],
        multicast=["239.1.1.1", "ff02::1"],
    )
    return vci


@pytest.fixture(scope="session")
def ci(vci):
    ei = EthernetInterfaceConfig(
        mac_address=MacAddress("3a:7f:1c:9b:4e:02"),
        virtual_interfaces=[vci],
    )
    ci = EthernetInterface(name="ei", interface_config=ei)
    return ci
