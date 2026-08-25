from types import SimpleNamespace

import pytest
from pydantic_core import PydanticCustomError

from flync.core.validators.connection_compatibility import (
    validate_gptp,
    validate_macsec,
    validate_optional_mii_config_compatibility,
)


def _mii(mode, speed=100, mii_type="mii"):
    return SimpleNamespace(mode=mode, speed=speed, type=mii_type)


def _macsec(mka_enabled=True, macsec_mode="integrity"):
    return SimpleNamespace(mka_enabled=mka_enabled, macsec_mode=macsec_mode)


def _ptp(cmlds_linkport_enabled=True, ptp_ports=None):
    return SimpleNamespace(cmlds_linkport_enabled=cmlds_linkport_enabled, ptp_ports=ptp_ports or [])


def _component(name, **configs):
    return SimpleNamespace(name=name, **configs)


class TestValidateOptionalMIIConfigCompatibility:
    def test_missing_component_is_ignored(self):
        assert validate_optional_mii_config_compatibility(None, _component("b", mii_config=_mii("mac")), "conn1") is None
        assert validate_optional_mii_config_compatibility(_component("a", mii_config=_mii("mac")), None, "conn1") is None

    def test_no_mii_config_on_either_side_is_accepted(self):
        comp1 = _component("a", mii_config=None)
        comp2 = _component("b", mii_config=None)

        assert validate_optional_mii_config_compatibility(comp1, comp2, "conn1") is None

    @pytest.mark.parametrize(
        "mii1, mii2",
        [
            (_mii("mac"), None),
            (None, _mii("phy")),
        ],
    )
    def test_mii_config_on_only_one_side_raises(self, mii1, mii2):
        comp1 = _component("a", mii_config=mii1)
        comp2 = _component("b", mii_config=mii2)

        with pytest.raises(PydanticCustomError) as exc_info:
            validate_optional_mii_config_compatibility(comp1, comp2, "conn1")

        assert exc_info.value.context["error_id"] == "FLYNC-CMN-MAJ-COMP-012"

    def test_compatible_pair_is_accepted(self):
        comp1 = _component("a", mii_config=_mii("mac"))
        comp2 = _component("b", mii_config=_mii("phy"))

        assert validate_optional_mii_config_compatibility(comp1, comp2, "conn1") is None

    @pytest.mark.parametrize(
        "mii1, mii2, expected_error_id",
        [
            (_mii("mac"), _mii("mac"), "FLYNC-CMN-MAJ-COMP-013"),
            (_mii("mac"), _mii("phy", speed=1000), "FLYNC-CMN-MAJ-COMP-014"),
            (_mii("mac"), _mii("phy", mii_type="rmii"), "FLYNC-CMN-MAJ-COMP-015"),
        ],
    )
    def test_incompatible_pair_raises(self, mii1, mii2, expected_error_id):
        comp1 = _component("a", mii_config=mii1)
        comp2 = _component("b", mii_config=mii2)

        with pytest.raises(PydanticCustomError) as exc_info:
            validate_optional_mii_config_compatibility(comp1, comp2, "conn1")

        assert exc_info.value.context["error_id"] == expected_error_id


class TestValidateMacsec:
    def test_missing_component_is_ignored(self):
        assert validate_macsec(None, _component("b", macsec_config=_macsec()), "conn1") is None
        assert validate_macsec(_component("a", macsec_config=_macsec()), None, "conn1") is None

    def test_no_macsec_config_on_either_side_is_accepted(self):
        comp1 = _component("a", macsec_config=None)
        comp2 = _component("b", macsec_config=None)

        assert validate_macsec(comp1, comp2, "conn1") is None

    @pytest.mark.parametrize(
        "macsec1, macsec2, configured_name, unconfigured_name",
        [
            (_macsec(), None, "a", "b"),
            (None, _macsec(), "b", "a"),
        ],
    )
    def test_macsec_config_on_only_one_side_raises(self, macsec1, macsec2, configured_name, unconfigured_name):
        comp1 = _component("a", macsec_config=macsec1)
        comp2 = _component("b", macsec_config=macsec2)

        with pytest.raises(PydanticCustomError) as exc_info:
            validate_macsec(comp1, comp2, "conn1")

        assert exc_info.value.context["error_id"] == "FLYNC-CMN-MAJ-COMP-018"
        message = str(exc_info.value)
        assert f"{configured_name} has a macsec config" in message
        assert f"but {unconfigured_name} does not" in message

    def test_matching_pair_is_accepted(self):
        comp1 = _component("a", macsec_config=_macsec())
        comp2 = _component("b", macsec_config=_macsec())

        assert validate_macsec(comp1, comp2, "conn1") is None

    @pytest.mark.parametrize(
        "macsec1, macsec2, expected_error_id",
        [
            (_macsec(mka_enabled=True), _macsec(mka_enabled=False), "FLYNC-CMN-MAJ-COMP-019"),
            (_macsec(macsec_mode="integrity"), _macsec(macsec_mode="confidentiality"), "FLYNC-CMN-MAJ-COMP-020"),
        ],
    )
    def test_incompatible_pair_raises(self, macsec1, macsec2, expected_error_id):
        comp1 = _component("a", macsec_config=macsec1)
        comp2 = _component("b", macsec_config=macsec2)

        with pytest.raises(PydanticCustomError) as exc_info:
            validate_macsec(comp1, comp2, "conn1")

        assert exc_info.value.context["error_id"] == expected_error_id


class TestValidateGptp:
    def test_missing_component_is_ignored(self):
        assert validate_gptp(None, _component("b", ptp_config=_ptp()), "conn1") is None
        assert validate_gptp(_component("a", ptp_config=_ptp()), None, "conn1") is None

    def test_no_ptp_config_on_either_side_is_accepted(self):
        comp1 = _component("a", ptp_config=None)
        comp2 = _component("b", ptp_config=None)

        assert validate_gptp(comp1, comp2, "conn1") is None

    @pytest.mark.parametrize(
        "ptp1, ptp2",
        [
            (_ptp(), None),
            (None, _ptp()),
        ],
    )
    def test_ptp_config_on_only_one_side_raises(self, ptp1, ptp2):
        comp1 = _component("a", ptp_config=ptp1)
        comp2 = _component("b", ptp_config=ptp2)

        with pytest.raises(PydanticCustomError) as exc_info:
            validate_gptp(comp1, comp2, "conn1")

        assert exc_info.value.context["error_id"] == "FLYNC-CMN-MAJ-COMP-021"

    def test_cmlds_mismatch_raises(self):
        comp1 = _component("a", ptp_config=_ptp(cmlds_linkport_enabled=True))
        comp2 = _component("b", ptp_config=_ptp(cmlds_linkport_enabled=False))

        with pytest.raises(PydanticCustomError) as exc_info:
            validate_gptp(comp1, comp2, "conn1")

        assert exc_info.value.context["error_id"] == "FLYNC-CMN-MAJ-COMP-022"
