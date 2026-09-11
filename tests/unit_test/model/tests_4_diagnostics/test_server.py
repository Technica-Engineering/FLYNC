import pytest
from pydantic import ValidationError

from flync.model.flync_4_diagnostics.uds.data_identifier import DataIdentifier
from flync.model.flync_4_diagnostics.uds.datatypes import DiagDataRecord
from flync.model.flync_4_diagnostics.uds.dtc import DiagnosticTroubleCode
from flync.model.flync_4_diagnostics.uds.routine import Routine
from flync.model.flync_4_diagnostics.uds.server import AccessProfile, UDSServer
from flync.model.flync_4_diagnostics.uds.services import (
    ClearDiagnosticInformationService,
    DiagnosticSessionControlService,
    DiagnosticSessionDefinition,
    EcuResetService,
    GenericUDSService,
    ReadDataByIdentifierService,
    ReadDTCInformationService,
    RoutineControlService,
    SecurityAccessService,
    SecurityLevelDeclaration,
    uds_service_tag,
)
from flync.model.flync_4_diagnostics.uds.timings import UDSTimingProfile, UDSTimingProfileSet
from flync.model.flync_4_diagnostics.uds.uds_config import UDSConfig
from tests.error_assertions import assert_single_error

SESSION_CONTROL = DiagnosticSessionControlService(
    sessions=[
        DiagnosticSessionDefinition(name="default", id=0x01),
        DiagnosticSessionDefinition(name="extended", id=0x03),
    ]
)
SECURITY_ACCESS = SecurityAccessService(
    security_levels=[SecurityLevelDeclaration(security_level="Locked"), SecurityLevelDeclaration(security_level=1)]
)
#: A server that offers DIDs must offer the service that reads them, and one that declares
#: DTCs must offer a service that reports or clears them - so the default service set carries
#: both, and tests that override ``services`` re-add whichever they need.
READ_DIDS = ReadDataByIdentifierService()
READ_DTCS = ReadDTCInformationService(report_types=["report_supported_dtc"], dtc_status_availability_mask=0x7F)


def minimal_server(**overrides):
    params = dict(
        name="EngineEcuDiagnostic",
        uds_timings_profile="uds_default",
        access_profiles=[AccessProfile(name="standard", default=True, sessions=["default"])],
        services=[SESSION_CONTROL, READ_DIDS, READ_DTCS],
    )
    params.update(overrides)
    return UDSServer(**params)


def test_minimal_server_accepted():
    server = minimal_server()
    assert server.name == "EngineEcuDiagnostic"


@pytest.mark.parametrize(
    "access_profiles",
    [
        pytest.param([AccessProfile(name="a", sessions=["default"]), AccessProfile(name="b", sessions=["default"])], id="no_default"),
        pytest.param(
            [AccessProfile(name="a", default=True, sessions=["default"]), AccessProfile(name="b", default=True, sessions=["default"])],
            id="two_defaults",
        ),
    ],
)
def test_server_requires_exactly_one_default_access_profile(access_profiles):
    with pytest.raises(ValidationError) as exc_info:
        minimal_server(access_profiles=access_profiles)
    assert_single_error(exc_info, "FLYNC-DIA-MAJ-CONS-267", "exactly one default access profile")


def test_access_profile_rejects_unknown_session():
    with pytest.raises(ValidationError) as exc_info:
        minimal_server(access_profiles=[AccessProfile(name="a", default=True, sessions=["nonexistent"])])
    assert_single_error(exc_info, "FLYNC-DIA-MAJ-REF-268", "unknown session(s)")


def test_access_profile_rejects_unknown_security_level():
    with pytest.raises(ValidationError) as exc_info:
        minimal_server(
            access_profiles=[AccessProfile(name="a", default=True, sessions=["default"], security_level=99)],
            services=[SESSION_CONTROL, SECURITY_ACCESS],
        )
    assert_single_error(exc_info, "FLYNC-DIA-MAJ-REF-269", "unknown security level")


