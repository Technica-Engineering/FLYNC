"""Factory fixtures shared by the ECU unit tests (inherited by the ``sockets/``, ``switch/``, ... subpackages).

Every fixture is a *factory*: it returns a builder so a single test can create several variants of the same
object - two deployments of one service instance, two sockets on one ECU - which is what the SOME/IP
uniqueness rules are about.
"""

import pytest

from flync.model.flync_4_ecu.controller import Controller, EthernetInterface, EthernetInterfaceConfig, VirtualControllerInterface
from flync.model.flync_4_ecu.internal_topology import ECUPortToControllerInterface, InternalTopology
from flync.model.flync_4_ecu.phy import BASET1
from flync.model.flync_4_ecu.port import ECUPort
from flync.model.flync_4_ecu.socket_container import SocketContainer
from flync.model.flync_4_ecu.sockets import IPv4AddressEndpoint
from flync.model.flync_4_metadata.metadata import BaseVersion, ECUMetadata, EmbeddedMetadata
from flync.model.flync_4_someip.deployment import SOMEIPServiceConsumer, SOMEIPServiceProvider

FLYNC_VERSION = "0.13.0"
ENDPOINT_ADDRESS = "10.0.20.2"
NETMASK = "255.255.255.0"

#: The service instance the SOME/IP uniqueness tests duplicate, as ``(service id, major version, instance id)``.
SERVICE_ID = 0x101
MAJOR_VERSION = 1
INSTANCE_ID = 5

#: SD timings profile each deployment role references, keyed by the ``role`` argument of ``someip_deployment``.
_DEPLOYMENT_ROLES = {
    "provider": (SOMEIPServiceProvider, "server_default"),
    "consumer": (SOMEIPServiceConsumer, "client_default"),
}


@pytest.fixture(scope="session")
def flync_version() -> BaseVersion:
    """The FLYNC version stamped into every metadata block built here."""
    return BaseVersion(version=FLYNC_VERSION)


@pytest.fixture
def someip_deployment():
    """Return a factory for one SOME/IP provider or consumer deployment of a service instance.

    ``role`` selects provider or consumer; the service triple defaults to
    ``(SERVICE_ID, MAJOR_VERSION, INSTANCE_ID)`` so a caller only spells out the part it wants to vary.
    """

    def _build(role: str, service: int = SERVICE_ID, major_version: int = MAJOR_VERSION, instance_id: int = INSTANCE_ID):
        deployment_model, sd_timings_profile = _DEPLOYMENT_ROLES[role]
        return deployment_model(
            service=service,
            major_version=major_version,
            instance_id=instance_id,
            someip_sd_timings_profile=sd_timings_profile,
        )

    return _build


@pytest.fixture
def udp_socket_data():
    """Return a factory for the *data* of a UDP socket carrying the given deployments.

    Unvalidated data, so that the construction a negative test is about happens inside its own
    ``pytest.raises`` / ``validate_with_policy`` block rather than in the factory call.
    """

    def _build(name: str = "my_socket", port_no: int = 30500, deployments=()) -> dict:
        return dict(
            name=name,
            endpoint_address=ENDPOINT_ADDRESS,
            port_no=port_no,
            protocol="udp",
            deployments=list(deployments),
        )

    return _build


@pytest.fixture
def minimal_ecu_kwargs(flync_version):
    """Return a factory for the kwargs of a minimal ECU: one controller / interface / VLAN hosting *sockets*.

    ``sockets`` takes whatever :class:`~flync.model.flync_4_ecu.socket_container.SocketContainer` accepts, so
    the socket data built by ``udp_socket_data`` can be handed over as-is.
    """

    def _build(sockets, name: str = "ECU1") -> dict:
        eth_iface = EthernetInterface(
            name="ETH_IF_1",
            interface_config=EthernetInterfaceConfig(
                virtual_interfaces=[
                    VirtualControllerInterface(
                        name="VLAN_1",
                        vlanid=0,
                        addresses=[IPv4AddressEndpoint(address=ENDPOINT_ADDRESS, ipv4netmask=NETMASK, sockets=[])],
                        multicast=[],
                    )
                ],
            ),
            sockets=[SocketContainer(name="ETH_CONTAINER_1", vlan_id=0, sockets=list(sockets))],
        )
        controller = Controller(
            name="CTRL1",
            controller_metadata=EmbeddedMetadata(
                type="embedded",
                author="TestTeam",
                target_system="Device1",
                compatible_flync_version=flync_version,
            ),
            ethernet_interfaces=[eth_iface],
        )
        port = ECUPort(name=f"{name}_ETH_IF_1_port", mdi_config=BASET1())
        topology = InternalTopology(
            connections=[
                ECUPortToControllerInterface(
                    id=f"conn_{name}_ETH_IF_1",
                    ecu_port=port.name,
                    controller_interface="ETH_IF_1",
                    controller="CTRL1",
                )
            ]
        )
        return dict(
            name=name,
            controllers=[controller],
            ports=[port],
            topology=topology,
            ecu_metadata=ECUMetadata(type="ecu", author="TestTeam", compatible_flync_version=flync_version),
        )

    return _build
