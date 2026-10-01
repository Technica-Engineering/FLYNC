"""
Negative system tests: FLYNC-dependent validation rules, only observable through binding the
measurement points against a loaded FLYNC model.
"""

import pytest
from pydantic import TypeAdapter
from pydantic_core import PydanticCustomError

from flync.model.flync_4_instrumentation import MeasurementPointType, bind_measurement_points
from tests.error_assertions import assert_bind_error


def _points(point: dict) -> list[MeasurementPointType]:
    """Validate one raw point dict into a concrete :class:`MeasurementPoint` under its ``name``."""
    return TypeAdapter(list[MeasurementPointType]).validate_python([{"name": "mp1", **point}])


def _bind_error(points: list[MeasurementPointType], flync_model) -> pytest.ExceptionInfo[PydanticCustomError]:
    with pytest.raises(PydanticCustomError) as exc_info:
        bind_measurement_points(points, flync_model)
    return exc_info


def test_bind_rejects_unknown_can_bus(flync_model):
    points = _points({"type": "can_bus", "bus": "NoSuchBus", "payload_types": ["can"], "interface_id": 1})

    exc_info = _bind_error(points, flync_model)
    assert_bind_error(exc_info, "FLYNC-INS-MAJ-REF-353", "taps unknown CAN bus 'NoSuchBus'")


def test_bind_rejects_unknown_lin_bus(flync_model):
    points = _points({"type": "lin_bus", "bus": "NoSuchBus", "interface_id": 1})

    exc_info = _bind_error(points, flync_model)
    assert_bind_error(exc_info, "FLYNC-INS-MAJ-REF-354", "taps unknown LIN bus 'NoSuchBus'")


def test_bind_rejects_unknown_ethernet_segment(flync_model):
    points = _points({"type": "ethernet_bus", "bus": "NoSuchSegment", "interface_id": 1})

    exc_info = _bind_error(points, flync_model)
    assert_bind_error(exc_info, "FLYNC-INS-MAJ-REF-355", "taps unknown Ethernet segment 'NoSuchSegment'")


def test_bind_rejects_a_lin_bus_name_under_the_can_type(flync_model):
    """A LIN bus name under ``type: can_bus`` resolves to nothing - the namespaces are separate, and
    the error says CAN, not the generic 'unknown element' the pre-discriminated model produced."""
    points = _points({"type": "can_bus", "bus": "BodyLIN", "payload_types": ["can"], "interface_id": 1})

    exc_info = _bind_error(points, flync_model)
    assert_bind_error(exc_info, "FLYNC-INS-MAJ-REF-353", "taps unknown CAN bus 'BodyLIN'")


def test_bind_rejects_unknown_ecu_port(flync_model):
    points = _points({"type": "ethernet_ports", "ports": [{"ecu_port": "no_such_port", "interface_id": 1}]})

    exc_info = _bind_error(points, flync_model)
    assert_bind_error(exc_info, "FLYNC-INS-MAJ-REF-356", "taps unknown ECU port 'no_such_port'")


@pytest.mark.parametrize(
    ("ports", "error_id", "fragment"),
    [
        pytest.param(
            [{"ecu_port": "zgw_p1", "interface_id": 1}, {"ecu_port": "hpc1_p1", "interface_id": 2}],
            "FLYNC-INS-MAJ-CONS-359",
            "not the two ends of one",
            id="different-links",
        ),
        pytest.param(
            [{"ecu_port": "z1_p2", "interface_id": 1}, {"ecu_port": "rear_lamp_left_p1", "interface_id": 2}],
            "FLYNC-INS-MAJ-CONS-359",
            "not the two ends of one",
            id="same-multidrop-segment",
        ),
    ],
)
def test_bind_requires_two_ports_to_share_a_connection(flync_model, ports, error_id, fragment):
    """The two ports of an ``ethernet_ports`` point must be the two ends of the same
    ``ecu_port_to_ecu_port`` connection - two ends of different links, or two nodes of one shared
    segment, are both tap-geometry mistakes."""
    points = _points({"type": "ethernet_ports", "ports": ports})

    exc_info = _bind_error(points, flync_model)
    assert_bind_error(exc_info, error_id, fragment)


def test_bind_accepts_two_ports_of_one_connection(flync_model):
    """The control for the rule above: the real pair of a connection binds cleanly."""
    points = _points({"type": "ethernet_ports", "ports": [{"ecu_port": "zgw_p1", "interface_id": 1}, {"ecu_port": "hpc1_p5", "interface_id": 2}]})

    bind_measurement_points(points, flync_model)

    link = points[0]
    assert [capture.ecu_port for capture in link.ports] == ["zgw_p1", "hpc1_p5"]
    assert all(capture.port is not None for capture in link.ports)


def test_bind_rejects_can_fd_payload_on_a_non_fd_bus(flync_model):
    points = _points({"type": "can_bus", "bus": "BodyCAN", "payload_types": ["can_fd"], "interface_id": 1})

    exc_info = _bind_error(points, flync_model)
    assert_bind_error(exc_info, "FLYNC-INS-MAJ-COMP-357", "bus 'BodyCAN' does not have fd_enabled=True")


def test_bind_requires_can_fd_payload_on_an_fd_bus(flync_model):
    points = _points({"type": "can_bus", "bus": "DiagCAN", "payload_types": ["can"], "interface_id": 1})

    exc_info = _bind_error(points, flync_model)
    assert_bind_error(exc_info, "FLYNC-INS-MAJ-COMP-358", "does not declare payload_type 'can_fd'")
