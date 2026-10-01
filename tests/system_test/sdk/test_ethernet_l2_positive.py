"""System-level SDK positive tests for the FLYNC Ethernet Layer 2 feature."""

import shutil

from flync.sdk.context.diagnostics_result import WorkspaceState
from flync.sdk.helpers.validation_helpers import validate_workspace

from .helper import (
    INTERFACE_VIFACE1,
    PORT_P0_MDI100,
    PORT_P0_MDI100_MII100,
    SWITCH_DEFAULT_YAML,
    SWITCH_PORT_MII_YAML,
    SWITCH_TWO_VLANS_YAML,
    TOPOLOGY_ECU_TO_SWITCH,
    add_controller_interface,
    add_switch,
    copy_example,
    write_ecu_ports,
)

# FLYNC error ids that indicate an Ethernet Layer-2 validation defect.
_L2_ERROR_IDS = {
    "FLYNC-ECU-MAJ-CONS-081",
    "FLYNC-CMN-MIN-VAL-002",
    "FLYNC-CMN-MAJ-UNIQ-009",
}


def _validate(destination_folder):
    result = validate_workspace(destination_folder)
    assert result.workspace is not None, f"SDK did not load workspace '{destination_folder}'"
    assert result.model is not None, f"SDK did not build a model for '{destination_folder}'"
    assert result.state in (
        WorkspaceState.VALID,
        WorkspaceState.WARNING,
    ), f"workspace '{destination_folder}' state is {result.state}, expected VALID or WARNING"
    for uri, errs in result.errors.items():
        for err in errs:
            assert err.get("type") == "warning", f"workspace '{destination_folder}' produced a non-warning diagnostic: {err.get('msg')}"
            assert (err.get("ctx") or {}).get(
                "error_id"
            ) not in _L2_ERROR_IDS, f"workspace '{destination_folder}' surfaced an L2 validation error: {err.get('msg')}"
    return result


def _ecu(result):
    return result.model.get_ecu_by_name("ecu_l2")


def _cleanup(destination_folder) -> None:
    if destination_folder.exists():
        shutil.rmtree(destination_folder)


# Valid ``ecu_l2`` port configurations used by the ECU-port scenarios.
_PORT_BASE_T1_1000 = """ports:
  - name: p0
    mdi_config:
      mode: base_t1
      speed: 1000
      duplex: full
      role: master
      autonegotiation: false
"""

_PORT_BASE_T1S_10 = """ports:
  - name: p0
    mdi_config:
      mode: base_t1s
      speed: 10
      duplex: half
      role: master
      autonegotiation: false
"""

_PORT_MII = """ports:
  - name: p0
    mii_config:
      type: rmii
      speed: 100
      mode: phy
"""


"""
============================================================
TEST NAME: ECUPort with BASE-T1 MDI 100 Mbit/s loads
RULE / CONSTRAINT: An Ethernet port may declare
    a MDI BASE-T1 PHY at 100 Mbit/s (allowed medium).
============================================================

       FLYNCWORKSPACE (copy of examples/flync_example)
            |
         ECU ecu_l2
            |  ports=[p0]
        ECUPort p0
            +-- mdi_config=BASE-T1 speed 100 role slave

Expected: workspace loads as VALID/WARNING with object discovery
showing mdi_config BASE-T1 at 100 Mbit/s.
"""


def test_ecu_port_mdi_base_t1_100(tmp_path):
    destination_folder = copy_example(tmp_path)
    try:
        write_ecu_ports(destination_folder, PORT_P0_MDI100)
        result = _validate(destination_folder)
        port = _ecu(result).get_all_ports()[0]
        assert port.name == "p0"
        assert port.mdi_config.mode == "base_t1"
        assert port.mdi_config.speed == 100
        assert port.mdi_config.role == "slave"
    finally:
        _cleanup(destination_folder)


