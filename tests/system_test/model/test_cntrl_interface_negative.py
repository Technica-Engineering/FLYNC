import pytest
from pydantic import ValidationError

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
from flync.model.flync_4_ecu.phy import BASET1, MII
from flync.model.flync_4_ecu.port import ECUPort
from flync.model.flync_4_ecu.switch import Switch, SwitchConfig, SwitchPort
from flync.model.flync_4_metadata.metadata import BaseVersion, ECUMetadata, EmbeddedMetadata, SystemMetadata
from flync.model.flync_4_topology.ethernet_topology import EthernetTopology, FLYNCTopology
from flync.model.flync_model import FLYNCModel
from tests.error_assertions import assert_single_error

FLYNC_VERSION = "0.13.0"


def _make_version() -> BaseVersion:
    """Return the FLYNC version used by every test in this module."""
    return BaseVersion(version=FLYNC_VERSION)


def _make_embedded_metadata() -> EmbeddedMetadata:
    """Return the common embedded metadata used for controllers and switches in this module."""
    return EmbeddedMetadata(type="embedded", author="TestTeam", target_system="Device1", compatible_flync_version=_make_version())


def _make_ecu_metadata() -> ECUMetadata:
    """Return the common ECU metadata used by every test in this module."""
    return ECUMetadata(type="ecu", author="TestTeam", compatible_flync_version=_make_version())


def _make_system_metadata() -> SystemMetadata:
    """Return the common system metadata used by every test in this module."""
    return SystemMetadata(type="system", release=_make_version(), author="TestTeam", compatible_flync_version=_make_version())


def _make_empty_topology() -> FLYNCTopology:
    """Return an empty system topology usable by every test in this module."""
    return FLYNCTopology(ethernet_topology=EthernetTopology(connections=[]))


# Verify that a Controller without any communication interface is rejected.
def test_controller_without_interfaces_is_invalid():
    controller_metadata = _make_embedded_metadata()

    with pytest.raises(ValidationError) as exc_info:
        Controller(
            name="CTRL1",
            controller_metadata=controller_metadata,
            ethernet_interfaces=[],
            can_interfaces=[],
            lin_interfaces=[],
        )
    assert_single_error(exc_info, "FLYNC-ECU-MAJ-REQ-066", "must declare at least one interface")


# Verify that a Controller cannot contain two interfaces with the same name.
def test_duplicate_interface_name_within_controller_is_invalid():
    eth1 = EthernetInterface(
        name="eth0", interface_config=EthernetInterfaceConfig(virtual_interfaces=[VirtualControllerInterface(name="vif0", addresses=[])])
    )
    eth2 = EthernetInterface(
        name="eth0", interface_config=EthernetInterfaceConfig(virtual_interfaces=[VirtualControllerInterface(name="vif0", addresses=[])])
    )
    controller_metadata = _make_embedded_metadata()

    with pytest.raises(ValidationError) as exc_info:
        Controller(
            name="CTRL1",
            controller_metadata=controller_metadata,
            ethernet_interfaces=[eth1, eth2],
        )
    assert_single_error(exc_info, "FLYNC-CMN-MAJ-UNIQ-009", "Duplicates found in Controller Interfaces")


