import pytest

from flync.model.flync_4_ecu import *
from flync.model.flync_4_ecu.controller import *
from flync.model.flync_4_ecu.internal_topology import *
from flync.model.flync_4_metadata import *
from flync.model.flync_4_topology import *
from flync.model.flync_model import FLYNCModel


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
    # --- System Version & Metadata ---
    system_version = BaseVersion(version_schema="semver", version="0.11.0")
    system_metadata = SystemMetadata(
        author="System_Architect",
        compatible_flync_version=system_version,
        release=system_version,
        oem="OEM_example",
        platform="Arch1",
    )

    # --- Embedded Metadata for ECU ---
    embedded_metadata = EmbeddedMetadata(
        type="embedded",
        author="test_team",
        compatible_flync_version=system_version,
        target_system="my_system",
    )

    # --- Controller Interface Configuration ---
    ipv4_ecu1 = IPv4AddressEndpoint(
        address=IPvAnyAddress("192.0.2.1"),
        ipv4netmask=IPvAnyAddress("192.0.0.0"),
    )
    virtual_iface_ecu1 = VirtualControllerInterface(name="virtual", vlanid=55, addresses=[ipv4_ecu1])
    ctrl_iface_ecu1 = ControllerInterface(
        name="control1",
        mac_address=MacAddress("00:00:5e:00:53:01"),
        virtual_interfaces=[virtual_iface_ecu1],
    )

    # --- Controller ---
    controller_ecu1 = Controller(
        name="controller_ecu1",
        meta=embedded_metadata,
        interfaces=[ctrl_iface_ecu1],
    )

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

    # --- ECU Metadata ---
    ecu_metadata = ECUMetadata(type="ecu", author="test_team", compatible_flync_version=system_version)

    # --- Create the ECU ---
    ecu1 = ECU(
        name="ecu1",
        ports=[port_ecu1],
        controllers=[controller_ecu1],
        topology=internal_topology_ecu1,
        ecu_metadata=ecu_metadata,
    )

    # --- External links ---
    empty_topology = FLYNCTopology(system_topology=SystemTopology(connections=[]))

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
    # --- System Version & Metadata ---
    system_version = BaseVersion(version_schema="semver", version="0.11.0")
    system_metadata = SystemMetadata(
        author="System_Architect",
        compatible_flync_version=system_version,
        release=system_version,
        oem="OEM_example",
        platform="Arch1",
    )

    # --- Embedded Metadata for ECU ---
    embedded_metadata = EmbeddedMetadata(
        type="embedded",
        author="test_team",
        compatible_flync_version=system_version,
        target_system="my_system",
    )

    # --- Controller Interface Configuration ---
    ipv4_ecu1 = IPv4AddressEndpoint(
        address=IPvAnyAddress("192.0.2.1"),
        ipv4netmask=IPvAnyAddress("192.0.0.0"),
    )
    virtual_iface_ecu1 = VirtualControllerInterface(name="virtual", vlanid=55, addresses=[ipv4_ecu1])
    ctrl_iface_ecu1 = ControllerInterface(
        name="control1",
        mac_address=MacAddress("00:00:5e:00:53:01"),
        virtual_interfaces=[virtual_iface_ecu1],
    )

    # --- Controller ---
    controller_ecu1 = Controller(
        name="controller_ecu1",
        meta=embedded_metadata,
        interfaces=[ctrl_iface_ecu1],
    )

    # --- ECU Controller Connection ---
    ecu_to_controller_cnx1 = ECUPortToControllerInterface(
        type="ecu_port_to_controller_interface",
        id="1",
        ecu_port="port1",
        controller_interface="control1",
    )

    # --- Internal links ---
    internal_topology_ecu1 = InternalTopology(connections=[InternalConnectionUnion(root=ecu_to_controller_cnx1)])

    # --- ECU Metadata ---
    ecu_metadata = ECUMetadata(type="ecu", author="test_team", compatible_flync_version=system_version)

    # --- Create the ECU (NO ECU PORT DEFINED) ---
    ecu1 = ECU(
        name="ecu1",
        ports=[],
        controllers=[controller_ecu1],
        topology=internal_topology_ecu1,
        ecu_metadata=ecu_metadata,
    )

    # --- External links ---
    empty_topology = FLYNCTopology(system_topology=SystemTopology(connections=[]))

    # --- Full FLYNC Model ---
    flync_model = FLYNCModel(ecus=[ecu1], topology=empty_topology, metadata=system_metadata)

    return flync_model