"""
============================================================
TEST NAME: ECUPort with BASE-T1 MDI 1000 Mbit/s loads
RULE / CONSTRAINT: An Ethernet port may declare
    a MDI BASE-T1 PHY at 1000 Mbit/s master (allowed medium).
============================================================

       FLYNCWORKSPACE (copy of examples/flync_example)
            |
         ECU ecu_l2
            |  ports=[p0]
        ECUPort p0
            +-- mdi_config=BASE-T1 speed 1000 role master

Expected: workspace loads as VALID/WARNING with object discovery
showing mdi_config BASE-T1 at 1000 Mbit/s.
"""


def test_ecu_port_mdi_base_t1_1000(tmp_path):
    destination_folder = copy_example(tmp_path)
    try:
        write_ecu_ports(destination_folder, _PORT_BASE_T1_1000)
        result = _validate(destination_folder)
        port = _ecu(result).get_all_ports()[0]
        assert port.mdi_config.mode == "base_t1"
        assert port.mdi_config.speed == 1000
        assert port.mdi_config.role == "master"
    finally:
        _cleanup(destination_folder)


"""
============================================================
TEST NAME: ECUPort with BASE-T1S MDI 10 Mbit/s loads
RULE / CONSTRAINT: An Ethernet port may declare
    a MDI BASE-T1S PHY (single-pair half-duplex) at 10 Mbit/s.
============================================================

       FLYNCWORKSPACE (copy of examples/flync_example)
            |
         ECU ecu_l2
            |  ports=[p0]
        ECUPort p0
            +-- mdi_config=BASE-T1S speed 10 duplex half

Expected: workspace loads as VALID/WARNING with object discovery
showing mdi_config BASE-T1S at 10 Mbit/s.
"""


def test_ecu_port_mdi_base_t1s_10(tmp_path):
    destination_folder = copy_example(tmp_path)
    try:
        write_ecu_ports(destination_folder, _PORT_BASE_T1S_10)
        result = _validate(destination_folder)
        port = _ecu(result).get_all_ports()[0]
        assert port.mdi_config.mode == "base_t1s"
        assert port.mdi_config.speed == 10
        assert port.mdi_config.duplex == "half"
    finally:
        _cleanup(destination_folder)


"""
============================================================
TEST NAME: ECUPort with an MII RMII config loads
RULE / CONSTRAINT: An Ethernet port may declare
    a media-independent (MII-family) interface.
============================================================

       FLYNCWORKSPACE (copy of examples/flync_example)
            |
         ECU ecu_l2
            |  ports=[p0]
        ECUPort p0
            +-- mii_config=RMII speed 100 mode phy

Expected: workspace loads as VALID/WARNING with object discovery
showing mii_config RMII at 100 Mbit/s.
"""


def test_ecu_port_mii(tmp_path):
    destination_folder = copy_example(tmp_path)
    try:
        write_ecu_ports(destination_folder, _PORT_MII)
        result = _validate(destination_folder)
        port = _ecu(result).get_all_ports()[0]
        assert port.mii_config is not None
        assert port.mii_config.type == "rmii"
        assert port.mii_config.speed == 100
    finally:
        _cleanup(destination_folder)


"""
============================================================
TEST NAME: ECUPort with matching MDI and MII speeds loads
RULE / CONSTRAINT: A Layer-2 port may define both a
    PHY (MDI) and a MAC-side (MII) interface, with matching speeds
    allowed.
============================================================

       FLYNCWORKSPACE (copy of examples/flync_example)
            |
         ECU ecu_l2
            |  ports=[p0]
        ECUPort p0
            +-- mdi_config=BASE-T1 speed 100
            +-- mii_config=RMII  speed 100   (match)

Expected: workspace loads as VALID/WARNING; both configs are
present and their speeds are equal (100).
"""


