"""Unit tests for the instrumentation overlay's FLYNC-independent structural rules.

Covers the list-level local validation (unique CMP interface id flattened across all points and
port captures; unique measurement point names) which run at parse time, without a bound FLYNC
model - exercised both directly on the helper and through the ``Instrumentation`` wrapper model -
and that the overlay is genuinely optional.
"""

import pytest
from pydantic import TypeAdapter, ValidationError
from pydantic_core import PydanticCustomError

from flync.model.flync_4_instrumentation import Instrumentation, MeasurementPointType, validate_measurement_points_local
from tests.error_assertions import assert_bind_error, assert_single_error


def _valid_points():
    return TypeAdapter(list[MeasurementPointType]).validate_python(
        [{"name": "tap1", "type": "can_bus", "bus": "SomeBus", "payload_types": ["can"], "interface_id": 1}]
    )


def _append(points, point):
    return points + TypeAdapter(list[MeasurementPointType]).validate_python([point])


def _raises_local_error(points) -> pytest.ExceptionInfo[PydanticCustomError]:
    with pytest.raises(PydanticCustomError) as exc_info:
        validate_measurement_points_local(points)
    return exc_info


def test_valid_list_parses_cleanly():
    points = _valid_points()

    point = points[0]
    # References are NOT resolved yet - that only happens via bind().
    assert point.observed_bus is None
    assert point.name == "tap1"
    assert point.interface_ids() == [1]


def test_rejects_duplicate_interface_id():
    data = list(_valid_points())
    data = _append(data, {"name": "tap2", "type": "lin_bus", "bus": "SomeOtherBus", "interface_id": 1})

    exc_info = _raises_local_error(data)
    assert_bind_error(exc_info, "FLYNC-INS-MAJ-UNIQ-350", "Duplicate interface_id 1 in MeasurementPoint 'tap2'")


def test_rejects_interface_id_colliding_with_a_port_capture_id():
    """The uniqueness rule is over the flattened id space - a link direction id counts like a bus id."""
    data = list(_valid_points())
    data = _append(
        data,
        TypeAdapter(MeasurementPointType).validate_python(
            {"name": "link", "type": "ethernet_ports", "ports": [{"ecu_port": "p1", "interface_id": 1}, {"ecu_port": "p2", "interface_id": 2}]}
        ),
    )

    exc_info = _raises_local_error(data)
    assert_bind_error(exc_info, "FLYNC-INS-MAJ-UNIQ-350", "Duplicate interface_id 1 in MeasurementPoint 'link'")


def test_rejects_duplicate_name():
    data = list(_valid_points())
    data = _append(data, {"name": "tap1", "type": "lin_bus", "bus": "SomeOtherBus", "interface_id": 2})

    exc_info = _raises_local_error(data)
    assert_bind_error(exc_info, "FLYNC-INS-MAJ-UNIQ-351", "Duplicate MeasurementPoint name 'tap1'")


def test_allows_distinct_ids_and_names():
    points = _append(list(_valid_points()), {"name": "tap2", "type": "lin_bus", "bus": "SomeOtherBus", "interface_id": 2})

    validate_measurement_points_local(points)

    assert [p.name for p in points] == ["tap1", "tap2"]


def test_empty_list_is_valid():
    """An empty instrumentation list is structurally valid - a workspace that declares the
    overlay but has not populated it yet."""
    validate_measurement_points_local([])


def test_none_list_is_valid():
    """The instrumentation overlay is optional - ``None`` (no file) is allowed and skipped."""
    validate_measurement_points_local(None)


def _raises_wrapper_error(points) -> pytest.ExceptionInfo[ValidationError]:
    with pytest.raises(ValidationError) as exc_info:
        Instrumentation(measurement_points=points)
    return exc_info


def test_wrapper_runs_local_validation():
    """The ``Instrumentation`` wrapper enforces the same structural rules at build time."""
    data = _append(list(_valid_points()), {"name": "tap2", "type": "lin_bus", "bus": "SomeOtherBus", "interface_id": 1})

    exc_info = _raises_wrapper_error(data)
    assert_single_error(exc_info, "FLYNC-INS-MAJ-UNIQ-350", "Duplicate interface_id 1 in MeasurementPoint 'tap2'")


def test_wrapper_accepts_clean_points():
    wrapper = Instrumentation(measurement_points=_valid_points())

    assert wrapper.measurement_points[0].name == "tap1"


def test_wrapper_without_points_is_valid():
    """``measurement_points`` is itself optional inside the wrapper (absent file -> ``None``)."""
    assert Instrumentation(measurement_points=None).measurement_points is None
