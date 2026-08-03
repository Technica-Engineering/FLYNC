import pytest
from pydantic import ValidationError

from flync.core.datatypes.macaddress import FLYNCMacAddress
from flync.model.flync_4_bus.lin_bus import LINBus, LINScheduleTable
from flync.model.flync_4_communication.flync_channels import FLYNCChannelConfig
from flync.model.flync_4_communication.flync_communication import FLYNCCommunicationConfig
from flync.model.flync_4_ecu.can_interface import CANInterface
from flync.model.flync_4_ecu.controller import (
    Controller,
    EthernetInterface,
    EthernetInterfaceConfig,
    VirtualControllerInterface,
    VirtualSwitch,
    VirtualSwitchPort,
)
from flync.model.flync_4_ecu.ecu import ECU
from flync.model.flync_4_ecu.internal_topology import InternalTopology, SwitchPortToControllerInterface
from flync.model.flync_4_ecu.lin_interface import LINMasterInterface, LINSlaveInterface
from flync.model.flync_4_ecu.phy import MII
from flync.model.flync_4_ecu.sockets import Socket
from flync.model.flync_4_ecu.switch import Switch, SwitchPort
from flync.model.flync_4_metadata.metadata import BaseVersion, ECUMetadata, EmbeddedMetadata, SystemMetadata
from flync.model.flync_4_topology.system_topology import ExternalConnection, FLYNCTopology, SystemTopology
from flync.model.flync_model import FLYNCModel


# Verify that a Controller without any communication interface is rejected.
def test_controller_without_interfaces_is_invalid():

    with pytest.raises(ValidationError):
        Controller(
            name="CTRL1",
            controller_metadata=EmbeddedMetadata(
                type="embedded", author="TestTeam", target_system="Device1", compatible_flync_version=BaseVersion(version="0.13.0")
            ),
            ethernet_interfaces=[],
            can_interfaces=[],
            lin_interfaces=[],
        )


# Verify that a Controller cannot contain two interfaces with the same name.
def test_duplicate_interface_name_within_controller_is_invalid():
    eth1 = EthernetInterface(
        name="eth0", interface_config=EthernetInterfaceConfig(virtual_interfaces=[VirtualControllerInterface(name="vif0", addresses=[])])
    )
    eth2 = EthernetInterface(
        name="eth0", interface_config=EthernetInterfaceConfig(virtual_interfaces=[VirtualControllerInterface(name="vif0", addresses=[])])
    )

    with pytest.raises(ValidationError):
        Controller(
            name="CTRL1",
            controller_metadata=EmbeddedMetadata(
                type="embedded", author="TestTeam", target_system="Device1", compatible_flync_version=BaseVersion(version="0.13.0")
            ),
            ethernet_interfaces=[eth1, eth2],
        )


# Verify that a different interfaces inside the same Controller cannot have the same name because it creates ambiguous references.
@pytest.mark.xfail(reason="FLYNC-1339")
def test_duplicate_interface_name_across_interface_types_is_invalid():
    eth = EthernetInterface(
        name="iface0", interface_config=EthernetInterfaceConfig(virtual_interfaces=[VirtualControllerInterface(name="vif0", addresses=[])])
    )
    can = CANInterface(name="iface0", bus_ref="can_bus")

    with pytest.raises(ValidationError):
        Controller(
            name="CTRL1",
            controller_metadata=EmbeddedMetadata(
                type="embedded", author="TestTeam", target_system="Device1", compatible_flync_version=BaseVersion(version="0.13.0")
            ),
            ethernet_interfaces=[eth],
            can_interfaces=[can],
        )


# Verify that two Ethernet interfaces inside the same Controller cannot have the same MAC address.
@pytest.mark.xfail(reason="FLYNC-1340")
def test_duplicate_ethernet_mac_address_is_invalid():
    eth1 = EthernetInterface(
        name="eth0",
        interface_config=EthernetInterfaceConfig(
            mac_address="00:11:22:33:44:55", virtual_interfaces=[VirtualControllerInterface(name="vif0", addresses=[])]
        ),
    )

    eth2 = EthernetInterface(
        name="eth1",
        interface_config=EthernetInterfaceConfig(
            mac_address="00:11:22:33:44:55", virtual_interfaces=[VirtualControllerInterface(name="vif1", addresses=[])]
        ),
    )

    with pytest.raises(ValidationError):
        Controller(
            name="CTRL1",
            controller_metadata=EmbeddedMetadata(
                type="embedded", author="TestTeam", target_system="Device1", compatible_flync_version=BaseVersion(version="0.13.0")
            ),
            ethernet_interfaces=[eth1, eth2],
        )


# Verify that a physical EthernetInterface without a MAC address is rejected.
@pytest.mark.xfail(reason="FLYNC-1341")
def test_physical_ethernet_interface_without_mac_address_is_invalid():
    with pytest.raises(ValidationError):
        EthernetInterface(
            name="eth0",
            interface_config=EthernetInterfaceConfig(
                # MAC address intentionally omitted
                virtual_interfaces=[VirtualControllerInterface(name="vif0", addresses=[])]
            ),
        )


