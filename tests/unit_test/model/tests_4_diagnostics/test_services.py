"""Tests for the UDS service models and the service-to-catalog cross-checks."""

import pytest
from pydantic import TypeAdapter, ValidationError

from flync.core.utils.exceptions_handling import validate_with_policy
from flync.model.flync_4_diagnostics.uds.data_identifier import DataIdentifier, DIDIOControl
from flync.model.flync_4_diagnostics.uds.datatypes import DiagDataRecord
from flync.model.flync_4_diagnostics.uds.dtc import DiagnosticTroubleCode
from flync.model.flync_4_diagnostics.uds.server import UDSServer
from flync.model.flync_4_diagnostics.uds.services import (
    CANONICAL_SERVICE_NAMES,
    ClearDiagnosticInformationService,
    EcuResetService,
    GenericUDSService,
    ReadDataByIdentifierService,
    ReadDTCInformationService,
    RequestDownloadService,
    RequestUploadService,
    UDSServiceEntry,
)
from flync.model.flync_4_diagnostics.uds.subfunctions import DTC_REPORT_TYPE_IDS, RESET_TYPE_IDS, status_mask_bits, status_mask_from_bits
from flync.model.flync_4_diagnostics.uds.uds_config import UDSConfig
from tests.error_assertions import assert_single_error, assert_single_warning

SERVICE_LIST = TypeAdapter(list[UDSServiceEntry])
ONE_BYTE = DiagDataRecord(byte_length=1, fields=[{"name": "value", "type": "uint8", "bit_offset": 0, "bit_length": 8}])

SESSION_CONTROL = {"service": "diagnostic_session_control", "sid": 0x10, "sessions": [{"name": "default", "id": 0x01}]}
READ_DIDS = {"service": "read_data_by_identifier", "sid": 0x22}
TESTER_PRESENT = {"service": "tester_present", "sid": 0x3E}


def server_data(**overrides) -> dict:
    """Return the raw data of a minimal UDS server, for use with ``validate_with_policy``."""

    data = {
        "name": "EngineEcuDiagnostic",
        "uds_timings_profile": "uds_default",
        "access_profiles": [{"name": "standard", "default": True, "sessions": ["default"]}],
        "services": [SESSION_CONTROL],
    }
    data.update(overrides)
    return data


def config_data(server: dict, **catalogs) -> dict:
    """Return the raw data of a UDS config wrapping one server plus its catalogs."""

    data = {"timings": {"profiles": [{"profile_id": "uds_default"}]}, "servers": [server]}
    data.update(catalogs)
    return data


# --------------------------------------------------------------------------------------
# Canonical service names
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("sid, service", sorted(CANONICAL_SERVICE_NAMES.items()))
def test_every_standardised_sid_accepts_its_canonical_name(sid, service):
    """The table itself must be loadable: each entry names a service the union can build."""

    entry = {"service": service, "sid": sid}
    if sid == 0x10:
        entry["sessions"] = [{"name": "default", "id": 0x01}]
    if sid in (0x34, 0x35):
        entry["max_block_length"] = 1026
    assert SERVICE_LIST.validate_python([entry])[0].sid == sid


@pytest.mark.parametrize(
    "sid, wrong_name",
    [
        pytest.param(0x2E, "write_did", id="0x2E_abbreviated"),
        pytest.param(0x3E, "testerpresent", id="0x3E_not_snake_case"),
        pytest.param(0x36, "transfer", id="0x36_truncated"),
        pytest.param(0x85, "control_dtc", id="0x85_truncated"),
    ],
)
def test_standardised_sid_rejects_a_non_canonical_name(sid, wrong_name):
    """A typo is caught even for the service ids that have no dedicated model."""

    with pytest.raises(ValidationError) as exc_info:
        SERVICE_LIST.validate_python([{"service": wrong_name, "sid": sid}])
    assert_single_error(exc_info, "FLYNC-DIA-MAJ-CONS-284", "in ISO 14229-1, but is named")


@pytest.mark.parametrize("sid", [pytest.param(0xBA, id="0xBA"), pytest.param(0xF0, id="0xF0")])
def test_oem_specific_sid_keeps_an_unconstrained_name(sid):
    service = SERVICE_LIST.validate_python([{"service": "oem_specific_thing", "sid": sid}])[0]
    assert type(service) is GenericUDSService
    assert service.service == "oem_specific_thing"


