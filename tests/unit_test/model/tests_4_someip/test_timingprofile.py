import pytest

from flync.model.flync_4_someip import (
    UInt8,
    SDConfig,
    SDTimings,
    SOMEIPEventgroup,
    SOMEIPEvent,
    SOMEIPEventTimings,
    SOMEIPField,
    SOMEIPFieldTimings,
    SOMEIPMethod,
    SOMEIPMethodTimings,
    SOMEIPParameter,
    SOMEIPServiceInterface,
    SOMEIPFireAndForgetMethod,
    SOMEIPTimingProfile,
    SOMEIPConfig,
    )


@pytest.mark.parametrize(
    "input_params",
    [
        pytest.param(SOMEIPFireAndForgetMethod(
            name="f&f",
            type="fire_and_forget",
            id=0x123,
            someip_timing ="method_default"
            )
        ),
       pytest.param(SOMEIPFireAndForgetMethod(
            name="f&f",
            type="fire_and_forget",
            id=0x123,
            someip_timing ="method_custom"
            )
        )
    ]
)
def test_implemented_timing_profile(metadata_entry,input_params,someip_sdconfig,someip_event_default_timings_profile,
                                        someip_field_default_timings_profile,
                                        someip_method_default_timings_profile,
                                        someip_event_custom_timings_profile,
                                        someip_field_custom_timings_profile,
                                        someip_method_custom_timings_profile
                                        ):

    f = SOMEIPField(
            name="a",
            parameters=[SOMEIPParameter(name="p1", datatype=UInt8())],
            notifier_id=1,
            someip_timing ="field_default"
        )
    e = SOMEIPEvent(
            name="t",
            id=2,
            parameters=[SOMEIPParameter(name="p1", datatype=UInt8())],
            someip_timing ="event_default"
        )

    m = input_params

    s = SOMEIPServiceInterface(
            meta=metadata_entry,
            name="a",
            id=1,
            events=[e],
            fields=[f],
            methods=[m],
            eventgroups=[
                SOMEIPEventgroup(
                    name="eg", id=1, events=[f,e], multicast_threshold=10
                )
            ],
        )
    sd_config = SDConfig(
        ip_address="224.224.224.255",
        port=30490,
        sd_timings=[SDTimings(
            profile_id="default",
            initial_delay_min=10,
            initial_delay_max=10,
            repetitions_base_delay=30,
            repetitions_max=3,
            request_response_delay_min=10,
            request_response_delay_max=10,
            offer_cyclic_delay=1000,
            offer_ttl=3,
            find_ttl=1000,
            subscribe_ttl=3
        )]
        )

    config = SOMEIPConfig(
        services=[s],
        sd_config=sd_config,
        someip_timings=SOMEIPTimingProfile(
            profiles=[someip_event_custom_timings_profile,
                    someip_field_custom_timings_profile,
                    someip_method_custom_timings_profile],
            defaults=[someip_event_default_timings_profile,
                    someip_field_default_timings_profile,
                    someip_method_default_timings_profile]
        )
    )


def test_field_not_implemented_timing_profile(metadata_entry,someip_sdconfig,someip_event_default_timings_profile,
                                        someip_field_default_timings_profile,
                                        someip_method_default_timings_profile,
                                        someip_event_custom_timings_profile,
                                        someip_field_custom_timings_profile,
                                        someip_method_custom_timings_profile
                                        ):

    f = SOMEIPField(
            name="a",
            parameters=[SOMEIPParameter(name="p1", datatype=UInt8())],
            notifier_id=1,
            someip_timing ="field_efault"
        )
    e = SOMEIPEvent(
            name="t",
            id=2,
            parameters=[SOMEIPParameter(name="p1", datatype=UInt8())],
            someip_timing ="event_default"
        )
    s = SOMEIPServiceInterface(
            meta=metadata_entry,
            name="a",
            id=1,
            events=[e],
            fields=[f],
            eventgroups=[
                SOMEIPEventgroup(
                    name="eg", id=1, events=[f,e], multicast_threshold=10
                )
            ],
        )
    sd_config = someip_sdconfig

    with pytest.raises(ValueError):
        config = SOMEIPConfig(
            services=[s],
            sd_config=sd_config,
            someip_timings=SOMEIPTimingProfile(
                profiles=[someip_event_custom_timings_profile,
                        someip_field_custom_timings_profile,
                        someip_method_custom_timings_profile],
                defaults=[someip_event_default_timings_profile,
                        someip_field_default_timings_profile,
                        someip_method_default_timings_profile]
            )
        )

