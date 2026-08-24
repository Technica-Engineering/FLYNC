from pydantic_core import PydanticCustomError

from flync.core.utils.exceptions import (
    CATEGORY_CODE,
    Category,
    Severity,
    _validation_warnings,
    compose_error_id,
    err_fatal,
    err_major,
    err_minor,
    module_code_for,
    warn,
)


class TestModuleCodeFor:
    def test_resolves_key_from_submodel_package(self):
        assert module_code_for("flync.model.flync_4_ecu.port") == "ECU"
        assert module_code_for("flync.model.flync_4_tsn.qos") == "TSN"
        assert module_code_for("flync.model.flync_4_someip.service_interface") == "SOM"

    def test_top_level_model_falls_back_to_gen(self):
        assert module_code_for("flync.model.flync_model") == "GEN"

    def test_version_migrators_fall_back_to_gen(self):
        assert module_code_for("flync.core.version_migrators.legacy_controller_check") == "GEN"

    def test_shared_utils_fall_back_to_cmn(self):
        assert module_code_for("flync.core.utils.validators_helpers") == "CMN"

    def test_unknown_module_falls_back_to_cmn(self):
        assert module_code_for("totally.made.up.module") == "CMN"


class TestComposeErrorId:
    def test_full_id(self):
        assert compose_error_id(Severity.MAJ, "ECU", Category.COMPATIBILITY, "005") == "FLYNC-ECU-MAJ-COMP-005"

    def test_missing_category_renders_unc(self):
        assert compose_error_id(Severity.MIN, "BUS", None, "010") == "FLYNC-BUS-MIN-UNC-010"

    def test_missing_number_renders_zeroes(self):
        assert compose_error_id(Severity.WARN, "GEN", Category.REQUIRED, None) == "FLYNC-GEN-WARN-REQ-000"


def test_every_category_has_a_short_code():
    assert set(CATEGORY_CODE) == set(Category)
    assert all(code and isinstance(code, str) for code in CATEGORY_CODE.values())


class TestFactories:
    def test_err_minor_type_and_id(self):
        err = err_minor("boom", category=Category.REQUIRED, error_number="007")
        assert isinstance(err, PydanticCustomError)
        assert err.type == "minor"
        assert err.context["error_id"].startswith("FLYNC-")
        assert err.context["error_id"].endswith("-MIN-REQ-007")

    def test_err_major_type(self):
        err = err_major("boom", category=Category.CONSISTENCY, error_number="008")
        assert err.type == "major"
        assert "-MAJ-CONS-008" in err.context["error_id"]

    def test_err_fatal_type(self):
        err = err_fatal("boom", category=Category.STRUCTURAL, error_number="009")
        assert err.type == "fatal"
        assert "-FAT-STRUCT-009" in err.context["error_id"]

    def test_defaults_when_unset(self):
        err = err_minor("boom")
        assert "-MIN-UNC-000" in err.context["error_id"]

    def test_context_placeholders_preserved(self):
        err = err_minor("value {v}", v=5, error_number="001")
        assert err.context["v"] == 5
        assert "error_id" in err.context


class TestWarn:
    def test_noop_without_active_context(self):
        _validation_warnings.set(None)
        assert warn("nobody listening", error_number="001") is None

    def test_records_into_active_list(self):
        token = _validation_warnings.set([])
        try:
            warn("heads up", category=Category.FORMAT, error_number="003")
            recorded = _validation_warnings.get()
        finally:
            _validation_warnings.reset(token)
        assert len(recorded) == 1
        entry = recorded[0]
        assert entry["type"] == "warning"
        assert entry["msg"] == "heads up"
        assert entry["ctx"]["error_id"].endswith("-WARN-FMT-003")
