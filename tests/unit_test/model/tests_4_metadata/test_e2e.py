import pytest
from pydantic import ValidationError

from flync.model.flync_4_someip import (
    SOMEIPConfig,
    SOMEIPEvent,
    SOMEIPEventgroup,
    SOMEIPServiceInterface,
    SOMEIPTimingProfile,
)
from tests.error_assertions import assert_single_error


def test_e2e_config():
    e = SOMEIPEvent(
        name="t",
        id=2,
        parameters=[],
        e2e={"profile": "AUTOSAR_Profile_1", "data_id": 0x12345678},
    )
    assert e.e2e.profile == "AUTOSAR_Profile_1"
    assert e.e2e.data_id == 0x12345678


def test_e2e_duplicate_data_id_in_profiles(
    metadata_entry,
    someip_sdconfig,
    someip_event_default_timings_profile,
    someip_field_default_timings_profile,
    someip_method_default_timings_profile,
    someip_event_custom_timings_profile,
    someip_field_custom_timings_profile,
    someip_method_custom_timings_profile,
):
    e1 = SOMEIPEvent(
        name="t",
        id=2,
        parameters=[],
        e2e={"profile": "AUTOSAR_Profile_1", "data_id": 0x12345678},
    )
    e2 = SOMEIPEvent(
        name="t",
        id=2,
        parameters=[],
        e2e={"profile": "AUTOSAR_Profile_2", "data_id": 0x12345678},
    )

    e3 = SOMEIPEvent(
        name="t",
        id=2,
        parameters=[],
        e2e={"profile": "AUTOSAR_Profile_2", "data_id": 0x12345678},
    )

    ets_01 = SOMEIPServiceInterface(
        meta=metadata_entry,
        name="a",
        id=1,
        events=[e1, e2],
        eventgroups=[SOMEIPEventgroup(name="eg", id=1, events=[e1, e2])],
    )

    ets_02 = SOMEIPServiceInterface(
        meta=metadata_entry,
        name="a",
        id=2,
        events=[e3],
        eventgroups=[SOMEIPEventgroup(name="eg", id=1, events=[e3])],
    )

    # sd_config and someip_timings are mandatory: without them SOMEIPConfig fails on the missing fields
    # before the duplicate-data_id check is reached, so supply valid ones.
    someip_timings = SOMEIPTimingProfile(
        profiles=[
            someip_event_custom_timings_profile,
            someip_field_custom_timings_profile,
            someip_method_custom_timings_profile,
        ],
        defaults=[
            someip_event_default_timings_profile,
            someip_field_default_timings_profile,
            someip_method_default_timings_profile,
        ],
    )

    # e2 and e3 share data_id 0x12345678 within AUTOSAR_Profile_2, across the two services.
    with pytest.raises(ValidationError) as exc_info:
        SOMEIPConfig(services=[ets_01, ets_02], sd_config=someip_sdconfig, someip_timings=someip_timings)
    # No error id: the validator raises a bare ValueError instead of going through err_major / err_minor.
    assert_single_error(exc_info, None, "Duplicate e2e.data_id")
