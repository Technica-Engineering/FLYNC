"""Workspace-level negatives for SOME/IP eventgroup multicast deployment.

Covers the two consistency rules a provider's ``multicast_config`` is subject to:

* the parent UDP socket must announce the group in ``multicast_tx`` (``FLYNC-GEN-MAJ-CONS-171``), and
* the parent socket must not be TCP (``FLYNC-GEN-MAJ-CONS-218``).
"""

from ipaddress import IPv4Address

import pytest
from pydantic import ValidationError

from flync.model.flync_4_communication.flync_communication import FLYNCCommunicationConfig
from flync.model.flync_4_ecu import EthernetInterface, EthernetInterfaceConfig, SocketTCP, SocketUDP, VirtualControllerInterface
from flync.model.flync_4_ecu.controller import Controller
from flync.model.flync_4_ecu.ecu import ECU
from flync.model.flync_4_ecu.internal_topology import ECUPortToControllerInterface, InternalTopology
from flync.model.flync_4_ecu.phy import BASET1
from flync.model.flync_4_ecu.port import ECUPort
from flync.model.flync_4_ecu.socket_container import SocketContainer
from flync.model.flync_4_ecu.sockets import IPv4AddressEndpoint
from flync.model.flync_4_metadata.metadata import BaseVersion, ECUMetadata, EmbeddedMetadata, SystemMetadata
from flync.model.flync_4_someip.deployment import SOMEIPEventgroupMulticastConfig, SOMEIPServiceProvider
from flync.model.flync_4_topology import EthernetTopology, FLYNCTopology
from flync.model.flync_model import FLYNCModel
from tests.error_assertions import assert_single_error

FLYNC_VERSION = "0.12.0"
MULTICAST_GROUP = "224.0.0.15"


def _make_version() -> BaseVersion:
    """Return the FLYNC version used by every test in this module."""
    return BaseVersion(version=FLYNC_VERSION)


def _make_multicast_config() -> SOMEIPEventgroupMulticastConfig:
    """Return an eventgroup multicast configuration for :data:`MULTICAST_GROUP`."""
    return SOMEIPEventgroupMulticastConfig(ip_address=MULTICAST_GROUP, port=30511, threshold=2, eventgroups=["eg_events_multicast"])


def _make_provider() -> SOMEIPServiceProvider:
    """Return a provided-service deployment that publishes an eventgroup over multicast."""
    return SOMEIPServiceProvider(
        service=0x101,
        instance_id=1,
        major_version=1,
        someip_sd_timings_profile="server_default",
        multicast_config=[_make_multicast_config()],
    )


def _make_model(socket) -> FLYNCModel:
    """Wrap *socket* in the smallest workspace that reaches the workspace-level multicast checks."""
    eth_iface = EthernetInterface(
        name="ETH_IF_1",
        interface_config=EthernetInterfaceConfig(
            virtual_interfaces=[
                VirtualControllerInterface(
                    name="VLAN_1",
                    vlanid=0,
                    addresses=[IPv4AddressEndpoint(address="10.0.20.2", ipv4netmask=IPv4Address("255.255.255.0"), sockets=[])],
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
    topology = InternalTopology(
        connections=[
            ECUPortToControllerInterface(
                id="conn_CTRL1_ETH_IF_1",
                ecu_port=port.name,
                controller_interface="ETH_IF_1",
                controller="CTRL1",
            )
        ]
    )
    ecu = ECU(
        name="ECU1",
        controllers=[controller],
        ports=[port],
        topology=topology,
        ecu_metadata=ECUMetadata(type="ecu", author="TestTeam", compatible_flync_version=_make_version()),
    )
    return FLYNCModel(
        ecus=[ecu],
        topology=FLYNCTopology(system_topology=EthernetTopology(connections=[])),
        metadata=SystemMetadata(type="system", release=_make_version(), author="TestTeam", compatible_flync_version=_make_version()),
        communication=FLYNCCommunicationConfig(),
    )


def test_provider_multicast_without_multicast_tx_entry_rejected():
    """A provider publishing an eventgroup group the parent UDP socket does not announce in multicast_tx is rejected."""
    socket = SocketUDP(
        name="someip_udp_socket_1",
        endpoint_address=MULTICAST_GROUP,
        port_no=30500,
        protocol="udp",
        multicast_tx=[],  # the group is missing here
        deployments=[_make_provider()],
    )

    with pytest.raises(ValidationError) as exc_info:
        _make_model(socket)
    assert_single_error(exc_info, "FLYNC-GEN-MAJ-CONS-171", "does not indicate by multicast_tx entry")


def test_provider_multicast_on_tcp_socket_rejected():
    """SOME/IP eventgroup multicast cannot be deployed on a TCP socket - TCP is point-to-point."""
    socket = SocketTCP(
        name="someip_tcp_socket_1",
        endpoint_address="10.0.20.2",
        port_no=30502,
        protocol="tcp",
        tcp_profile=1,
        multicast_tx=[MULTICAST_GROUP],
        deployments=[_make_provider()],
    )

    with pytest.raises(ValidationError) as exc_info:
        _make_model(socket)
    assert_single_error(exc_info, "FLYNC-GEN-MAJ-CONS-218", "SOME/IP eventgroup multicast requires a UDP socket")


# NOTE: no positive counterpart here. Both checks above fire before validate_multicast_paths, but a *valid*
# minimal model of this shape does not get that far: compute_path() needs the VLAN -> interface backref, which a
# programmatically built VirtualControllerInterface does not carry (the same gap the multicast-group tests hit,
# see tests/system_test/model/test_multicast_groups_negative.py). The accepted case is covered by the bundled
# example workspace (examples/flync_example/.../sockets/socket_someip.flync.yaml).