def invalid_controller_isolated():
    """
    Purpose:
        Test a controller that is not connected to any port or interface.
    Schema:
         +-------------------+
         |        ECU1       |
         |    [ECU port1]    |
         |                   |
         |   [Controller1]   |
         |    (isolated)     |
         +-------------------+
    Controller is not connected
    """
    # --- System Version & Metadata ---
    system_version = BaseVersion(version_schema="semver", version="0.11.0")
    system_metadata = SystemMetadata(
        author="System_Architect",
        compatible_flync_version=system_version,
        release=system_version,
        oem="OEM_example",
        platform="Arch1",
    )

    # --- Embedded Metadata for ECU ---
    embedded_metadata = EmbeddedMetadata(
        type="embedded",
        author="test_team",
        compatible_flync_version=system_version,
        target_system="my_system",
    )

    # --- Controller Interface Configuration ---
    ipv4_ecu1 = IPv4AddressEndpoint(
        address=IPvAnyAddress("192.0.2.1"),
        ipv4netmask=IPvAnyAddress("192.0.0.0"),
    )
    virtual_iface_ecu1 = VirtualControllerInterface(name="virtual", vlanid=55, addresses=[ipv4_ecu1])
    ctrl_iface_ecu1 = ControllerInterface(
        name="control1",
        mac_address=MacAddress("00:00:5e:00:53:01"),
        virtual_interfaces=[virtual_iface_ecu1],
    )

    # --- Controller ---
    controller_ecu1 = Controller(
        name="controller_ecu1",
        meta=embedded_metadata,
        interfaces=[ctrl_iface_ecu1],
    )

    # --- ECU Port Configuration ---
    port_ecu1 = ECUPort(
        name="port1",
        mdi_config=BASET1(mode="base_t1", speed=100, role="master"),
        mii_config=MII(type="mii", mode="mac"),
    )

    # --- ECU Controller Connection ---
    ecu_to_controller_cnx1 = ECUPortToControllerInterface(
        type="ecu_port_to_controller_interface",
        id="1",
        ecu_port="port1",
        controller_interface="control1",
    )

    # --- NO CONNECTION ---
    internal_topology_ecu1 = InternalTopology(connections=[])

    # --- ECU Metadata ---
    ecu_metadata = ECUMetadata(type="ecu", author="test_team", compatible_flync_version=system_version)

    # --- Create the ECU ---
    ecu1 = ECU(
        name="ecu1",
        ports=[port_ecu1],
        controllers=[controller_ecu1],
        topology=internal_topology_ecu1,
        ecu_metadata=ecu_metadata,
    )

    # --- External links ---
    empty_topology = FLYNCTopology(system_topology=SystemTopology(connections=[]))

    # --- Full FLYNC Model ---
    flync_model = FLYNCModel(ecus=[ecu1], topology=empty_topology, metadata=system_metadata)

    return flync_model