# Verify that a different interfaces inside the same Controller cannot have the same name because it creates ambiguous references.
@pytest.mark.xfail(reason="FLYNC-1339")
def test_duplicate_interface_name_across_interface_types_is_invalid():
    eth = EthernetInterface(
        name="iface0", interface_config=EthernetInterfaceConfig(virtual_interfaces=[VirtualControllerInterface(name="vif0", addresses=[])])
    )
    can = CANInterface(name="iface0", bus_ref="can_bus")
    controller_metadata = _make_embedded_metadata()

    with pytest.raises(ValidationError):
        Controller(
            name="CTRL1",
            controller_metadata=controller_metadata,
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
    controller_metadata = _make_embedded_metadata()

    with pytest.raises(ValidationError):
        Controller(
            name="CTRL1",
            controller_metadata=controller_metadata,
            ethernet_interfaces=[eth1, eth2],
        )


# Verify that a physical EthernetInterface without a MAC address is rejected.
@pytest.mark.xfail(reason="FLYNC-1341")
def test_physical_ethernet_interface_without_mac_address_is_invalid():
    interface_config = EthernetInterfaceConfig(
        # MAC address intentionally omitted
        virtual_interfaces=[VirtualControllerInterface(name="vif0", addresses=[])]
    )

    with pytest.raises(ValidationError):
        EthernetInterface(name="eth0", interface_config=interface_config)


# Verify that a LIN Master cannot use a LIN bus without a schedule table.
@pytest.mark.xfail(reason="FLYNC-1342")
def test_lin_master_without_schedule_table_is_invalid():

    lin_bus = LINBus(name="lin_bus_1", lin_protocol_version="2.0", lin_language_version="2.0", baud_rate=19200, schedule_tables=[])

    lin_master = LINMasterInterface(name="lin_master_1", bus_ref="lin_bus_1", lin_protocol="2.0", p2_min=10, st_min=10)

    controller = Controller(
        name="CTRL1",
        controller_metadata=_make_embedded_metadata(),
        lin_interfaces=[lin_master],
    )

    ecu = ECU(
        name="ECU1",
        controllers=[controller],
        topology=InternalTopology(),
        ecu_metadata=_make_ecu_metadata(),
    )
    general = FLYNCCommunicationConfig(channels=FLYNCChannelConfig(lin_buses=[lin_bus]))
    topology = _make_empty_topology()
    metadata = _make_system_metadata()

    with pytest.raises(ValidationError):
        FLYNCModel(ecus=[ecu], general=general, topology=topology, metadata=metadata)


# Verify that a LIN Slave cannot use a LIN bus with a schedule table. Scheduling is handled by the LIN Master only.
@pytest.mark.xfail(reason="FLYNC-1343")
def test_lin_slave_with_schedule_table_is_invalid():

    schedule_table = LINScheduleTable(name="schedule_table_1", entries=[])

    lin_bus = LINBus(name="lin_bus_1", lin_protocol_version="2.0", lin_language_version="2.0", baud_rate=19200, schedule_tables=[schedule_table])

    lin_slave = LINSlaveInterface(name="lin_slave_1", bus_ref="lin_bus_1", lin_protocol="2.0", configured_nad=1, initial_nad=1)

    controller = Controller(
        name="CTRL1",
        controller_metadata=_make_embedded_metadata(),
        lin_interfaces=[lin_slave],
    )

    ecu = ECU(
        name="ECU1",
        controllers=[controller],
        topology=InternalTopology(),
        ecu_metadata=_make_ecu_metadata(),
    )
    general = FLYNCCommunicationConfig(channels=FLYNCChannelConfig(lin_buses=[lin_bus]))
    topology = _make_empty_topology()
    metadata = _make_system_metadata()

    with pytest.raises(ValidationError):
        FLYNCModel(ecus=[ecu], general=general, topology=topology, metadata=metadata)


# Verify that an Ethernet switch cannot connect to a CAN interface. Ethernet switches support Ethernet interfaces only.
def test_ethernet_switch_connected_to_can_interface_is_invalid():

    can_iface = CANInterface(name="can_iface", bus_ref="can_bus")

    virtual_switch = VirtualSwitch(name="vswitch_1", vlans=[], ports=[VirtualSwitchPort(name="invalid_vswitch", node_connected="can_iface")])
    controller_metadata = _make_embedded_metadata()

    with pytest.raises(ValidationError) as exc_info:
        Controller(
            name="CTRL1",
            controller_metadata=controller_metadata,
            can_interfaces=[can_iface],
            virtual_switch=virtual_switch,
        )
    assert_single_error(exc_info, "FLYNC-ECU-MIN-REF-067", "interface or compute node")


# Verify that an Ethernet switch cannot connect to a LIN interface. Ethernet switches support Ethernet interfaces only and cannot connect to LIN interfaces.
def test_ethernet_switch_connected_to_lin_interface_is_invalid():

    lin_iface = LINMasterInterface(name="lin_master_iface", bus_ref="lin_bus", lin_protocol="2.0", p2_min=10, st_min=10)

    virtual_switch = VirtualSwitch(name="vswitch_1", vlans=[], ports=[VirtualSwitchPort(name="invalid_vswitch", node_connected="lin_master_iface")])
    controller_metadata = _make_embedded_metadata()

    with pytest.raises(ValidationError) as exc_info:
        Controller(
            name="CTRL1",
            controller_metadata=controller_metadata,
            lin_interfaces=[lin_iface],
            virtual_switch=virtual_switch,
        )
    assert_single_error(exc_info, "FLYNC-ECU-MIN-REF-067", "interface or compute node")


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
        controller_metadata=_make_embedded_metadata(),
        ethernet_interfaces=[eth_iface],
        virtual_switch=virtual_switch,
    )

    switch = Switch(
        name="switch1",
        switch_config=SwitchConfig(
            ports=[
                SwitchPort(name="port1", mii_config=MII(speed=100, mode="phy"), silicon_port_no=1, default_vlan_id=1),
                SwitchPort(name="port2", mii_config=MII(speed=100, mode="phy"), silicon_port_no=2, default_vlan_id=1),
            ],
            vlans=[],
            meta=_make_embedded_metadata(),
        ),
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
        ecu_metadata=_make_ecu_metadata(),
    )
    topology = _make_empty_topology()
    metadata = _make_system_metadata()

    with pytest.raises(ValidationError):
        FLYNCModel(ecus=[ecu], topology=topology, metadata=metadata)


