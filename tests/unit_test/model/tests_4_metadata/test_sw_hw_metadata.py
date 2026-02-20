import pytest
from pydantic import ValidationError
from semver import Version as SemVersion
from flync.model.flync_4_metadata.metadata import (
    HardwareBaseMetadata,
    SoftwareBaseMetadata,
)


def test_software_metadata_inherits_baseversion():
    sw = SoftwareBaseMetadata.model_validate(
        {"version_schema": "semver", "version": "3.2.1"}
    )
    assert isinstance(sw.version, SemVersion)


def test_hardware_metadata_optional_fields():
    hw = HardwareBaseMetadata.model_validate(
        {
            "version_schema": "semver",
            "version": "1.0.1",
            "supplier": "My-HW-Supplier",
            "product_id": "ABC-123",
        }
    )
    assert hw.supplier == "My-HW-Supplier"
    assert hw.product_id == "ABC-123"
    assert isinstance(hw.version, SemVersion)


def test_hardware_metadata_missing_version():
    with pytest.raises(ValidationError) as exc:
        HardwareBaseMetadata.model_validate(
            {"version_schema": "semver", "supplier": "My-HW-Supplier"}
        )
    assert "version" in str(exc.value)
    assert "Field required" in str(exc.value)
