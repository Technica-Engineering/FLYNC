import pytest
from pydantic import ValidationError

from flync.model.flync_4_someip import (
    SOMEIPConfig,
    SOMEIPEvent,
    SOMEIPEventgroup,
    SOMEIPField,
    SOMEIPFireAndForgetMethod,
    SOMEIPParameter,
    SOMEIPServiceInterface,
    SOMEIPTimingProfile,
    UInt8,
)
from tests.error_assertions import assert_single_error


@pytest.fixture
def someip_timings(
    someip_event_default_timings_profile,
    someip_field_default_timings_profile,
    someip_method_default_timings_profile,
    someip_event_custom_timings_profile,
    someip_field_custom_timings_profile,
    someip_method_custom_timings_profile,
):
    """The timing catalog every case resolves its ``someip_timing`` references against."""
    return SOMEIPTimingProfile(
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


def _fire_and_forget_method(someip_timing):
    """Build the fire-and-forget method whose timing reference is under test."""
    return SOMEIPFireAndForgetMethod(name="f&f", type="fire_and_forget", id=0x123, someip_timing=someip_timing)


def _someip_config(metadata_entry, sd_config, someip_timings, field_timing, event_timing, method=None):
    """Build a one-service SOMEIPConfig whose field, event and method name the given timing profiles."""
    field = SOMEIPField(
        name="a",
        parameters=[SOMEIPParameter(name="p1", datatype=UInt8())],
        notifier_id=1,
        someip_timing=field_timing,
    )
    event = SOMEIPEvent(
        name="t",
        id=2,
        parameters=[SOMEIPParameter(name="p1", datatype=UInt8())],
        someip_timing=event_timing,
    )
    service = SOMEIPServiceInterface(
        meta=metadata_entry,
        name="a",
        id=1,
        events=[event],
        fields=[field],
        methods=[method] if method is not None else [],
        eventgroups=[SOMEIPEventgroup(name="eg", id=1, events=[field, event])],
    )

    return SOMEIPConfig(services=[service], sd_config=sd_config, someip_timings=someip_timings)


@pytest.mark.parametrize("method_timing", ["method_default", "method_custom"])
def test_implemented_timing_profile(metadata_entry, someip_sdconfig, someip_timings, method_timing):
    """Timing references that name a declared default or custom profile resolve."""

    config = _someip_config(
        metadata_entry,
        someip_sdconfig,
        someip_timings,
        field_timing="field_default",
        event_timing="event_default",
        method=_fire_and_forget_method(method_timing),
    )

    assert isinstance(config, SOMEIPConfig)


@pytest.mark.parametrize(
    "field_timing, event_timing, method_timing, message",
    [
        pytest.param("field_efault", "event_default", None, "does not exist in SOMEIPFieldTimings", id="field"),
        pytest.param("field_default", "event_efault", None, "does not exist in SOMEIPEventTimings", id="event"),
        pytest.param("field_default", "event_default", "method_efault", "does not exist in SOMEIPMethodTimings", id="method_default_typo"),
        pytest.param("field_default", "event_default", "method_ustom", "does not exist in SOMEIPMethodTimings", id="method_custom_typo"),
    ],
)
def test_not_implemented_timing_profile(metadata_entry, someip_sdconfig, someip_timings, field_timing, event_timing, method_timing, message):
    """A ``someip_timing`` naming no declared profile is rejected, and the message names the timing table it was looked up in."""

    with pytest.raises(ValidationError) as exc_info:
        _someip_config(
            metadata_entry,
            someip_sdconfig,
            someip_timings,
            field_timing=field_timing,
            event_timing=event_timing,
            method=_fire_and_forget_method(method_timing) if method_timing is not None else None,
        )

    assert_single_error(exc_info, "FLYNC-SOM-MAJ-REF-340", message)