def invalid_wrong_connection_type():
    """
    Purpose:
        Test a port connected to a component with the wrong type.
    Schema:
        +------------------------------------------------------+
        |                     ECU1                             |
        | [ECU port1] ↔ [Controller Iface1] (used as switch)   |
        +------------------------------------------------------+
    Connection type is incorrect
    """
    # --- System Version & Metadata ---
    system_version = BaseVersion(version_schema="semver", version="0.11.0")
    system_metadata = SystemMetadata(
        author="System_Architect",
        compatible_flync_version=system_version,
        release=system_version,
        oem="OEM_example",
        platform="Arch1",
    )

    # --- Embedded Metadata for ECU ---
    embedded_metadata = EmbeddedMetadata(
        type="embedded",
        author="test_team",
        compatible_flync_version=system_version,
        target_system="my_system",
    )

    # --- Controller Interface Configuration ---
    ipv4_ecu1 = IPv4AddressEndpoint(
        address=IPvAnyAddress("192.0.2.1"),
        ipv4netmask=IPvAnyAddress("192.0.0.0"),
    )
    virtual_iface_ecu1 = VirtualControllerInterface(name="virtual", vlanid=55, addresses=[ipv4_ecu1])
    ctrl_iface_ecu1 = ControllerInterface(
        name="control1",
        mac_address=MacAddress("00:00:5e:00:53:01"),
        virtual_interfaces=[virtual_iface_ecu1],
    )

    # --- Controller ---
    controller_ecu1 = Controller(
        name="controller_ecu1",
        meta=embedded_metadata,
        interfaces=[ctrl_iface_ecu1],
    )

    # --- ECU Port Configuration ---
    port_ecu1 = ECUPort(
        name="port1",
        mdi_config=BASET1(mode="base_t1", speed=100, role="master"),
        mii_config=MII(type="mii", mode="mac"),
    )

    # --- WRONG CONNECTION TYPE ---
    ecu_to_wrong_cnx = ECUPortToSwitchPort(
        type="ecu_port_to_switch_port",
        id="1",
        ecu_port="port1",
        switch_port="control1",
    )

    # --- Internal links ---
    internal_topology_ecu1 = InternalTopology(connections=[InternalConnectionUnion(root=ecu_to_wrong_cnx)])

    # --- ECU Metadata ---
    ecu_metadata = ECUMetadata(type="ecu", author="test_team", compatible_flync_version=system_version)

    # --- Create the ECU ---
    ecu1 = ECU(
        name="ecu1",
        ports=[port_ecu1],
        controllers=[controller_ecu1],
        topology=internal_topology_ecu1,
        ecu_metadata=ecu_metadata,
    )

    # --- External links ---
    empty_topology = FLYNCTopology(system_topology=SystemTopology(connections=[]))

    # --- Full FLYNC Model ---
    flync_model = FLYNCModel(ecus=[ecu1], topology=empty_topology, metadata=system_metadata)

    return flync_model


