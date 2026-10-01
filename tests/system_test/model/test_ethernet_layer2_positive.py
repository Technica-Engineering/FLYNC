"""System-level positive tests for the FLYNC Ethernet Layer 2 feature."""

import json

from flync.model.flync_4_ecu.controller import (
    Controller,
    EthernetInterface,
    EthernetInterfaceConfig,
    VirtualControllerInterface,
)
from flync.model.flync_4_ecu.ecu import ECU
from flync.model.flync_4_ecu.internal_topology import InternalTopology
from flync.model.flync_4_ecu.phy import (
    BASET,
    BASET1,
    BASET1S,
    RGMII,
    SGMII,
)
from flync.model.flync_4_ecu.port import ECUPort
from flync.model.flync_4_ecu.switch import Switch, SwitchConfig, SwitchPort
from flync.model.flync_4_ecu.vlan_entry import VLANEntry
from flync.model.flync_4_metadata.metadata import BaseVersion, ECUMetadata, EmbeddedMetadata, SystemMetadata
from flync.model.flync_4_topology.ethernet_topology import EthernetTopology, FLYNCTopology
from flync.model.flync_model import FLYNCModel

FLYNC_VERSION = "0.14.0"


def _version() -> BaseVersion:
    return BaseVersion(version=FLYNC_VERSION)


def _embedded() -> EmbeddedMetadata:
    return EmbeddedMetadata(type="embedded", author="TestTeam", target_system="Device1", compatible_flync_version=_version())


def _ecu_metadata() -> ECUMetadata:
    return ECUMetadata(type="ecu", author="TestTeam", compatible_flync_version=_version())


def _system_metadata() -> SystemMetadata:
    return SystemMetadata(type="system", release=_version(), author="TestTeam", compatible_flync_version=_version())


def _topology() -> FLYNCTopology:
    return FLYNCTopology(system_topology=EthernetTopology(connections=[]))


def _default_ecu_port() -> ECUPort:
    return ECUPort(name="p0", mdi_config=BASET1(speed=100, role="master", duplex="full", autonegotiation=False))


def _full_model(*, ports=None, controllers=None, switches=None) -> FLYNCModel:
    """Assemble a complete FLYNCModel around the given Layer-2 components."""
    if controllers or switches:
        ports = ports or [_default_ecu_port()]

    ecu = ECU(
        name="ECU1",
        ports=ports or [],
        controllers=controllers or [],
        switches=switches or [],
        topology=InternalTopology(),
        ecu_metadata=_ecu_metadata(),
    )
    return FLYNCModel(ecus=[ecu], topology=_topology(), metadata=_system_metadata())


def _ecu_with_controller(iface: EthernetInterface) -> FLYNCModel:
    ctrl = Controller(name="CTRL1", controller_metadata=_embedded(), ethernet_interfaces=[iface])
    return _full_model(controllers=[ctrl])


"""
============================================================
TEST NAME: 100BASE-T1 Layer-2 ECU port
RULE / CONSTRAINT: Ethernet Layer 2 includes the
    IEEE 802.3 single-pair PHY at 100 Mb/s, full duplex,
    master/slave (OA L2 spec refs [2] IEEE 802.3bw, [3]).
============================================================

       FLYNCModel
         |
        ECU1
         |  ports=[p0]
      ECUPort p0 (mdi=BASE-T1 100Mb/s full master/slave)

Relationships:
- ECUPort p0 is an Ethernet Layer-2 PHY port of the ECU
- Important configuration:
  - mode "base_t1", speed 100, duplex "full", role "master"
"""


def test_ecu_port_base_t1_100_mbps():
    port = ECUPort(
        name="p0",
        mdi_config=BASET1(speed=100, duplex="full", role="master", autonegotiation=False),
    )
    model = _full_model(ports=[port])

    ecu = next(ecu for ecu in model.ecus if ecu.name == "ECU1")
    port = next(port for port in ecu.ports if port.name == "p0")

    assert port.mdi_config.mode == "base_t1"
    assert port.mdi_config.speed == 100
    assert port.mdi_config.duplex == "full"
    assert port.mdi_config.role == "master"