def test_ecu_port_mdi_mii_matching(tmp_path):
    destination_folder = copy_example(tmp_path)
    try:
        write_ecu_ports(destination_folder, PORT_P0_MDI100_MII100)
        result = _validate(destination_folder)
        port = _ecu(result).get_all_ports()[0]
        assert port.mdi_config.speed == 100
        assert port.mii_config is not None
        assert port.mii_config.speed == 100
    finally:
        _cleanup(destination_folder)


"""
============================================================
TEST NAME: Switch ports with a default VLAN ID load
RULE / CONSTRAINT: Every switch port may be
    assigned a default (PVID) VLAN for untagged ingress frames.
============================================================

       FLYNCWORKSPACE (copy of examples/flync_example)
            |
         ECU ecu_l2
            |  switches=[sw1]
        Switch sw1
            |  ports=[sp0, sp1]
            |    sp0: silicon 0, default_vlan_id 1
            |    sp1: silicon 1, default_vlan_id 1

Expected: workspace loads as VALID/WARNING; each switch port
carries its default_vlan_id.
"""


def test_switch_ports_default_vlan(tmp_path):
    destination_folder = copy_example(tmp_path)
    try:
        add_switch(destination_folder)
        result = _validate(destination_folder)
        switch = _ecu(result).switches[0]
        assert [p.default_vlan_id for p in switch.ports] == [1, 1]
    finally:
        _cleanup(destination_folder)


"""
============================================================
TEST NAME: Switch VLAN membership over ports loads
RULE / CONSTRAINT: A VLAN maps a set of switch
    ports into a single Layer-2 broadcast/forwarding domain.
============================================================

       FLYNCWORKSPACE (copy of examples/flync_example)
            |
         ECU ecu_l2
            |  switches=[sw1]
        Switch sw1
            |  ports=[sp0, sp1]
            |  vlans=[VLAN10(ports sp0, sp1)]

Expected: workspace loads as VALID/WARNING; VLAN10 membership
resolves to [sp0, sp1].
"""


def test_switch_vlan_membership(tmp_path):
    destination_folder = copy_example(tmp_path)
    try:
        add_switch(destination_folder)
        result = _validate(destination_folder)
        switch = _ecu(result).switches[0]
        vlan = switch.vlans[0]
        assert vlan.id == 10
        assert vlan.ports == ["sp0", "sp1"]
    finally:
        _cleanup(destination_folder)


"""
============================================================
TEST NAME: Multiple VLANs on a switch load
RULE / CONSTRAINT: A switch may host several
    independent VLAN broadcast domains.
============================================================

       FLYNCWORKSPACE (copy of examples/flync_example)
            |
         ECU ecu_l2
            |  switches=[sw1]
        Switch sw1
            |  ports=[sp0, sp1]
            |  vlans=[VLAN10, VLAN20]

Expected: workspace loads as VALID/WARNING; two VLAN entries
exist with distinct ids 10 and 20.
"""


def test_switch_multiple_vlans(tmp_path):
    destination_folder = copy_example(tmp_path)
    try:
        add_switch(destination_folder, SWITCH_TWO_VLANS_YAML)
        result = _validate(destination_folder)
        switch = _ecu(result).switches[0]
        assert {v.id for v in switch.vlans} == {10, 20}
    finally:
        _cleanup(destination_folder)


"""
============================================================
TEST NAME: Unique silicon port numbers load
RULE / CONSTRAINT: Each switch port is uniquely
    identified by its silicon hardware port number.
============================================================

       FLYNCWORKSPACE (copy of examples/flync_example)
            |
         ECU ecu_l2
            |  switches=[sw1]
        Switch sw1
            |  ports=[sp0(silicon 0), sp1(silicon 1)]

Expected: workspace loads as VALID/WARNING; the switch exposes
two distinct silicon port numbers.
"""


def test_switch_port_silicon_numbers(tmp_path):
    destination_folder = copy_example(tmp_path)
    try:
        add_switch(destination_folder, SWITCH_DEFAULT_YAML)
        result = _validate(destination_folder)
        switch = _ecu(result).switches[0]
        nums = [p.silicon_port_no for p in switch.ports]
        assert nums == [0, 1]
        assert len(set(nums)) == len(nums)
    finally:
        _cleanup(destination_folder)


