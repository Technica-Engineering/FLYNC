import pytest
from pydantic import ValidationError

from flync.core.datatypes.macaddress import MacAddress
from flync.model.flync_4_ecu import *
from flync.model.flync_4_ecu.controller import *
from flync.model.flync_4_ecu.internal_topology import *
from flync.model.flync_4_ecu.switch import SwitchConfig
from flync.model.flync_4_metadata import *
from flync.model.flync_4_topology import *
from flync.model.flync_model import FLYNCModel
from tests.error_assertions import assert_single_error


def _system_metadata_setup():
    system_version = BaseVersion(version_schema="semver", version="0.11.0")
    system_metadata = SystemMetadata(
        author="System_Architect",
        compatible_flync_version=system_version,
        release=system_version,
        oem="OEM_example",
        platform="Arch1",
    )
    embedded_metadata = EmbeddedMetadata(
        type="embedded",
        author="test_team",
        compatible_flync_version=system_version,
        target_system="my_system",
    )
    ecu_metadata = ECUMetadata(type="ecu", author="test_team", compatible_flync_version=system_version)
    return system_metadata, embedded_metadata, ecu_metadata


def _ethernet_interface(name, mac_address, addresses=None):
    """Build a NEW-API EthernetInterface with one valid virtual interface and a config that owns a MAC."""
    if addresses is None:
        addresses = [IPv4AddressEndpoint(address=IPvAnyAddress("192.0.2.1"), ipv4netmask=IPvAnyAddress("192.0.0.0"))]
    virtual_iface = VirtualControllerInterface(name="virtual", vlanid=55, addresses=addresses)
    interface_config = EthernetInterfaceConfig(mac_address=MacAddress(mac_address), virtual_interfaces=[virtual_iface])
    return EthernetInterface(name=name, interface_config=interface_config)


def _controller(embedded_metadata, name, iface_name, mac_address):
    return Controller(
        name=name,
        controller_metadata=embedded_metadata,
        ethernet_interfaces=[_ethernet_interface(iface_name, mac_address)],
    )


def invalid_interface_missing():
    """
    Purpose:
        Test a connection to a non-existent controller interface.
    Schema:
         +-------------------------------+
         |            ECU1               |
         | [ECU port1] ↔ [UNKNOWN_IFACE] |
         +-------------------------------+
    Destination interface does not exist
    """
    system_metadata, embedded_metadata, ecu_metadata = _system_metadata_setup()

    # --- Controller ---
    controller_ecu1 = _controller(embedded_metadata, "controller_ecu1", "control1", "00:00:5e:00:53:01")

    # --- ECU Port Configuration ---
    port_ecu1 = ECUPort(
        name="port1",
        mdi_config=BASET1(mode="base_t1", speed=100, role="master"),
        mii_config=MII(type="mii", mode="mac"),
    )

    # --- INVALID CONNECTION (interface does not exist) ---
    ecu_to_controller_cnx1 = ECUPortToControllerInterface(
        type="ecu_port_to_controller_interface",
        id="1",
        ecu_port="port1",
        controller_interface="UNKNOWN_IFACE",
    )

    # --- Internal links ---
    internal_topology_ecu1 = InternalTopology(connections=[InternalConnectionUnion(root=ecu_to_controller_cnx1)])

    # --- Create the ECU ---
    ecu1 = ECU(
        name="ecu1",
        ports=[port_ecu1],
        controllers=[controller_ecu1],
        topology=internal_topology_ecu1,
        ecu_metadata=ecu_metadata,
    )

    # --- External links ---
    empty_topology = FLYNCTopology(ethernet_topology=EthernetTopology(connections=[]))

    # --- Full FLYNC Model ---
    flync_model = FLYNCModel(ecus=[ecu1], topology=empty_topology, metadata=system_metadata)

    return flync_model