"""
============================================================
TEST NAME: 1000BASE-T1 Layer-2 ECU port
RULE / CONSTRAINT: Ethernet Layer 2 permits the
    gigabit single-pair PHY (1000 Mb/s) on a port.
============================================================

       FLYNCModel
         |
        ECU1
         |  ports=[p0]
      ECUPort p0 (mdi=BASE-T1 1000Mb/s)

Relationships:
- ECUPort p0 is an Ethernet Layer-2 gigabit PHY port
- Important configuration:
  - mode "base_t1", speed 1000, duplex "full"
"""


def test_ecu_port_base_t1_1000_mbps():
    port = ECUPort(name="p0", mdi_config=BASET1(speed=1000, role="slave"))
    model = _full_model(ports=[port])

    ecu = next(ecu for ecu in model.ecus if ecu.name == "ECU1")
    port = next(port for port in ecu.ports if port.name == "p0")

    assert port.mdi_config.mode == "base_t1"
    assert port.mdi_config.speed == 1000
    assert port.mdi_config.duplex == "full"
    assert port.mdi_config.role == "slave"


"""
============================================================
TEST NAME: BASE-T1S Layer-2 ECU port
RULE / CONSTRAINT: Ethernet Layer 2 permits the
    10BASE-T1S single-pair half-duplex PHY (10 Mb/s).
============================================================

       FLYNCModel
         |
        ECU1
         |  ports=[p0]
      ECUPort p0 (mdi=BASE-T1S 10Mb/s half)

Relationships:
- ECUPort p0 is an Ethernet Layer-2 single-pair half-duplex port
- Important configuration:
  - mode "base_t1s", speed 10, duplex "half", role "master"
"""


def test_ecu_port_base_t1s():
    port = ECUPort(name="p0", mdi_config=BASET1S())
    model = _full_model(ports=[port])

    mdi = model.ecus[0].ports[0].mdi_config
    assert mdi.mode == "base_t1s"
    assert mdi.speed == 10
    assert mdi.duplex == "half"


"""
============================================================
TEST NAME: BASE-T Layer-2 ECU ports (100/1000)
RULE / CONSTRAINT: Ethernet Layer 2 permits
    IEEE 802.3 BASE-T PHYs at 100 and 1000 Mb/s.
============================================================

       FLYNCModel
         |
        ECU1
         |  ports=[p100, p1000]
   ECUPort p100  (BASET 100Mb/s)
   ECUPort p1000 (BASET 1000Mb/s)

Relationships:
- Both are Layer-2 twisted-pair PHY ports of the ECU
- Important configuration:
  - mode "base_t", full duplex, role slave
"""


def test_ecu_port_base_t_100_and_1000():
    p100 = ECUPort(name="p100", mdi_config=BASET(speed=100))
    p1000 = ECUPort(name="p1000", mdi_config=BASET(speed=1000))
    model = _full_model(ports=[p100, p1000])

    speeds = {p.mdi_config.speed for p in model.ecus[0].ports}
    assert speeds == {100, 1000}
    assert {p.mdi_config.mode for p in model.ecus[0].ports} == {"base_t"}


"""
============================================================
TEST NAME: MDI + MII speed consistency (RGMII)
RULE / CONSTRAINT: A Layer-2 port joining a PHY
    (MDI) and a MAC-side interface (MII) must use the same
    link speed on both sides.
============================================================

       FLYNCModel
         |
        ECU1
         |  ports=[p0]
      ECUPort p0
         +-- mdi_config=BASE-T1 speed 1000
         +-- mii_config=RGMII  speed 1000

Relationships:
- mdi and mii belong to the same ECUPort
- Important configuration:
  - matching speed 1000 on both interfaces
"""


