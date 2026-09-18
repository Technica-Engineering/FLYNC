"""System-level negative tests for the FLYNC Ethernet Layer 2 feature."""

import pytest
from pydantic import ValidationError

from flync.core.utils.exceptions_handling import validate_with_policy
from flync.model.flync_4_ecu.controller import (
    Controller,
    EthernetInterface,
    EthernetInterfaceConfig,
    VirtualControllerInterface,
)
from flync.model.flync_4_ecu.ecu import ECU
from flync.model.flync_4_ecu.internal_topology import (
    ECUPortToSwitchPort,
    InternalTopology,
    SwitchPortToControllerInterface,
)
from flync.model.flync_4_ecu.phy import BASET1, RGMII
from flync.model.flync_4_ecu.port import ECUPort
from flync.model.flync_4_ecu.sockets import IPv4AddressEndpoint
from flync.model.flync_4_ecu.switch import Switch, SwitchConfig, SwitchPort
from flync.model.flync_4_metadata.metadata import BaseVersion, ECUMetadata, EmbeddedMetadata, SystemMetadata
from flync.model.flync_4_topology.ethernet_topology import EthernetPointToPointConnection, EthernetTopology, FLYNCTopology
from flync.model.flync_model import FLYNCModel
from tests.error_assertions import assert_single_error, assert_single_warning

FLYNC_VERSION = "0.14.0"


def _version() -> BaseVersion:
    return BaseVersion(version=FLYNC_VERSION)


def _embedded() -> EmbeddedMetadata:
    return EmbeddedMetadata(type="embedded", author="TestTeam", target_system="Device1", compatible_flync_version=_version())


def _ecu_metadata() -> ECUMetadata:
    return ECUMetadata(type="ecu", author="TestTeam", compatible_flync_version=_version())


def _system_metadata() -> SystemMetadata:
    return SystemMetadata(type="system", release=_version(), author="TestTeam", compatible_flync_version=_version())


def _version_dict() -> dict:
    return {"version_schema": "semver", "version": FLYNC_VERSION}


def _embedded_dict() -> dict:
    return {
        "type": "embedded",
        "author": "TestTeam",
        "target_system": "Device1",
        "compatible_flync_version": _version_dict(),
    }


def _mdi(mode="base_t1", speed=1000, role="master", autonegotiation=False) -> dict:
    return {
        "mode": mode,
        "speed": speed,
        "duplex": "full",
        "role": role,
        "autonegotiation": autonegotiation,
    }


def _wired_ecu(name: str, port_name: str, switch_port_name: str, mdi: dict) -> dict:
    """Raw ECU input with its port and switch port wired together in the internal topology, so the system-level
    reference warning under test is the only finding reported."""
    return {
        "name": name,
        "ports": [{"name": port_name, "mdi_config": mdi}],
        "controllers": [],
        "switches": [
            {
                "name": "SW1",
                "switch_config": {
                    "meta": _embedded_dict(),
                    "ports": [{"name": switch_port_name, "silicon_port_no": 0, "default_vlan_id": 1}],
                    "vlans": [],
                },
            }
        ],
        "topology": {
            "connections": [
                {
                    "type": "ecu_port_to_switch_port",
                    "id": "int1",
                    "ecu_port_name": port_name,
                    "switch_port_name": switch_port_name,
                }
            ]
        },
        "ecu_metadata": {"type": "ecu", "author": "TestTeam", "compatible_flync_version": _version_dict()},
    }


def _validate_external(ecu1: dict, ecu2: dict, connections: list) -> tuple:
    """Validate two wired ECUs joined by the given external topology connections, returning (model, findings)."""
    return validate_with_policy(
        FLYNCModel,
        {
            "ecus": [ecu1, ecu2],
            "topology": {"ethernet_topology": {"connections": connections}},
            "metadata": {
                "type": "system",
                "release": _version_dict(),
                "author": "TestTeam",
                "compatible_flync_version": _version_dict(),
            },
        },
        path=None,
    )


def _ecu(name: str, *, ports=None, controllers=None, switches=None) -> ECU:
    return ECU(
        name=name,
        ports=ports or [],
        controllers=controllers or [],
        switches=switches or [],
        topology=InternalTopology(),
        ecu_metadata=_ecu_metadata(),
    )


def _ecu_with_topology(name: str, *, ports=None, controllers=None, switches=None, connections=None) -> ECU:
    return ECU(
        name=name,
        ports=ports or [],
        controllers=controllers or [],
        switches=switches or [],
        topology=InternalTopology(connections=connections or []),
        ecu_metadata=_ecu_metadata(),
    )