def invalid_undeclared_switch():
    """
    Purpose:
        Test a switch used in a connection that is not declared in the ECU.
    Schema:
         +----------------------------------------+
         |                      ECU1              |
         | [ECU port1] ↔ [Switch1] (not declared) |
         +----------------------------------------+
    Switch does not exist in ECU
    """
    # --- System Version & Metadata ---
    system_version = BaseVersion(version_schema="semver", version="0.11.0")
    system_metadata = SystemMetadata(
        author="System_Architect",
        compatible_flync_version=system_version,
        release=system_version,
        oem="OEM_example",
        platform="Arch1",
    )

    # --- Embedded Metadata for ECU ---
    embedded_metadata = EmbeddedMetadata(
        type="embedded",
        author="test_team",
        compatible_flync_version=system_version,
        target_system="my_system",
    )

    # --- Controller Interface Configuration ---
    ipv4_ecu1 = IPv4AddressEndpoint(
        address=IPvAnyAddress("192.0.2.1"),
        ipv4netmask=IPvAnyAddress("192.0.0.0"),
    )
    virtual_iface_ecu1 = VirtualControllerInterface(name="virtual", vlanid=55, addresses=[ipv4_ecu1])
    ctrl_iface_ecu1 = ControllerInterface(
        name="control1",
        mac_address=MacAddress("00:00:5e:00:53:01"),
        virtual_interfaces=[virtual_iface_ecu1],
    )

    # --- Controller ---
    controller_ecu1 = Controller(
        name="controller_ecu1",
        meta=embedded_metadata,
        interfaces=[ctrl_iface_ecu1],
    )

    # --- ECU Port Configuration ---
    port_ecu1 = ECUPort(
        name="port1",
        mdi_config=BASET1(mode="base_t1", speed=100, role="master"),
        mii_config=MII(type="mii", mode="mac"),
    )

    # --- ECU Controller Connection ---
    ecu_to_controller_cnx1 = ECUPortToControllerInterface(
        type="ecu_port_to_controller_interface",
        id="1",
        ecu_port="port1",
        controller_interface="control1",
    )

    # --- INVALID connection (undeclared switch) ---
    invalid_cnx = ECUPortToSwitchPort(
        type="ecu_port_to_switch_port",
        id="2",
        ecu_port="port1",
        switch_port="sw1",
    )

    # --- Internal links ---
    internal_topology_ecu1 = InternalTopology(
        connections=[
            InternalConnectionUnion(root=ecu_to_controller_cnx1),
            InternalConnectionUnion(root=invalid_cnx),
        ]
    )

    # --- ECU Metadata ---
    ecu_metadata = ECUMetadata(type="ecu", author="test_team", compatible_flync_version=system_version)

    # --- Create the ECU ---
    ecu1 = ECU(
        name="ecu1",
        ports=[port_ecu1],
        controllers=[controller_ecu1],
        topology=internal_topology_ecu1,
        ecu_metadata=ecu_metadata,
    )

    # --- External links ---
    empty_topology = FLYNCTopology(system_topology=SystemTopology(connections=[]))

    # --- Full FLYNC Model ---
    flync_model = FLYNCModel(ecus=[ecu1], topology=empty_topology, metadata=system_metadata)

    return flync_model


def invalid_loop_connection():
    """
    Purpose:
        Test an invalid loop inside the ECU (component connected to itself).
    Schema:
         +--------------------------------------+
         |                   ECU1               |
         | [Switch1] ↔ [Switch1] (loop invalid) |
         +--------------------------------------+
    Loop or connection type not allowed
    """
    # --- System Version & Metadata ---
    system_version = BaseVersion(version_schema="semver", version="0.11.0")
    system_metadata = SystemMetadata(
        author="System_Architect",
        compatible_flync_version=system_version,
        release=system_version,
        oem="OEM_example",
        platform="Arch1",
    )

    # --- Embedded Metadata for ECU ---
    embedded_metadata = EmbeddedMetadata(
        type="embedded",
        author="test_team",
        compatible_flync_version=system_version,
        target_system="my_system",
    )

    # --- Controller Interface Configuration ---
    ipv4_ecu1 = IPv4AddressEndpoint(
        address=IPvAnyAddress("192.0.2.1"),
        ipv4netmask=IPvAnyAddress("192.0.0.0"),
    )
    virtual_iface_ecu1 = VirtualControllerInterface(name="virtual", vlanid=55, addresses=[ipv4_ecu1])
    ctrl_iface_ecu1 = ControllerInterface(
        name="control1",
        mac_address=MacAddress("00:00:5e:00:53:01"),
        virtual_interfaces=[virtual_iface_ecu1],
    )

    # --- Controller ---
    controller_ecu1 = Controller(
        name="controller_ecu1",
        meta=embedded_metadata,
        interfaces=[ctrl_iface_ecu1],
    )

    # --- Switch Port ---
    switch_port1 = SwitchPort(
        name="sw_port1",
        silicon_port_no=1,
        default_vlan_id=1,
        mii_config=MII(type="mii", speed=100, mode="phy"),
    )

    # --- Switch ---
    Switch(name="switch1", ports=[switch_port1], vlans=[], meta=embedded_metadata)

    # --- ECU Port Configuration ---
    port_ecu1 = ECUPort(name="port1")

    # --- ECU Controller Connection ---
    ecu_to_controller_cnx1 = ECUPortToControllerInterface(
        type="ecu_port_to_controller_interface",
        id="1",
        ecu_port="port1",
        controller_interface="control1",
    )

    # --- LOOP connection (port ↔ same switch) ---
    loop_cnx = SwitchPortToSwitchPort(
        type="switch_to_switch_same_ecu",
        id="loop",
        switch_port="sw_port1",
        switch2_port="sw_port1",
    )

    # --- Internal links ---
    internal_topology_ecu1 = InternalTopology(
        connections=[
            InternalConnectionUnion(root=ecu_to_controller_cnx1),
            InternalConnectionUnion(loop_cnx),
        ]
    )

    # --- ECU Metadata ---
    ecu_metadata = ECUMetadata(type="ecu", author="test_team", compatible_flync_version=system_version)

    # --- Create the ECU ---
    ecu1 = ECU(
        name="ecu1",
        ports=[port_ecu1],
        controllers=[controller_ecu1],
        topology=internal_topology_ecu1,
        ecu_metadata=ecu_metadata,
    )

    # --- External links ---
    empty_topology = FLYNCTopology(system_topology=SystemTopology(connections=[]))

    # --- Full FLYNC Model ---
    flync_model = FLYNCModel(ecus=[ecu1], topology=empty_topology, metadata=system_metadata)

    return flync_model


