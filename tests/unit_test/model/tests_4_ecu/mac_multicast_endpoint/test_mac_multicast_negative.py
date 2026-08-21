import pytest
from pydantic import ValidationError

from flync.core.datatypes.macaddress import MacAddress
from flync.model.flync_4_ecu.mac_multicast_endpoint import (
    AVTPMulticastEndpoint,
    MACEndpointUnion,
    MACMulticastEndpoints,
)
from tests.error_assertions import assert_single_error


def test_mmes_rejects_invalid_meu_object():
    """
    Ensure MACMulticastEndpoints does not accept objects that are not MACEndpointUnion instances.
    """
    with pytest.raises(ValidationError) as exc_info:
        MACMulticastEndpoints(endpoints=["invalid"])

    assert_single_error(exc_info, None, "dictionary or object")


def test_meu_rejects_non_ame_root():
    """
    Ensure MACEndpointUnion only accepts AVTPMulticastEndpoint as root.
    """
    with pytest.raises(ValidationError) as exc_info:
        MACEndpointUnion(root="invalid")

    assert_single_error(exc_info, None, "dictionary or object")


def test_mmes_rejects_mixed_valid_and_invalid_meu():
    """
    Ensure system fails when at least one MACEndpointUnion in the list is invalid.
    """
    # MACEndpointUnion only accepts an AVTPMulticastEndpoint as root, so that is what the valid half must be.
    valid_ame = AVTPMulticastEndpoint(
        name="mme",
        mac_address=MacAddress("91:E0:F0:00:00:01"),
        protocol="avtp",
        ethertype=0x22F0,
        vlan_id=1,
        multicast_tx=[],
    )
    valid_meu = MACEndpointUnion(root=valid_ame)

    # The invalid entry is passed as raw data: building a MACEndpointUnion from it would already fail here,
    # before MACMulticastEndpoints - the collection - ever got a chance to reject it.
    with pytest.raises(ValidationError) as exc_info:
        MACMulticastEndpoints(endpoints=[valid_meu, "invalid"])

    assert_single_error(exc_info, None, "dictionary or object")


# Each case pins the expected FLYNC error id (None for plain Pydantic errors raised without an id) and a
# message fragment so the parametrized test asserts the precise failure it is named for.
invalid_cases = [
    # name
    pytest.param(None, "91:E0:F0:00:00:01", "avtp", 0x22F0, 10, [], None, "Input should be a valid string"),  # name is None
    # mac
    pytest.param("A1", 12345, "avtp", 0x22F0, 10, [], None, "MAC address must be a string"),  # mac is not a string
    pytest.param("A1", None, "avtp", 0x22F0, 10, [], None, "MAC address must be a string"),  # mac is None
    pytest.param("A1", "INVALID", "avtp", 0x22F0, 10, [], None, "Length for a INVALID MAC address"),  # malformed mac format
    pytest.param("A1", "91:E0:F0:00:00", "avtp", 0x22F0, 10, [], None, "must be (6, 8, 20)"),  # mac too short
    pytest.param("A1", "ZZ:ZZ:ZZ:ZZ:ZZ:ZZ", "avtp", 0x22F0, 10, [], None, "Unrecognized format"),  # non-hex mac
    pytest.param("A1", "", "avtp", 0x22F0, 10, [], None, "Length for a  MAC address must be 14"),  # empty mac
    # protocol
    pytest.param("A1", "91:E0:F0:00:00:01", 123, 0x22F0, 10, [], None, "does not match any of the expected tags"),  # protocol not string
    pytest.param("A1", "91:E0:F0:00:00:01", None, 0x22F0, 10, [], None, "does not match any of the expected tags"),  # protocol is None
    pytest.param("A1", "91:E0:F0:00:00:01", "udp", 0x22F0, 10, [], None, "does not match any of the expected tags"),  # wrong protocol
    pytest.param("A1", "91:E0:F0:00:00:01", "", 0x22F0, 10, [], None, "does not match any of the expected tags"),  # empty protocol
    pytest.param("A1", "91:E0:F0:00:00:01", "aVtP", 0x22F0, 10, [], None, "does not match any of the expected tags"),  # case-insensitive protocol
    # ethertype
    pytest.param("A1", "91:E0:F0:00:00:01", "avtp", "0x22F0", 10, [], None, "Input should be 8944"),  # ethertype is not int
    pytest.param("A1", "91:E0:F0:00:00:01", "avtp", [0x22F0], 10, [], None, "Input should be 8944"),  # ethertype is list
    pytest.param("A1", "91:E0:F0:00:00:01", "avtp", -1, 10, [], None, "Input should be 8944"),  # ethertype negative
    pytest.param("A1", "91:E0:F0:00:00:01", "avtp", 0x10000, 10, [], None, "Input should be 8944"),  # ethertype out of range
    pytest.param("A1", "91:E0:F0:00:00:01", "avtp", "INVALID", 10, [], None, "Input should be 8944"),  # ethertype not int
    # vlan
    pytest.param(
        "A1",
        "91:E0:F0:00:00:01",
        "avtp",
        0x22F0,
        "10.f",
        [],
        None,
        "unable to parse string as an integer",
    ),  # vlan not int
    pytest.param("A1", "91:E0:F0:00:00:01", "avtp", 0x22F0, [10], [], None, "Input should be a valid integer"),  # vlan is list
    pytest.param("A1", "91:E0:F0:00:00:01", "avtp", 0x22F0, -1, [], "FLYNC-CMN-MIN-VAL-002", "VLAN ID must be in the range 0-4094"),  # vlan negative
    pytest.param(
        "A1", "91:E0:F0:00:00:01", "avtp", 0x22F0, 5000, [], "FLYNC-CMN-MIN-VAL-002", "VLAN ID must be in the range 0-4094"
    ),  # vlan out of range
    # multicast_tx
    pytest.param("A1", "91:E0:F0:00:00:01", "avtp", 0x22F0, 10, "INVALID", None, "Input should be a valid list"),  # not a list
    pytest.param("A1", "91:E0:F0:00:00:01", "avtp", 0x22F0, 10, [123], None, "MAC address must be a string"),  # non-mac inside list
    pytest.param(
        "A1", "91:E0:F0:00:00:01", "avtp", 0x22F0, 10, ["02:00:00:00:00:01"], "FLYNC-CMN-MIN-FMT-005", "not a MAC Multicast"
    ),  # not multicast MAC
    pytest.param("A1", "91:E0:F0:00:00:01", "avtp", 0x22F0, 10, [""], None, "Length for a  MAC address must be 14"),  # empty MAC string
]


@pytest.mark.parametrize("name,mac,protocol,type,vlan,tx,error_id,message_fragment", invalid_cases)
def test_meu_wraps_ame_inside_mmes_invalid_values(name, mac, protocol, type, vlan, tx, error_id, message_fragment):
    """
    Ensure endpoint creation fails for invalid values, types, or inconsistent configurations.
    """
    # Validated from raw data so every invalid value is rejected by the union itself; building the
    # AVTPMulticastEndpoint (or its MacAddress) up front would raise before the call under test.
    endpoint_payload = {
        "name": name,
        "mac_address": mac,
        "protocol": protocol,
        "ethertype": type,
        "vlan_id": vlan,
        "multicast_tx": tx,
    }

    with pytest.raises(ValidationError) as exc_info:
        MACEndpointUnion.model_validate(endpoint_payload)

    assert_single_error(exc_info, error_id, message_fragment)
