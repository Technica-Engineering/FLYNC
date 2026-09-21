"""Unit tests for MeasurementPoint's structural (FLYNC-independent) validation.

FLYNC-dependent ``observes`` resolution against the real FLYNC model (physical vs. VLAN
sub-interface, unresolved refs, payload_type/medium compatibility) is covered in
tests/system_test/model/test_measurements_bind_positive.py and test_measurements_bind_negative.py.
"""

import pytest
from pydantic import ValidationError
from pydantic_core import PydanticCustomError

from flync.model.flync_4_measurements import MeasurementPoint


def test_measurement_point_parses_cleanly_and_observed_is_empty_before_bind():
    interface = MeasurementPoint(name="tap1", interface_id=1, payload_types=["can"], observes=["SomeBus"])

    assert interface.name == "tap1"
    assert interface.interface_id == 1
    assert interface.payload_types == ["can"]
    assert interface.observes == ["SomeBus"]
    # `observes` entries are NOT resolved yet - that only happens via .bind().
    assert interface.observed == []


def test_validate_payload_types_distinct_rejects_duplicate_payload_type():
    with pytest.raises(ValidationError, match="more than once"):
        MeasurementPoint(name="tap1", interface_id=1, payload_types=["can", "can"], observes=["SomeBus"])


def test_bind_rejects_ethernet_interface_ref_ambiguous_between_physical_and_virtual():
    """A name matching both a physical EthernetInterface and a VLAN sub-interface (something
    FLYNC's own model does not itself prevent) must be rejected, not silently resolved to
    whichever dict happens to be checked first."""
    interface = MeasurementPoint(name="tap1", interface_id=1, payload_types=["ethernet"], observes=["shared_name"])

    with pytest.raises(PydanticCustomError, match="ambiguous"):
        interface.bind(
            buses_by_name={},
            ethernet_interfaces_by_name={"shared_name": object()},
            virtual_interfaces_by_name={"shared_name": object()},
        )