def invalid_cross_ecu_internal_connection():
    """
    Purpose:
        Test a connection inside InternalTopology that crosses ECUs.
    Schema:
         +----------------------+          +----------------------+
         |   ECU1               |          |   ECU2               |
         | [Controller Iface1] <-----------> [Controller Iface2]  |
         +----------------------+          +----------------------+
    InternalTopology cannot cross ECUs
    """
    # --- System Version & Metadata ---
    system_version = BaseVersion(version_schema="semver", version="0.11.0")
    system_metadata = SystemMetadata(
        author="System_Architect",
        compatible_flync_version=system_version,
        release=system_version,
        oem="OEM_example",
        platform="Arch1",
    )

    # --- Embedded Metadata for ECU ---
    embedded_metadata = EmbeddedMetadata(
        type="embedded",
        author="test_team",
        compatible_flync_version=system_version,
        target_system="my_system",
    )

    # --- Controller Interface Configuration ---
    ipv4_ecu1 = IPv4AddressEndpoint(
        address=IPvAnyAddress("192.0.2.1"),
        ipv4netmask=IPvAnyAddress("192.0.0.0"),
    )
    virtual_iface_ecu1 = VirtualControllerInterface(name="virtual1", vlanid=55, addresses=[ipv4_ecu1])
    ctrl_iface_ecu1 = ControllerInterface(
        name="control1",
        mac_address=MacAddress("00:00:5e:00:53:01"),
        virtual_interfaces=[virtual_iface_ecu1],
        mii_config=MII(type="mii", mode="mac"),
    )

    ipv4_ecu2 = IPv4AddressEndpoint(
        address=IPvAnyAddress("192.0.2.2"),
        ipv4netmask=IPvAnyAddress("192.0.0.0"),
    )
    virtual_iface_ecu2 = VirtualControllerInterface(name="virtual2", vlanid=55, addresses=[ipv4_ecu2])
    ctrl_iface_ecu2 = ControllerInterface(
        name="control2",
        mac_address=MacAddress("00:00:5e:00:53:02"),
        virtual_interfaces=[virtual_iface_ecu2],
        mii_config=MII(type="mii", mode="phy"),
    )

    # --- Controller ---
    controller_ecu1 = Controller(
        name="controller_ecu1",
        meta=embedded_metadata,
        interfaces=[ctrl_iface_ecu1],
    )
    controller_ecu2 = Controller(
        name="controller_ecu2",
        meta=embedded_metadata,
        interfaces=[ctrl_iface_ecu2],
    )

    # --- ECU Port Configuration ---
    port_ecu1 = ECUPort(
        name="port1",
        mdi_config=BASET1(mode="base_t1", speed=100, role="master"),
        mii_config=MII(type="mii", mode="phy"),
    )
    port_ecu2 = ECUPort(
        name="port2",
        mdi_config=BASET1(mode="base_t1", speed=100, role="slave"),
        mii_config=MII(type="mii", mode="mac"),
    )

    # --- ECU Controller Connection ---
    ecu_to_controller_cnx1 = ECUPortToControllerInterface(
        type="ecu_port_to_controller_interface",
        id="1",
        ecu_port="port1",
        controller_interface="control1",
    )
    ecu_to_controller_cnx2 = ECUPortToControllerInterface(
        type="ecu_port_to_controller_interface",
        id="2",
        ecu_port="port2",
        controller_interface="control2",
    )
    ecu1_to_ecu2_controller_cnx = ControllerInterfaceToControllerInterface(
        type="controller_interface_to_controller_interface",
        id="cross",
        controller_interface1="control1",
        controller_interface2="control2",
    )

    # --- Internal links ---
    internal_topology_ecu1 = InternalTopology(
        connections=[
            InternalConnectionUnion(root=ecu_to_controller_cnx1),
            InternalConnectionUnion(root=ecu1_to_ecu2_controller_cnx),
        ]
    )
    internal_topology_ecu2 = InternalTopology(
        connections=[
            InternalConnectionUnion(root=ecu_to_controller_cnx2),
            InternalConnectionUnion(root=ecu1_to_ecu2_controller_cnx),
        ]
    )

    # --- ECU Metadata ---
    ecu_metadata = ECUMetadata(type="ecu", author="test_team", compatible_flync_version=system_version)

    # --- Create the ECU ---
    ecu1 = ECU(
        name="ecu1",
        ports=[port_ecu1],
        controllers=[controller_ecu1],
        topology=internal_topology_ecu1,
        ecu_metadata=ecu_metadata,
    )
    ecu2 = ECU(
        name="ecu2",
        ports=[port_ecu2],
        controllers=[controller_ecu2],
        topology=internal_topology_ecu2,
        ecu_metadata=ecu_metadata,
    )

    # --- External links ---
    ecus_topology = FLYNCTopology(
        system_topology=SystemTopology(
            connections=[
                ExternalConnection(
                    type="ecu_port_to_ecu_port",
                    id="1",
                    ecu1_port="port1",
                    ecu2_port="port2",
                )
            ]
        )
    )

    # --- Full FLYNC Model ---
    flync_model = FLYNCModel(ecus=[ecu1, ecu2], topology=ecus_topology, metadata=system_metadata)

    return flync_model