def test_event_not_implemented_timing_profile(metadata_entry,someip_sdconfig,someip_event_default_timings_profile,
                                        someip_field_default_timings_profile,
                                        someip_method_default_timings_profile,
                                        someip_event_custom_timings_profile,
                                        someip_field_custom_timings_profile,
                                        someip_method_custom_timings_profile
                                        ):

    f = SOMEIPField(
            name="a",
            parameters=[SOMEIPParameter(name="p1", datatype=UInt8())],
            notifier_id=1,
            someip_timing ="field_default"
        )

    e = SOMEIPEvent(
            name="t",
            id=2,
            parameters=[SOMEIPParameter(name="p1", datatype=UInt8())],
            someip_timing ="event_efault"
        )

    s = SOMEIPServiceInterface(
            meta=metadata_entry,
            name="a",
            id=1,
            events=[e],
            fields=[f],
            eventgroups=[
                SOMEIPEventgroup(
                    name="eg", id=1, events=[f,e], multicast_threshold=10
                )
            ],
        )
    sd_config = someip_sdconfig

    with pytest.raises(ValueError):
        config = SOMEIPConfig(
            services=[s],
            sd_config=sd_config,
            someip_timings=SOMEIPTimingProfile(
                profiles=[someip_event_custom_timings_profile,
                        someip_field_custom_timings_profile,
                        someip_method_custom_timings_profile],
                defaults=[someip_event_default_timings_profile,
                        someip_field_default_timings_profile,
                        someip_method_default_timings_profile]
            )
        )

@pytest.mark.parametrize(
    "input_params",
    [
        pytest.param(SOMEIPFireAndForgetMethod(
            name="f&f",
            type="fire_and_forget",
            id=0x123,
            someip_timing ="method_efault"
            )
        ),
       pytest.param(SOMEIPFireAndForgetMethod(
            name="f&f",
            type="fire_and_forget",
            id=0x123,
            someip_timing ="method_ustom"
            )
        )
    ]
)

def test_method_not_implemented_timing_profile(metadata_entry,input_params,someip_sdconfig,someip_event_default_timings_profile,
                                        someip_field_default_timings_profile,
                                        someip_method_default_timings_profile,
                                        someip_event_custom_timings_profile,
                                        someip_field_custom_timings_profile,
                                        someip_method_custom_timings_profile
                                        ):

    f = SOMEIPField(
            name="a",
            parameters=[SOMEIPParameter(name="p1", datatype=UInt8())],
            notifier_id=1,
            someip_timing ="field_default"
        )

    e = SOMEIPEvent(
            name="t",
            id=2,
            parameters=[SOMEIPParameter(name="p1", datatype=UInt8())],
            someip_timing ="event_default"
        )

    m = input_params

    s = SOMEIPServiceInterface(
            meta=metadata_entry,
            name="a",
            id=1,
            events=[e],
            fields=[f],
            methods=[m],
            eventgroups=[
                SOMEIPEventgroup(
                    name="eg", id=1, events=[f,e], multicast_threshold=10
                )
            ],
        )
    sd_config = someip_sdconfig

    with pytest.raises(ValueError):
        config = SOMEIPConfig(
            services=[s],
            sd_config=sd_config,
            someip_timings=SOMEIPTimingProfile(
                profiles=[someip_event_custom_timings_profile,
                        someip_field_custom_timings_profile,
                        someip_method_custom_timings_profile],
                defaults=[someip_event_default_timings_profile,
                        someip_field_default_timings_profile,
                        someip_method_default_timings_profile]
            )
        )