def _system_model(ecus: list, external_connections: list | None = None) -> FLYNCModel:
    topology = FLYNCTopology(system_topology=EthernetTopology(connections=external_connections or []))
    return FLYNCModel(ecus=ecus, topology=topology, metadata=_system_metadata())


def _controller_with_mac(name: str, mac: str, mii_config=None) -> Controller:
    iface = EthernetInterface(
        name="eth0",
        interface_config=EthernetInterfaceConfig(
            mac_address=mac,
            mii_config=mii_config,
            virtual_interfaces=[
                VirtualControllerInterface(
                    name="viface1",
                    vlanid=10,
                    addresses=[IPv4AddressEndpoint(address="10.0.10.5", ipv4netmask="255.255.255.0")],
                )
            ],
        ),
    )
    return Controller(name=name, controller_metadata=_embedded(), ethernet_interfaces=[iface])


"""
============================================================
TEST NAME: external connection referencing unknown ECU1 port
RULE / CONSTRAINT: Every ecu1_port /
    ecu2_port_name of an EthernetPointToPointConnection in the system
    topology must resolve to a real ECUPort somewhere in the
    system.
============================================================

     FLYNCModel
       |
   topology.system_topology
       |  connections=[ecu1_port_to_ecu_port]  <-- INVALID
   EthernetPointToPointConnection
       +-- ecu1_port="GHOST_PORT"  (does not exist)
       +-- ecu2_port_name="ecu2_p1"
"""


def test_external_connection_unknown_ecu1_port_invalid():
    result = _validate_external(
        _wired_ecu("ECU1", "ecu1_p1", "sp1", _mdi(role="master")),
        _wired_ecu("ECU2", "ecu2_p1", "sp2", _mdi(role="slave")),
        [
            {"type": "ecu_port_to_ecu_port", "id": "conn0", "ecu1_port": "ecu1_p1", "ecu2_port": "ecu2_p1"},
            {"type": "ecu_port_to_ecu_port", "id": "conn1", "ecu1_port": "GHOST_PORT", "ecu2_port": "ecu2_p1"},
        ],
    )
    assert_single_warning(
        result,
        "FLYNC-GEN-WARN-REF-164",
        "ECU port name GHOST_PORT in connection conn1 of system topology does not exist",
    )


"""
============================================================
TEST NAME: external connection referencing unknown ECU2 port
RULE / CONSTRAINT: (symmetric case for ecu2_port_name)
============================================================

"""


def test_external_connection_unknown_ecu2_port_invalid():
    result = _validate_external(
        _wired_ecu("ECU1", "ecu1_p1", "sp1", _mdi(role="master")),
        _wired_ecu("ECU2", "ecu2_p1", "sp2", _mdi(role="slave")),
        [
            {"type": "ecu_port_to_ecu_port", "id": "conn0", "ecu1_port": "ecu1_p1", "ecu2_port": "ecu2_p1"},
            {"type": "ecu_port_to_ecu_port", "id": "conn1", "ecu1_port": "ecu1_p1", "ecu2_port": "GHOST_PORT"},
        ],
    )
    assert_single_warning(
        result,
        "FLYNC-GEN-WARN-REF-164",
        "ECU port name GHOST_PORT in connection conn1 of system topology does not exist",
    )


"""
============================================================
TEST NAME: external connection MDI mode mismatch across ECUs
RULE / CONSTRAINT: the two physical ports linked
    by an EthernetPointToPointConnection must use the same MDI mode
    (e.g. BASE-T1 on one side cannot be wired to BASE-T on the
    other).
============================================================

   ECU1:ecu1_p1 --- EthernetPointToPointConnection --- ECU2:ecu2_p1
   mdi=BASE-T1                              mdi=BASE-T   <-- INVALID

"""


def test_external_connection_mdi_mode_mismatch_invalid():
    result = _validate_external(
        _wired_ecu("ECU1", "ecu1_p1", "sp1", _mdi(role="master")),
        _wired_ecu("ECU2", "ecu2_p1", "sp2", _mdi(mode="base_t", role="slave")),
        [{"type": "ecu_port_to_ecu_port", "id": "conn1", "ecu1_port": "ecu1_p1", "ecu2_port": "ecu2_p1"}],
    )
    assert_single_warning(
        result,
        "FLYNC-GEN-WARN-REF-164",
        "Incompatible MDI Mode: ECU1:ecu1_p1 (base_t1) ↔ ECU2:ecu2_p1 (base_t)",
    )