def test_ecu_port_mdi_mii_speed_consistency():
    port = ECUPort(name="p0", mdi_config=BASET1(speed=1000, role="slave"), mii_config=RGMII(speed=1000, mode="mac"))
    model = _full_model(ports=[port])

    p = model.ecus[0].ports[0]
    assert p.mdi_config.speed == 1000
    assert p.mii_config.speed == 1000


"""
============================================================
TEST NAME: MDI + MII speed consistency (SGMII)
RULE / CONSTRAINT: A Layer-2 port joining a PHY
    (MDI) and a MAC-side interface (MII) must use the same
    link speed on both sides.
============================================================

       FLYNCModel
         |
        ECU1
         |  ports=[p0]
      ECUPort p0
         +-- mdi_config=BASE-T1 speed 1000
         +-- mii_config=SGMII  speed 1000

Relationships:
- mdi and mii belong to the same ECUPort
- Important configuration:
  - matching speed 1000 on both interfaces
"""


def test_ecu_port_sgmii_speed_consistency():
    port = ECUPort(name="p0", mdi_config=BASET1(speed=1000, role="slave"), mii_config=SGMII(speed=1000, mode="mac"))
    model = _full_model(ports=[port])

    p = model.ecus[0].ports[0]
    assert p.mdi_config.speed == p.mii_config.speed == 1000


"""
============================================================
TEST NAME: switch VLAN membership over existing ports
RULE / CONSTRAINT: A Layer-2 VLAN must map to
    existing member ports so that frames reach the intended
    ports (OA L2 §5.3 VLAN testing).
          VLAN ID within 0-4094.
============================================================

       FLYNCModel
         |
        ECU1
         |  switches=[SW1]
      Switch SW1
         |  ports=[SP1, SP2]
         |  vlans=[VLAN(10, ports=[SP1,SP2])]
   SwitchPort SP1, SP2 (silicon 0,1)  <-- referenced by VLAN

Relationships:
- VLANEntry v1 references existing switch ports SP1 and SP2
- Important configuration:
  - vlan id 10 (valid 802.1Q ID), default_priority 0
"""


def test_switch_vlan_membership_valid():
    sw = Switch(
        name="SW1",
        switch_config=SwitchConfig(
            meta=_embedded(),
            ports=[SwitchPort(name="SP1", silicon_port_no=0, default_vlan_id=1), SwitchPort(name="SP2", silicon_port_no=1, default_vlan_id=2)],
            vlans=[VLANEntry(name="v1", id=10, default_priority=0, ports=["SP1", "SP2"])],
        ),
    )
    model = _full_model(switches=[sw])

    switch = model.ecus[0].switches[0]
    assert switch.name == "SW1"
    assert switch.vlans[0].id == 10
    assert set(switch.vlans[0].ports) == {"SP1", "SP2"}
    assert switch.find_switch_port("SP1").silicon_port_no == 0


"""
============================================================
TEST NAME: switch port identity uniqueness
RULE / CONSTRAINT: Layer-2 switch ports must be
    uniquely identified by name and by silicon port number.
============================================================

       FLYNCModel
         |
        ECU1
         |  switches=[SW1]
      Switch SW1
         |  ports=[SP1(0), SP2(1), SP3(2)]
   three distinct named, numbered ports

Relationships:
- ports are independent Layer-2 switch ports
- Important configuration:
  - distinct names and distinct silicon_port_no values
"""


def test_switch_unique_port_names_and_silicon():
    sw = Switch(
        name="SW1",
        switch_config=SwitchConfig(
            meta=_embedded(),
            ports=[
                SwitchPort(name="SP1", silicon_port_no=0, default_vlan_id=1),
                SwitchPort(name="SP2", silicon_port_no=1, default_vlan_id=2),
                SwitchPort(name="SP3", silicon_port_no=2, default_vlan_id=3),
            ],
            vlans=[],
        ),
    )
    model = _full_model(switches=[sw])

    switch = model.ecus[0].switches[0]
    assert len(switch.ports) == 3
    assert {p.name for p in switch.ports} == {"SP1", "SP2", "SP3"}
    assert {p.silicon_port_no for p in switch.ports} == {0, 1, 2}


