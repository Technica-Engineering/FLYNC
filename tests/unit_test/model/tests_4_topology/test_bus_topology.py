"""Unit tests for the runtime-derived CAN/LIN bus topology (:mod:`flync.model.flync_4_topology.bus_topology`)."""

from types import SimpleNamespace

import pytest
from pydantic_core import PydanticCustomError

from flync.core.utils.exceptions import _validation_warnings
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
# .lin_interfaces / .name / .bus_ref and
# communication.channels.can_buses/lin_buses.
# ---------------------------------------------------------------------------


def _controller(name, can_ifaces=None, lin_ifaces=None):
    return SimpleNamespace(
        name=name,
        can_interfaces=can_ifaces or [],
        lin_interfaces=lin_ifaces or [],
    )


def _ecu(name, controllers):
    return SimpleNamespace(name=name, controllers=controllers)


def _model(ecus, can_buses=None, lin_buses=None):
    channels = SimpleNamespace(can_buses=can_buses, lin_buses=lin_buses)
    return SimpleNamespace(ecus=ecus, communication=SimpleNamespace(channels=channels))


def _capture_warnings(fn):
    """Run *fn* with an active warning list and return the warnings it emitted."""
    token = _validation_warnings.set([])
    try:
        fn()
        return _validation_warnings.get() or []
    finally:
        _validation_warnings.reset(token)


def _no_attachment_warnings(warnings):
    return [w for w in warnings if "no ECU interface attaches" in w["msg"]]


def _bus(name):
    return SimpleNamespace(name=name)


def _can_iface(name, bus_ref):
    return CANInterface(name=name, bus_ref=bus_ref)


def _j1939_can_iface(name, bus_ref):
    return CANInterface(name=name, bus_ref=bus_ref, j1939_name=1, source_address=0)


def _lin_master(name, bus_ref):
    return LINMasterInterface(name=name, bus_ref=bus_ref, lin_protocol="2.1", p2_min=50.0, st_min=10.0)


def _lin_slave(name, bus_ref, nad=0x20):
    return LINSlaveInterface(name=name, bus_ref=bus_ref, lin_protocol="2.1", configured_nad=nad, initial_nad=nad)


def _can_attachment(bus_name="DiagCAN"):
    return BusAttachmentPoint(ecu_name="E1", controller_name="C1", interface_name="ci", role="can_node")


def _lin_attachment(role, iface_name="li"):
    return BusAttachmentPoint(ecu_name="E1", controller_name="C1", interface_name=iface_name, role=role)


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


def test_build_groups_can_interfaces_across_ecus_by_bus_ref():
    ecu1 = _ecu("E1", [_controller("C1", can_ifaces=[_can_iface("ci1", "DiagCAN")])])
    ecu2 = _ecu("E2", [_controller("C2", can_ifaces=[_can_iface("ci2", "DiagCAN")])])
    can_topos, lin_topos, can_defs, lin_defs, _j1939 = build_bus_topologies(_model([ecu1, ecu2], can_buses=[_bus("DiagCAN")]))

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
    _can_topos, lin_topos, _can_defs, _lin_defs, _j1939 = build_bus_topologies(_model([ecu], lin_buses=[_bus("BodyLIN")]))

    assert len(lin_topos) == 1
    topo = lin_topos[0]
    assert topo.master is not None
    assert topo.master.role == "lin_master"
    assert len(topo.slaves) == 1


def test_build_seeds_zero_attachment_entry_for_unused_declared_bus():
    ecu = _ecu("E1", [_controller("C1", can_ifaces=[_can_iface("ci", "DiagCAN")])])
    can_topos, _lin_topos, _can_defs, _lin_defs, _j1939 = build_bus_topologies(_model([ecu], can_buses=[_bus("DiagCAN"), _bus("UnusedCAN")]))

    by_name = {t.bus_name: t for t in can_topos}
    assert set(by_name) == {"DiagCAN", "UnusedCAN"}
    assert by_name["UnusedCAN"].attachments == []


def test_build_returns_none_defs_when_no_channels():
    ecu = _ecu("E1", [_controller("C1", can_ifaces=[_can_iface("ci", "DiagCAN")])])
    model = SimpleNamespace(ecus=[ecu], communication=None)
    _can_topos, _lin_topos, can_defs, lin_defs, _j1939 = build_bus_topologies(model)
    assert can_defs is None
    assert lin_defs is None


def test_validate_raises_on_unknown_can_bus_ref():
    topo = CANBusTopology(bus_name="Ghost", attachments=[_can_attachment()])
    real = _bus("Real")
    with pytest.raises(PydanticCustomError):
        validate_bus_topologies([topo], [], {"Real": real}, {})


def test_validate_raises_on_multiple_lin_masters():
    topo = LINBusTopology(
        bus_name="BodyLIN",
        attachments=[_lin_attachment("lin_master", "m1"), _lin_attachment("lin_master", "m2")],
    )
    bodylin = _bus("BodyLIN")
    with pytest.raises(PydanticCustomError):
        validate_bus_topologies([], [topo], {}, {"BodyLIN": bodylin})


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


def test_build_collects_j1939_bus_names():
    ecu = _ecu("E1", [_controller("J1939C", can_ifaces=[_j1939_can_iface("j1939_if", "J1939BusCAN")])])
    _can_topos, _lin_topos, _can_defs, _lin_defs, j1939 = build_bus_topologies(_model([ecu], can_buses=[_bus("J1939BusCAN")]))
    assert j1939 == {"J1939BusCAN"}


def test_build_excludes_buses_without_j1939_interface():
    ecu = _ecu("E1", [_controller("C1", can_ifaces=[_can_iface("ci", "BodyCAN")])])
    _can_topos, _lin_topos, _can_defs, _lin_defs, j1939 = build_bus_topologies(_model([ecu], can_buses=[_bus("BodyCAN")]))
    assert j1939 == set()


def test_validate_no_attachment_226_suppressed_for_j1939_bus():
    topo = CANBusTopology(bus_name="J1939BusCAN")  # zero CAN interface attachments
    warnings = _capture_warnings(lambda: validate_bus_topologies([topo], [], {"J1939BusCAN": _bus("J1939BusCAN")}, {}, {"J1939BusCAN"}))
    assert _no_attachment_warnings(warnings) == []


def test_validate_no_attachment_226_emitted_for_plain_can_bus():
    topo = CANBusTopology(bus_name="UnusedCAN")
    warnings = _capture_warnings(lambda: validate_bus_topologies([topo], [], {"UnusedCAN": _bus("UnusedCAN")}, {}, set()))
    assert len(_no_attachment_warnings(warnings)) == 1
    assert "FLYNC-TOP-WARN-CONS-226" in warnings[0]["ctx"]["error_id"]
