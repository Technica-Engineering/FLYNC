import pytest
from pydantic import ValidationError

from flync.model.flync_4_diagnostics.doip.timings import DoIPTimingProfile, DoIPTimingProfileSet
from flync.model.flync_4_diagnostics.uds.timings import UDSTimingProfile, UDSTimingProfileSet
from tests.error_assertions import assert_single_error


def test_doip_timing_profile_uses_iso_13400_defaults():
    profile = DoIPTimingProfile(profile_id="p1")
    assert profile.a_doip_ctrl == 2000
    assert profile.t_tcp_general_inactivity == 300000


def test_uds_timing_profile_uses_iso_14229_defaults():
    profile = UDSTimingProfile(profile_id="p1")
    assert profile.p2_server == 50
    assert profile.p2_star_server == 5000
    assert profile.s3_server == 5000


@pytest.mark.parametrize(
    "container, profile_cls",
    [
        pytest.param(DoIPTimingProfileSet, DoIPTimingProfile, id="doip"),
        pytest.param(UDSTimingProfileSet, UDSTimingProfile, id="uds"),
    ],
)
def test_timings_container_accepts_unique_ids_across_profiles_and_defaults(container, profile_cls):
    timings = container(profiles=[profile_cls(profile_id="server")], defaults=[profile_cls(profile_id="fallback")])
    assert set(timings.by_id()) == {"server", "fallback"}


@pytest.mark.parametrize(
    "container, profile_cls",
    [
        pytest.param(DoIPTimingProfileSet, DoIPTimingProfile, id="doip"),
        pytest.param(UDSTimingProfileSet, UDSTimingProfile, id="uds"),
    ],
)
def test_timings_container_rejects_duplicate_ids_across_profiles_and_defaults(container, profile_cls):
    profiles = [profile_cls(profile_id="shared")]
    defaults = [profile_cls(profile_id="shared")]
    with pytest.raises(ValidationError) as exc_info:
        container(profiles=profiles, defaults=defaults)
    assert_single_error(exc_info, "FLYNC-CMN-MAJ-UNIQ-009", "Duplicates found")


@pytest.mark.parametrize("field_name", ["a_doip_ctrl", "t_tcp_general_inactivity", "a_doip_announce_num"])
def test_doip_timers_reject_non_positive_values(field_name):
    with pytest.raises(ValidationError) as exc_info:
        DoIPTimingProfile(profile_id="p1", **{field_name: 0})
    assert_single_error(exc_info, None, field_name)


@pytest.mark.parametrize("field_name", ["p2_server", "p2_star_server", "s3_server"])
def test_uds_timers_reject_non_positive_values(field_name):
    with pytest.raises(ValidationError) as exc_info:
        UDSTimingProfile(profile_id="p1", **{field_name: 0})
    assert_single_error(exc_info, None, field_name)
