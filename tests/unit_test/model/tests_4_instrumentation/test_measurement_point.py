"""Unit tests for the MeasurementPoint discriminated union's structural (FLYNC-independent) validation.

FLYNC-dependent reference resolution (unknown buses/segments/ports, the two-port connection rule,
CAN FD payload compatibility) is covered in
tests/system_test/model/test_instrumentation_bind_positive.py and test_instrumentation_bind_negative.py.
"""

import pytest
from pydantic import TypeAdapter, ValidationError

from flync.model.flync_4_instrumentation import (
    CANBusMeasurementPoint,
    EthernetBusMeasurementPoint,
    EthernetPortsMeasurementPoint,
    LINBusMeasurementPoint,
    MeasurementPointType,
)
from tests.error_assertions import assert_single_error

_ADAPTER = TypeAdapter(list[MeasurementPointType])


def _points():
    return [
        {"name": "can1", "type": "can_bus", "bus": "BodyCAN", "payload_types": ["can"], "interface_id": 1},
        {"name": "lin1", "type": "lin_bus", "bus": "BodyLIN", "interface_id": 2},
        {"name": "ethbus", "type": "ethernet_bus", "bus": "RearLampSegment", "interface_id": 3},
        {
            "name": "p2p",
            "type": "ethernet_ports",
            "ports": [{"ecu_port": "zgw_p1", "interface_id": 4}, {"ecu_port": "hpc1_p5", "interface_id": 5}],
        },
    ]


def test_discriminated_union_resolves_every_type_to_its_class():
    points = TypeAdapter(list[MeasurementPointType]).validate_python(_points())

    assert [type(p) for p in points] == [
        CANBusMeasurementPoint,
        LINBusMeasurementPoint,
        EthernetBusMeasurementPoint,
        EthernetPortsMeasurementPoint,
    ]
    assert [p.interface_ids() for p in points] == [[1], [2], [3], [4, 5]]
    assert [p.captured_payload_types() for p in points] == [["can"], ["lin"], ["ethernet"], ["ethernet"]]
    # References stay unresolved until bind() runs.
    assert points[0].observed_bus is None
    assert points[3].ports[0].port is None


def test_unknown_measurement_point_type_is_rejected():
    data = {"name": "x", "type": "nope", "bus": "BodyCAN", "interface_id": 1}

    with pytest.raises(ValidationError) as exc_info:
        _ADAPTER.validate_python([data])
    assert_single_error(exc_info, None, "nope")


def test_rejects_duplicate_payload_types():
    with pytest.raises(ValidationError) as exc_info:
        _ADAPTER.validate_python([_points()[0] | {"payload_types": ["can", "can"]}])
    assert_single_error(exc_info, "FLYNC-INS-MAJ-UNIQ-352", "declares payload_type 'can' more than once")


@pytest.mark.parametrize("num_ports", [0, 3], ids=["none", "three"])
def test_rejects_port_count_outside_one_or_two(num_ports):
    ports = [{"ecu_port": f"port{i}", "interface_id": i} for i in range(num_ports)]

    with pytest.raises(ValidationError) as exc_info:
        _ADAPTER.validate_python([{"name": "p2p", "type": "ethernet_ports", "ports": ports}])
    assert_single_error(exc_info, None, "ports")


def test_rejects_same_port_twice_in_one_point():
    ports = [{"ecu_port": "zgw_p1", "interface_id": 4}, {"ecu_port": "zgw_p1", "interface_id": 5}]

    with pytest.raises(ValidationError) as exc_info:
        _ADAPTER.validate_python([{"name": "p2p", "type": "ethernet_ports", "ports": ports}])
    assert_single_error(exc_info, "FLYNC-INS-MAJ-UNIQ-360", "captures port 'zgw_p1' more than once")


def test_interface_id_above_32_bit_is_rejected():
    with pytest.raises(ValidationError) as exc_info:
        _ADAPTER.validate_python([_points()[0] | {"interface_id": 2**32}])
    assert_single_error(exc_info, None, "interface_id")