def test_access_profile_accepts_known_security_level():
    server = minimal_server(
        access_profiles=[AccessProfile(name="a", default=True, sessions=["default"], security_level=1)],
        services=[SESSION_CONTROL, SECURITY_ACCESS],
    )
    assert server.access_profiles[0].security_level == 1


def test_session_control_requires_exactly_one_default_session():
    with pytest.raises(ValidationError) as exc_info:
        minimal_server(services=[DiagnosticSessionControlService(sessions=[DiagnosticSessionDefinition(name="extended", id=0x03)])])
    assert_single_error(exc_info, "FLYNC-DIA-MAJ-CONS-266", "exactly one session named 'default'")


def test_service_rejects_unknown_access_profile():
    with pytest.raises(ValidationError) as exc_info:
        minimal_server(services=[SESSION_CONTROL, ClearDiagnosticInformationService(access_profile="not_defined")])
    assert_single_error(exc_info, "FLYNC-DIA-MAJ-REF-270", "unknown access profile")


def test_service_accepts_known_access_profile():
    server = minimal_server(services=[SESSION_CONTROL, ClearDiagnosticInformationService(access_profile="standard")])
    assert server.services[1].access_profile == "standard"


def test_server_rejects_duplicate_service_sids():
    with pytest.raises(ValidationError) as exc_info:
        minimal_server(services=[SESSION_CONTROL, GenericUDSService(service="a", sid=0xBA), GenericUDSService(service="b", sid=0xBA)])
    assert_single_error(exc_info, "FLYNC-CMN-MAJ-UNIQ-009", "Duplicates found")


@pytest.mark.parametrize(
    "raw_service, expected_cls",
    [
        pytest.param(
            {"service": "diagnostic_session_control", "sid": 0x10, "sessions": [{"name": "default", "id": 1}]},
            DiagnosticSessionControlService,
            id="0x10",
        ),
        pytest.param({"service": "clear_diagnostic_information", "sid": 0x14}, ClearDiagnosticInformationService, id="0x14"),
        pytest.param({"service": "security_access", "sid": 0x27}, SecurityAccessService, id="0x27"),
        pytest.param({"service": "routine_control", "sid": 0x31}, RoutineControlService, id="0x31"),
        pytest.param({"service": "ecu_reset", "sid": 0x11}, EcuResetService, id="0x11"),
        pytest.param({"service": "read_dtc_information", "sid": 0x19}, ReadDTCInformationService, id="0x19"),
        pytest.param({"service": "read_data_by_identifier", "sid": 0x22}, ReadDataByIdentifierService, id="0x22"),
        pytest.param({"service": "write_data_by_identifier", "sid": 0x2E}, GenericUDSService, id="unmodelled_but_named_0x2E"),
        pytest.param({"service": "oem_specific", "sid": 0xBA}, GenericUDSService, id="unmodelled_0xBA"),
    ],
)
def test_service_class_is_selected_by_sid(raw_service, expected_cls):
    server = minimal_server(access_profiles=[], services=[raw_service])
    assert type(server.services[0]) is expected_cls


def test_modelled_sid_enforces_its_service_name():
    """A modelled ``sid`` pins the ``service`` name too - it cannot fall back to the generic service."""

    with pytest.raises(ValidationError) as exc_info:
        minimal_server(access_profiles=[], services=[{"service": "something_else", "sid": 0x27}])
    assert_single_error(exc_info, None, "Input should be 'security_access'")


def test_specialised_service_shape_is_enforced_by_the_sid_not_by_union_order():
    """``sid: 0x10`` must resolve to DiagnosticSessionControl, so a routine list is rejected as extra."""

    with pytest.raises(ValidationError) as exc_info:
        minimal_server(
            services=[{"service": "diagnostic_session_control", "sid": 0x10, "sessions": [{"name": "default", "id": 1}], "routines": ["erase"]}]
        )
    assert_single_error(exc_info, None, "routines")