"""
============================================================
TEST NAME: Switch port with an MII config loads
RULE / CONSTRAINT: A switch port may declare an
    MII-family media-independent interface.
============================================================

       FLYNCWORKSPACE (copy of examples/flync_example)
            |
         ECU ecu_l2
            |  switches=[sw1]
        Switch sw1
            |  ports=[sp0(mii RMII 100), sp1]

Expected: workspace loads as VALID/WARNING; sp0 exposes an
RMII config at 100 Mbit/s.
"""


def test_switch_port_mii_config(tmp_path):
    destination_folder = copy_example(tmp_path)
    try:
        add_switch(destination_folder, SWITCH_PORT_MII_YAML)
        result = _validate(destination_folder)
        switch = _ecu(result).switches[0]
        assert switch.ports[0].mii_config is not None
        assert switch.ports[0].mii_config.type == "rmii"
        assert switch.ports[0].mii_config.speed == 100
    finally:
        _cleanup(destination_folder)


"""
============================================================
TEST NAME: Internal topology ECU-port<->switch-port loads
RULE / CONSTRAINT: An ECU port is
    wired to a switch port through the internal topology so a
    Layer-2 path exists between the two.
============================================================

       FLYNCWORKSPACE (copy of examples/flync_example)
            |
         ECU ecu_l2
            |  ports=[p0]
            |  switches=[sw1]
            |  topology: conn1 ecu_port_to_switch_port
            |              p0 <-> sp0

Expected: workspace loads as VALID/WARNING; the topology
connection resolves so switch port sp0 is bound to ECU port p0.
"""


def test_switch_ecu_port_topology(tmp_path):
    destination_folder = copy_example(tmp_path)
    try:
        write_ecu_ports(destination_folder, PORT_P0_MDI100, topology_yaml=TOPOLOGY_ECU_TO_SWITCH)
        (destination_folder / "ecus" / "ecu_l2" / "switches" / "sw1").mkdir(parents=True)
        (destination_folder / "ecus" / "ecu_l2" / "switches" / "sw1" / "switch.flync.yaml").write_text(SWITCH_DEFAULT_YAML, encoding="utf-8")
        result = _validate(destination_folder)
        ecu = _ecu(result)
        switch = ecu.switches[0]
        bound = switch.ports[0].connected_component
        assert bound is not None
        assert bound.name == "p0"
        conns = ecu.topology.connections
        assert len(conns) >= 1
        assert conns[0].root.type == "ecu_port_to_switch_port"
    finally:
        _cleanup(destination_folder)


"""
============================================================
TEST NAME: Controller interface virtual interfaces (VLANs) load
RULE / CONSTRAINT: A controller Ethernet interface
    may stack multiple VLAN-tagged virtual interfaces, each with
    a unique VLAN id.
============================================================

       FLYNCWORKSPACE (copy of examples/flync_example)
            |
         ECU ecu_l2
            |  controllers=[ctrl1]
        Controller ctrl1
            |  ethernet_interfaces=[iface1]
        iface1: mac 00:11:03:02:02:02, RMII 100
            |  virtual_interfaces=[viface1 (vlan 10, 10.0.20.1)]

Expected: workspace loads as VALID/WARNING; the interface carries
one virtual interface with vlanid 10.
"""


def test_interface_virtual_interfaces(tmp_path):
    destination_folder = copy_example(tmp_path)
    try:
        add_controller_interface(destination_folder, INTERFACE_VIFACE1)
        result = _validate(destination_folder)
        iface = _ecu(result).controllers[0].ethernet_interfaces[0].interface_config
        assert len(iface.virtual_interfaces) == 1
        assert iface.virtual_interfaces[0].vlanid == 10
        assert iface.virtual_interfaces[0].name == "viface1"
    finally:
        _cleanup(destination_folder)
