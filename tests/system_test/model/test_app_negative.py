"""System-level negative tests for the app layer (flync_4_app)."""

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

FLYNC_VERSION = "0.14.0"
SERVICE_NAME = "TelemetryService"
SERVICE_ID = 0x101
MAJOR_VERSION = 1
CONSUMED_INSTANCE = 5
PROVIDED_INSTANCE = 9
APP_NAME = "telemetry_app"
CONTROLLER_NAME = "CTRL1"
ENDPOINT_ADDRESS = "10.0.20.2"

DUPLICATE_APP_NAMES_ERROR_ID = "FLYNC-CMN-MAJ-UNIQ-009"
UNDEFINED_SERVICE_REF_ERROR_ID = "FLYNC-GEN-MAJ-REF-186"
UNDEFINED_APP_BINDING_ERROR_ID = "FLYNC-CMN-MAJ-REF-187"
UNMATCHED_APP_BINDING_ERROR_ID = "FLYNC-GEN-MAJ-CONS-245"


def _make_version() -> BaseVersion:
    """Return the FLYNC version used by every metadata block in this module."""
    return BaseVersion(version=FLYNC_VERSION)


def _make_metadata() -> SystemMetadata:
    """Return the system metadata every workspace built here carries."""
    return SystemMetadata(type="system", release=_make_version(), author="TestTeam", compatible_flync_version=_make_version())


def _make_someip_config() -> SOMEIPConfig:
    """Return a SOME/IP config declaring :data:`SERVICE_NAME` and the SD timing profiles deployments reference."""
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


def _make_consumer(instance_id: int = CONSUMED_INSTANCE) -> SOMEIPServiceConsumer:
    """Return a consumer deployment of :data:`SERVICE_NAME`, by default of the instance the app consumes."""
    return SOMEIPServiceConsumer(
        service=SERVICE_ID,
        major_version=MAJOR_VERSION,
        instance_id=instance_id,
        someip_sd_timings_profile="client_default",
    )


def _make_provider(instance_id: int = PROVIDED_INSTANCE) -> SOMEIPServiceProvider:
    """Return a provider deployment of :data:`SERVICE_NAME`, by default of the instance the app provides."""
    return SOMEIPServiceProvider(
        service=SERVICE_ID,
        major_version=MAJOR_VERSION,
        instance_id=instance_id,
        someip_sd_timings_profile="server_default",
    )


def _make_app(consumer_refs=(), provider_refs=(), name: str = APP_NAME) -> App:
    """Return an app carrying the given consumer/provider reference triples."""
    refs = {}
    if consumer_refs:
        refs["service_consumer_refs"] = [dict(r) for r in consumer_refs]
    if provider_refs:
        refs["service_provider_refs"] = [dict(r) for r in provider_refs]
    return App(name=name, **refs)


def _make_model(app: App, deployments=(), app_refs=()) -> FLYNCModel:
    """Return the smallest workspace hosting *app* on a controller whose one socket carries *deployments*."""
    socket = SocketUDP(
        name="someip_udp_socket_1",
        endpoint_address=ENDPOINT_ADDRESS,
        port_no=30500,
        protocol="udp",
        deployments=list(deployments),
    )
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
        app_bindings=AppBindings(app_refs=list(app_refs)),
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
        apps=[app],
        metadata=_make_metadata(),
        communication=FLYNCCommunicationConfig(someip_config=_make_someip_config()),
    )


def test_duplicate_app_names_rejected():
    """
    ============================================================
    TEST NAME: two apps sharing a name are rejected system-wide
    RULE / CONSTRAINT: RULE-AP-07
      Identifiable elements (applications) must have unique names within
      the system scope so each stays referrable (System Template §9.4).
    ============================================================

    App "dashboard_app"     App "dashboard_app"   (same name)
              \\                  //
               \\                //
                FLYNCModel.apps  --> rejection

    Relationships:
    - Both apps carry the same system-wide name
    - Duplicate identity is rejected with FLYNC-CMN-MAJ-UNIQ-009
    """

    apps = [App(name="dashboard_app"), App(name="dashboard_app")]

    with pytest.raises(ValidationError) as exc_info:
        FLYNCModel(ecus=[], apps=apps, metadata=_make_metadata())
    assert_single_error(exc_info, DUPLICATE_APP_NAMES_ERROR_ID, "Duplicates found in App names")


