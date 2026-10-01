import pytest
from pydantic import ValidationError

from flync.model.flync_4_diagnostics.diagnostics_config import DiagnosticsConfig
from flync.model.flync_4_diagnostics.doip.doip_config import DoIPConfig
from flync.model.flync_4_diagnostics.doip.timings import DoIPTimingProfile, DoIPTimingProfileSet
from flync.model.flync_4_diagnostics.uds.server import AccessProfile, UDSServer
from flync.model.flync_4_diagnostics.uds.services import DiagnosticSessionControlService, DiagnosticSessionDefinition
from flync.model.flync_4_diagnostics.uds.timings import UDSTimingProfile, UDSTimingProfileSet
from flync.model.flync_4_diagnostics.uds.uds_config import UDSConfig

SESSION_CONTROL = DiagnosticSessionControlService(sessions=[DiagnosticSessionDefinition(name="default", id=0x01)])


def doip_config() -> DoIPConfig:
    return DoIPConfig(timings=DoIPTimingProfileSet(profiles=[DoIPTimingProfile(profile_id="doip_default")]))


def uds_config() -> UDSConfig:
    return UDSConfig(
        timings=UDSTimingProfileSet(profiles=[UDSTimingProfile(profile_id="uds_default")]),
        servers=[
            UDSServer(
                name="EngineEcuDiagnostic",
                uds_timings_profile="uds_default",
                access_profiles=[AccessProfile(name="standard", default=True, sessions=["default"])],
                services=[SESSION_CONTROL],
            )
        ],
    )


@pytest.mark.parametrize(
    "doip, uds",
    [
        pytest.param(True, True, id="both_protocols"),
        pytest.param(True, False, id="doip_only"),
        pytest.param(False, True, id="uds_only"),
    ],
)
def test_diagnostics_config_accepts_any_present_protocol(doip, uds):
    config = DiagnosticsConfig(doip=doip_config() if doip else None, uds=uds_config() if uds else None)
    assert (config.doip is not None) is doip
    assert (config.uds is not None) is uds


def test_diagnostics_config_rejects_having_neither_protocol():
    """Raised as a bare ``ValueError`` on purpose: the loader reads it as "this folder is not a
    diagnostics config" and leaves the field unset, so an absent ``communication/diagnostics/``
    directory does not materialise a phantom config that would be written back to disk."""

    with pytest.raises(ValidationError) as exc_info:
        DiagnosticsConfig()
    errors = exc_info.value.errors()
    assert len(errors) == 1, errors
    assert "'doip' and/or a 'uds'" in errors[0]["msg"]


@pytest.mark.parametrize(
    "doip, expected_profile_ids",
    [
        pytest.param(True, {"doip_default"}, id="present"),
        pytest.param(False, set(), id="absent"),
    ],
)
def test_doip_timings_by_id_covers_an_absent_doip_config(doip, expected_profile_ids):
    config = DiagnosticsConfig(doip=doip_config() if doip else None, uds=uds_config())
    assert set(config.doip_timings_by_id()) == expected_profile_ids


@pytest.mark.parametrize(
    "uds, expected_server_names",
    [
        pytest.param(True, {"EngineEcuDiagnostic"}, id="present"),
        pytest.param(False, set(), id="absent"),
    ],
)
def test_uds_servers_by_name_covers_an_absent_uds_config(uds, expected_server_names):
    config = DiagnosticsConfig(doip=doip_config(), uds=uds_config() if uds else None)
    assert set(config.uds_servers_by_name()) == expected_server_names


@pytest.mark.parametrize(
    "config_cls",
    [pytest.param(DoIPConfig, id="doip"), pytest.param(UDSConfig, id="uds")],
)
def test_protocol_config_requires_its_timings(config_cls):
    """A protocol folder without its ``timings.flync.yaml`` describes nothing usable."""

    with pytest.raises(ValidationError) as exc_info:
        config_cls()
    assert [error["type"] for error in exc_info.value.errors()] == ["missing"]
