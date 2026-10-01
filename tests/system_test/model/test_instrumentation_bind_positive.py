"""
Positive tests: binding a set of measurement points against a self-contained FLYNC model resolves
each reference to the real bus, segment or port it names.

The model is built programmatically (``make_instrumentation_model``) rather than loaded from an
example workspace, so the bind behaviour is exercised without depending on the bundled examples.
"""

from pydantic import TypeAdapter

from flync.model.flync_4_bus import CANBus, LINBus
from flync.model.flync_4_ecu import ECUPort
from flync.model.flync_4_instrumentation import (
    EthernetBusMeasurementPoint,
    EthernetPortsMeasurementPoint,
    MeasurementPointType,
    bind_measurement_points,
)
from flync.model.flync_4_topology import EthernetMultidropConnection
from tests.model_builders import make_instrumentation_model, make_model


def _points():
    """Validated raw point dicts covering each medium, none sharing an interface id."""
    return TypeAdapter(list[MeasurementPointType]).validate_python(
        [
            {"name": "body_can", "type": "can_bus", "bus": "BodyCAN", "payload_types": ["can"], "interface_id": 0x00020001},
            {"name": "diagnostics_can_fd", "type": "can_bus", "bus": "DiagCAN", "payload_types": ["can", "can_fd"], "interface_id": 0x00020002},
            {"name": "body_lin", "type": "lin_bus", "bus": "BodyLIN", "interface_id": 0x00020003},
            {
                "name": "gateway_to_hpc_link",
                "type": "ethernet_ports",
                "ports": [
                    {"ecu_port": "zgw_p1", "interface_id": 0x00010001},
                    {"ecu_port": "hpc1_p5", "interface_id": 0x00010002},
                ],
            },
            {"name": "rear_lamp_segment_bus", "type": "ethernet_bus", "bus": "RearLampSegment", "interface_id": 0x00010003},
        ]
    )


def _bound_by_name():
    model = make_instrumentation_model()
    points = _points()
    bind_measurement_points(points, model)
    return {point.name: point for point in points}


def test_bus_points_resolve_to_real_buses():
    """CAN and LIN points bind ``observed_bus`` to the real bus of that name from the channels."""
    points = _bound_by_name()

    body_can = points["body_can"]
    assert isinstance(body_can.observed_bus, CANBus)
    assert body_can.observed_bus.name == "BodyCAN"
    assert body_can.captured_payload_types() == ["can"]

    can_fd = points["diagnostics_can_fd"]
    assert can_fd.observed_bus.fd_enabled is True
    assert can_fd.captured_payload_types() == ["can", "can_fd"]

    body_lin = points["body_lin"]
    assert isinstance(body_lin.observed_bus, LINBus)
    assert body_lin.observed_bus.name == "BodyLIN"


def test_ethernet_ports_point_resolves_both_ends_of_the_link():
    """A point-to-point link tapped at both ends resolves each capture to its ECU port and keeps one id per direction."""
    link = _bound_by_name()["gateway_to_hpc_link"]

    assert isinstance(link, EthernetPortsMeasurementPoint)
    assert [capture.ecu_port for capture in link.ports] == ["zgw_p1", "hpc1_p5"]
    assert all(isinstance(capture.port, ECUPort) for capture in link.ports)
    assert link.interface_ids() == [0x00010001, 0x00010002]


def test_ethernet_bus_point_resolves_the_shared_segment():
    """An Ethernet shared-medium point binds ``observed_segment`` to the multidrop connection of that id."""
    segment = _bound_by_name()["rear_lamp_segment_bus"]

    assert isinstance(segment, EthernetBusMeasurementPoint)
    assert isinstance(segment.observed_segment, EthernetMultidropConnection)
    assert segment.observed_segment.id == "RearLampSegment"


def test_unbound_points_leave_references_none():
    """Before binding (the ordinary construction state), no reference is resolved."""
    points = _points()

    for point in points:
        assert getattr(point, "observed_bus", None) is None
        assert getattr(point, "observed_segment", None) is None


def test_model_without_instrumentation_is_none_and_binds_as_noop():
    """The overlay is optional at the model level: a model with no instrumentation stays ``None``
    and binding an absent list is a no-op."""
    model = make_model()

    assert model.instrumentation is None
    bind_measurement_points(None, model)