def test_consumer_reference_to_undefined_service_rejected():
    """
    ============================================================
    TEST NAME: app referencing an undeclared service is rejected
    RULE / CONSTRAINT: RULE-AP-02
      A service's Service Identifier is unique within one system and an
      application's service reference must resolve to a service that
      exists (ProvidedServiceInstance.serviceIdentifier).
    ============================================================

    App (telemetry_app)
      |
      | service_consumer_refs --> (0x0500 / inst 1 / v1)  [undeclared]
      v
    SOME/IP config (declares only 0x0101)  --> rejection

    Relationships:
    - App references a service id/major_version not declared anywhere
    - Unresolvable reference is rejected with FLYNC-GEN-MAJ-REF-186
    """

    app = _make_app(consumer_refs=[dict(service_id=0x0500, instance_id=1, major_version=1)])

    with pytest.raises(ValidationError) as exc_info:
        _make_model(app, app_refs=[])
    assert_single_error(exc_info, UNDEFINED_SERVICE_REF_ERROR_ID, f"{0x0500:#06x}")


def test_controller_binding_to_undefined_app_rejected():
    """
    ============================================================
    TEST NAME: controller binding to an undefined app is rejected
    RULE / CONSTRAINT: RULE-AP-05 / RULE-AP-03
      Software (processes/executables) is deployed onto a Machine through
      an explicit process-to-machine mapping; that mapping must name an
      existing deployable application.
    ============================================================

    Controller CTRL1 (Machine)
      |
      | app_bindings.app_refs = ["ghost_app"]   [not declared]
      v
    FLYNCModel.apps (declares only telemetry_app)  --> rejection

    Relationships:
    - Controller binding names an app that is not defined
    - Undefined binding target is rejected with FLYNC-CMN-MAJ-REF-187
    """

    app = _make_app()

    with pytest.raises(ValidationError) as exc_info:
        _make_model(app, app_refs=["ghost_app"])
    assert_single_error(exc_info, UNDEFINED_APP_BINDING_ERROR_ID, "ghost_app")


@pytest.mark.parametrize(
    "deployments",
    [
        pytest.param([], id="no_deployment_at_all"),
        pytest.param([_make_consumer(instance_id=CONSUMED_INSTANCE + 1)], id="consumer_of_another_instance"),
        pytest.param([_make_provider(instance_id=CONSUMED_INSTANCE)], id="provider_instead_of_consumer"),
    ],
)
def test_app_bound_to_controller_without_matching_deployment_rejected(deployments):
    """
    ============================================================
    TEST NAME: app bound to controller without matching deployment rejected
    RULE / CONSTRAINT: RULE-AP-03 / RULE-AP-04
      Each process is mapped to one machine and its required service
      instance must be mapped to that machine's communication connector
      ([constr_5004], [TPS_MANI_03001]).
    ============================================================

    Controller CTRL1 (Machine)
      |
      | app_bindings.app_refs = [telemetry_app]
      | socket.deployments = <deployments>   [no matching consumer]
      v
    App telemetry_app  --consumes--> 0x101 / inst 5 / v1  --> rejection

    Relationships:
    - App is bound to controller CTRL1
    - Controller never deploys the consumed instance as a SOME/IP consumer
    - Unmatched binding is rejected with FLYNC-GEN-MAJ-CONS-245
    """

    app = _make_app(consumer_refs=[dict(service_id=SERVICE_ID, instance_id=CONSUMED_INSTANCE, major_version=MAJOR_VERSION)])

    with pytest.raises(ValidationError) as exc_info:
        _make_model(app, deployments=deployments, app_refs=[APP_NAME])
    assert_single_error(exc_info, UNMATCHED_APP_BINDING_ERROR_ID, APP_NAME)