# Verify that duplicate VLAN IDs inside the same Ethernet interface are rejected.
def test_ethernet_vlan_conflict_is_invalid():
    mii_config = MII(speed=100, mode="mac")
    vif0 = VirtualControllerInterface(name="vif0", vlanid=10, addresses=[])
    vif1 = VirtualControllerInterface(name="vif1", vlanid=10, addresses=[])

    # The duplicate-VLAN check lives on EthernetInterfaceConfig, so that is the call under test.
    with pytest.raises(ValidationError) as exc_info:
        EthernetInterfaceConfig(mii_config=mii_config, virtual_interfaces=[vif0, vif1])
    assert_single_error(exc_info, "FLYNC-CMN-MAJ-UNIQ-009", "Duplicates found in VLAN IDs of virtual Controller Interface")


# Verify that topology loading fails when a referenced ControllerInterface does not exist.
def test_unresolved_controller_interface_reference_in_topology_is_invalid():

    switch = Switch(
        name="switch1",
        switch_config=SwitchConfig(
            ports=[SwitchPort(name="port1", silicon_port_no=1, default_vlan_id=1, mii_config=MII(speed=100, mode="phy"))],
            vlans=[],
            meta=_make_embedded_metadata(),
        ),
    )

    eth_iface = EthernetInterface(
        name="eth0",
        interface_config=EthernetInterfaceConfig(
            mii_config=MII(speed=100, mode="mac"), virtual_interfaces=[VirtualControllerInterface(name="vif0", addresses=[])]
        ),
    )

    controller = Controller(
        name="CTRL1",
        controller_metadata=_make_embedded_metadata(),
        ethernet_interfaces=[eth_iface],
    )
    internal_topology = InternalTopology(
        connections=[
            SwitchPortToControllerInterface(
                id="conn1", switch="switch1", switch_port="port1", controller_interface="eth_missing", controller="CTRL1"
            )
        ]
    )
    ecu_metadata = _make_ecu_metadata()
    port = ECUPort(name="ecu_port1", mdi_config=BASET1())

    with pytest.raises(ValidationError) as exc_info:
        ECU(name="ECU1", controllers=[controller], switches=[switch], ports=[port], topology=internal_topology, ecu_metadata=ecu_metadata)
    assert_single_error(exc_info, "FLYNC-ECU-MAJ-REF-078", "was not found or was not validated")