def invalid_ecu_no_port():
    """
    Purpose:
        Test an ECU with no ports defined.
    Schema:
         +--------------------+
         |        ECU1        |
         |     (NO PORT)      |
         |    [Controller1]   |
         +--------------------+
    ECU violates required port rule
    """
    system_metadata, embedded_metadata, ecu_metadata = _system_metadata_setup()

    # --- Controller ---
    controller_ecu1 = _controller(embedded_metadata, "controller_ecu1", "control1", "00:00:5e:00:53:01")

    # --- Create the ECU (NO ECU PORT DEFINED) ---
    ecu1 = ECU(
        name="ecu1",
        ports=[],
        controllers=[controller_ecu1],
        topology=InternalTopology(connections=[]),
        ecu_metadata=ecu_metadata,
    )

    # --- External links ---
    empty_topology = FLYNCTopology(ethernet_topology=EthernetTopology(connections=[]))

    # --- Full FLYNC Model ---
    flync_model = FLYNCModel(ecus=[ecu1], topology=empty_topology, metadata=system_metadata)

    return flync_model


def invalid_controller_reference():
    """
    Purpose:
        Test a connection that references a controller which is not declared in the ECU.
    Schema:
         +-----------------------------+
         |            ECU1             |
         | [ECU port1] ↔ [controller:] |
         |       (controller missing)  |
         +-----------------------------+
    Referenced controller does not exist
    """
    system_metadata, embedded_metadata, ecu_metadata = _system_metadata_setup()

    # --- Controller ---
    controller_ecu1 = _controller(embedded_metadata, "controller_ecu1", "control1", "00:00:5e:00:53:01")

    # --- ECU Port Configuration ---
    port_ecu1 = ECUPort(
        name="port1",
        mdi_config=BASET1(mode="base_t1", speed=100, role="master"),
        mii_config=MII(type="mii", mode="mac"),
    )

    # --- INVALID CONNECTION (controller does not exist) ---
    ecu_to_controller_cnx1 = ECUPortToControllerInterface(
        type="ecu_port_to_controller_interface",
        id="1",
        ecu_port="port1",
        controller_interface="control1",
        controller="UNKNOWN_CONTROLLER",
    )

    # --- Internal links ---
    internal_topology_ecu1 = InternalTopology(connections=[InternalConnectionUnion(root=ecu_to_controller_cnx1)])

    # --- Create the ECU ---
    ecu1 = ECU(
        name="ecu1",
        ports=[port_ecu1],
        controllers=[controller_ecu1],
        topology=internal_topology_ecu1,
        ecu_metadata=ecu_metadata,
    )

    # --- External links ---
    empty_topology = FLYNCTopology(ethernet_topology=EthernetTopology(connections=[]))

    # --- Full FLYNC Model ---
    flync_model = FLYNCModel(ecus=[ecu1], topology=empty_topology, metadata=system_metadata)

    return flync_model


def invalid_wrong_connection_type():
    """
    Purpose:
        Test a port connected to a switch port that does not exist (wrong component type in use).
    Schema:
        +------------------------------------------------------+
        |                     ECU1                             |
        | [ECU port1] ↔ [SwitchPort1] (no such switch port)    |
        +------------------------------------------------------+
    Referenced switch port does not exist
    """
    system_metadata, embedded_metadata, ecu_metadata = _system_metadata_setup()

    # --- Controller ---
    controller_ecu1 = _controller(embedded_metadata, "controller_ecu1", "control1", "00:00:5e:00:53:01")

    # --- ECU Port Configuration ---
    port_ecu1 = ECUPort(
        name="port1",
        mdi_config=BASET1(mode="base_t1", speed=100, role="master"),
        mii_config=MII(type="mii", mode="mac"),
    )

    # --- WRONG CONNECTION (no switch port exists in the ECU) ---
    ecu_to_switch_cnx = ECUPortToSwitchPort(
        type="ecu_port_to_switch_port",
        id="1",
        ecu_port="port1",
        switch_port="missing_sw_port",
    )

    # --- Internal links ---
    internal_topology_ecu1 = InternalTopology(connections=[InternalConnectionUnion(root=ecu_to_switch_cnx)])

    # --- Create the ECU ---
    ecu1 = ECU(
        name="ecu1",
        ports=[port_ecu1],
        controllers=[controller_ecu1],
        topology=internal_topology_ecu1,
        ecu_metadata=ecu_metadata,
    )

    # --- External links ---
    empty_topology = FLYNCTopology(ethernet_topology=EthernetTopology(connections=[]))

    # --- Full FLYNC Model ---
    flync_model = FLYNCModel(ecus=[ecu1], topology=empty_topology, metadata=system_metadata)

    return flync_model


