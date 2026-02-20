import pytest
from pydantic import ValidationError
from semver import Version as SemVersion
from flync.model.flync_4_metadata.metadata import SystemMetadata


def test_positive_system_metadata():
    sys_meta = SystemMetadata.model_validate(
        {
            "author": "OEM Corp",
            "compatible_flync_version": {
                "version_schema": "semver",
                "version": "0.9.0",
            },
            "release": {
                "version_schema": "semver",
                "version": "2.0.0",
            },
            "oem": "OEM Corp",
            "platform": "Gen5",
        }
    )

    assert sys_meta.type == "system"
    assert isinstance(sys_meta.release.version, SemVersion)


def test_system_metadata_invalid_type_literal():
    with pytest.raises(ValidationError) as exc:
        SystemMetadata.model_validate(
            {
                "type": "ecu",
                "author": "OEM Corp",
                "compatible_flync_version": {
                    "version_schema": "semver",
                    "version": "0.9.0",
                },
                "release": {
                    "version_schema": "semver",
                    "version": "2.0.0",
                },
            }
        )
    errors = exc.value.errors()
    assert len(errors) == 1

    err = errors[0]
    assert err["loc"] == ("type",)
    assert err["type"] == "literal_error"
    assert "system" in err["msg"]
    assert err["input"] == "ecu"
