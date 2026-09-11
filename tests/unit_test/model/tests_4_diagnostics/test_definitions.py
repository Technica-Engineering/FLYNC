import pytest
from pydantic import ValidationError

from flync.model.flync_4_diagnostics.uds.data_identifier import DataIdentifier
from flync.model.flync_4_diagnostics.uds.datatypes import DiagDataRecord
from flync.model.flync_4_diagnostics.uds.dtc import DiagnosticTroubleCode
from flync.model.flync_4_diagnostics.uds.routine import Routine
from tests.error_assertions import assert_single_error

READ_DATA = DiagDataRecord(byte_length=1)
WRITE_DATA = DiagDataRecord(byte_length=1)


def test_did_read_access_accepted_with_read_data():
    did = DataIdentifier(name="vin", did=0xF190, access="read", read_data=READ_DATA)
    assert did.did == 0xF190


def test_did_read_write_access_accepted_with_both_data():
    did = DataIdentifier(name="vin", did=0xF190, access="read_write", read_data=READ_DATA, write_data=WRITE_DATA)
    assert did.access == "read_write"


def test_did_write_access_accepted_with_write_data():
    did = DataIdentifier(name="vin", did=0xF190, access="write", write_data=WRITE_DATA)
    assert did.write_data is WRITE_DATA


def test_did_read_access_rejected_without_read_data():
    with pytest.raises(ValidationError) as exc_info:
        DataIdentifier(name="vin", did=0xF190, access="read")
    assert_single_error(exc_info, "FLYNC-DIA-MAJ-REQ-259", "no read_data")


def test_did_write_access_rejected_without_write_data():
    with pytest.raises(ValidationError) as exc_info:
        DataIdentifier(name="vin", did=0xF190, access="write")
    assert_single_error(exc_info, "FLYNC-DIA-MAJ-REQ-260", "no write_data")


def test_did_read_access_rejected_with_write_data():
    with pytest.raises(ValidationError) as exc_info:
        DataIdentifier(name="vin", did=0xF190, access="read", read_data=READ_DATA, write_data=WRITE_DATA)
    assert_single_error(exc_info, "FLYNC-DIA-MAJ-CONS-261", "defines write_data")


@pytest.mark.parametrize("did", [0x0000, 0xFFFF])
def test_did_id_boundaries_accepted(did):
    DataIdentifier(name="d", did=did, access="read", read_data=READ_DATA)


@pytest.mark.parametrize("did", [-1, 0x10000])
def test_did_id_out_of_range_rejected(did):
    with pytest.raises(ValidationError) as exc_info:
        DataIdentifier(name="d", did=did, access="read", read_data=READ_DATA)
    assert_single_error(exc_info, None, "did")


def test_did_write_access_rejected_with_read_data():
    with pytest.raises(ValidationError) as exc_info:
        DataIdentifier(name="vin", did=0xF190, access="write", read_data=READ_DATA, write_data=WRITE_DATA)
    assert_single_error(exc_info, "FLYNC-DIA-MAJ-CONS-283", "declared 'write' but defines read_data")


def test_did_write_access_accepted_with_write_data_only():
    did = DataIdentifier(name="vin", did=0xF190, access="write", write_data=WRITE_DATA)
    assert did.read_data is None


def test_routine_start_accepted_with_start_request():
    routine = Routine(name="r", rid=0xFF00, supported_sub_functions=["start"], start_request=DiagDataRecord(byte_length=0))
    assert routine.rid == 0xFF00


def test_routine_start_rejected_without_start_request():
    with pytest.raises(ValidationError) as exc_info:
        Routine(name="r", rid=0xFF00, supported_sub_functions=["start"])
    assert_single_error(exc_info, "FLYNC-DIA-MAJ-REQ-263", "no start_request")


def test_routine_stop_rejected_without_stop_request():
    with pytest.raises(ValidationError) as exc_info:
        Routine(name="r", rid=0xFF00, supported_sub_functions=["start", "stop"], start_request=DiagDataRecord(byte_length=0))
    assert_single_error(exc_info, "FLYNC-DIA-MAJ-REQ-264", "no stop_request")


def test_routine_request_results_rejected_without_response():
    with pytest.raises(ValidationError) as exc_info:
        Routine(
            name="r",
            rid=0xFF00,
            supported_sub_functions=["start", "request_results"],
            start_request=DiagDataRecord(byte_length=0),
        )
    assert_single_error(exc_info, "FLYNC-DIA-MAJ-REQ-265", "no request_results_response")


def test_routine_rejects_unknown_sub_function():
    with pytest.raises(ValidationError) as exc_info:
        Routine(name="r", rid=0xFF00, supported_sub_functions=["not_a_real_sub_function"])
    assert_single_error(exc_info, None, "supported_sub_functions")


def test_routine_accepts_all_sub_functions_with_their_data():
    routine = Routine(
        name="r",
        rid=0xFF00,
        supported_sub_functions=["start", "stop", "request_results"],
        start_request=DiagDataRecord(byte_length=0),
        stop_request=DiagDataRecord(byte_length=0),
        request_results_response=DiagDataRecord(byte_length=1),
    )
    assert routine.supported_sub_functions == ["start", "stop", "request_results"]


def test_dtc_accepts_defaults():
    dtc = DiagnosticTroubleCode(name="d", dtc=0x010203)
    assert dtc.format == "iso_14229_1"
    assert dtc.severity == "no_severity"


@pytest.mark.parametrize("dtc_value", [0x000000, 0xFFFFFF])
def test_dtc_id_boundaries_accepted(dtc_value):
    DiagnosticTroubleCode(name="d", dtc=dtc_value)


def test_dtc_id_out_of_range_rejected():
    with pytest.raises(ValidationError) as exc_info:
        DiagnosticTroubleCode(name="d", dtc=0x1000000)
    assert_single_error(exc_info, None, "dtc")