# --------------------------------------------------------------------------------------
# 0x11 EcuReset
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "reset_types",
    [
        pytest.param(["hard_reset"], id="single_iso_name"),
        pytest.param(sorted(RESET_TYPE_IDS), id="every_iso_name"),
        pytest.param([0x40], id="supplier_specific_int"),
        pytest.param([0x5F], id="supplier_specific_upper_bound"),
        pytest.param(["soft_reset", 0x41], id="mixed_name_and_int"),
        pytest.param(["hard_reset", "0x42"], id="hex_string_int"),
    ],
)
def test_ecu_reset_accepts_iso_names_and_numeric_escapes(reset_types):
    assert len(EcuResetService(reset_types=reset_types).reset_types) == len(reset_types)


def test_ecu_reset_rejects_a_misspelled_reset_type():
    """A union field reports one error per member, so pin the field rather than a single error."""

    with pytest.raises(ValidationError, match="reset_types"):
        EcuResetService(reset_types=["hardreset"])


def test_ecu_reset_rejects_duplicate_reset_types():
    with pytest.raises(ValidationError) as exc_info:
        EcuResetService(reset_types=["soft_reset", "soft_reset"])
    assert_single_error(exc_info, "FLYNC-CMN-MAJ-UNIQ-009", "reset types")


@pytest.mark.parametrize("power_down_time", [pytest.param(0x00, id="lower_bound"), pytest.param(0xFE, id="upper_bound")])
def test_ecu_reset_accepts_power_down_time_with_rapid_shutdown(power_down_time):
    service = EcuResetService(reset_types=["enable_rapid_power_shutdown"], power_down_time=power_down_time)
    assert service.power_down_time == power_down_time


def test_ecu_reset_rejects_power_down_time_no_reset_type_reports():
    with pytest.raises(ValidationError) as exc_info:
        EcuResetService(reset_types=["hard_reset"], power_down_time=5)
    assert_single_error(exc_info, "FLYNC-DIA-MAJ-CONS-285", "does not offer 'enable_rapid_power_shutdown'")


def test_ecu_reset_rejects_the_iso_reserved_power_down_time():
    """0xFF means "failure or time not available" on the wire and cannot be configured."""

    with pytest.raises(ValidationError) as exc_info:
        EcuResetService(reset_types=["enable_rapid_power_shutdown"], power_down_time=0xFF)
    assert_single_error(exc_info, None, "power_down_time")


def test_ecu_reset_without_reset_types_warns():
    result = validate_with_policy(EcuResetService, {}, path=None)
    assert_single_warning(result, "FLYNC-DIA-WARN-REQ-286", "declares no reset_types")


# --------------------------------------------------------------------------------------
# 0x19 ReadDTCInformation
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "report_types",
    [
        pytest.param(["report_supported_dtc"], id="single_iso_name"),
        pytest.param(sorted(DTC_REPORT_TYPE_IDS), id="every_iso_name"),
        pytest.param([0x77], id="unnamed_int"),
        pytest.param(["report_dtc_by_status_mask", "0x78"], id="mixed_name_and_hex_string"),
    ],
)
def test_read_dtc_information_accepts_iso_names_and_numeric_escapes(report_types):
    service = ReadDTCInformationService(report_types=report_types, dtc_status_availability_mask=0x7F)
    assert len(service.report_types) == len(report_types)


def test_read_dtc_information_rejects_a_misspelled_report_type():
    """A union field reports one error per member, so pin the field rather than a single error."""

    with pytest.raises(ValidationError, match="report_types"):
        ReadDTCInformationService(report_types=["report_supportd_dtc"], dtc_status_availability_mask=0x7F)


def test_read_dtc_information_rejects_duplicate_report_types():
    with pytest.raises(ValidationError) as exc_info:
        ReadDTCInformationService(report_types=["report_supported_dtc"] * 2, dtc_status_availability_mask=0x7F)
    assert_single_error(exc_info, "FLYNC-CMN-MAJ-UNIQ-009", "report types")


