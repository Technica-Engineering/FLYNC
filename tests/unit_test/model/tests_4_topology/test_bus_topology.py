"""Unit tests for the runtime-derived CAN/LIN bus topology (:mod:`flync.model.flync_4_topology.bus_topology`)."""

from types import SimpleNamespace

import pytest
from pydantic_core import PydanticCustomError

from flync.model.flync_4_ecu.can_interface import CANInterface
from flync.model.flync_4_ecu.lin_interface import LINMasterInterface, LINSlaveInterface
from flync.model.flync_4_topology.bus_topology import (
    BusAttachmentPoint,
    CANBusTopology,
    LINBusTopology,
    build_bus_topologies,
    validate_bus_topologies,
)

# ---------------------------------------------------------------------------
# Helpers — lightweight stand-ins for the FLYNCModel container hierarchy.
# build_bus_topologies only reads .ecus / .controllers / .can_interfaces /
# .lin_interfaces / .name / .bus_ref and communication.channels.can_buses/lin_buses.
# ---------------------------------------------------------------------------


def _controller(name, can_ifaces=None, lin_ifaces=None):
    return SimpleNamespace(name=name, can_interfaces=can_ifaces or [], lin_interfaces=lin_ifaces or [])


def _ecu(name, controllers):
    return SimpleNamespace(name=name, controllers=controllers)


def _model(ecus, can_buses=None, lin_buses=None):
    channels = SimpleNamespace(can_buses=can_buses, lin_buses=lin_buses)
    return SimpleNamespace(ecus=ecus, communication=SimpleNamespace(channels=channels))


def _bus(name):
    return SimpleNamespace(name=name)


def _can_iface(name, bus_ref):
    return CANInterface(name=name, bus_ref=bus_ref)


def _lin_master(name, bus_ref):
    return LINMasterInterface(name=name, bus_ref=bus_ref, lin_protocol="2.1", p2_min=50.0, st_min=10.0)


def _lin_slave(name, bus_ref, nad=0x20):
    return LINSlaveInterface(name=name, bus_ref=bus_ref, lin_protocol="2.1", configured_nad=nad, initial_nad=nad)


def _can_attachment(bus_name="DiagCAN"):
    return BusAttachmentPoint(ecu_name="E1", controller_name="C1", interface_name="ci", role="can_node")


def _lin_attachment(role, iface_name="li"):
    return BusAttachmentPoint(ecu_name="E1", controller_name="C1", interface_name=iface_name, role=role)


# ---------------------------------------------------------------------------
# Topology model classes
# ---------------------------------------------------------------------------


def test_can_bus_topology_defaults():
    topo = CANBusTopology(bus_name="DiagCAN")
    assert topo.bus_type == "can"
    assert topo.attachments == []


def test_lin_bus_topology_master_and_slaves_properties():
    master = _lin_attachment("lin_master", "m")
    slave1 = _lin_attachment("lin_slave", "s1")
    slave2 = _lin_attachment("lin_slave", "s2")
    topo = LINBusTopology(bus_name="BodyLIN", attachments=[master, slave1, slave2])
    assert topo.bus_type == "lin"
    assert topo.master is master
    assert topo.slaves == [slave1, slave2]


def test_lin_bus_topology_master_is_none_when_absent():
    topo = LINBusTopology(bus_name="BodyLIN", attachments=[_lin_attachment("lin_slave")])
    assert topo.master is None
    assert len(topo.slaves) == 1


# ---------------------------------------------------------------------------
# build_bus_topologies
# ---------------------------------------------------------------------------


def test_build_groups_can_interfaces_across_ecus_by_bus_ref():
    ecu1 = _ecu("E1", [_controller("C1", can_ifaces=[_can_iface("ci1", "DiagCAN")])])
    ecu2 = _ecu("E2", [_controller("C2", can_ifaces=[_can_iface("ci2", "DiagCAN")])])
    can_topos, lin_topos, can_defs, lin_defs = build_bus_topologies(_model([ecu1, ecu2], can_buses=[_bus("DiagCAN")]))

    assert lin_topos == []
    assert len(can_topos) == 1
    topo = can_topos[0]
    assert topo.bus_name == "DiagCAN"
    assert len(topo.attachments) == 2
    assert {a.ecu_name for a in topo.attachments} == {"E1", "E2"}
    assert all(a.role == "can_node" for a in topo.attachments)


