import pytest
import json
from pathlib import Path
from flync.model.flync_4_ecu import *
from flync.model.flync_4_metadata import *
from flync.model.flync_4_topology import *
from flync.model.flync_4_ecu.controller import *
from flync.model.flync_4_ecu.internal_topology import *
from flync.model.flync_model import FLYNCModel
from flync.sdk.workspace.flync_workspace import FLYNCWorkspace


def valid_simple_ecu():
    """
    Purpose:
        Validate a simple internal ECU topology.
    Schema:
     +---------------------------------------------+
     |                  ECU1                       |
     | ECU port1 ↔ Controller Iface1 ↔ Controller1 |
     +---------------------------------------------+
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
    virtual_iface_ecu1 = VirtualControllerInterface(
        name="virtual", vlanid=55, addresses=[ipv4_ecu1]
    )
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
    port_ecu1 = ECUPort(name="port1")

    # --- ECU Controller Connection ---
    ecu_to_controller_cnx1 = ECUPortToControllerInterface(
        type="ecu_port_to_controller_interface",
        id="1",
        ecu_port="port1",
        controller_interface="control1",
    )

    # --- Internal links ---
    internal_topology_ecu1 = InternalTopology(
        connections=[InternalConnectionUnion(root=ecu_to_controller_cnx1)]
    )

    # --- ECU Metadata ---
    ecu_metadata = ECUMetadata(
        type="ecu", author="test_team", compatible_flync_version=system_version
    )

    # --- Create the ECU ---
    ecu1 = ECU(
        name="ecu1",
        ports=[port_ecu1],
        controllers=[controller_ecu1],
        topology=internal_topology_ecu1,
        ecu_metadata=ecu_metadata,
    )

    # --- External links ---
    empty_topology = FLYNCTopology(
        system_topology=SystemTopology(connections=[])
    )

    # --- Full FLYNC Model ---
    flync_model = FLYNCModel(
        ecus=[ecu1], topology=empty_topology, metadata=system_metadata
    )

    return flync_model


def valid_ecu_with_switch():
    """
    Purpose:
        Validate an internal ECU topology using a switch.
    Schema:
     +----------------------------------------------------------------------+
     |                              ECU1                                    |
     | ECU port1 ↔ Switch port1 ↔ Switch1 ↔ Controller Iface2 ↔ Controller2 |
     +----------------------------------------------------------------------+
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
    virtual_iface_ecu1 = VirtualControllerInterface(
        name="virtual", vlanid=55, addresses=[ipv4_ecu1]
    )
    ctrl_iface_ecu1 = ControllerInterface(
        name="control1",
        mac_address=MacAddress("00:00:5e:00:53:01"),
        virtual_interfaces=[virtual_iface_ecu1],
        mii_config=MII(type="mii", speed=100, mode="phy"),
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
    switch1 = Switch(
        name="switch1", ports=[switch_port1], vlans=[], meta=embedded_metadata
    )

    # --- ECU Port Configuration ---
    port_ecu1 = ECUPort(name="port1")

    # --- ECU Controller Connection ---
    ecu_to_controller_cnx1 = ECUPortToControllerInterface(
        type="ecu_port_to_controller_interface",
        id="1",
        ecu_port="port1",
        controller_interface="control1",
    )

    # --- Switch Controller Connection ---
    switch_to_controller_cnx1 = SwitchPortToControllerInterface(
        type="switch_port_to_controller_interface",
        id="2",
        switch_port="sw_port1",
        controller_interface="control1",
    )

    # --- Internal links ---
    internal_topology_ecu1 = InternalTopology(
        connections=[
            InternalConnectionUnion(root=ecu_to_controller_cnx1),
            InternalConnectionUnion(switch_to_controller_cnx1),
        ]
    )

    # --- ECU Metadata ---
    ecu_metadata = ECUMetadata(
        type="ecu", author="test_team", compatible_flync_version=system_version
    )

    # --- Create the ECU ---
    ecu1 = ECU(
        name="ecu1",
        ports=[port_ecu1],
        controllers=[controller_ecu1],
        topology=internal_topology_ecu1,
        ecu_metadata=ecu_metadata,
        switches=[switch1],
    )

    # --- External links ---
    empty_topology = FLYNCTopology(
        system_topology=SystemTopology(connections=[])
    )

    # --- Full FLYNC Model ---
    flync_model = FLYNCModel(
        ecus=[ecu1], topology=empty_topology, metadata=system_metadata
    )

    return flync_model


def valid_inter_ecu_connection():
    """
    Purpose:
        Validate communication between two ECUs via their ports.
    Schema:
         +----------------------------------------------------+          +----------------------------------------------------+
         |                       ECU1                         |          |                       ECU2                         |
         | Controller1 ↔ Controller Iface1 ↔ Controller port1 <----------> Controller port2 ↔ Controller Iface2 ↔ Controller2 |
         +----------------------------------------------------+          +----------------------------------------------------+
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
    virtual_iface_ecu1 = VirtualControllerInterface(
        name="virtual1", vlanid=55, addresses=[ipv4_ecu1]
    )
    ctrl_iface_ecu1 = ControllerInterface(
        name="control1",
        mac_address=MacAddress("00:00:5e:00:53:01"),
        virtual_interfaces=[virtual_iface_ecu1],
    )

    ipv4_ecu2 = IPv4AddressEndpoint(
        address=IPvAnyAddress("192.0.2.2"),
        ipv4netmask=IPvAnyAddress("192.0.0.0"),
    )
    virtual_iface_ecu2 = VirtualControllerInterface(
        name="virtual2", vlanid=55, addresses=[ipv4_ecu2]
    )
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
    port_ecu1 = ECUPort(name="port1", mdi_config=BASET1(role="master"))
    port_ecu2 = ECUPort(name="port2", mdi_config=BASET1(role="slave"))

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

    # --- Internal links ---
    internal_topology_ecu1 = InternalTopology(
        connections=[InternalConnectionUnion(root=ecu_to_controller_cnx1)]
    )
    internal_topology_ecu2 = InternalTopology(
        connections=[InternalConnectionUnion(root=ecu_to_controller_cnx2)]
    )

    # --- ECU Metadata ---
    ecu_metadata = ECUMetadata(
        type="ecu", author="test_team", compatible_flync_version=system_version
    )

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
    flync_model = FLYNCModel(
        ecus=[ecu1, ecu2], topology=ecus_topology, metadata=system_metadata
    )

    return flync_model


def valid_iface_to_iface():
    """
    Purpose:
        Validate direct communication between controller interfaces.
    Schema:
         +-------------------------------------------------------------------+
         |                              ECU1                                 |
         | Controller1 ↔ Controller Iface1 ↔ Controller Iface2 ↔ Controller2 |
         +-------------------------------------------------------------------+
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
    virtual_iface_ecu1 = VirtualControllerInterface(
        name="virtual", vlanid=55, addresses=[ipv4_ecu1]
    )
    ctrl_iface_ecu1 = ControllerInterface(
        name="control1",
        mac_address=MacAddress("00:00:5e:00:53:01"),
        virtual_interfaces=[virtual_iface_ecu1],
        mii_config=MII(type="mii", speed=100, mode="phy"),
    )

    ipv4_ecu2 = IPv4AddressEndpoint(
        address=IPvAnyAddress("192.0.2.2"),
        ipv4netmask=IPvAnyAddress("192.0.0.0"),
    )
    virtual_iface_ecu2 = VirtualControllerInterface(
        name="virtual2", vlanid=55, addresses=[ipv4_ecu2]
    )
    ctrl_iface_ecu2 = ControllerInterface(
        name="control2",
        mac_address=MacAddress("00:00:5e:00:53:02"),
        virtual_interfaces=[virtual_iface_ecu2],
        mii_config=MII(type="mii", speed=100, mode="mac"),
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
    port_ecu1 = ECUPort(name="port1")

    # --- ECU Controller Connection ---
    ecu_to_controller_cnx1 = ECUPortToControllerInterface(
        type="ecu_port_to_controller_interface",
        id="1",
        ecu_port="port1",
        controller_interface="control1",
    )

    # --- Controller Controller connection ---
    controller_to_controller_cnx1 = ControllerInterfaceToControllerInterface(
        type="controller_interface_to_controller_interface",
        id="2",
        controller_interface1="control1",
        controller_interface2="control2",
    )

    # --- Internal links ---
    internal_topology_ecu1 = InternalTopology(
        connections=[
            InternalConnectionUnion(root=ecu_to_controller_cnx1),
            InternalConnectionUnion(root=controller_to_controller_cnx1),
        ]
    )

    # --- ECU Metadata ---
    ecu_metadata = ECUMetadata(
        type="ecu", author="test_team", compatible_flync_version=system_version
    )

    # --- Create the ECU ---
    ecu1 = ECU(
        name="ecu1",
        ports=[port_ecu1],
        controllers=[controller_ecu1, controller_ecu2],
        topology=internal_topology_ecu1,
        ecu_metadata=ecu_metadata,
    )

    # --- External links ---
    empty_topology = FLYNCTopology(
        system_topology=SystemTopology(connections=[])
    )

    # --- Full FLYNC Model ---
    flync_model = FLYNCModel(
        ecus=[ecu1], topology=empty_topology, metadata=system_metadata
    )

    return flync_model


@pytest.mark.parametrize(
    "valid_model_func",
    [
        valid_simple_ecu,
        valid_ecu_with_switch,
        valid_inter_ecu_connection,
        valid_iface_to_iface,
    ],
)
@pytest.mark.xfail(reason="Known bug")
def test_flync_model(tmpdir, valid_model_func):
    """
    Full validation:
    - Build model
    - Validate structure
    - Round-trip (save/load)
    - Compare models
    """

    # --- Build model ---
    initial_model = valid_model_func()

    # --- Validate initial model integrity ---
    assert initial_model.validate_unique_ips() is initial_model
    assert hasattr(initial_model, "model_config")
    assert len(initial_model.get_all_ecus()) > 0
    assert len(initial_model.get_all_controllers()) > 0
    assert len(initial_model.get_all_ecu_ports()) > 0
    assert len(initial_model.get_all_interfaces_names()) > 0
    assert initial_model.get_system_topology_info() is not None

    # --- Workspace ---
    workspace_path = Path(tmpdir) / "temp_workspace"
    workspace = FLYNCWorkspace.load_model(
        flync_model=initial_model,
        workspace_name="TestWorkspace",
        file_path=workspace_path,
    )
    workspace.generate_configs()

    # --- Reload ---
    ws = FLYNCWorkspace.load_workspace(
        workspace_name="new_workspace", workspace_path=workspace_path
    )
    final_model = ws.flync_model

    # --- Validate reloaded model integrity ---
    assert final_model.validate_unique_ips() is final_model
    assert hasattr(final_model, "model_config")
    assert len(final_model.get_all_ecus()) > 0
    assert len(final_model.get_all_controllers()) > 0
    assert len(final_model.get_all_ecu_ports()) > 0
    assert len(final_model.get_all_interfaces_names()) > 0
    assert final_model.get_system_topology_info() is not None

    # --- Compare models ---
    initial_json = json.dumps(initial_model.dict(), sort_keys=True)
    final_json = json.dumps(final_model.dict(), sort_keys=True)

    assert (
        initial_json == final_json
    ), "The final model is different from the initial model!"
