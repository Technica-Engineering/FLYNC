import pytest
from pydantic import ValidationError
from packaging.version import Version as Pep440Version
from semver import Version as SemVersion
from flync.model.flync_4_metadata.metadata import ECUMetadata


def test_ecu_metadata_full_positive():
    ecu = ECUMetadata.model_validate(
        {
            "author": "Tier1",
            "compatible_flync_version": {
                "version_schema": "semver",
                "version": "1.1.0",
            },
            "hardware": {
                "version_schema": "pep440",
                "version": "1.0",
                "supplier": "My-Tier1",
            },
            "software": {
                "version_schema": "semver",
                "version": "5.4.3",
            },
        }
    )

    assert ecu.type == "ecu"
    assert ecu.hardware.supplier == "My-Tier1"
    assert isinstance(ecu.software.version, SemVersion)
    assert isinstance(ecu.hardware.version, Pep440Version)


def test_ecu_metadata_invalid_nested_version():
    with pytest.raises(ValidationError) as exc:
        ECUMetadata.model_validate(
            {
                "author": "Tier1",
                "compatible_flync_version": {
                    "version_schema": "semver",
                    "version": "1.1.0",
                },
                "software": {
                    "version_schema": "semver",
                    "version": "bad.version",
                },
            }
        )

        assert "not valid PEP 440" in str(exc.value)
        assert "not valid Semantic Version" in str(exc.value)


def test_system_metadata_invalid_type_literal():
    with pytest.raises(ValidationError) as exc:
        ECUMetadata.model_validate(
            {
                "type": "embedded",
                "author": "developer1",
                "compatible_flync_version": {
                    "version_schema": "semver",
                    "version": "0.9.0",
                },
                "hardware": {
                    "version_schema": "semver",
                    "version": "2.0.0",
                },
                "software": {
                    "version_schema": "semver",
                    "version": "1.3.0",
                },
            }
        )
    errors = exc.value.errors()
    assert len(errors) == 1

    err = errors[0]
    assert err["loc"] == ("type",)
    assert err["type"] == "literal_error"
    assert "ecu" in err["msg"]
    assert err["input"] == "embedded"
