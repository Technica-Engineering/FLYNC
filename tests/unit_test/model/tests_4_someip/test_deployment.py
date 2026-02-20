import pydantic
import pytest

from flync.model.flync_4_someip import (
    Parameters,
    SOMEIPEvent,
    SOMEIPEventgroup,
    SOMEIPServiceInterface,
    SOMEIPServiceDeployment,
    SOMEIPServiceProvider,
    SOMEIPServiceConsumer,
)


def test_someip_service_deployment(
    metadata_entry, someip_sd_server_timings_profile_entry
):
    s = SOMEIPServiceInterface(meta=metadata_entry, name="s", id=1)
    sd = SOMEIPServiceProvider(
        service=1, instance_id=1, someip_sd_timings_profile="server_default"
    )
    sd._serialize_field_as_service(s)


def test_someip_service_deployment_lookup_service_from_id(metadata_entry):
    s = SOMEIPServiceInterface(meta=metadata_entry, name="s", id=1)
    lookup = SOMEIPServiceDeployment._lookup_service_from_id(1)
    assert lookup == s
    lookup_by_name = SOMEIPServiceDeployment._lookup_service_from_id(1)
    assert lookup_by_name == s


def test_someip_service_deployment_serialize_field_as_service(
    metadata_entry, someip_sd_server_timings_profile_entry
):
    s = SOMEIPServiceInterface(meta=metadata_entry, name="s", id=1)
    sd = SOMEIPServiceProvider(
        service=1, instance_id=1, someip_sd_timings_profile="server_default"
    )
    id = sd._serialize_field_as_service(s)
    assert id == 1


def test_someip_service_deployment_profile_serialize(
    metadata_entry, someip_sd_server_timings_profile_entry
):
    s = SOMEIPServiceInterface(meta=metadata_entry, name="s", id=1)
    sd = SOMEIPServiceProvider(
        service=1, instance_id=1, someip_sd_timings_profile="server_default"
    )
    assert (
        sd.someip_sd_timings_profile
        == someip_sd_server_timings_profile_entry.INSTANCES[
            "server_default"
        ].profile_id
    )


def test_someip_service_consumer_deployment_empty_eventgroups(
    metadata_entry, someip_sd_server_timings_profile_entry
):
    s = SOMEIPServiceInterface(meta=metadata_entry, name="s", id=1)
    sd = SOMEIPServiceConsumer(
        service=1, instance_id=1, someip_sd_timings_profile="server_default"
    )


def test_someip_service_consumer_deployment_with_eventgroups(metadata_entry):
    e1 = SOMEIPEvent(
        name="a",
        id=1,
        parameters=[Parameters(name="p1", type="uint8")],
    )
    e2 = SOMEIPEvent(
        name="b",
        id=2,
        parameters=[Parameters(name="p1", type="uint8")],
    )
    eg1 = SOMEIPEventgroup(name="eg_e1", id=1, events=[e1])
    eg2 = SOMEIPEventgroup(name="eg_e2", id=2, events=[e2])
    s = SOMEIPServiceInterface(
        meta=metadata_entry,
        name="s",
        id=1,
        events=[e1, e2],
        eventgroups=[eg1, eg2],
    )
    with pytest.raises(
        pydantic.ValidationError,
        match="Did not find eventgroups with names",
    ):
        sd = SOMEIPServiceConsumer(
            service=1,
            instance_id=1,
            consumed_eventgroups=["eg_e3", "eg_e1"],
            someip_sd_timings_profile="server_default",
        )
