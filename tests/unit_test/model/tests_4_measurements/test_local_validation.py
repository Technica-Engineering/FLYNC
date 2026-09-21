"""Unit tests for MeasurementSystem's local validation.

Covers ``interface_id``/``name`` uniqueness across every measurement point in the whole system -
all of which run automatically at parse time, without needing a bound FLYNC model.

Built directly in Python from raw dicts, mirroring how ``*.flync-measurements.yaml`` would be
``yaml.safe_load``-ed.
"""

import copy

import pytest
from pydantic import ValidationError

from flync.model.flync_4_measurements import MeasurementSystem
from tests.error_assertions import assert_single_error


def _valid_data():
    return {
        "measurement_points": [
            {"name": "tap1", "interface_id": 1, "payload_types": ["can"], "observes": ["SomeBus"]},
        ],
    }


def test_valid_measurement_system_parses_cleanly():
    measurement_system = MeasurementSystem(**_valid_data())

    interface = measurement_system.measurement_points[0]
    # `observes` entries are NOT resolved yet - that only happens via .bind().
    assert interface.observed == []
    assert interface.name == "tap1"
    assert interface.interface_id == 1


def test_rejects_duplicate_interface_id():
    data = copy.deepcopy(_valid_data())
    data["measurement_points"].append({"name": "tap2", "interface_id": 1, "payload_types": ["lin"], "observes": ["SomeOtherBus"]})

    with pytest.raises(ValidationError) as exc_info:
        MeasurementSystem(**data)
    assert_single_error(exc_info, "FLYNC-MEA-MAJ-UNIQ-348", "Duplicate MeasurementPoint interface_id 1")


def test_rejects_duplicate_interface_name():
    """name is unique across the whole system - it is the key a later measurement setup uses to
    refer to a measurement point, so it must never be ambiguous."""
    data = copy.deepcopy(_valid_data())
    data["measurement_points"].append({"name": "tap1", "interface_id": 2, "payload_types": ["lin"], "observes": ["SomeOtherBus"]})

    with pytest.raises(ValidationError) as exc_info:
        MeasurementSystem(**data)
    assert_single_error(exc_info, "FLYNC-MEA-MAJ-UNIQ-349", "Duplicate MeasurementPoint name 'tap1'")


def test_allows_distinct_interface_ids_and_names():
    data = copy.deepcopy(_valid_data())
    data["measurement_points"].append({"name": "tap2", "interface_id": 2, "payload_types": ["lin"], "observes": ["SomeOtherBus"]})

    measurement_system = MeasurementSystem(**data)

    assert [i.interface_id for i in measurement_system.measurement_points] == [1, 2]
    assert [i.name for i in measurement_system.measurement_points] == ["tap1", "tap2"]


def test_one_interface_may_observe_several_elements():
    """One interface may observe several elements; separating their traffic is handled
    downstream, based on each frame's own VLAN tag."""
    data = copy.deepcopy(_valid_data())
    data["measurement_points"][0]["observes"] = ["SomeBus", "SomeOtherBus"]

    system = MeasurementSystem(**data)

    assert system.measurement_points[0].observes == ["SomeBus", "SomeOtherBus"]


def test_rejects_missing_observes():
    data = copy.deepcopy(_valid_data())
    del data["measurement_points"][0]["observes"]

    with pytest.raises(ValidationError) as exc_info:
        MeasurementSystem(**data)
    assert_single_error(exc_info, None, "observes")


def test_measurement_system_with_no_interfaces_is_valid():
    """An empty measurement system is structurally valid - a workspace that declares the
    overlay but has not populated it yet."""
    measurement_system = MeasurementSystem()

    assert measurement_system.measurement_points == []