# Verify that a LIN Master cannot use a LIN bus without a schedule table.
@pytest.mark.xfail(reason="FLYNC-1342")
def test_lin_master_without_schedule_table_is_invalid():

    lin_bus = LINBus(name="lin_bus_1", lin_protocol_version="2.0", lin_language_version="2.0", baud_rate=19200, schedule_tables=[])

    lin_master = LINMasterInterface(name="lin_master_1", bus_ref="lin_bus_1", lin_protocol="2.0", p2_min=10, st_min=10)

    controller = Controller(
        name="CTRL1",
        controller_metadata=EmbeddedMetadata(
            type="embedded", author="TestTeam", target_system="Device1", compatible_flync_version=BaseVersion(version="0.13.0")
        ),
        lin_interfaces=[lin_master],
    )

    ecu = ECU(
        name="ECU1",
        controllers=[controller],
        topology=InternalTopology(),
        ecu_metadata=ECUMetadata(type="ecu", author="TestTeam", compatible_flync_version=BaseVersion(version="0.13.0")),
    )

    with pytest.raises(ValidationError):
        FLYNCModel(
            ecus=[ecu],
            general=FLYNCCommunicationConfig(channels=FLYNCChannelConfig(lin_buses=[lin_bus])),
            topology=FLYNCTopology(system_topology=SystemTopology(connections=[])),
            metadata=SystemMetadata(
                type="system", release=BaseVersion(version="0.13.0"), author="TestTeam", compatible_flync_version=BaseVersion(version="0.13.0")
            ),
        )


# Verify that a LIN Slave cannot use a LIN bus with a schedule table. Scheduling is handled by the LIN Master only.
@pytest.mark.xfail(reason="FLYNC-1343")
def test_lin_slave_with_schedule_table_is_invalid():

    schedule_table = LINScheduleTable(name="schedule_table_1", entries=[])

    lin_bus = LINBus(name="lin_bus_1", lin_protocol_version="2.0", lin_language_version="2.0", baud_rate=19200, schedule_tables=[schedule_table])

    lin_slave = LINSlaveInterface(name="lin_slave_1", bus_ref="lin_bus_1", lin_protocol="2.0", configured_nad=1, initial_nad=1)

    controller = Controller(
        name="CTRL1",
        controller_metadata=EmbeddedMetadata(
            type="embedded", author="TestTeam", target_system="Device1", compatible_flync_version=BaseVersion(version="0.13.0")
        ),
        lin_interfaces=[lin_slave],
    )

    ecu = ECU(
        name="ECU1",
        controllers=[controller],
        topology=InternalTopology(),
        ecu_metadata=ECUMetadata(type="ecu", author="TestTeam", compatible_flync_version=BaseVersion(version="0.13.0")),
    )

    with pytest.raises(ValidationError):
        FLYNCModel(
            ecus=[ecu],
            general=FLYNCCommunicationConfig(channels=FLYNCChannelConfig(lin_buses=[lin_bus])),
            topology=FLYNCTopology(system_topology=SystemTopology(connections=[])),
            metadata=SystemMetadata(
                type="system", release=BaseVersion(version="0.13.0"), author="TestTeam", compatible_flync_version=BaseVersion(version="0.13.0")
            ),
        )


# Verify that an Ethernet switch cannot connect to a CAN interface. Ethernet switches support Ethernet interfaces only.
def test_ethernet_switch_connected_to_can_interface_is_invalid():

    can_iface = CANInterface(name="can_iface", bus_ref="can_bus")

    virtual_switch = VirtualSwitch(name="vswitch_1", vlans=[], ports=[VirtualSwitchPort(name="invalid_vswitch", node_connected="can_iface")])

    with pytest.raises(ValidationError):
        Controller(
            name="CTRL1",
            controller_metadata=EmbeddedMetadata(
                type="embedded", author="TestTeam", target_system="Device1", compatible_flync_version=BaseVersion(version="0.13.0")
            ),
            can_interfaces=[can_iface],
            virtual_switch=virtual_switch,
        )


# Verify that an Ethernet switch cannot connect to a LIN interface. Ethernet switches support Ethernet interfaces only and cannot connect to LIN interfaces.
def test_ethernet_switch_connected_to_lin_interface_is_invalid():

    lin_iface = LINMasterInterface(name="lin_master_iface", bus_ref="lin_bus", lin_protocol="2.0", p2_min=10, st_min=10)

    virtual_switch = VirtualSwitch(name="vswitch_1", vlans=[], ports=[VirtualSwitchPort(name="invalid_vswitch", node_connected="lin_master_iface")])

    with pytest.raises(ValidationError):
        Controller(
            name="CTRL1",
            controller_metadata=EmbeddedMetadata(
                type="embedded", author="TestTeam", target_system="Device1", compatible_flync_version=BaseVersion(version="0.13.0")
            ),
            lin_interfaces=[lin_iface],
            virtual_switch=virtual_switch,
        )