def invalid_undeclared_switch():
    """
    Purpose:
        Test a connection that references a switch which is not declared in the ECU.
    Schema:
         +----------------------------------------+
         |                      ECU1              |
         | [ECU port1] ↔ [Switch1] (not declared) |
         +----------------------------------------+
    Switch does not exist in ECU
    """
    system_metadata, embedded_metadata, ecu_metadata = _system_metadata_setup()

    # --- Controller ---
    controller_ecu1 = _controller(embedded_metadata, "controller_ecu1", "control1", "00:00:5e:00:53:01")

    # --- ECU Port Configuration ---
    port_ecu1 = ECUPort(name="port1")

    # --- INVALID connection (undeclared switch) ---
    invalid_cnx = ECUPortToSwitchPort(
        type="ecu_port_to_switch_port",
        id="2",
        ecu_port="port1",
        switch_port="sw1",
        switch="UNKNOWN_SWITCH",
    )

    # --- Internal links ---
    internal_topology_ecu1 = InternalTopology(connections=[InternalConnectionUnion(root=invalid_cnx)])

    # --- Create the ECU ---
    ecu1 = ECU(
        name="ecu1",
        ports=[port_ecu1],
        controllers=[controller_ecu1],
        topology=internal_topology_ecu1,
        ecu_metadata=ecu_metadata,
    )

    # --- External links ---
    empty_topology = FLYNCTopology(ethernet_topology=EthernetTopology(connections=[]))

    # --- Full FLYNC Model ---
    flync_model = FLYNCModel(ecus=[ecu1], topology=empty_topology, metadata=system_metadata)

    return flync_model


def invalid_loop_connection():
    """
    Purpose:
        Test an invalid loop inside the ECU (switch port connected to itself).
    Schema:
         +--------------------------------------+
         |                   ECU1               |
         | [Switch1.p1] ↔ [Switch1.p1] (loop)   |
         +--------------------------------------+
    Switch port connected to itself
    """
    system_metadata, embedded_metadata, ecu_metadata = _system_metadata_setup()

    # --- Controller ---
    controller_ecu1 = _controller(embedded_metadata, "controller_ecu1", "control1", "00:00:5e:00:53:01")

    # --- Switch Port ---
    switch_port1 = SwitchPort(
        name="sw_port1",
        silicon_port_no=1,
        default_vlan_id=1,
        mii_config=MII(type="mii", speed=100, mode="phy"),
    )

    # --- Switch ---
    switch1 = Switch(name="switch1", switch_config=SwitchConfig(ports=[switch_port1], vlans=[], meta=embedded_metadata))

    # --- ECU Port Configuration ---
    port_ecu1 = ECUPort(name="port1")

    # --- LOOP connection (switch port ↔ same switch port) ---
    loop_cnx = SwitchPortToSwitchPort(
        type="switch_to_switch_same_ecu",
        id="loop",
        switch_port="sw_port1",
        switch2_port="sw_port1",
    )

    # --- Internal links ---
    internal_topology_ecu1 = InternalTopology(connections=[InternalConnectionUnion(root=loop_cnx)])

    # --- Create the ECU ---
    ecu1 = ECU(
        name="ecu1",
        ports=[port_ecu1],
        controllers=[controller_ecu1],
        switches=[switch1],
        topology=internal_topology_ecu1,
        ecu_metadata=ecu_metadata,
    )

    # --- External links ---
    empty_topology = FLYNCTopology(ethernet_topology=EthernetTopology(connections=[]))

    # --- Full FLYNC Model ---
    flync_model = FLYNCModel(ecus=[ecu1], topology=empty_topology, metadata=system_metadata)

    return flync_model