"""
============================================================
TEST NAME: multiple unique VLANs on an Ethernet interface
RULE / CONSTRAINT: VLAN IDs on one Ethernet
    interface must be unique.
          VLAN IDs within 0-4094.
============================================================

       FLYNCModel
         |
        ECU1
         |
     Controller CTRL1
         |
   EthernetInterface eth0
      interface_config.virtual_interfaces:
         - safety_vlan    (vlanid 10)
         - infotainment   (vlanid 20)
         - management     (vlanid 30)

Relationships:
- virtual interfaces (VLANs) are stacked on the physical iface
- Important configuration:
  - unique VLAN IDs 10, 20, 30
"""


def test_ethernet_interface_multiple_unique_vlans():
    iface = EthernetInterface(
        name="eth0",
        interface_config=EthernetInterfaceConfig(
            mac_address="3a:7f:1c:9b:4e:02",
            virtual_interfaces=[
                VirtualControllerInterface(name="safety_vlan", vlanid=10, addresses=[]),
                VirtualControllerInterface(name="infotainment", vlanid=20, addresses=[]),
                VirtualControllerInterface(name="management", vlanid=30, addresses=[]),
            ],
        ),
    )
    model = _ecu_with_controller(iface)

    vifs = model.ecus[0].controllers[0].ethernet_interfaces[0].interface_config.virtual_interfaces
    assert {vif.vlanid for vif in vifs} == {10, 20, 30}


"""
============================================================
TEST NAME: VLAN ID boundary values 0 and 4094 are valid
RULE / CONSTRAINT: usable VLAN IDs are 0-4094
    (IEEE 802.1Q 12-bit VID); 4095 is reserved.
============================================================

       FLYNCModel
         |
        ECU1
         |  switches=[SW1]
      Switch SW1
         |  ports=[SP1]
         |  vlans=[VLAN_MIN(id=0), VLAN_MAX(id=4094)]

Relationships:
- both VLAN entries reference existing switch port SP1
- Important configuration:
  - boundary VLAN IDs 0 and 4094 are accepted
"""


def test_vlan_id_boundary_values_valid():
    sw = Switch(
        name="SW1",
        switch_config=SwitchConfig(
            meta=_embedded(),
            ports=[SwitchPort(name="SP1", silicon_port_no=0, default_vlan_id=1)],
            vlans=[
                VLANEntry(name="v_min", id=0, default_priority=0, ports=["SP1"]),
                VLANEntry(name="v_max", id=4094, default_priority=0, ports=["SP1"]),
            ],
        ),
    )
    model = _full_model(switches=[sw])

    ids = {v.id for v in model.ecus[0].switches[0].vlans}
    assert ids == {0, 4094}


"""
============================================================
TEST NAME: Layer-2 port configuration serialization roundtrip
RULE / CONSTRAINT: A valid Layer-2 port
    must survive model serialization and re-validation without
    loss (model roundtrip preserved).
============================================================

       FLYNCModel (before)
         |
        ECU1  ports=[p0] (BASE-T1 1000 + RGMII 1000)
         |
       model_dump / model_validate
         |
       FLYNCModel (after) == dump identical

Relationships:
- complete model is serialized and re-parsed
- Important configuration:
  - PHY speed consistency preserved across roundtrip
"""


def test_ethernet_layer2_model_serialization_roundtrip():
    port = ECUPort(name="p0", mdi_config=BASET1(speed=1000, role="slave"), mii_config=RGMII(speed=1000, mode="mac"))
    model = _full_model(ports=[port])

    dumped = json.loads(model.model_dump_json(by_alias=True))
    rebuilt = FLYNCModel.model_validate(dumped)

    assert json.dumps(rebuilt.model_dump(by_alias=True), sort_keys=True) == json.dumps(model.model_dump(by_alias=True), sort_keys=True)
