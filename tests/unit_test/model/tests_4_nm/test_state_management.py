"""Unit tests for the flync_4_nm model classes."""

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from flync.model.flync_4_bus.can_bus import CANBus
from flync.model.flync_4_nm import (
    GroupTiming,
    StateManagementConfig,
    StateManagementGroup,
    StateMembershipRef,
)
from tests.error_assertions import assert_single_error

FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture(name):
    with open(FIXTURES / name) as f:
        return yaml.safe_load(f)


def _make_timing(
    *,
    name="standard",
    cycle_time_ms=500,
    timeout_ms=2000,
    wait_before_sleep_ms=1500,
    announcement_duration_ms=1000,
    burst_count=None,
    burst_cycle_time_ms=None,
    include_announcement=True,
    include_sleep=True,
    extensions=None,
):
    values = {"name": name, "cycle_time_ms": cycle_time_ms}
    if include_announcement:
        announcement = {"duration_ms": announcement_duration_ms}
        if burst_count is not None:
            announcement["burst_count"] = burst_count
        if burst_cycle_time_ms is not None:
            announcement["burst_cycle_time_ms"] = burst_cycle_time_ms
        values["announcement"] = announcement
    if include_sleep:
        values["sleep"] = {"timeout_ms": timeout_ms, "wait_before_sleep_ms": wait_before_sleep_ms}
    if extensions is not None:
        values["extensions"] = extensions
    return GroupTiming(**values)


# ---------------------------------------------------------------------------
# GroupTiming (reusable timing profile)
# ---------------------------------------------------------------------------


def test_positive_group_timing():
    timing = _make_timing()
    assert timing.name == "standard"
    assert timing.cycle_time_ms == 500
    assert timing.sleep.timeout_ms == 2000
    assert timing.sleep.wait_before_sleep_ms == 1500
    assert timing.announcement.duration_ms == 1000


def test_group_timing_timeout_must_exceed_cycle_time_negative():
    with pytest.raises(ValidationError) as exc_info:
        _make_timing(timeout_ms=500)
    assert_single_error(exc_info, "FLYNC-CMN-MAJ-VAL-204", "timeout_ms must be greater than cycle_time_ms")


def test_group_timing_timeout_below_cycle_time_negative():
    with pytest.raises(ValidationError) as exc_info:
        _make_timing(timeout_ms=100)
    assert_single_error(exc_info, "FLYNC-CMN-MAJ-VAL-204", "timeout_ms must be greater than cycle_time_ms")


@pytest.mark.parametrize("field", ["cycle_time_ms", "timeout_ms", "wait_before_sleep_ms", "announcement_duration_ms"])
def test_group_timing_rejects_non_positive_values_negative(field):
    with pytest.raises(ValidationError):
        _make_timing(**{field: 0})


def test_positive_group_timing_oem_extensions():
    timing = _make_timing(extensions={"oem_tx_confirmation": "true"})
    assert timing.extensions == {"oem_tx_confirmation": "true"}
    assert GroupTiming.model_validate(timing.model_dump()).extensions == {"oem_tx_confirmation": "true"}


def test_positive_group_timing_with_announcement_burst():
    timing = _make_timing(burst_cycle_time_ms=20, burst_count=5)
    assert timing.announcement.burst_cycle_time_ms == 20
    assert timing.announcement.burst_count == 5


def test_group_timing_defaults_without_announcement_burst():
    timing = _make_timing()
    assert timing.announcement.burst_cycle_time_ms is None
    assert timing.announcement.burst_count is None


def test_positive_group_timing_without_announcement():
    # The announcement phase is optional; a profile without it is valid.
    timing = _make_timing(include_announcement=False)
    assert timing.announcement is None
    assert timing.sleep.timeout_ms == 2000


def test_group_timing_requires_sleep_negative():
    # sleep is required; omitting it is rejected.
    with pytest.raises(ValidationError):
        _make_timing(include_sleep=False)