def invalid_ambiguous_controller_interface():
    """
    Purpose:
        Test a connection referencing a controller interface name that is ambiguous across
        multiple controllers of the same ECU.
    Schema:
         +----------------------------------------------+
         |                    ECU1                      |
         | [ECU port1] ↔ [control1] (two controllers)   |
         +----------------------------------------------+
    Controller interface reference is ambiguous within the ECU
    """
    system_metadata, embedded_metadata, ecu_metadata = _system_metadata_setup()

    # --- Controllers (both expose an interface named "control1") ---
    controller_ecu1 = _controller(embedded_metadata, "controller_ecu1", "control1", "00:00:5e:00:53:01")
    controller_ecu2 = _controller(embedded_metadata, "controller_ecu2", "control1", "00:00:5e:00:53:02")

    # --- ECU Port Configuration ---
    port_ecu1 = ECUPort(name="port1")

    # --- AMBIGUOUS connection (interface name exists in two controllers) ---
    ecu_to_controller_cnx1 = ECUPortToControllerInterface(
        type="ecu_port_to_controller_interface",
        id="1",
        ecu_port="port1",
        controller_interface="control1",
    )

    # --- Internal links ---
    internal_topology_ecu1 = InternalTopology(connections=[InternalConnectionUnion(root=ecu_to_controller_cnx1)])

    # --- Create the ECU ---
    ecu1 = ECU(
        name="ecu1",
        ports=[port_ecu1],
        controllers=[controller_ecu1, controller_ecu2],
        topology=internal_topology_ecu1,
        ecu_metadata=ecu_metadata,
    )

    # --- External links ---
    empty_topology = FLYNCTopology(ethernet_topology=EthernetTopology(connections=[]))

    # --- Full FLYNC Model ---
    flync_model = FLYNCModel(ecus=[ecu1], topology=empty_topology, metadata=system_metadata)

    return flync_model


def invalid_shared_switch_port():
    """
    Purpose:
        Test a switch port that is connected to more than one component (shared).
    Schema:
         +------------------------------------------+
         |                   ECU1                   |
         | [ECU port1] ↔ [Switch1.p0] ↔ [ECU port2] |
         +------------------------------------------+
    Switch port connected to more than one component
    """
    system_metadata, embedded_metadata, ecu_metadata = _system_metadata_setup()

    # --- Controller ---
    controller_ecu1 = _controller(embedded_metadata, "controller_ecu1", "control1", "00:00:5e:00:53:01")

    # --- Switch Port ---
    switch_port1 = SwitchPort(name="sw_port1", silicon_port_no=1, default_vlan_id=1)

    # --- Switch ---
    switch1 = Switch(name="switch1", switch_config=SwitchConfig(ports=[switch_port1], vlans=[], meta=embedded_metadata))

    # --- ECU Port Configuration ---
    port_ecu1 = ECUPort(name="port1")
    port_ecu2 = ECUPort(name="port2")

    # --- Both ECU ports connect to the SAME switch port (INVALID) ---
    ecu_to_switch_cnx1 = ECUPortToSwitchPort(
        type="ecu_port_to_switch_port",
        id="1",
        ecu_port="port1",
        switch_port="sw_port1",
    )
    ecu_to_switch_cnx2 = ECUPortToSwitchPort(
        type="ecu_port_to_switch_port",
        id="2",
        ecu_port="port2",
        switch_port="sw_port1",
    )

    # --- Internal links ---
    internal_topology_ecu1 = InternalTopology(
        connections=[
            InternalConnectionUnion(root=ecu_to_switch_cnx1),
            InternalConnectionUnion(root=ecu_to_switch_cnx2),
        ]
    )

    # --- Create the ECU ---
    ecu1 = ECU(
        name="ecu1",
        ports=[port_ecu1, port_ecu2],
        controllers=[controller_ecu1],
        switches=[switch1],
        topology=internal_topology_ecu1,
        ecu_metadata=ecu_metadata,
    )

    # --- External links ---
    empty_topology = FLYNCTopology(ethernet_topology=EthernetTopology(connections=[]))

    # --- Full FLYNC Model ---
    flync_model = FLYNCModel(ecus=[ecu1], topology=empty_topology, metadata=system_metadata)

    return flync_model