def invalid_shared_internal_switch():
    """
    Purpose:
        Test using the same internal switch across multiple ECUs (not allowed).
    Schema:
         +----------------------------+       +-------------------+
         |        ECU1                |       |       ECU2        |
         | [Controller1] ↔ [Switch1] <----------> [Controller2]   |
         +----------------------------+       +-------------------+
    Each ECU must have its own switch; sharing is invalid
    """
    # --- System Version & Metadata ---
    system_version = BaseVersion(version_schema="semver", version="0.11.0")
    system_metadata = SystemMetadata(
        author="System_Architect",
        compatible_flync_version=system_version,
        release=system_version,
        oem="OEM_example",
        platform="Arch1",
    )

    # --- Embedded Metadata for ECU ---
    embedded_metadata = EmbeddedMetadata(
        type="embedded",
        author="test_team",
        compatible_flync_version=system_version,
        target_system="my_system",
    )

    # --- Controller Interface Configuration ---
    ipv4_ecu1 = IPv4AddressEndpoint(
        address=IPvAnyAddress("192.0.2.1"),
        ipv4netmask=IPvAnyAddress("192.0.0.0"),
    )
    virtual_iface_ecu1 = VirtualControllerInterface(name="virtual1", vlanid=55, addresses=[ipv4_ecu1])
    ctrl_iface_ecu1 = ControllerInterface(
        name="control1",
        mac_address=MacAddress("00:00:5e:00:53:01"),
        virtual_interfaces=[virtual_iface_ecu1],
    )

    ipv4_ecu2 = IPv4AddressEndpoint(
        address=IPvAnyAddress("192.0.2.2"),
        ipv4netmask=IPvAnyAddress("192.0.0.0"),
    )
    virtual_iface_ecu2 = VirtualControllerInterface(name="virtual2", vlanid=55, addresses=[ipv4_ecu2])
    ctrl_iface_ecu2 = ControllerInterface(
        name="control2",
        mac_address=MacAddress("00:00:5e:00:53:02"),
        virtual_interfaces=[virtual_iface_ecu2],
    )

    # --- Controller ---
    controller_ecu1 = Controller(
        name="controller_ecu1",
        meta=embedded_metadata,
        interfaces=[ctrl_iface_ecu1],
    )
    controller_ecu2 = Controller(
        name="controller_ecu2",
        meta=embedded_metadata,
        interfaces=[ctrl_iface_ecu2],
    )

    # --- ECU Port Configuration ---
    port_ecu1 = ECUPort(
        name="port1",
        mdi_config=BASET1(mode="base_t1", speed=100, role="master"),
        mii_config=MII(type="mii", speed=100, mode="mac"),
    )
    port_ecu2 = ECUPort(
        name="port2",
        mdi_config=BASET1(mode="base_t1", speed=100, role="slave"),
        mii_config=MII(type="mii", mode="mac"),
    )

    # --- ECU Controller Connection ---
    ecu_to_controller_cnx1 = ECUPortToControllerInterface(
        type="ecu_port_to_controller_interface",
        id="1",
        ecu_port="port1",
        controller_interface="control1",
    )
    ecu_to_controller_cnx2 = ECUPortToControllerInterface(
        type="ecu_port_to_controller_interface",
        id="2",
        ecu_port="port2",
        controller_interface="control2",
    )

    # --- Switch Port ---
    switch_port1 = SwitchPort(name="sw_port1", silicon_port_no=1, default_vlan_id=1)

    # --- Shared Switch (INVALID) ---
    Switch(name="switch1", ports=[switch_port1], vlans=[], meta=embedded_metadata)

    # --- ECU Switch Connection ---
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
            InternalConnectionUnion(root=ecu_to_controller_cnx1),
            InternalConnectionUnion(root=ecu_to_switch_cnx1),
        ]
    )
    internal_topology_ecu2 = InternalTopology(
        connections=[
            InternalConnectionUnion(root=ecu_to_controller_cnx2),
            InternalConnectionUnion(root=ecu_to_switch_cnx2),
        ]
    )

    # --- ECU Metadata ---
    ecu_metadata = ECUMetadata(type="ecu", author="test_team", compatible_flync_version=system_version)

    # --- Create the ECU ---
    ecu1 = ECU(
        name="ecu1",
        ports=[port_ecu1],
        controllers=[controller_ecu1],
        topology=internal_topology_ecu1,
        ecu_metadata=ecu_metadata,
    )
    ecu2 = ECU(
        name="ecu2",
        ports=[port_ecu2],
        controllers=[controller_ecu2],
        topology=internal_topology_ecu2,
        ecu_metadata=ecu_metadata,
    )

    # --- External links ---
    empty_topology = FLYNCTopology(system_topology=SystemTopology(connections=[]))

    # --- Full FLYNC Model ---
    flync_model = FLYNCModel(ecus=[ecu1, ecu2], topology=empty_topology, metadata=system_metadata)

    return flync_model