# Verify that the same physical ControllerInterface cannot be connected multiple times inside ECU topology.
@pytest.mark.xfail(reason="FLYNC-1344")
def test_same_physical_interface_connected_multiple_times_is_invalid():

    eth_iface = EthernetInterface(
        name="eth0",
        interface_config=EthernetInterfaceConfig(
            mii_config=MII(speed=100, mode="mac"), virtual_interfaces=[VirtualControllerInterface(name="vif0", addresses=[])]
        ),
    )

    virtual_switch = VirtualSwitch(
        name="switch1",
        vlans=[],
        ports=[VirtualSwitchPort(name="port1", node_connected="eth0"), VirtualSwitchPort(name="port2", node_connected="eth0")],
    )

    internal_connections = InternalTopology(
        connections=[
            SwitchPortToControllerInterface(id="conn1", switch_port="port1", controller_interface="eth0", switch="switch1", controller="CTRL1"),
            SwitchPortToControllerInterface(id="conn2", switch_port="port2", controller_interface="eth0", switch="switch1", controller="CTRL1"),
        ]
    )

    controller = Controller(
        name="CTRL1",
        controller_metadata=EmbeddedMetadata(
            type="embedded", author="TestTeam", target_system="Device1", compatible_flync_version=BaseVersion(version="0.13.0")
        ),
        ethernet_interfaces=[eth_iface],
        virtual_switch=virtual_switch,
    )

    switch = Switch(
        name="switch1",
        ports=[
            SwitchPort(name="port1", mii_config=MII(speed=100, mode="phy"), silicon_port_no=1, default_vlan_id=1),
            SwitchPort(name="port2", mii_config=MII(speed=100, mode="phy"), silicon_port_no=2, default_vlan_id=1),
        ],
        vlans=[],
        meta=EmbeddedMetadata(type="embedded", author="TestTeam", target_system="Device1", compatible_flync_version=BaseVersion(version="0.13.0")),
    )

    ecu = ECU(
        name="ECU1",
        controllers=[controller],
        switches=[switch],
        topology=InternalTopology(
            connections=[
                SwitchPortToControllerInterface(id="conn1", switch="switch1", switch_port="port1", controller_interface="eth0", controller="CTRL1"),
                SwitchPortToControllerInterface(id="conn2", switch="switch1", switch_port="port2", controller_interface="eth0", controller="CTRL1"),
            ]
        ),
        ecu_metadata=ECUMetadata(type="ecu", author="TestTeam", compatible_flync_version=BaseVersion(version="0.13.0")),
    )

    with pytest.raises(ValidationError):
        FLYNCModel(
            ecus=[ecu],
            topology=FLYNCTopology(system_topology=SystemTopology(connections=[])),
            metadata=SystemMetadata(
                type="system", release=BaseVersion(version="0.13.0"), author="TestTeam", compatible_flync_version=BaseVersion(version="0.13.0")
            ),
        )


# Verify that duplicate VLAN IDs inside the same Ethernet interface are rejected.
def test_ethernet_vlan_conflict_is_invalid():

    with pytest.raises(ValidationError):
        EthernetInterface(
            name="eth0",
            interface_config=EthernetInterfaceConfig(
                mii_config=MII(speed=100, mode="mac"),
                virtual_interfaces=[
                    VirtualControllerInterface(name="vif0", vlanid=10, addresses=[]),
                    VirtualControllerInterface(name="vif1", vlanid=10, addresses=[]),
                ],
            ),
        )


# Verify that topology loading fails when a referenced ControllerInterface does not exist.
def test_unresolved_controller_interface_reference_in_topology_is_invalid():

    switch = Switch(
        name="switch1",
        ports=[SwitchPort(name="port1", silicon_port_no=1, default_vlan_id=1, mii_config=MII(speed=100, mode="phy"))],
        vlans=[],
        meta=EmbeddedMetadata(type="embedded", author="TestTeam", target_system="Device1", compatible_flync_version=BaseVersion(version="0.13.0")),
    )

    eth_iface = EthernetInterface(
        name="eth0",
        interface_config=EthernetInterfaceConfig(
            mii_config=MII(speed=100, mode="mac"), virtual_interfaces=[VirtualControllerInterface(name="vif0", addresses=[])]
        ),
    )

    controller = Controller(
        name="CTRL1",
        controller_metadata=EmbeddedMetadata(
            type="embedded", author="TestTeam", target_system="Device1", compatible_flync_version=BaseVersion(version="0.13.0")
        ),
        ethernet_interfaces=[eth_iface],
    )

    with pytest.raises(ValidationError):
        ECU(
            name="ECU1",
            controllers=[controller],
            switches=[switch],
            topology=InternalTopology(
                connections=[
                    SwitchPortToControllerInterface(
                        id="conn1", switch="switch1", switch_port="port1", controller_interface="eth_missing", controller="CTRL1"
                    )
                ]
            ),
            ecu_metadata=ECUMetadata(type="ecu", author="TestTeam", compatible_flync_version=BaseVersion(version="0.13.0")),
        )
