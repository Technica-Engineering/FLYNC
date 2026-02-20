import pytest
from pydantic import ValidationError
from packaging.version import Version as Pep440Version
from semver import Version as SemVersion
from flync.model.flync_4_metadata.metadata import EmbeddedMetadata


def test_positive_embedded_metadata():
    emb = EmbeddedMetadata.model_validate(
        {
            "author": "OEM",
            "compatible_flync_version": {
                "version_schema": "pep440",
                "version": "1.0",
            },
            "target_system": "rtos",
            "app": {"version_schema": "pep440", "version": "3.0.0"},
            "bootloader": {"version_schema": "semver", "version": "5.0.1"},
        }
    )

    assert emb.type == "embedded"
    assert emb.target_system == "rtos"
    assert isinstance(emb.app.version, Pep440Version)
    assert isinstance(emb.bootloader.version, SemVersion)


def test_system_metadata_invalid_type_literal():
    with pytest.raises(ValidationError) as exc:
        EmbeddedMetadata.model_validate(
            {
                "type": "ecu",
                "author": "developer1",
                "compatible_flync_version": {
                    "version_schema": "semver",
                    "version": "0.9.0",
                },
                "hardware": {
                    "version_schema": "semver",
                    "version": "2.0.0",
                },
                "app": {
                    "version_schema": "semver",
                    "version": "1.0.0",
                },
                "bootloader": {
                    "version_schema": "semver",
                    "version": "1.0.0",
                },
                "target_system": "rtos",
            }
        )
    errors = exc.value.errors()
    assert len(errors) == 1

    err = errors[0]
    assert err["loc"] == ("type",)
    assert err["type"] == "literal_error"
    assert "embedded" in err["msg"]
    assert err["input"] == "ecu"