@pytest.mark.parametrize(
    "value, expected_tag",
    [
        pytest.param({"sid": 0x10}, "0x10", id="int_sid"),
        pytest.param({"sid": "0x31"}, "0x31", id="quoted_hex_sid"),
        pytest.param({"sid": "186"}, "generic", id="quoted_decimal_unmodelled_sid"),
        pytest.param({"sid": "nonsense"}, "generic", id="unparsable_sid"),
        pytest.param({}, "generic", id="missing_sid"),
        pytest.param({"sid": None}, "generic", id="null_sid"),
        pytest.param(SecurityAccessService(), "0x27", id="model_instance"),
    ],
)
def test_uds_service_tag_resolves_or_falls_back_to_generic(value, expected_tag):
    """The union tag comes from the ``sid``, whatever shape it arrives in; anything unusable is generic."""

    assert uds_service_tag(value) == expected_tag


def test_quoted_hex_sid_still_selects_the_specialised_service():
    server = minimal_server(access_profiles=[], services=[{"service": "routine_control", "sid": "0x31", "routines": []}])
    assert type(server.services[0]) is RoutineControlService
    assert server.services[0].sid == 0x31


@pytest.mark.parametrize(
    "p2, p2_star, expected_p2, expected_p2_star",
    [
        pytest.param("50ms", "5s", 50, 5000, id="suffixed_strings"),
        pytest.param(50, 5000, 50, 5000, id="plain_ints"),
        pytest.param(None, None, None, None, id="unset_falls_back_to_the_profile"),
    ],
)
def test_session_p2_timings_accept_durations(p2, p2_star, expected_p2, expected_p2_star):
    session = DiagnosticSessionDefinition(name="extended", id=0x03, p2=p2, p2_star=p2_star)
    assert session.p2 == expected_p2
    assert session.p2_star == expected_p2_star


@pytest.mark.parametrize("p2", [pytest.param(0, id="int"), pytest.param("0ms", id="suffixed_string")])
def test_session_p2_rejects_non_positive_duration(p2):
    with pytest.raises(ValidationError) as exc_info:
        DiagnosticSessionDefinition(name="extended", id=0x03, p2=p2)
    assert_single_error(exc_info, None, "p2")


def test_session_p2_timings_serialize_back_as_millisecond_strings():
    dumped = DiagnosticSessionDefinition(name="extended", id=0x03, p2="5s", p2_star=10000).model_dump()
    assert dumped["p2"] == "5000ms"
    assert dumped["p2_star"] == "10000ms"


def test_unset_session_p2_timings_are_omitted_from_the_dump():
    """An unset override must not be written back as an explicit value - the profile still applies."""

    dumped = DiagnosticSessionDefinition(name="extended", id=0x03).model_dump()
    assert "p2" not in dumped
    assert "p2_star" not in dumped


def test_every_service_inherits_the_generic_service_fields():
    server = minimal_server(services=[SESSION_CONTROL, SecurityAccessService(access_profile="standard", subfunctions=[{"id": 1, "name": "seed"}])])
    security_access = server.services[1]
    assert isinstance(security_access, GenericUDSService)
    assert security_access.subfunctions[0].name == "seed"


def test_server_bind_resolves_did_dtc_and_routine_names():
    did = DataIdentifier(name="vin", did=0xF190, access="read", read_data=DiagDataRecord(byte_length=1))
    dtc = DiagnosticTroubleCode(name="overheat", dtc=0x010203)
    routine = Routine(name="erase", rid=0xFF00, start_request=DiagDataRecord(byte_length=0))
    timings = UDSTimingProfile(profile_id="uds_default")

    server = minimal_server(
        services=[SESSION_CONTROL, READ_DIDS, READ_DTCS, RoutineControlService(routines=["erase"])],
        dids=["vin"],
        dtcs=["overheat"],
    )
    server.bind({"uds_default": timings}, {"vin": did}, {"overheat": dtc}, {"erase": routine})

    assert server._timings_ref is timings
    assert server._did_refs == [did]
    assert server._dtc_refs == [dtc]
    routine_control = next(s for s in server.services if isinstance(s, RoutineControlService))
    assert routine_control._routine_refs == [routine]


def test_server_bind_rejects_unknown_timings_profile():
    server = minimal_server(uds_timings_profile="missing")
    with pytest.raises(ValidationError) as exc_info:
        UDSConfig(timings=UDSTimingProfileSet(profiles=[UDSTimingProfile(profile_id="uds_default")]), servers=[server])
    assert_single_error(exc_info, "FLYNC-DIA-MAJ-REF-277", "unknown UDS timings profile 'missing'")