@pytest.mark.parametrize(
    "mask, expected",
    [
        pytest.param(0x01, 0x01, id="lowest_bit"),
        pytest.param(0x7F, 0x7F, id="typical"),
        pytest.param(0xFF, 0xFF, id="upper_bound"),
        pytest.param("0xFF", 0xFF, id="hex_string"),
    ],
)
def test_dtc_status_availability_mask_accepts_the_byte(mask, expected):
    """The mask is the ISO byte, and the field shape stays scalar so the SDK object mapper can
    map it back onto its YAML node."""

    assert (
        ReadDTCInformationService(report_types=["report_supported_dtc"], dtc_status_availability_mask=mask).dtc_status_availability_mask == expected
    )


def test_dtc_status_availability_mask_rejects_a_byte_out_of_range():
    with pytest.raises(ValidationError) as exc_info:
        ReadDTCInformationService(report_types=["report_supported_dtc"], dtc_status_availability_mask=0x100)
    assert_single_error(exc_info, None, "dtc_status_availability_mask")


def test_dtc_status_availability_mask_rejects_an_all_zero_byte():
    with pytest.raises(ValidationError) as exc_info:
        ReadDTCInformationService(report_types=["report_supported_dtc"], dtc_status_availability_mask=0x00)
    assert_single_error(exc_info, "FLYNC-DIA-MAJ-VAL-287", "all-zero dtc_status_availability_mask")


@pytest.mark.parametrize(
    "bits, expected_mask",
    [
        pytest.param([], 0x00, id="no_bits"),
        pytest.param(["test_failed"], 0x01, id="lowest_bit"),
        pytest.param(["warning_indicator_requested"], 0x80, id="highest_bit"),
        pytest.param(["test_failed", "confirmed_dtc"], 0x09, id="two_bits"),
    ],
)
def test_status_mask_helpers_round_trip(bits, expected_mask):
    """The bit names an OEM specification lists convert to the byte the model stores, and back."""

    assert status_mask_from_bits(bits) == expected_mask
    assert status_mask_bits(expected_mask) == bits


def test_status_mask_from_bits_rejects_an_unknown_bit_name():
    with pytest.raises(KeyError):
        status_mask_from_bits(["test_faild"])


@pytest.mark.parametrize(
    "overrides, expected_id, expected_message",
    [
        pytest.param(
            {"report_types": [], "dtc_status_availability_mask": 0x7F},
            "FLYNC-DIA-WARN-REQ-288",
            "declares no report_types",
            id="no_report_types",
        ),
        pytest.param(
            {"report_types": ["report_supported_dtc"]},
            "FLYNC-DIA-WARN-REQ-289",
            "declares no dtc_status_availability_mask",
            id="no_mask",
        ),
        pytest.param(
            {"report_types": ["report_emissions_obd_dtc_by_status_mask"], "dtc_status_availability_mask": 0x7F},
            "FLYNC-DIA-WARN-LIFE-290",
            "ISO 14229-1:2020 deprecates",
            id="deprecated_report_type",
        ),
        pytest.param(
            {"report_types": ["report_user_def_memory_dtc_by_status_mask"], "dtc_status_availability_mask": 0x7F},
            "FLYNC-DIA-WARN-CONS-291",
            "declares no memory_selections",
            id="user_def_memory_without_selections",
        ),
    ],
)
def test_read_dtc_information_warns_on_incomplete_configuration(overrides, expected_id, expected_message):
    assert_single_warning(validate_with_policy(ReadDTCInformationService, overrides, path=None), expected_id, expected_message)


def test_user_def_memory_report_type_with_memory_selections_does_not_warn():
    _, findings = validate_with_policy(
        ReadDTCInformationService,
        {"report_types": ["report_user_def_memory_dtc_by_status_mask"], "dtc_status_availability_mask": 0x7F, "memory_selections": [0x01]},
        path=None,
    )
    assert findings == []


# --------------------------------------------------------------------------------------
# 0x14 ClearDiagnosticInformation
# --------------------------------------------------------------------------------------


def test_clear_diagnostic_information_accepts_unique_groups():
    service = ClearDiagnosticInformationService(dtc_groups=[{"name": "all", "id": 0xFFFFFF}, {"name": "powertrain", "id": 0x010000}])
    assert len(service.dtc_groups) == 2


