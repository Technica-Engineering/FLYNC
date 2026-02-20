import pytest
from pydantic import ValidationError

from flync.model.flync_4_ecu.switch import MulticastGroup, VLANEntry


def test_positive_multicast_ipv4_group():
    mcast_group = {"address": "224.0.0.1", "ports": ["port1", "port2"]}
    vlan_entry = VLANEntry.model_validate(
        {
            "name": "vlan_entry1",
            "id": 10,
            "default_priority": 1,
            "ports": ["port1", "port2"],
            "multicast": [mcast_group],
        }
    )

    assert isinstance(vlan_entry.multicast[0], MulticastGroup)


def test_negative_multicast_ipv4_group():
    mcast_group = {"address": "10.0.0.1", "ports": ["port1", "port2"]}
    with pytest.raises(ValidationError) as err:
        vlan_entry = VLANEntry.model_validate(
            {
                "name": "vlan_entry1",
                "id": 10,
                "default_priority": 1,
                "ports": ["port1", "port2"],
                "multicast": [mcast_group],
            }
        )


def test_positive_multicast_ipv6_group():
    mcast_group = {"address": "FF02::1", "ports": ["port1", "port2"]}
    vlan_entry = VLANEntry.model_validate(
        {
            "name": "vlan_entry1",
            "id": 10,
            "default_priority": 1,
            "ports": ["port1", "port2"],
            "multicast": [mcast_group],
        }
    )

    assert isinstance(vlan_entry.multicast[0], MulticastGroup)


def test_negative_multicast_ipv6_group():
    mcast_group = {
        "address": '"2001:0db8:85a3:0000:0000:8a2e:0370:7334"',
        "ports": ["port1", "port2"],
    }
    with pytest.raises(ValidationError) as err:
        vlan_entry = VLANEntry.model_validate(
            {
                "name": "vlan_entry1",
                "id": 10,
                "default_priority": 1,
                "ports": ["port1", "port2"],
                "multicast": [mcast_group],
            }
        )
