import pytest
from pydantic import ValidationError
from pydantic_core import PydanticCustomError

from flync.model.flync_4_diagnostics.doip.deployment import DoIPDiscoveryDeployment, DoIPServerDeployment
from flync.model.flync_4_diagnostics.doip.timings import DoIPTimingProfile
from flync.model.flync_4_diagnostics.uds.server import AccessProfile, UDSServer
from flync.model.flync_4_diagnostics.uds.services import DiagnosticSessionControlService, DiagnosticSessionDefinition
from flync.model.flync_4_ecu.sockets import SocketTCP, SocketUDP
from tests.error_assertions import assert_bind_error, assert_single_error

SESSION_CONTROL = DiagnosticSessionControlService(sessions=[DiagnosticSessionDefinition(name="default", id=0x01)])

SERVER_DEPLOYMENT = {
    "deployment_type": "doip_server",
    "name": "EngineEcu",
    "logical_address": 0x0101,
    "uds_server": "EngineEcuDiagnostic",
}


def make_server(**overrides):
    params = dict(
        name="EngineEcuDiagnostic",
        uds_timings_profile="uds_default",
        access_profiles=[AccessProfile(name="standard", default=True, sessions=["default"])],
        services=[SESSION_CONTROL],
    )
    params.update(overrides)
    return UDSServer(**params)


def test_doip_server_deployment_bind_resolves_server_and_timings():
    server = make_server()
    timings = DoIPTimingProfile(profile_id="doip_default")
    dep = DoIPServerDeployment(name="EngineEcu", logical_address=0x0101, uds_server="EngineEcuDiagnostic", doip_timings_profile="doip_default")
    dep.bind({"EngineEcuDiagnostic": server}, {"doip_default": timings})
    assert dep._uds_server_ref is server
    assert dep._timings_ref is timings


def test_doip_server_deployment_bind_leaves_timings_unset_without_profile():
    dep = DoIPServerDeployment(name="EngineEcu", logical_address=0x0101, uds_server="EngineEcuDiagnostic")
    dep.bind({"EngineEcuDiagnostic": make_server()}, {})
    assert dep._timings_ref is None


def test_doip_server_deployment_bind_rejects_unknown_server():
    dep = DoIPServerDeployment(name="EngineEcu", logical_address=0x0101, uds_server="missing")
    with pytest.raises(PydanticCustomError) as exc_info:
        dep.bind({}, {})
    assert_bind_error(exc_info, "FLYNC-DIA-MAJ-REF-278", "unknown UDS server 'missing'")


def test_doip_server_deployment_bind_rejects_unknown_timings_profile():
    dep = DoIPServerDeployment(name="EngineEcu", logical_address=0x0101, uds_server="EngineEcuDiagnostic", doip_timings_profile="missing")
    server = make_server()
    with pytest.raises(PydanticCustomError) as exc_info:
        dep.bind({"EngineEcuDiagnostic": server}, {})
    assert_bind_error(exc_info, "FLYNC-DIA-MAJ-REF-280", "unknown DoIP timings profile 'missing'")


def test_doip_discovery_deployment_bind_resolves_timings():
    timings = DoIPTimingProfile(profile_id="doip_default")
    dep = DoIPDiscoveryDeployment(doip_timings_profile="doip_default")
    dep.bind({"doip_default": timings})
    assert dep._timings_ref is timings


def test_doip_discovery_deployment_bind_is_noop_without_timings_profile():
    dep = DoIPDiscoveryDeployment()
    dep.bind({})
    assert dep._timings_ref is None


def test_doip_discovery_deployment_bind_rejects_unknown_timings_profile():
    dep = DoIPDiscoveryDeployment(doip_timings_profile="missing")
    with pytest.raises(PydanticCustomError) as exc_info:
        dep.bind({})
    assert_bind_error(exc_info, "FLYNC-DIA-MAJ-REF-279", "unknown DoIP timings profile 'missing'")


def test_doip_discovery_deployment_defaults():
    dep = DoIPDiscoveryDeployment()
    assert dep.vehicle_identification is True
    assert dep.vehicle_announcement is True
    assert dep.name is None


@pytest.mark.parametrize("logical_address", [0x0000, 0xFFFF])
def test_doip_server_logical_address_boundaries_accepted(logical_address):
    dep = DoIPServerDeployment(name="e", logical_address=logical_address, uds_server="EngineEcuDiagnostic")
    assert dep.logical_address == logical_address


def test_doip_server_logical_address_out_of_range_rejected():
    with pytest.raises(ValidationError) as exc_info:
        DoIPServerDeployment(name="e", logical_address=0x10000, uds_server="EngineEcuDiagnostic")
    assert_single_error(exc_info, None, "logical_address")


def test_doip_server_deployment_on_tcp_socket_accepted():
    SocketTCP(name="s", endpoint_address="10.0.20.5", port_no=13400, tcp_profile=1, deployments=[SERVER_DEPLOYMENT])


def test_doip_server_deployment_on_udp_socket_rejected():
    with pytest.raises(ValidationError) as exc_info:
        SocketUDP(name="s", endpoint_address="10.0.20.5", port_no=13400, deployments=[SERVER_DEPLOYMENT])
    assert_single_error(exc_info, "FLYNC-ECU-MAJ-COMP-274", "requires a TCP socket")


def test_doip_discovery_deployment_on_udp_socket_accepted():
    SocketUDP(name="s", endpoint_address="10.0.20.5", port_no=13400, deployments=[{"deployment_type": "doip_discovery"}])


def test_doip_discovery_deployment_on_tcp_socket_rejected():
    with pytest.raises(ValidationError) as exc_info:
        SocketTCP(
            name="s",
            endpoint_address="10.0.20.5",
            port_no=13400,
            tcp_profile=1,
            deployments=[{"deployment_type": "doip_discovery"}],
        )
    assert_single_error(exc_info, "FLYNC-ECU-MAJ-COMP-275", "requires a UDP socket")