def test_build_assigns_lin_master_and_slave_roles():
    ecu = _ecu(
        "E1",
        [_controller("C1", lin_ifaces=[_lin_master("m", "BodyLIN"), _lin_slave("s", "BodyLIN")])],
    )
    _can_topos, lin_topos, _can_defs, _lin_defs = build_bus_topologies(_model([ecu], lin_buses=[_bus("BodyLIN")]))

    assert len(lin_topos) == 1
    topo = lin_topos[0]
    assert topo.master is not None and topo.master.role == "lin_master"
    assert len(topo.slaves) == 1


def test_build_seeds_zero_attachment_entry_for_unused_declared_bus():
    ecu = _ecu("E1", [_controller("C1", can_ifaces=[_can_iface("ci", "DiagCAN")])])
    can_topos, _lin_topos, _can_defs, _lin_defs = build_bus_topologies(_model([ecu], can_buses=[_bus("DiagCAN"), _bus("UnusedCAN")]))

    by_name = {t.bus_name: t for t in can_topos}
    assert set(by_name) == {"DiagCAN", "UnusedCAN"}
    assert by_name["UnusedCAN"].attachments == []


def test_build_returns_none_defs_when_no_channels():
    ecu = _ecu("E1", [_controller("C1", can_ifaces=[_can_iface("ci", "DiagCAN")])])
    model = SimpleNamespace(ecus=[ecu], communication=None)
    _can_topos, _lin_topos, can_defs, lin_defs = build_bus_topologies(model)
    assert can_defs is None
    assert lin_defs is None


# ---------------------------------------------------------------------------
# validate_bus_topologies — raising (major) cases
# ---------------------------------------------------------------------------


def test_validate_raises_on_unknown_can_bus_ref():
    topo = CANBusTopology(bus_name="Ghost", attachments=[_can_attachment()])
    with pytest.raises(PydanticCustomError):
        validate_bus_topologies([topo], [], {"Real": _bus("Real")}, {})


def test_validate_raises_on_multiple_lin_masters():
    topo = LINBusTopology(
        bus_name="BodyLIN",
        attachments=[_lin_attachment("lin_master", "m1"), _lin_attachment("lin_master", "m2")],
    )
    with pytest.raises(PydanticCustomError):
        validate_bus_topologies([], [topo], {}, {"BodyLIN": _bus("BodyLIN")})


# ---------------------------------------------------------------------------
# validate_bus_topologies — non-raising cases (warnings are silently dropped
# outside a validate_with_policy context, so we only assert no error is raised).
# ---------------------------------------------------------------------------


def test_validate_accepts_single_lin_master_with_slaves():
    topo = LINBusTopology(
        bus_name="BodyLIN",
        attachments=[_lin_attachment("lin_master", "m"), _lin_attachment("lin_slave", "s")],
    )
    validate_bus_topologies([], [topo], {}, {"BodyLIN": _bus("BodyLIN")})


def test_validate_accepts_known_multi_node_can_bus():
    topo = CANBusTopology(
        bus_name="DiagCAN",
        attachments=[
            BusAttachmentPoint(ecu_name="E1", controller_name="C1", interface_name="a", role="can_node"),
            BusAttachmentPoint(ecu_name="E2", controller_name="C2", interface_name="b", role="can_node"),
        ],
    )
    validate_bus_topologies([topo], [], {"DiagCAN": _bus("DiagCAN")}, {})


def test_validate_tolerates_single_node_and_unused_bus_warnings():
    single = CANBusTopology(bus_name="DiagCAN", attachments=[_can_attachment()])
    unused = CANBusTopology(bus_name="UnusedCAN")
    # Both only emit warnings; neither should raise.
    validate_bus_topologies([single, unused], [], {"DiagCAN": _bus("DiagCAN"), "UnusedCAN": _bus("UnusedCAN")}, {})