def undeclared_switch_reference():
    """
    Purpose:
        Test an ECU port referencing a switch that exists but isn’t declared in the ECU.
    Schema:
         +------------------------------+
         |           ECU1               |
         | [Controller1] ↔ [ECU port1] <----------> [Switch1] (not inside ECU)
         +------------------------------+
    ECU ports referencing switches not declared in the ECU.
    """
    # --- System Version & Metadata ---
    system_version = BaseVersion(version_schema="semver", version="0.11.0")
    system_metadata = SystemMetadata(
        author="System_Architect",
        compatible_flync_version=system_version,
        release=system_version,
        oem="OEM_example",
        platform="Arch1",
    )

    # --- Embedded Metadata for ECU ---
    embedded_metadata = EmbeddedMetadata(
        type="embedded",
        author="test_team",
        compatible_flync_version=system_version,
        target_system="my_system",
    )

    # --- Controller Interface Configuration ---
    ipv4_ecu1 = IPv4AddressEndpoint(
        address=IPvAnyAddress("192.0.2.1"),
        ipv4netmask=IPvAnyAddress("192.0.0.0"),
    )
    virtual_iface_ecu1 = VirtualControllerInterface(name="virtual", vlanid=55, addresses=[ipv4_ecu1])
    ctrl_iface_ecu1 = ControllerInterface(
        name="control1",
        mac_address=MacAddress("00:00:5e:00:53:01"),
        virtual_interfaces=[virtual_iface_ecu1],
    )

    # --- Controller ---
    controller_ecu1 = Controller(
        name="controller_ecu1",
        meta=embedded_metadata,
        interfaces=[ctrl_iface_ecu1],
    )

    # --- Switch Port ---
    switch_port1 = SwitchPort(
        name="sw_port1",
        silicon_port_no=1,
        default_vlan_id=1,
        mii_config=MII(type="mii", speed=100, mode="mac"),
    )

    # --- Switch ---
    Switch(name="switch1", ports=[switch_port1], vlans=[], meta=embedded_metadata)

    # --- ECU Port Configuration ---
    port_ecu1 = ECUPort(
        name="port1",
        mdi_config=BASET1(mode="base_t1", speed=100, role="master"),
        mii_config=MII(type="mii", mode="mac"),
    )

    # --- ECU Controller Connection ---
    ecu_to_controller_cnx1 = ECUPortToControllerInterface(
        type="ecu_port_to_controller_interface",
        id="1",
        ecu_port="port1",
        controller_interface="control1",
    )

    # --- ECU Switch Connection ---
    ecu_to_switch_cnx1 = ECUPortToSwitchPort(
        type="ecu_port_to_switch_port",
        id="2",
        ecu_port="port1",
        switch_port="sw_port1",
    )

    # --- Internal links ---
    internal_topology_ecu1 = InternalTopology(
        connections=[
            InternalConnectionUnion(root=ecu_to_controller_cnx1),
            InternalConnectionUnion(root=ecu_to_switch_cnx1),
        ]
    )

    # --- ECU Metadata ---
    ecu_metadata = ECUMetadata(type="ecu", author="test_team", compatible_flync_version=system_version)

    # --- INVALID ECU (undeclared switch) ---
    ecu1 = ECU(
        name="ecu1",
        ports=[port_ecu1],
        controllers=[controller_ecu1],
        topology=internal_topology_ecu1,
        ecu_metadata=ecu_metadata,
        switches=[],
    )

    # --- External links ---
    empty_topology = FLYNCTopology(system_topology=SystemTopology(connections=[]))

    # --- Full FLYNC Model ---
    flync_model = FLYNCModel(ecus=[ecu1], topology=empty_topology, metadata=system_metadata)

    return flync_model


@pytest.mark.parametrize(
    "invalid_model_func",
    [
        pytest.param(invalid_interface_missing),
        pytest.param(invalid_ecu_no_port),
        pytest.param(invalid_controller_isolated, marks=pytest.mark.xfail),
        pytest.param(invalid_wrong_connection_type),
        pytest.param(invalid_undeclared_switch),
        pytest.param(invalid_loop_connection),
        pytest.param(invalid_cross_ecu_internal_connection, marks=pytest.mark.xfail),
        pytest.param(invalid_shared_internal_switch, marks=pytest.mark.xfail),
        pytest.param(undeclared_switch_reference),
    ],
)
def test_invalid_models_raise(invalid_model_func):
    """
    Test that invalid model functions raise error.
    """
    with pytest.raises(Exception):
        invalid_model_func()