def invalid_ambiguous_switch_port():
    """
    Purpose:
        Test a connection referencing a switch port name that is ambiguous across multiple
        switches of the same ECU.
    Schema:
         +-----------------------------------------------------+
         |                     ECU1                            |
         | [ECU port1] ↔ [p0 on switch1 | p0 on switch2]       |
         +-----------------------------------------------------+
    Switch port reference is ambiguous within the ECU
    """
    system_metadata, embedded_metadata, ecu_metadata = _system_metadata_setup()

    # --- Controller ---
    controller_ecu1 = _controller(embedded_metadata, "controller_ecu1", "control1", "00:00:5e:00:53:01")

    # --- Two switches, both with a port named "p0" ---
    switch1_port = SwitchPort(name="p0", silicon_port_no=0, default_vlan_id=1)
    switch2_port = SwitchPort(name="p0", silicon_port_no=0, default_vlan_id=1)
    switch1 = Switch(name="switch1", switch_config=SwitchConfig(ports=[switch1_port], vlans=[], meta=embedded_metadata))
    switch2 = Switch(name="switch2", switch_config=SwitchConfig(ports=[switch2_port], vlans=[], meta=embedded_metadata))

    # --- ECU Port Configuration ---
    port_ecu1 = ECUPort(name="port1")

    # --- AMBIGUOUS connection (switch port name exists in two switches) ---
    ecu_to_switch_cnx1 = ECUPortToSwitchPort(
        type="ecu_port_to_switch_port",
        id="1",
        ecu_port="port1",
        switch_port="p0",
    )

    # --- Internal links ---
    internal_topology_ecu1 = InternalTopology(connections=[InternalConnectionUnion(root=ecu_to_switch_cnx1)])

    # --- Create the ECU ---
    ecu1 = ECU(
        name="ecu1",
        ports=[port_ecu1],
        controllers=[controller_ecu1],
        switches=[switch1, switch2],
        topology=internal_topology_ecu1,
        ecu_metadata=ecu_metadata,
    )

    # --- External links ---
    empty_topology = FLYNCTopology(ethernet_topology=EthernetTopology(connections=[]))

    # --- Full FLYNC Model ---
    flync_model = FLYNCModel(ecus=[ecu1], topology=empty_topology, metadata=system_metadata)

    return flync_model


@pytest.mark.parametrize(
    "invalid_model_func,error_id,message_fragment",
    [
        pytest.param(invalid_interface_missing, "FLYNC-ECU-MAJ-REF-078", "UNKNOWN_IFACE"),
        pytest.param(invalid_ecu_no_port, "FLYNC-ECU-MAJ-REQ-227", "no ECU ports defined"),
        pytest.param(invalid_controller_reference, "FLYNC-ECU-MAJ-REF-076", "UNKNOWN_CONTROLLER"),
        pytest.param(invalid_wrong_connection_type, "FLYNC-ECU-MAJ-REF-075", "missing_sw_port"),
        pytest.param(invalid_undeclared_switch, "FLYNC-ECU-MAJ-REF-073", "UNKNOWN_SWITCH"),
        pytest.param(invalid_loop_connection, "FLYNC-ECU-MAJ-COMP-209", "connected to itself"),
        pytest.param(invalid_ambiguous_controller_interface, "FLYNC-ECU-MAJ-UNIQ-077", "ambiguous"),
        pytest.param(invalid_shared_switch_port, "FLYNC-ECU-MAJ-COMP-210", "more than one component"),
        pytest.param(invalid_ambiguous_switch_port, "FLYNC-ECU-MAJ-UNIQ-074", "ambiguous"),
    ],
)
def test_invalid_models_raise(invalid_model_func, error_id, message_fragment):
    """
    Test that invalid model functions raise error.
    """
    with pytest.raises(ValidationError) as exc_info:
        invalid_model_func()
    assert_single_error(exc_info, error_id, message_fragment)
