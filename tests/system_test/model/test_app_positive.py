"""System-level positive tests for the app layer (flync_4_app)."""

from flync.core.utils.exceptions_handling import validate_with_policy
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
from flync.model.flync_4_someip.deployment import SOMEIPServiceConsumer
from flync.model.flync_4_someip.service_interface import SDConfig, SDTimings, SOMEIPConfig, SOMEIPServiceInterface, SOMEIPTimingProfile
from flync.model.flync_model import FLYNCModel

FLYNC_VERSION = "0.14.0"
SERVICE_NAME = "TelemetryService"
SERVICE_ID = 0x101
MAJOR_VERSION = 1
CONSUMED_INSTANCE = 5
PROVIDED_INSTANCE = 9
APP_NAME = "telemetry_app"
CONTROLLER_NAME = "CTRL1"
ENDPOINT_ADDRESS = "10.0.20.2"

SELF_CONSUMED_WARNING_ERROR_ID = "FLYNC-CMN-WARN-CONS-242"


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


def _make_app(consumer=True, provider=False) -> App:
    """Return an app with optional consumer / provider references."""
    refs: dict = {}
    if consumer:
        refs["service_consumer_refs"] = [dict(service_id=SERVICE_ID, instance_id=CONSUMED_INSTANCE, major_version=MAJOR_VERSION)]
    if provider:
        refs["service_provider_refs"] = [dict(service_id=SERVICE_ID, instance_id=PROVIDED_INSTANCE, major_version=MAJOR_VERSION)]
    return App(name=APP_NAME, **refs)


def _make_model_data(app: App, deployments=(), app_refs=()) -> dict:
    """Return the raw data of the smallest workspace hosting *app* on a controller whose socket carries *deployments*."""
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
    return dict(
        ecus=[ecu],
        apps=[app],
        metadata=_make_metadata(),
        communication=FLYNCCommunicationConfig(someip_config=_make_someip_config()),
    )


def _make_model(app: App, deployments=(), app_refs=()) -> FLYNCModel:
    """Return the smallest workspace hosting *app* on a controller whose socket carries *deployments*."""
    return FLYNCModel(**_make_model_data(app, deployments, app_refs))


def _find_warning(findings, error_id):
    """Return the first finding carrying *error_id*, or ``None``."""
    return next((f for f in findings if (f.get("ctx") or {}).get("error_id") == error_id), None)


def test_app_with_consumer_reference_to_declared_service_valid():
    """
    ============================================================
    TEST NAME: app consuming a declared SOME/IP service builds
    RULE / CONSTRAINT: RULE-AP-02 / RULE-AP-06
      An application's service references must resolve to a service
      declared in the system; an instance is addressed by its
      (service_id, instance_id, major_version) triple.
    ============================================================

    App (telemetry_app)
      |
      | service_consumer_refs  (0x101 / inst 5 / v1)
      v
    SOME/IP Service "TelemetryService"  (declared in someip_config)

    Relationships:
    - App references a SOME/IP service declared system-wide
    - The referenced instance triple is well-formed
    - No controller binding is required for a standalone app

    Only describe objects created by this test.
    """

    app = _make_app(consumer=True, provider=False)

    model = _make_model(app, app_refs=[])

    assert [a.name for a in model.apps] == [APP_NAME]
    assert model.apps[0].service_consumer_refs[0].service_id == SERVICE_ID


def test_app_with_provider_reference_to_declared_service_valid():
    """
    ============================================================
    TEST NAME: app providing a declared SOME/IP service builds
    RULE / CONSTRAINT: RULE-AP-02 / RULE-AP-06
      An application may provide a service instance it exposes to
      consumers; the provided instance triple must resolve to a
      declared service.
    ============================================================

    App (telemetry_app)
      |
      | service_provider_refs  (0x101 / inst 9 / v1)
      v
    SOME/IP Service "TelemetryService"  (declared in someip_config)

    Relationships:
    - App provides a SOME/IP service declared system-wide
    - Only a provider role is declared (no consumer refs)
    """

    app = _make_app(consumer=False, provider=True)

    model = _make_model(app, app_refs=[])

    assert model.apps[0].service_provider_refs[0].instance_id == PROVIDED_INSTANCE


def test_app_consuming_and_providing_distinct_instances_valid():
    """
    ============================================================
    TEST NAME: app consuming and providing distinct instances is clean
    RULE / CONSTRAINT: RULE-AP-06
      A service instance is identified by its (service_id, instance_id,
      major_version) triple; an app may consume one instance and provide
      a different instance without flagging self-consumption.
    ============================================================

    App (telemetry_app)
      |--service_consumer_refs--> consume (0x101 / inst 5 / v1)
      |--service_provider_refs--> provide (0x101 / inst 9 / v1)

    Relationships:
    - Consumer reference names instance 5
    - Provider reference names instance 9 (distinct)
    - No self-consume warning (242) is emitted
    """

    app = _make_app(consumer=True, provider=True)

    model, findings = validate_with_policy(FLYNCModel, _make_model_data(app, app_refs=[]), path=None)

    assert model is not None
    assert _find_warning(findings, SELF_CONSUMED_WARNING_ERROR_ID) is None


