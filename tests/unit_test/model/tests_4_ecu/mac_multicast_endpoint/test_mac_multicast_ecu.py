import pytest
from pydantic import ValidationError

from flync.model.flync_4_ecu import ECU
from flync.model.flync_4_ecu.mac_multicast_endpoint import AVTPMulticastEndpoint, MACEndpointUnion, MACMulticastEndpoints
from tests.error_assertions import assert_single_error
from tests.model_builders import make_ethernet_ecu

#: Not the MAC of any interface built by :func:`make_ethernet_ecu`.
_UNKNOWN_MAC = "02:00:00:00:00:99"


def _ecu_with_endpoint(endpoint: AVTPMulticastEndpoint) -> ECU:
    template = make_ethernet_ecu()
    return ECU(
        name=template.name,
        controllers=template.controllers,
        ports=template.ports,
        topology=template.topology,
        ecu_metadata=template.ecu_metadata,
        mac_multicast_endpoints=MACMulticastEndpoints(endpoints=[MACEndpointUnion(root=endpoint)]),
    )


def test_endpoint_without_multicast_tx_needs_no_interface():
    """An endpoint that transmits nothing creates no TX group, so its MAC does not have to belong to an interface."""
    ecu = _ecu_with_endpoint(AVTPMulticastEndpoint(name="ep", mac_address=_UNKNOWN_MAC, protocol="avtp"))

    assert ecu.multicast_groups == []


def test_endpoint_with_multicast_tx_needs_an_interface():
    endpoint = AVTPMulticastEndpoint(name="ep", mac_address=_UNKNOWN_MAC, protocol="avtp", multicast_tx=["91:E0:F0:00:00:01"])

    with pytest.raises(ValidationError) as exc_info:
        _ecu_with_endpoint(endpoint)

    assert_single_error(exc_info, "FLYNC-ECU-MIN-REF-071", _UNKNOWN_MAC)


def test_multicast_tx_null_loads_as_empty_list():
    endpoint = AVTPMulticastEndpoint(name="ep", mac_address=_UNKNOWN_MAC, protocol="avtp", multicast_tx=None)

    assert endpoint.multicast_tx == []