@pytest.mark.parametrize(
    "server_overrides, expected_error_id, expected_message",
    [
        pytest.param({"dids": ["missing"]}, "FLYNC-DIA-MAJ-REF-271", "unknown DID 'missing'", id="did"),
        pytest.param({"dtcs": ["missing"]}, "FLYNC-DIA-MAJ-REF-272", "unknown DTC 'missing'", id="dtc"),
        pytest.param(
            {"services": [SESSION_CONTROL, RoutineControlService(routines=["missing"])]},
            "FLYNC-DIA-MAJ-REF-273",
            "unknown routine 'missing'",
            id="routine",
        ),
    ],
)
def test_server_bind_rejects_unknown_catalog_names(server_overrides, expected_error_id, expected_message):
    with pytest.raises(ValidationError) as exc_info:
        UDSConfig(
            timings=UDSTimingProfileSet(profiles=[UDSTimingProfile(profile_id="uds_default")]),
            servers=[minimal_server(**server_overrides)],
        )
    assert_single_error(exc_info, expected_error_id, expected_message)


def test_server_bind_rejects_did_requiring_an_access_profile_it_does_not_declare():
    did = DataIdentifier(name="vin", did=0xF190, access="read", read_data=DiagDataRecord(byte_length=1), access_profile="programming")
    with pytest.raises(ValidationError) as exc_info:
        UDSConfig(
            timings=UDSTimingProfileSet(profiles=[UDSTimingProfile(profile_id="uds_default")]),
            servers=[minimal_server(dids=["vin"])],
            dids=[did],
        )
    assert_single_error(exc_info, "FLYNC-DIA-MAJ-REF-281", "requires unknown access profile 'programming'")


def test_server_bind_rejects_routine_requiring_an_access_profile_it_does_not_declare():
    routine = Routine(name="erase", rid=0xFF00, start_request=DiagDataRecord(byte_length=0), access_profile="programming")
    with pytest.raises(ValidationError) as exc_info:
        UDSConfig(
            timings=UDSTimingProfileSet(profiles=[UDSTimingProfile(profile_id="uds_default")]),
            servers=[minimal_server(services=[SESSION_CONTROL, RoutineControlService(routines=["erase"])])],
            routines=[routine],
        )
    assert_single_error(exc_info, "FLYNC-DIA-MAJ-REF-282", "requires unknown access profile 'programming'")


def test_server_bind_accepts_catalog_access_profile_it_declares():
    did = DataIdentifier(name="vin", did=0xF190, access="read", read_data=DiagDataRecord(byte_length=1), access_profile="standard")
    config = UDSConfig(
        timings=UDSTimingProfileSet(profiles=[UDSTimingProfile(profile_id="uds_default")]),
        servers=[minimal_server(dids=["vin"])],
        dids=[did],
    )
    assert config.servers[0]._did_refs == [did]


def test_uds_config_binds_matching_names_end_to_end():
    did = DataIdentifier(name="vin", did=0xF190, access="read", read_data=DiagDataRecord(byte_length=1))
    dtc = DiagnosticTroubleCode(name="overheat", dtc=0x010203)
    routine = Routine(name="erase", rid=0xFF00, start_request=DiagDataRecord(byte_length=0))

    config = UDSConfig(
        timings=UDSTimingProfileSet(profiles=[UDSTimingProfile(profile_id="uds_default")]),
        servers=[
            minimal_server(
                services=[SESSION_CONTROL, READ_DIDS, READ_DTCS, RoutineControlService(routines=["erase"])],
                dids=["vin"],
                dtcs=["overheat"],
            )
        ],
        dids=[did],
        dtcs=[dtc],
        routines=[routine],
    )
    server = config.servers_by_name()["EngineEcuDiagnostic"]
    assert server._did_refs == [did]
    assert server._dtc_refs == [dtc]
    assert server._timings_ref.profile_id == "uds_default"
