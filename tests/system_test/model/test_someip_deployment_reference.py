"""Workspace-level negatives for the reference resolution `SOMEIPServiceDeployment.bind` performs.

`bind` is not called directly by these tests: it runs from `FLYNCModel.resolve_someip_deployments`,
a `model_validator(mode="after")` that walks every socket's deployments once the workspace is built -
see ``src/flync/model/flync_model.py``.

Covers:

* the deployed ``(service, major_version)`` must exist among ``communication.someip_config.services``
  (``FLYNC-SOM-MAJ-REF-341``), and
* the deployment's ``someip_sd_timings_profile`` must exist among ``someip_config.sd_config.sd_timings``
  (``FLYNC-SOM-MAJ-REF-342``).
"""

import pytest
from pydantic import ValidationError

from flync.model.flync_4_communication.flync_communication import FLYNCCommunicationConfig
from flync.model.flync_4_ecu import EthernetInterface, EthernetInterfaceConfig, SocketUDP, VirtualControllerInterface
from flync.model.flync_4_ecu.controller import Controller
from flync.model.flync_4_ecu.ecu import ECU
from flync.model.flync_4_ecu.internal_topology import ECUPortToControllerInterface, InternalTopology
from flync.model.flync_4_ecu.phy import BASET1
from flync.model.flync_4_ecu.port import ECUPort
from flync.model.flync_4_ecu.socket_container import SocketContainer
from flync.model.flync_4_ecu.sockets import IPv4AddressEndpoint
from flync.model.flync_4_metadata.metadata import BaseVersion, ECUMetadata, EmbeddedMetadata, SystemMetadata
from flync.model.flync_4_someip.deployment import SOMEIPServiceProvider
from flync.model.flync_4_someip.service_interface import SDConfig, SDTimings, SOMEIPConfig, SOMEIPServiceInterface, SOMEIPTimingProfile
from flync.model.flync_model import FLYNCModel
from tests.error_assertions import assert_single_error

FLYNC_VERSION = "0.13.0"
SERVICE_NAME = "TelemetryService"
SERVICE_ID = 0x101
MAJOR_VERSION = 1
ENDPOINT_ADDRESS = "10.0.20.2"


def _make_version() -> BaseVersion:
    """Return the FLYNC version used by every metadata block in this module."""
    return BaseVersion(version=FLYNC_VERSION)


def _make_someip_config() -> SOMEIPConfig:
    """Return a SOME/IP config declaring :data:`SERVICE_NAME` and the ``server_default`` SD timings profile."""
    service = SOMEIPServiceInterface(
        meta={"author": "Dev", "compatible_flync_version": {"version_schema": "semver", "version": FLYNC_VERSION}},
        name=SERVICE_NAME,
        id=SERVICE_ID,
        major_version=MAJOR_VERSION,
    )
    return SOMEIPConfig(
        sd_config=SDConfig(ip_address="224.224.224.255", sd_timings=[SDTimings(profile_id="server_default")]),
        services=[service],
        someip_timings=SOMEIPTimingProfile(),
    )


def _make_model(deployment: SOMEIPServiceProvider) -> FLYNCModel:
    """Wrap *deployment* in the smallest workspace that reaches ``FLYNCModel.resolve_someip_deployments``."""
    socket = SocketUDP(name="someip_udp_socket_1", endpoint_address=ENDPOINT_ADDRESS, port_no=30500, protocol="udp", deployments=[deployment])
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
        name="CTRL1",
        controller_metadata=EmbeddedMetadata(type="embedded", author="TestTeam", target_system="Device1", compatible_flync_version=_make_version()),
        ethernet_interfaces=[eth_iface],
    )
    port = ECUPort(name="CTRL1_ETH_IF_1_port", mdi_config=BASET1())
    ecu = ECU(
        name="ECU1",
        controllers=[controller],
        ports=[port],
        topology=InternalTopology(
            connections=[
                ECUPortToControllerInterface(
                    id="conn_CTRL1_ETH_IF_1",
                    ecu_port=port.name,
                    controller_interface="ETH_IF_1",
                    controller="CTRL1",
                )
            ]
        ),
        ecu_metadata=ECUMetadata(type="ecu", author="TestTeam", compatible_flync_version=_make_version()),
    )
    return FLYNCModel(
        ecus=[ecu],
        metadata=SystemMetadata(type="system", release=_make_version(), author="TestTeam", compatible_flync_version=_make_version()),
        communication=FLYNCCommunicationConfig(someip_config=_make_someip_config()),
    )


def test_deployment_of_unknown_service_rejected():
    """A deployment referencing a ``(service, major_version)`` pair no declared service matches is rejected."""
    deployment = SOMEIPServiceProvider(
        service=SERVICE_ID,
        major_version=MAJOR_VERSION + 1,  # someip_config only declares major_version=1
        instance_id=1,
        someip_sd_timings_profile="server_default",
    )

    with pytest.raises(ValidationError) as exc_info:
        _make_model(deployment)
    assert_single_error(exc_info, "FLYNC-SOM-MAJ-REF-341", "No service found for id=")


def test_deployment_of_unknown_sd_timings_profile_rejected():
    """A deployment referencing an SD timings profile absent from ``sd_config.sd_timings`` is rejected."""
    deployment = SOMEIPServiceProvider(
        service=SERVICE_ID,
        major_version=MAJOR_VERSION,
        instance_id=1,
        someip_sd_timings_profile="unknown_profile",
    )

    with pytest.raises(ValidationError) as exc_info:
        _make_model(deployment)
    assert_single_error(exc_info, "FLYNC-SOM-MAJ-REF-342", "No SD timings profile 'unknown_profile'")


def test_deployment_of_known_service_and_profile_accepted():
    """Sanity check: a deployment matching a declared service and SD timings profile is accepted."""
    deployment = SOMEIPServiceProvider(
        service=SERVICE_ID,
        major_version=MAJOR_VERSION,
        instance_id=1,
        someip_sd_timings_profile="server_default",
    )

    model = _make_model(deployment)

    assert model.communication.someip_config.services[0].name == SERVICE_NAME