@pytest.mark.parametrize(
    "dtc_groups, fragment",
    [
        pytest.param([{"name": "all", "id": 0xFFFFFF}, {"name": "all", "id": 0x010000}], "DTC group names", id="duplicate_names"),
        pytest.param([{"name": "all", "id": 0xFFFFFF}, {"name": "everything", "id": 0xFFFFFF}], "DTC group ids", id="duplicate_ids"),
    ],
)
def test_clear_diagnostic_information_rejects_duplicate_groups(dtc_groups, fragment):
    with pytest.raises(ValidationError) as exc_info:
        ClearDiagnosticInformationService(dtc_groups=dtc_groups)
    assert_single_error(exc_info, "FLYNC-CMN-MAJ-UNIQ-009", fragment)


@pytest.mark.parametrize(
    "overrides, expected_id, expected_message",
    [
        pytest.param({}, "FLYNC-DIA-WARN-REQ-292", "declares no dtc_groups", id="no_groups"),
        pytest.param(
            {"dtc_groups": [{"name": "powertrain", "id": 0x010000}]},
            "FLYNC-DIA-WARN-CONS-293",
            "'all groups' mask",
            id="no_all_groups_mask",
        ),
    ],
)
def test_clear_diagnostic_information_warns_on_incomplete_groups(overrides, expected_id, expected_message):
    assert_single_warning(validate_with_policy(ClearDiagnosticInformationService, overrides, path=None), expected_id, expected_message)


# --------------------------------------------------------------------------------------
# 0x22 ReadDataByIdentifier
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("max_dids", [pytest.param(None, id="unset"), pytest.param(1, id="lower_bound"), pytest.param(16, id="typical")])
def test_read_data_by_identifier_accepts_a_request_limit(max_dids):
    assert ReadDataByIdentifierService(max_dids_per_request=max_dids).max_dids_per_request == max_dids


def test_read_data_by_identifier_rejects_a_zero_request_limit():
    with pytest.raises(ValidationError) as exc_info:
        ReadDataByIdentifierService(max_dids_per_request=0)
    assert_single_error(exc_info, None, "max_dids_per_request")


# --------------------------------------------------------------------------------------
# 0x34 / 0x35 block transfer set-up
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("cls", [pytest.param(RequestDownloadService, id="0x34"), pytest.param(RequestUploadService, id="0x35")])
def test_transfer_setup_defaults_to_an_uncompressed_four_byte_format(cls):
    service = cls(max_block_length=1026)
    assert (service.memory_address_length, service.memory_size_length, service.data_format_identifiers) == (4, 4, [0x00])


@pytest.mark.parametrize(
    "region, expected_id, fragment",
    [
        pytest.param({"name": "app", "address": 0xFFFFFFFF, "size": 1}, None, None, id="address_exactly_fits"),
        pytest.param({"name": "app", "address": 0, "size": 0xFFFFFFFF}, None, None, id="size_exactly_fits"),
        pytest.param(
            {"name": "app", "address": 0x1FFFFFFFF, "size": 1},
            "FLYNC-DIA-MAJ-CONS-294",
            "does not fit in memory_address_length",
            id="address_too_wide",
        ),
        pytest.param(
            {"name": "app", "address": 0, "size": 0x1FFFFFFFF},
            "FLYNC-DIA-MAJ-CONS-295",
            "does not fit in memory_size_length",
            id="size_too_wide",
        ),
    ],
)
def test_transfer_setup_checks_regions_against_the_declared_widths(region, expected_id, fragment):
    if expected_id is None:
        assert RequestDownloadService(max_block_length=1026, memory_regions=[region]).memory_regions[0].name == "app"
        return
    with pytest.raises(ValidationError) as exc_info:
        RequestDownloadService(max_block_length=1026, memory_regions=[region])
    assert_single_error(exc_info, expected_id, fragment)


def test_transfer_setup_requires_a_max_block_length():
    with pytest.raises(ValidationError) as exc_info:
        RequestDownloadService()
    assert_single_error(exc_info, None, "max_block_length")


# --------------------------------------------------------------------------------------
# Server-level service coherence
# --------------------------------------------------------------------------------------


def test_server_rejects_dtcs_without_a_dtc_service():
    with pytest.raises(ValidationError) as exc_info:
        UDSServer(**server_data(dtcs=["overheat"]))
    assert_single_error(exc_info, "FLYNC-DIA-MAJ-CONS-297", "offers neither ReadDTCInformation (0x19)")