def test_group_timing_announcement_burst_requires_both_fields_negative():
    with pytest.raises(ValidationError) as exc_info:
        _make_timing(burst_cycle_time_ms=20)
    assert_single_error(exc_info, "FLYNC-CMN-MAJ-VAL-203", "must be set together")


def test_group_timing_announcement_burst_must_be_faster_than_cycle_negative():
    with pytest.raises(ValidationError) as exc_info:
        _make_timing(burst_cycle_time_ms=500, burst_count=2)
    assert_single_error(exc_info, "FLYNC-CMN-MAJ-VAL-205", "must be shorter than cycle_time_ms")


def test_group_timing_announcement_burst_must_fit_announcement_duration_negative():
    # 30 x 100 ms = 3000 ms burst does not fit within the announcement duration_ms=1000
    with pytest.raises(ValidationError) as exc_info:
        _make_timing(burst_cycle_time_ms=100, burst_count=30)
    assert_single_error(exc_info, "FLYNC-CMN-MAJ-VAL-206", "does not fit within the announcement duration_ms")


# ---------------------------------------------------------------------------
# StateMembershipRef
# ---------------------------------------------------------------------------


def test_positive_membership_defaults():
    ref = StateMembershipRef(group="COMFORT")
    assert ref.role == "participant"
    assert ref.relevance_bits is None


def test_positive_membership_participant_with_bit():
    ref = StateMembershipRef(group="DRIVE", role="participant", relevance_bits=["PowerDist"])
    assert ref.relevance_bits == ["PowerDist"]


def test_positive_membership_participant_with_several_bits():
    ref = StateMembershipRef(group="VEHICLE", role="participant", relevance_bits=["AutonomousDriving", "OnlineCommunication"])
    assert ref.relevance_bits == ["AutonomousDriving", "OnlineCommunication"]


def test_positive_membership_observer_without_bit():
    ref = StateMembershipRef(group="COMFORT", role="observer")
    assert ref.role == "observer"
    assert ref.relevance_bits is None


def test_membership_observer_owns_no_bit_negative():
    with pytest.raises(ValidationError) as exc_info:
        StateMembershipRef(group="COMFORT", role="observer", relevance_bits=["X"])
    assert_single_error(exc_info, "FLYNC-CMN-MAJ-CONS-207", "participants reference bits")


def test_membership_observer_empty_bits_ok():
    # An empty list means "no bits" for an observer and is accepted, not rejected.
    ref = StateMembershipRef(group="COMFORT", role="observer", relevance_bits=[])
    assert ref.role == "observer"


def test_membership_duplicate_bits_negative():
    with pytest.raises(ValidationError) as exc_info:
        StateMembershipRef(group="VEHICLE", role="participant", relevance_bits=["Comfort", "Comfort"])
    assert_single_error(exc_info, "FLYNC-CMN-MAJ-UNIQ-208", "more than once")


def test_membership_rejects_unknown_role_negative():
    with pytest.raises(ValidationError):
        StateMembershipRef(group="COMFORT", role="proxy")


def test_positive_membership_oem_extensions():
    ref = StateMembershipRef(group="COMFORT", extensions={"oem_node_id": "7"})
    assert ref.extensions == {"oem_node_id": "7"}
    assert StateMembershipRef.model_validate(ref.model_dump()).extensions == {"oem_node_id": "7"}


# ---------------------------------------------------------------------------
# StateManagementGroup
# ---------------------------------------------------------------------------


def test_positive_group_minimal():
    group = StateManagementGroup(name="COMFORT", nm_pdu="PDU_Nm_Comfort", timing_profile="standard")
    assert group.name == "COMFORT"
    assert group.nm_pdu == "PDU_Nm_Comfort"
    assert group.timing_profile == "standard"
    assert group.description is None
    assert group.extensions is None


