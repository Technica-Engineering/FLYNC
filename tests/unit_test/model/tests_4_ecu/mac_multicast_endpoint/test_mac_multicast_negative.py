import pytest
from flync.model.flync_4_ecu.mac_multicast_endpoint import *
from flync.core.datatypes.macaddress import MacAddress

def test_mmes_rejects_invalid_meu_object():
    """
    Ensure MACMulticastEndpoints does not accept objects that are not MACEndpointUnion instances.
    """
    with pytest.raises(Exception):
        MACMulticastEndpoints(endpoints=["invalid"])
    
def test_meu_rejects_non_ame_root():
    """
    Ensure MACEndpointUnion only accepts AVTPMulticastEndpoint as root.
    """
    with pytest.raises(Exception):
        MACEndpointUnion(root="invalid")

def test_mmes_rejects_mixed_valid_and_invalid_meu():
    """
    Ensure system fails when at least one MACEndpointUnion in the list is invalid.
    """
    valid_mme = MACMulticastEndpoint(name="mme",mac_address=MacAddress("00:00:5e:00:53:01"),protocol="avtp",ethertype=0x22F0,vlan_id=1)

    with pytest.raises(Exception):
        invalid_meu = MACEndpointUnion(root="invalid")
        MACMulticastEndpoints(endpoints=[MACEndpointUnion(root=valid_mme), invalid_meu])

invalid_cases = [
    # name
    pytest.param(None, "91:E0:F0:00:00:01", "avtp", 0x22F0, 10, []),   # name is None
    pytest.param("", "91:E0:F0:00:00:01", "avtp", 0x22F0, 10, [], marks=pytest.mark.xfail),     # empty name

    # mac
    pytest.param("A1", 12345, "avtp", 0x22F0, 10, []),                 # mac is not a string
    pytest.param("A1", None, "avtp", 0x22F0, 10, []),                  # mac is None
    pytest.param("A1", "INVALID", "avtp", 0x22F0, 10, []),             # malformed mac format
    pytest.param("A1", "91:E0:F0:00:00", "avtp", 0x22F0, 10, []),      # mac too short
    pytest.param("A1", "ZZ:ZZ:ZZ:ZZ:ZZ:ZZ", "avtp", 0x22F0, 10, []),   # non-hex mac
    pytest.param("A1", "", "avtp", 0x22F0, 10, []),                    # empty mac

    # protocol
    pytest.param("A1", "91:E0:F0:00:00:01", 123, 0x22F0, 10, []),      # protocol not string
    pytest.param("A1", "91:E0:F0:00:00:01", None, 0x22F0, 10, []),     # protocol is None
    pytest.param("A1", "91:E0:F0:00:00:01", "udp", 0x22F0, 10, []),    # wrong protocol
    pytest.param("A1", "91:E0:F0:00:00:01", "", 0x22F0, 10, []),       # empty protocol
    pytest.param("A1", "91:E0:F0:00:00:01", "aVtP", 0x22F0, 10, []),   # case-insensitive protocol

    # ethertype
    pytest.param("A1", "91:E0:F0:00:00:01", "avtp", "0x22F0", 10, []), # ethertype is not int
    pytest.param("A1", "91:E0:F0:00:00:01", "avtp", [0x22F0], 10, []), # ethertype is list
    pytest.param("A1", "91:E0:F0:00:00:01", "avtp", -1, 10, []),       # ethertype negative
    pytest.param("A1", "91:E0:F0:00:00:01", "avtp", 0x10000, 10, []),  # ethertype out of range
    pytest.param("A1", "91:E0:F0:00:00:01", "avtp", "INVALID", 10, []),# ethertype not int

    # vlan
    pytest.param("A1", "91:E0:F0:00:00:01", "avtp", 0x22F0, "10", [], marks=pytest.mark.xfail), # vlan not int
    pytest.param("A1", "91:E0:F0:00:00:01", "avtp", 0x22F0, [10], []), # vlan is list
    pytest.param("A1", "91:E0:F0:00:00:01", "avtp", 0x22F0, -1, []),   # vlan negative
    pytest.param("A1", "91:E0:F0:00:00:01", "avtp", 0x22F0, 5000, []), # vlan out of range

    # multicast_tx
    pytest.param("A1", "91:E0:F0:00:00:01", "avtp", 0x22F0, 10, "INVALID"),              # not a list
    pytest.param("A1", "91:E0:F0:00:00:01", "avtp", 0x22F0, 10, [123]),                  # non-mac inside list
    pytest.param("A1", "91:E0:F0:00:00:01", "avtp", 0x22F0, 10, ["02:00:00:00:00:01"]),  # not multicast MAC
    pytest.param("A1", "91:E0:F0:00:00:01", "avtp", 0x22F0, 10, [""]),                   # empty MAC string
]
@pytest.mark.parametrize("name,mac,protocol,type,vlan,tx",invalid_cases)
def test_meu_wraps_ame_inside_mmes_invalid_values(name,mac,protocol,type,vlan,tx):
    """
    Ensure endpoint creation fails for invalid values, types, or inconsistent configurations.
    """
    with pytest.raises(Exception):
        MACEndpointUnion(root=AVTPMulticastEndpoint(name=name,mac_address=MacAddress(mac),protocol=protocol,ethertype=type,vlan_id=vlan,multicast_tx=tx))