"""
============================================================
TEST NAME: external connection MDI speed mismatch across ECUs
RULE / CONSTRAINT: the two physical ports linked
    by an EthernetPointToPointConnection must agree on link speed. This is
    the system-level counterpart of the single-ECU
    "MDI/MII speed mismatch" unit test: here the mismatch is
    between two ports on *different* ECUs joined by a real
    cable (EthernetPointToPointConnection), not the MDI/MII pairing on one
    port.
============================================================

   ECU1:ecu1_p1 --- EthernetPointToPointConnection --- ECU2:ecu2_p1
   BASE-T1 1000                             BASE-T1 100   <-- INVALID

"""


def test_external_connection_mdi_speed_mismatch_invalid():
    result = _validate_external(
        _wired_ecu("ECU1", "ecu1_p1", "sp1", _mdi(role="master")),
        _wired_ecu("ECU2", "ecu2_p1", "sp2", _mdi(speed=100, role="slave")),
        [{"type": "ecu_port_to_ecu_port", "id": "conn1", "ecu1_port": "ecu1_p1", "ecu2_port": "ecu2_p1"}],
    )
    assert_single_warning(
        result,
        "FLYNC-GEN-WARN-REF-164",
        "Incompatible MDI Speed: ECU1:ecu1_p1 (1000) ↔ ECU2:ecu2_p1 (100)",
    )


"""
============================================================
TEST NAME: external connection MDI role mismatch (master/master)
RULE / CONSTRAINT: A physical BASE-T1 link needs
    exactly one master and one slave; two masters (or two
    slaves) on the same cable is invalid.
============================================================

   ECU1:ecu1_p1 --- EthernetPointToPointConnection --- ECU2:ecu2_p1
   role=master                              role=master  <-- INVALID

   """


def test_external_connection_mdi_role_mismatch_invalid():
    result = _validate_external(
        _wired_ecu("ECU1", "ecu1_p1", "sp1", _mdi(role="master")),
        _wired_ecu("ECU2", "ecu2_p1", "sp2", _mdi(role="master")),
        [{"type": "ecu_port_to_ecu_port", "id": "conn1", "ecu1_port": "ecu1_p1", "ecu2_port": "ecu2_p1"}],
    )
    assert_single_warning(
        result,
        "FLYNC-GEN-WARN-REF-164",
        "Incompatible MDI Roles: ECU1:ecu1_p1 (master) ↔ ECU2:ecu2_p1 (master)",
    )


"""
============================================================
TEST NAME: external connection MDI autonegotiation mismatch
RULE / CONSTRAINT: both ends of a physical link
    must agree on whether autonegotiation is used.
============================================================

   ECU1:ecu1_p1 --- EthernetPointToPointConnection --- ECU2:ecu2_p1
   autonegotiation=True                     autonegotiation=False  <-- INVALID

"""


def test_external_connection_mdi_autonegotiation_mismatch_invalid():
    result = _validate_external(
        _wired_ecu("ECU1", "ecu1_p1", "sp1", _mdi(role="master", autonegotiation=True)),
        _wired_ecu("ECU2", "ecu2_p1", "sp2", _mdi(role="slave", autonegotiation=False)),
        [{"type": "ecu_port_to_ecu_port", "id": "conn1", "ecu1_port": "ecu1_p1", "ecu2_port": "ecu2_p1"}],
    )
    assert_single_warning(
        result,
        "FLYNC-GEN-WARN-REF-164",
        "Incompatible MDI Autonegotiation: ECU1:ecu1_p1 (True) ↔ ECU2:ecu2_p1 (False)",
    )


"""
============================================================
TEST NAME: duplicate MAC address across two ECUs
RULE / CONSTRAINT: MAC addresses must be unique
    across the *whole system*, not just within one ECU. Both
    ECUs are otherwise fully and validly wired together via a
    real system topology link, isolating the duplicate-MAC
    violation.
============================================================

   ECU1.CTRL1.eth0  mac=00:11:22:33:44:55
   ECU2.CTRL1.eth0  mac=00:11:22:33:44:55  <-- INVALID (duplicate)

   ECU1:ecu1_p1 === (valid EthernetPointToPointConnection) === ECU2:ecu2_p1

"""