def test_positive_group_oem_extensions():
    group = StateManagementGroup(
        name="COMFORT",
        nm_pdu="PDU_Nm_Comfort",
        timing_profile="standard",
        extensions={"parameter_a": "value_a"},
    )
    assert group.extensions == {"parameter_a": "value_a"}
    reloaded = StateManagementGroup.model_validate(group.model_dump())
    assert reloaded.extensions == {"parameter_a": "value_a"}


def test_group_requires_nm_pdu_negative():
    with pytest.raises(ValidationError):
        StateManagementGroup(name="COMFORT", timing_profile="standard")


def test_group_requires_timing_profile_negative():
    with pytest.raises(ValidationError):
        StateManagementGroup(name="COMFORT", nm_pdu="PDU_Nm_Comfort")


def test_config_duplicate_group_name_negative():
    twin = {"name": "TWIN", "nm_pdu": "PDU_Nm", "timing_profile": "standard"}
    payload = {"groups": [twin, dict(twin)]}

    with pytest.raises(ValidationError) as exc_info:
        StateManagementConfig.model_validate(payload)
    assert_single_error(exc_info, "FLYNC-CMN-MAJ-UNIQ-009", "Duplicates found")


def test_config_duplicate_timing_profile_name_negative():
    profile = _make_timing().model_dump()
    payload = {"timing_profiles": [profile, dict(profile)]}

    with pytest.raises(ValidationError) as exc_info:
        StateManagementConfig.model_validate(payload)
    assert_single_error(exc_info, "FLYNC-CMN-MAJ-UNIQ-009", "Duplicates found")


# ---------------------------------------------------------------------------
# StateManagementConfig — concept fixtures (multi-group set + single-group variant)
# ---------------------------------------------------------------------------


def test_positive_config_defaults_to_empty():
    config = StateManagementConfig()
    assert config.groups == []


def test_positive_config_none_groups_to_empty():
    config = StateManagementConfig.model_validate({"groups": None})
    assert config.groups == []


def test_positive_config_multi_group_fixture():
    config = StateManagementConfig.model_validate(_load_fixture("groups.yaml"))
    assert [g.name for g in config.groups] == ["COMFORT", "DRIVE", "DIAGNOSTICS"]
    assert config.groups[1].nm_pdu == "PDU_Nm_Drive"
    assert config.groups[1].timing_profile == "drive_fast"
    profiles = {p.name: p for p in config.timing_profiles}
    assert profiles["drive_fast"].cycle_time_ms == 100


def test_positive_config_single_group_variant_fixture():
    # The single-group variant must pass with zero special-casing.
    config = StateManagementConfig.model_validate(_load_fixture("groups_single_group_variant.yaml"))
    assert [g.name for g in config.groups] == ["VEHICLE"]
    assert config.groups[0].nm_pdu == "PDU_NmMessage"
    assert config.groups[0].timing_profile == "standard"


@pytest.mark.parametrize("fixture", ["groups.yaml", "groups_single_group_variant.yaml"])
def test_positive_config_roundtrip(fixture):
    config = StateManagementConfig.model_validate(_load_fixture(fixture))
    dumped = config.model_dump()
    reloaded = StateManagementConfig.model_validate(dumped)
    assert reloaded.model_dump() == dumped


# ---------------------------------------------------------------------------
# Bus-level membership — fixture per the concept docs
# ---------------------------------------------------------------------------


def test_positive_bus_level_membership_fixture():
    bus = CANBus.model_validate(_load_fixture("body_can.yaml"))
    assert bus.name == "BodyCan"
    # the fixture declares no role, so it defaults to "participant"
    assert [(m.group, m.role, m.relevance_bits) for m in bus.state_memberships] == [("COMFORT", "participant", ["BodyCan"])]


def test_positive_bus_membership_defaults_to_empty():
    bus = CANBus(name="EmptyCan", baud_rate=500_000)
    assert bus.state_memberships == []
