"""test service class"""

import ipaddress

import pytest
from pydantic import ValidationError

from flync.core.utils.base_utils import is_ip_multicast
from flync.model.flync_4_someip import (
    SOMEIPEvent,
    SOMEIPEventgroup,
    SOMEIPField,
    SOMEIPParameter,
    SOMEIPServiceInterface,
    UInt8,
)
from tests.error_assertions import assert_single_error


def test_service_check_for_events_without_eg(metadata_entry):
    f = SOMEIPField(
        name="a",
        parameters=[SOMEIPParameter(name="p1", datatype=UInt8())],
        notifier_id=1,
    )
    e = SOMEIPEvent(
        name="t",
        id=2,
        parameters=[SOMEIPParameter(name="p1", datatype=UInt8())],
    )
    eg = SOMEIPEventgroup(name="eg", id=1, events=[f])
    with pytest.warns(UserWarning, match="not assigned to an eventgroup") as w:
        s = SOMEIPServiceInterface(
            meta=metadata_entry,
            name="a",
            id=1,
            events=[e],
            fields=[f],
            eventgroups=[eg],
        )
    with pytest.warns(UserWarning, match="not assigned to an eventgroup") as w:
        s.validate_for_notifiers_without_eventgroup()


def test_is_multicast():
    unicast_ipv4 = ipaddress.ip_address("127.0.0.1")
    assert is_ip_multicast(unicast_ipv4)[0] == False
    multicast_address = ipaddress.ip_address("224.245.1.1")
    assert is_ip_multicast(multicast_address)[0] == True


def _service(metadata_entry, **kw) -> SOMEIPServiceInterface:
    """Build a SOME/IP service with the given extra members on a fixed id."""
    return SOMEIPServiceInterface(meta=metadata_entry, name="s", id=1, **kw)


def _event(name: str, sid: int) -> SOMEIPEvent:
    return SOMEIPEvent(name=name, id=sid, parameters=[SOMEIPParameter(name="p", datatype=UInt8())])


def test_field_without_identifier_raises():
    params = [SOMEIPParameter(name="p1", datatype=UInt8())]
    with pytest.raises(ValidationError) as exc_info:
        SOMEIPField(name="f", parameters=params)
    assert_single_error(exc_info, "FLYNC-SOM-MIN-REQ-135", '"f":')


def test_field_with_identifier_ok():
    SOMEIPField(name="f", parameters=[SOMEIPParameter(name="p1", datatype=UInt8())], notifier_id=1)


def test_eventgroup_undeclared_element_raises(metadata_entry):
    orphan = _event("orphan", 99)
    eg = SOMEIPEventgroup(name="eg", id=1, events=[orphan])
    with pytest.raises(ValidationError) as exc_info:
        _service(metadata_entry, eventgroups=[eg])
    assert_single_error(exc_info, "FLYNC-SOM-MIN-REF-136", '"orphan"')


def test_eventgroup_declared_element_ok(metadata_entry):
    declared = _event("mine", 1)
    eg = SOMEIPEventgroup(name="eg", id=1, events=[declared])
    _service(metadata_entry, events=[declared], eventgroups=[eg])


def test_duplicate_identifier_raises(metadata_entry):
    events = [_event("e1", 1), _event("e2", 1)]
    with pytest.raises(ValidationError) as exc_info:
        _service(metadata_entry, events=events)
    assert_single_error(exc_info, "FLYNC-SOM-MIN-UNIQ-137", "Entities share same identifier: 1")


def test_unique_identifiers_ok(metadata_entry):
    _service(metadata_entry, events=[_event("a", 1), _event("b", 2)])
