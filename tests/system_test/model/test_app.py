"""Workspace-level specs for applications and their controller bindings."""

import pytest
from pydantic import ValidationError

from flync.model.flync_4_app import App, AppBindings
from flync.model.flync_4_communication.flync_communication import FLYNCCommunicationConfig
from flync.model.flync_4_ecu import EthernetInterface, EthernetInterfaceConfig, VirtualControllerInterface
from flync.model.flync_4_ecu.controller import Controller
from flync.model.flync_4_ecu.ecu import ECU
from flync.model.flync_4_ecu.internal_topology import ECUPortToControllerInterface, InternalTopology
from flync.model.flync_4_ecu.phy import BASET1
from flync.model.flync_4_ecu.port import ECUPort
from flync.model.flync_4_ecu.socket_container import SocketContainer
from flync.model.flync_4_ecu.sockets import IPv4AddressEndpoint, SocketUDP
from flync.model.flync_4_metadata.metadata import BaseVersion, ECUMetadata, EmbeddedMetadata, SystemMetadata
from flync.model.flync_4_someip.deployment import SOMEIPServiceConsumer, SOMEIPServiceProvider
from flync.model.flync_4_someip.service_interface import SDConfig, SDTimings, SOMEIPConfig, SOMEIPServiceInterface, SOMEIPTimingProfile
from flync.model.flync_model import FLYNCModel
from tests.error_assertions import assert_single_error

FLYNC_VERSION = "0.13.0"
SERVICE_NAME = "TelemetryService"
SERVICE_ID = 0x101
MAJOR_VERSION = 1
INSTANCE_ID = 5
APP_NAME = "telemetry_app"
CONTROLLER_NAME = "CTRL1"
ENDPOINT_ADDRESS = "10.0.20.2"

DUPLICATE_APP_NAMES_ERROR_ID = "FLYNC-CMN-MAJ-UNIQ-009"
UNMATCHED_APP_BINDING_ERROR_ID = "FLYNC-GEN-MAJ-CONS-245"


def _make_version() -> BaseVersion:
    """Return the FLYNC version used by every metadata block in this module."""
    return BaseVersion(version=FLYNC_VERSION)


def _make_metadata() -> SystemMetadata:
    """Return the system metadata every workspace built here carries."""
    return SystemMetadata(type="system", release=_make_version(), author="TestTeam", compatible_flync_version=_make_version())


def _make_someip_config() -> SOMEIPConfig:
    """Return a SOME/IP config declaring :data:`SERVICE_NAME` and the SD timings profiles deployments reference."""
    service = SOMEIPServiceInterface(
        meta={"author": "Dev", "compatible_flync_version": {"version_schema": "semver", "version": FLYNC_VERSION}},
        name=SERVICE_NAME,
        id=SERVICE_ID,
        major_version=MAJOR_VERSION,
    )
    return SOMEIPConfig(
        sd_config=SDConfig(
            ip_address="224.224.224.255",
            sd_timings=[SDTimings(profile_id="server_default"), SDTimings(profile_id="client_default")],
        ),
        services=[service],
        someip_timings=SOMEIPTimingProfile(),
    )


def _make_consumer(instance_id: int = INSTANCE_ID) -> SOMEIPServiceConsumer:
    """Return a consumer deployment of :data:`SERVICE_NAME`, by default of the instance the app references."""
    return SOMEIPServiceConsumer(
        service=SERVICE_ID,
        major_version=MAJOR_VERSION,
        instance_id=instance_id,
        someip_sd_timings_profile="client_default",
    )


def _make_provider(instance_id: int = INSTANCE_ID) -> SOMEIPServiceProvider:
    """Return a provider deployment of :data:`SERVICE_NAME` - the wrong direction for a consumer reference."""
    return SOMEIPServiceProvider(
        service=SERVICE_ID,
        major_version=MAJOR_VERSION,
        instance_id=instance_id,
        someip_sd_timings_profile="server_default",
    )


