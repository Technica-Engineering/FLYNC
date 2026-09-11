"""Testing a multidrop segment."""

from pydantic import IPvAnyAddress

from flync.model import FLYNCModel
from flync.model.flync_4_ecu.controller import (
    Controller,
    EthernetInterface,
    EthernetInterfaceConfig,
    VirtualControllerInterface,
)
from flync.model.flync_4_ecu.ecu import ECU
from flync.model.flync_4_ecu.internal_topology import ECUPortToControllerInterface, InternalConnectionUnion, InternalTopology
from flync.model.flync_4_ecu.phy import BASET1S
from flync.model.flync_4_ecu.port import ECUPort
from flync.model.flync_4_ecu.sockets import IPv4AddressEndpoint
from flync.model.flync_4_metadata import EmbeddedMetadata
from flync.model.flync_4_metadata.metadata import BaseVersion, ECUMetadata, SystemMetadata
from flync.model.flync_4_topology import FLYNCTopology
from flync.model.flync_4_topology.ethernet_multidrop import EthernetMultidropConnection
from flync.model.flync_4_topology.ethernet_topology import EthernetTopology

SEGMENT = "RearLampSegment"

_SYSTEM_VERSION = BaseVersion(version_schema="semver", version="0.11.0")

# (ecu name, port name, MAC, IP, transmit opportunity)
_NODES = [
    ("rear_lamp_left", "rear_lamp_left_p1", "00:00:5e:00:53:01", "192.0.2.1", 1),
    ("rear_lamp_center", "rear_lamp_center_p1", "00:00:5e:00:53:02", "192.0.2.2", 2),
    ("rear_lamp_right", "rear_lamp_right_p1", "00:00:5e:00:53:03", "192.0.2.3", 3),
    ("zonal_platform1", "z1_p2", "00:00:5e:00:53:04", "192.0.2.4", 0),
]


def _ecu(name, port_name, mac, ip, _opportunity):
    """One ECU with a single multidrop port wired to a lone controller interface."""
    embedded = EmbeddedMetadata(type="embedded", author="test", compatible_flync_version=_SYSTEM_VERSION, target_system="t1s")
    addr = IPv4AddressEndpoint(address=IPvAnyAddress(ip), ipv4netmask=IPvAnyAddress("192.0.0.0"))
    vif = VirtualControllerInterface(name=f"{name}_vif", vlanid=55, addresses=[addr])
    iface_config = EthernetInterfaceConfig(mac_address=mac, virtual_interfaces=[vif])
    iface = EthernetInterface(name="eth_iface1", interface_config=iface_config)
    controller = Controller(name="ctrl1", controller_metadata=embedded, ethernet_interfaces=[iface])

    port = ECUPort(name=port_name, mdi_config=BASET1S(speed=10, duplex="half", topology="multidrop"))
    connection = ECUPortToControllerInterface(
        type="ecu_port_to_controller_interface",
        id=f"{name}_int",
        ecu_port=port_name,
        controller_interface="eth_iface1",
    )
    internal = InternalTopology(connections=[InternalConnectionUnion(root=connection)])
    return ECU(
        name=name,
        ports=[port],
        controllers=[controller],
        topology=internal,
        ecu_metadata=ECUMetadata(type="ecu", author="test", compatible_flync_version=_SYSTEM_VERSION),
    )


def build_multidrop_model():
    """The rear-lamp segment as one multidrop connection over four ECUs."""
    ecus = [_ecu(*node) for node in _NODES]
    segment = EthernetMultidropConnection(
        id=SEGMENT,
        plca={"transmit_opportunity_count": 4, "to_timer": 32},
        nodes=[{"ecu_port": port, "node_id": opportunity} for _, port, _, _, opportunity in _NODES],
    )
    return FLYNCModel(
        ecus=ecus,
        topology=FLYNCTopology(ethernet_topology=EthernetTopology(connections=[segment])),
        metadata=SystemMetadata(author="test", compatible_flync_version=_SYSTEM_VERSION, release=_SYSTEM_VERSION, oem="test", platform="t1s"),
        communication={"tcp_profiles": []},
    )