@pytest.mark.parametrize(
    "dtc_service",
    [
        pytest.param(
            {"service": "read_dtc_information", "sid": 0x19, "report_types": ["report_supported_dtc"], "dtc_status_availability_mask": 127},
            id="0x19",
        ),
        pytest.param({"service": "clear_diagnostic_information", "sid": 0x14, "dtc_groups": [{"name": "all", "id": 0xFFFFFF}]}, id="0x14"),
    ],
)
def test_server_accepts_dtcs_with_either_dtc_service(dtc_service):
    server = UDSServer(**server_data(services=[SESSION_CONTROL, dtc_service], dtcs=["overheat"]))
    assert server.dtcs == ["overheat"]


@pytest.mark.parametrize(
    "services, expected_id, fragment",
    [
        pytest.param(
            [SESSION_CONTROL, {"service": "transfer_data", "sid": 0x36}],
            "FLYNC-DIA-MAJ-CONS-298",
            "neither RequestDownload (0x34)",
            id="transfer_data_alone",
        ),
        pytest.param(
            [SESSION_CONTROL, {"service": "request_download", "sid": 0x34, "max_block_length": 1026}],
            "FLYNC-DIA-MAJ-CONS-299",
            "does not offer TransferData (0x36)",
            id="request_download_alone",
        ),
    ],
)
def test_server_rejects_an_incomplete_block_transfer_set(services, expected_id, fragment):
    with pytest.raises(ValidationError) as exc_info:
        UDSServer(**server_data(services=services))
    assert_single_error(exc_info, expected_id, fragment)


def test_server_accepts_a_complete_block_transfer_set():
    services = [
        SESSION_CONTROL,
        {"service": "request_download", "sid": 0x34, "max_block_length": 1026},
        {"service": "transfer_data", "sid": 0x36},
        {"service": "request_transfer_exit", "sid": 0x37},
    ]
    assert len(UDSServer(**server_data(services=services)).services) == 4


@pytest.mark.parametrize(
    "services, expected_id, expected_message",
    [
        pytest.param(
            [
                SESSION_CONTROL,
                {"service": "read_dtc_information", "sid": 0x19, "report_types": ["report_supported_dtc"], "dtc_status_availability_mask": 127},
            ],
            "FLYNC-DIA-WARN-CONS-300",
            "but declares no DTCs",
            id="0x19_without_dtcs",
        ),
        pytest.param(
            [SESSION_CONTROL, {"service": "clear_diagnostic_information", "sid": 0x14, "dtc_groups": [{"name": "all", "id": 0xFFFFFF}]}],
            "FLYNC-DIA-WARN-CONS-301",
            "but declares no DTCs",
            id="0x14_without_dtcs",
        ),
        pytest.param(
            [SESSION_CONTROL, {"service": "control_dtc_setting", "sid": 0x85}],
            "FLYNC-DIA-WARN-CONS-302",
            "no DTC service (0x19/0x14) it applies to",
            id="0x85_without_a_dtc_service",
        ),
        pytest.param(
            [
                {"service": "diagnostic_session_control", "sid": 0x10, "sessions": [{"name": "default", "id": 1}, {"name": "extended", "id": 3}]},
            ],
            "FLYNC-DIA-WARN-CONS-303",
            "does not offer TesterPresent (0x3E)",
            id="non_default_session_without_tester_present",
        ),
        pytest.param(
            [
                SESSION_CONTROL,
                {"service": "request_download", "sid": 0x34, "max_block_length": 1026},
                {"service": "transfer_data", "sid": 0x36},
            ],
            "FLYNC-DIA-WARN-CONS-304",
            "not RequestTransferExit (0x37)",
            id="transfer_without_exit",
        ),
    ],
)
def test_server_warns_on_incoherent_service_sets(services, expected_id, expected_message):
    assert_single_warning(validate_with_policy(UDSServer, server_data(services=services), path=None), expected_id, expected_message)


def test_non_default_session_with_tester_present_does_not_warn():
    services = [
        {"service": "diagnostic_session_control", "sid": 0x10, "sessions": [{"name": "default", "id": 1}, {"name": "extended", "id": 3}]},
        TESTER_PRESENT,
    ]
    _, findings = validate_with_policy(UDSServer, server_data(services=services), path=None)
    assert findings == []