def test_duplicate_mac_across_ecus_invalid():
    dup_mac = "00:11:22:33:44:55"
    ecu1 = _ecu(
        "ECU1",
        ports=[ECUPort(name="ecu1_p1", mdi_config=BASET1(speed=1000, role="master"))],
        controllers=[_controller_with_mac("CTRL1", dup_mac)],
    )
    ecu2 = _ecu(
        "ECU2",
        ports=[ECUPort(name="ecu2_p1", mdi_config=BASET1(speed=1000, role="slave"))],
        controllers=[_controller_with_mac("CTRL1", dup_mac)],
    )
    conn = EthernetPointToPointConnection(type="ecu_port_to_ecu_port", id="conn1", ecu1_port="ecu1_p1", ecu2_port_name="ecu2_p1")
    with pytest.raises(ValidationError) as exc_info:
        _system_model([ecu1, ecu2], [conn])
    assert_single_error(exc_info, "FLYNC-GEN-MAJ-UNIQ-172", "is repeated in ECU")


# ============================================================================
# Internal topology (cross-component chains within one ECU)
# ============================================================================

"""
============================================================
TEST NAME: internal topology connection references unknown ECU port
RULE / CONSTRAINT: every ecu_port_name in an
    internal topology connection must resolve to a real
    ECUPort of the same ECU.
============================================================

       ECU1
        |  ports=[p1]
        |  switches=[SW1(ports=[sp1])]
        |  topology.connections=[ecu_port_to_switch_port]  <-- INVALID
   ECUPortToSwitchPort
        +-- ecu_port_name="GHOST_PORT"  (does not exist)
        +-- switch_port_name="sp1"
"""


def test_internal_topology_unknown_ecu_port_invalid():
    """An internal L2 connection must reference an existing ECU port."""
    switch = Switch(
        name="SW1",
        switch_config=SwitchConfig(
            meta=_embedded(),
            ports=[
                SwitchPort(
                    name="sp1",
                    silicon_port_no=0,
                    default_vlan_id=1,
                )
            ],
            vlans=[],
        ),
    )

    port = ECUPort(
        name="p1",
        mdi_config=BASET1(speed=1000, role="master"),
    )
    conn = ECUPortToSwitchPort(
        type="ecu_port_to_switch_port",
        id="conn1",
        ecu_port_name="GHOST_PORT",
        switch_port_name="sp1",
    )

    with pytest.raises(ValidationError) as exc_info:
        _ecu_with_topology(
            "ECU1",
            ports=[port],
            switches=[switch],
            connections=[conn],
        )

    assert_single_error(
        exc_info,
        "FLYNC-ECU-MAJ-REF-072",
        "ECU port 'GHOST_PORT' referenced in connection 'conn1' was not found",
    )


"""
============================================================
TEST NAME: switch port <-> controller interface MII speed mismatch
RULE / CONSTRAINT: an internal
    switch_port_to_controller_interface connection joins two
    *different kinds* of components (a hardware switch port and
    a software controller interface); both sides must still
    agree on MII speed, mirroring the physical-layer check but
    for an internal, cross-component link.
============================================================

   Switch SW1.sp_ctrl  mii=RGMII speed=1000 mode=mac
        |
   (SwitchPortToControllerInterface)  <-- INVALID
        |
   Controller CTRL1.eth0  mii=RGMII speed=100 mode=phy
"""


def test_switch_port_to_controller_interface_mii_speed_mismatch_invalid():
    """An L2 connection must reject switch and controller interfaces with different MII speeds."""
    switch = Switch(
        name="SW1",
        switch_config=SwitchConfig(
            meta=_embedded(),
            ports=[
                SwitchPort(
                    name="sp_ctrl",
                    silicon_port_no=0,
                    default_vlan_id=1,
                    mii_config=RGMII(speed=1000, mode="mac"),
                )
            ],
            vlans=[],
        ),
    )

    controller = _controller_with_mac(
        "CTRL1",
        "00:11:22:33:44:66",
        mii_config=RGMII(speed=100, mode="phy"),
    )

    port = ECUPort(
        name="p1",
        mdi_config=BASET1(speed=1000, role="master"),
    )
    conn = SwitchPortToControllerInterface(
        type="switch_port_to_controller_interface",
        id="conn1",
        switch_port_name="sp_ctrl",
        iface_name="eth0",
    )

    with pytest.raises(ValidationError) as exc_info:
        _ecu_with_topology(
            "ECU1",
            ports=[port],
            switches=[switch],
            controllers=[controller],
            connections=[conn],
        )

    assert_single_error(
        exc_info,
        "FLYNC-CMN-MAJ-COMP-014",
        "Incompatible MII Speed: sp_ctrl (1000) ↔ eth0(100)",
    )
