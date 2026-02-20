"""test service class"""

import pytest
import ipaddress
from flync.model.flync_4_someip import (
    SOMEIPServiceInterface,
    SOMEIPEventgroup,
    SOMEIPEvent,
    SOMEIPField,
    UInt8,
    Parameters,
)
from flync.core.utils.base_utils import is_ip_multicast


def test_service_check_for_events_without_eg(metadata_entry):
    with pytest.warns(UserWarning, match="not assigned to an eventgroup") as w:
        f = SOMEIPField(name="a", parameters=[UInt8()], notifier_id=1)
        e = SOMEIPEvent(
            name="t",
            id=2,
            parameters=[Parameters(name="p1", type="uint8")],
        )
        s = SOMEIPServiceInterface(
            meta=metadata_entry,
            name="a",
            id=1,
            events=[e],
            fields=[f],
            eventgroups=[
                SOMEIPEventgroup(
                    name="eg", id=1, events=[f], multicast_threshold=10
                )
            ],
        )
    with pytest.warns(UserWarning, match="not assigned to an eventgroup") as w:
        s.validate_for_notifiers_without_eventgroup()


def test_is_multicast():
    unicast_ipv4 = ipaddress.ip_address("127.0.0.1")
    assert is_ip_multicast(unicast_ipv4)[0] == False
    multicast_address = ipaddress.ip_address("224.245.1.1")
    assert is_ip_multicast(multicast_address)[0] == True