# --------------------------------------------------------------------------------------
# Catalog cross-checks resolved in UDSServer.bind
# --------------------------------------------------------------------------------------

READABLE_DID = DataIdentifier(name="vin", did=0xF190, access="read", read_data=ONE_BYTE)
WRITABLE_DID = DataIdentifier(name="limit", did=0x0102, access="write", write_data=ONE_BYTE)
CONTROLLABLE_DID = DataIdentifier(name="fan", did=0x0103, access="read", read_data=ONE_BYTE, io_control=DIDIOControl(control_state=ONE_BYTE))


@pytest.mark.parametrize(
    "did, services, expected_id, service_label",
    [
        pytest.param(READABLE_DID, [SESSION_CONTROL], "FLYNC-DIA-MAJ-REQ-305", "ReadDataByIdentifier (0x22)", id="readable_needs_0x22"),
        pytest.param(WRITABLE_DID, [SESSION_CONTROL], "FLYNC-DIA-MAJ-REQ-306", "WriteDataByIdentifier (0x2E)", id="writable_needs_0x2E"),
        # CONTROLLABLE_DID is readable too, so 0x22 is present to isolate the 0x2F rule.
        pytest.param(
            CONTROLLABLE_DID,
            [SESSION_CONTROL, READ_DIDS],
            "FLYNC-DIA-MAJ-REQ-307",
            "InputOutputControlByIdentifier (0x2F)",
            id="controllable_needs_0x2F",
        ),
    ],
)
def test_server_rejects_a_did_no_service_can_access(did, services, expected_id, service_label):
    with pytest.raises(ValidationError) as exc_info:
        UDSConfig(**config_data(server_data(services=services, dids=[did.name]), dids=[did]))
    assert_single_error(exc_info, expected_id, f"but not {service_label} to access it")


@pytest.mark.parametrize(
    "did, service",
    [
        pytest.param(READABLE_DID, READ_DIDS, id="readable_with_0x22"),
        pytest.param(WRITABLE_DID, {"service": "write_data_by_identifier", "sid": 0x2E}, id="writable_with_0x2E"),
    ],
)
def test_server_accepts_a_did_its_services_can_access(did, service):
    config = UDSConfig(**config_data(server_data(services=[SESSION_CONTROL, service], dids=[did.name]), dids=[did]))
    assert config.servers[0]._did_refs == [did]


def test_read_write_did_needs_both_access_services():
    did = DataIdentifier(name="limit", did=0x0102, access="read_write", read_data=ONE_BYTE, write_data=ONE_BYTE)
    config = UDSConfig(
        **config_data(
            server_data(services=[SESSION_CONTROL, READ_DIDS, {"service": "write_data_by_identifier", "sid": 0x2E}], dids=["limit"]),
            dids=[did],
        )
    )
    assert config.servers[0]._did_refs == [did]


@pytest.mark.parametrize(
    "service, expected_id",
    [
        pytest.param(READ_DIDS, "FLYNC-DIA-WARN-CONS-308", id="0x22_without_readable_did"),
        pytest.param({"service": "write_data_by_identifier", "sid": 0x2E}, "FLYNC-DIA-WARN-CONS-309", id="0x2E_without_writable_did"),
        pytest.param({"service": "input_output_control_by_identifier", "sid": 0x2F}, "FLYNC-DIA-WARN-CONS-310", id="0x2F_without_controllable_did"),
    ],
)
def test_server_warns_on_an_access_service_with_nothing_to_act_on(service, expected_id):
    result = validate_with_policy(UDSConfig, config_data(server_data(services=[SESSION_CONTROL, service])), path=None)
    assert_single_warning(result, expected_id, "no DID it offers can be accessed that way")


def test_server_warns_on_dtcs_reported_in_more_than_one_format():
    dtcs = [
        DiagnosticTroubleCode(name="a", dtc=0x010203, format="iso_14229_1"),
        DiagnosticTroubleCode(name="b", dtc=0x010204, format="saej1939_73"),
    ]
    server = server_data(
        services=[SESSION_CONTROL, {"service": "clear_diagnostic_information", "sid": 0x14, "dtc_groups": [{"name": "all", "id": 0xFFFFFF}]}],
        dtcs=["a", "b"],
    )
    result = validate_with_policy(UDSConfig, config_data(server, dtcs=dtcs), path=None)
    assert_single_warning(result, "FLYNC-DIA-WARN-CONS-311", "more than one format")