def test_app_bound_to_controller_with_matching_deployment_accepted():
    """
    ============================================================
    TEST NAME: app bound to controller with matching deployment accepted
    RULE / CONSTRAINT: RULE-AP-03 / RULE-AP-04
      Each process must be mapped to a machine, and the required service
      instance must be mapped to that machine's communication connector
      ([constr_5004], [TPS_MANI_03001]).
    ============================================================

    Controller CTRL1 (Machine)
      |  app_bindings.app_refs = [telemetry_app]
      |  socket.deployments = [SOME/IP consumer 0x101/inst5/v1]
      v
    App telemetry_app  --consumes--> 0x101 / inst 5 / v1

    Relationships:
    - App is bound to controller CTRL1
    - Controller deploys the consumed instance as a SOME/IP consumer
    - Binding resolves and consumer reference is matched
    """

    app = _make_app(consumer=True, provider=False)

    model = _make_model(app, deployments=[_make_consumer()], app_refs=[APP_NAME])

    bound = model.get_all_controllers()[0].app_bindings.apps
    assert [a.name for a in bound] == [APP_NAME]


def test_distinct_app_names_accepted():
    """
    ============================================================
    TEST NAME: distinct app names accepted
    RULE / CONSTRAINT: RULE-AP-07
      Identifiable elements (applications) must have unique names within
      the system scope so each is referrable unambiguously.
    ============================================================

    App "dashboard_app"      App "diagnostics_app"
              \\              //
               \\            //
                FLYNCModel.apps

    Relationships:
    - Two apps share the system model
    - Their names differ, so both are retained in declaration order
    """

    apps = [App(name="dashboard_app"), App(name="diagnostics_app")]

    model = FLYNCModel(ecus=[], apps=apps, metadata=_make_metadata())

    assert [app.name for app in model.apps] == ["dashboard_app", "diagnostics_app"]


def test_app_self_consuming_same_instance_flagged_by_warning():
    """
    ============================================================
    TEST NAME: app consuming and providing the same instance is warned
    RULE / CONSTRAINT: RULE-AP-06 (implementation warning 242)
      A single instance is identified by one (service_id, instance_id,
      major_version) triple; referencing it both as a required and a
      provided service maps the same deployed endpoint, which is flagged
      as a consistency warning rather than a hard error.
    ============================================================

    App (telemetry_app)
      |--service_consumer_refs--> (0x101 / inst 5 / v1)
      |--service_provider_refs--> (0x101 / inst 5 / v1)  [same triple]

    Relationships:
    - The same instance triple appears on both sides
    - Model still builds; warning FLYNC-CMN-WARN-CONS-242 is reported
    """

    app = App(
        name=APP_NAME,
        service_consumer_refs=[dict(service_id=SERVICE_ID, instance_id=CONSUMED_INSTANCE, major_version=MAJOR_VERSION)],
        service_provider_refs=[dict(service_id=SERVICE_ID, instance_id=CONSUMED_INSTANCE, major_version=MAJOR_VERSION)],
    )

    model, findings = validate_with_policy(FLYNCModel, _make_model_data(app, app_refs=[]), path=None)

    assert model is not None
    warning = _find_warning(findings, SELF_CONSUMED_WARNING_ERROR_ID)
    assert warning is not None, [f["msg"] for f in findings]
    assert f"{SERVICE_ID:#06x}" in warning["msg"]


def test_app_feature_preserved_through_model_roundtrip():
    """
    ============================================================
    TEST NAME: app feature is preserved through model serialization
    RULE / CONSTRAINT: RULE-AP-01
      An application's identity (name) and its provided/required service
      interactions must survive serialization so the configured app is
      round-tripped intact.
    ============================================================

    FLYNCModel
      |  model_dump()
      v
    serialized app dict  --validate-->  App (reconstructed)
      |  name = telemetry_app
      |  service_consumer_refs = [...]
      |  service_provider_refs = [...]

    Relationships:
    - App is dumped as part of the complete model
    - Dumped data reconstructs an equivalent App
    """

    app = _make_app(consumer=True, provider=True)

    model = _make_model(app, deployments=[_make_consumer()], app_refs=[APP_NAME])

    dumped = model.model_dump()["apps"][0]
    assert dumped["name"] == APP_NAME
    assert len(dumped["service_consumer_refs"]) == 1
    assert len(dumped["service_provider_refs"]) == 1

    rebuilt = App(**dumped)
    assert rebuilt.model_dump() == dumped
