import pytest
from flync.model.flync_4_ecu.mac_multicast_endpoint import *
from flync.core.datatypes.macaddress import MacAddress

valid_cases = [
    ["A1", "91:E0:F0:00:00:01", "avtp",0],
    ["A2", "91:E0:F0:00:00:10", "AVTP",4095],
    ["A3", "91:E0:F0:00:00:11", "avtp",None],
]
@pytest.mark.parametrize("name,mac,protocol,vlan",valid_cases)
def test_meu_wraps_ame_inside_mmes_default_values(name,mac,protocol,vlan):
    """
    Verify that an AVTPMulticastEndpoint endpoint wrapped in MACEndpointUnion is correctly stored and accessible through MACMulticastEndpoints using only default values.
    """
    ame = AVTPMulticastEndpoint(name=name,mac_address=MacAddress(mac),protocol=protocol,vlan_id=vlan)
    meu = MACEndpointUnion(root=ame)
    mmes = MACMulticastEndpoints(endpoints=[meu])

    assert ame.ethertype == 8944
    assert ame.multicast_tx == []
    assert isinstance(mmes.endpoints[0].root, AVTPMulticastEndpoint)

valid_cases = [
    ["A1", "91:E0:F0:00:00:01", "avtp",8944,10,[]],
    ["A2", "91:E0:F0:00:00:01", "AVTP",0x22F0,10,["91:E0:F0:00:00:20","91:E0:F0:00:00:30"]],
]
@pytest.mark.parametrize("name,mac,protocol,type,vlan,tx",valid_cases)
def test_meu_wraps_ame_inside_mmes_optional_values(name,mac,protocol,type,vlan,tx):
    """
    Verify that an AVTPMulticastEndpoint endpoint wrapped in MACEndpointUnion is correctly stored and accessible through MACMulticastEndpoints using both default and optional values.
    """
    ame = AVTPMulticastEndpoint(name=name,mac_address=MacAddress(mac),protocol=protocol,ethertype=type,vlan_id=vlan,multicast_tx=tx)
    meu = MACEndpointUnion(root=ame)
    mmes = MACMulticastEndpoints(endpoints=[meu])

    assert isinstance(mmes.endpoints[0].root, AVTPMulticastEndpoint)