def _make_app() -> App:
    """Return the app consuming instance :data:`INSTANCE_ID` of service :data:`SERVICE_ID`."""
    return App(
        name=APP_NAME,
        service_consumer_refs=[dict(service_id=SERVICE_ID, instance_id=INSTANCE_ID, major_version=MAJOR_VERSION)],
    )


def _make_bound_model(deployments=()) -> FLYNCModel:
    """Return the smallest workspace binding :func:`_make_app` to a controller whose one socket carries *deployments*."""
    socket = SocketUDP(name="someip_udp_socket_1", endpoint_address=ENDPOINT_ADDRESS, port_no=30500, protocol="udp", deployments=list(deployments))
    eth_iface = EthernetInterface(
        name="ETH_IF_1",
        interface_config=EthernetInterfaceConfig(
            virtual_interfaces=[
                VirtualControllerInterface(
                    name="VLAN_1",
                    vlanid=0,
                    addresses=[IPv4AddressEndpoint(address=ENDPOINT_ADDRESS, ipv4netmask="255.255.255.0", sockets=[])],
                    multicast=[],
                )
            ],
        ),
        sockets=[SocketContainer(name="ETH_CONTAINER_1", vlan_id=0, sockets=[socket])],
    )
    controller = Controller(
        name=CONTROLLER_NAME,
        controller_metadata=EmbeddedMetadata(type="embedded", author="TestTeam", target_system="Device1", compatible_flync_version=_make_version()),
        ethernet_interfaces=[eth_iface],
        app_bindings=AppBindings(app_refs=[APP_NAME]),
    )
    port = ECUPort(name="ECU1_ETH_IF_1_port", mdi_config=BASET1())
    ecu = ECU(
        name="ECU1",
        controllers=[controller],
        ports=[port],
        topology=InternalTopology(
            connections=[
                ECUPortToControllerInterface(
                    id="conn_ECU1_ETH_IF_1",
                    ecu_port=port.name,
                    controller_interface="ETH_IF_1",
                    controller=CONTROLLER_NAME,
                )
            ]
        ),
        ecu_metadata=ECUMetadata(type="ecu", author="TestTeam", compatible_flync_version=_make_version()),
    )
    return FLYNCModel(
        ecus=[ecu],
        apps=[_make_app()],
        metadata=_make_metadata(),
        communication=FLYNCCommunicationConfig(someip_config=_make_someip_config()),
    )


def test_duplicate_app_names_rejected():
    """Two apps sharing a name are rejected system-wide, mirroring ECU / port name uniqueness."""

    apps = [App(name="dashboard_app"), App(name="dashboard_app")]

    metadata = _make_metadata()
    with pytest.raises(ValidationError) as exc_info:
        FLYNCModel(ecus=[], apps=apps, metadata=metadata)
    assert_single_error(exc_info, DUPLICATE_APP_NAMES_ERROR_ID, "Duplicates found in App names")


def test_distinct_app_names_accepted():
    """Sanity check: differently named apps are accepted and kept in declaration order."""

    apps = [App(name="dashboard_app"), App(name="diagnostics_app")]

    model = FLYNCModel(ecus=[], apps=apps, metadata=_make_metadata())

    assert [app.name for app in model.apps] == ["dashboard_app", "diagnostics_app"]


@pytest.mark.parametrize(
    "deployments",
    [
        pytest.param([], id="no_deployment_at_all"),
        pytest.param([_make_consumer(instance_id=INSTANCE_ID + 1)], id="consumer_of_another_instance"),
        pytest.param([_make_provider()], id="provider_instead_of_consumer"),
    ],
)
def test_app_bound_to_controller_without_matching_deployment_rejected(deployments):
    """The app expects to consume an instance the controller it is bound to never deploys as a consumer."""

    with pytest.raises(ValidationError) as exc_info:
        _make_bound_model(deployments)
    assert_single_error(exc_info, UNMATCHED_APP_BINDING_ERROR_ID, APP_NAME)


def test_app_bound_to_controller_with_matching_deployment_accepted():
    """Sanity check: the same binding is accepted once the controller consumes the referenced instance."""

    model = _make_bound_model([_make_consumer()])

    assert [app.name for app in model.get_all_controllers()[0].app_bindings.apps] == [APP_NAME]