@pytest.mark.parametrize(
    "report_type, expected_id, expected_message",
    [
        pytest.param(
            "report_dtc_snapshot_record_by_dtc_number",
            "FLYNC-DIA-WARN-CONS-312",
            "no DTC it declares has snapshot_records",
            id="snapshot",
        ),
        pytest.param(
            "report_dtc_ext_data_record_by_dtc_number",
            "FLYNC-DIA-WARN-CONS-313",
            "extended_data_records",
            id="extended_data",
        ),
        pytest.param(
            "report_severity_information_of_dtc",
            "FLYNC-DIA-WARN-CONS-314",
            "severity 'no_severity'",
            id="severity",
        ),
    ],
)
def test_server_warns_when_a_report_type_has_no_dtc_data_behind_it(report_type, expected_id, expected_message):
    dtc = DiagnosticTroubleCode(name="a", dtc=0x010203)
    server = server_data(
        services=[
            SESSION_CONTROL,
            {"service": "read_dtc_information", "sid": 0x19, "report_types": [report_type], "dtc_status_availability_mask": 0x7F},
        ],
        dtcs=["a"],
    )
    result = validate_with_policy(UDSConfig, config_data(server, dtcs=[dtc]), path=None)
    assert_single_warning(result, expected_id, expected_message)


def test_snapshot_report_type_with_a_snapshot_record_does_not_warn():
    dtc = DiagnosticTroubleCode(name="a", dtc=0x010203, snapshot_records=[{"record_number": 0x01, "data": ONE_BYTE}])
    server = server_data(
        services=[
            SESSION_CONTROL,
            {
                "service": "read_dtc_information",
                "sid": 0x19,
                "report_types": ["report_dtc_snapshot_record_by_dtc_number"],
                "dtc_status_availability_mask": 0x7F,
            },
        ],
        dtcs=["a"],
    )
    _, findings = validate_with_policy(UDSConfig, config_data(server, dtcs=[dtc]), path=None)
    assert findings == []


# --------------------------------------------------------------------------------------
# DID IO control
# --------------------------------------------------------------------------------------


def test_io_control_defaults_to_short_term_adjustment():
    assert DIDIOControl(control_state=ONE_BYTE).supported_parameters == ["short_term_adjustment"]


@pytest.mark.parametrize(
    "supported_parameters",
    [
        pytest.param(["return_control_to_ecu"], id="no_short_term_adjustment_needs_no_record"),
        pytest.param(["reset_to_default", "freeze_current_state"], id="two_iso_names"),
        pytest.param([0x04], id="manufacturer_specific_int"),
    ],
)
def test_io_control_without_short_term_adjustment_needs_no_control_state(supported_parameters):
    assert DIDIOControl(supported_parameters=supported_parameters).control_state is None


def test_io_control_requires_a_control_state_for_short_term_adjustment():
    with pytest.raises(ValidationError) as exc_info:
        DIDIOControl(supported_parameters=["short_term_adjustment"])
    assert_single_error(exc_info, "FLYNC-DIA-MAJ-REQ-296", "declares no control_state")


def test_io_control_rejects_duplicate_parameters():
    with pytest.raises(ValidationError) as exc_info:
        DIDIOControl(supported_parameters=["reset_to_default", "reset_to_default"])
    assert_single_error(exc_info, "FLYNC-CMN-MAJ-UNIQ-009", "IO control parameters")


@pytest.mark.parametrize(
    "field_count, expected_bytes",
    [pytest.param(1, 1, id="one_field"), pytest.param(8, 1, id="exactly_one_byte"), pytest.param(9, 2, id="spills_into_a_second_byte")],
)
def test_control_enable_mask_byte_length_follows_the_control_state(field_count, expected_bytes):
    record = DiagDataRecord(
        byte_length=field_count,
        fields=[{"name": f"f{i}", "type": "uint8", "bit_offset": 8 * i, "bit_length": 8} for i in range(field_count)],
    )
    assert DIDIOControl(control_state=record).control_enable_mask_byte_length() == expected_bytes
