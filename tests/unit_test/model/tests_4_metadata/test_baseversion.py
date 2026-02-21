import pytest

from pydantic import ValidationError
from packaging.version import Version as Pep440Version
from semver import Version as SemVersion

from flync.model.flync_4_metadata.metadata import BaseVersion


def test_baseversion_pep440_valid_string():
    v = BaseVersion.model_validate(
        {"version_schema": "pep440", "version": "1.2.3rc1"}
    )
    assert isinstance(v.version, Pep440Version)
    assert str(v.version) == "1.2.3rc1"


def test_baseversion_semver_valid_string():
    v = BaseVersion.model_validate(
        {"version_schema": "semver", "version": "2.5.1"}
    )
    assert isinstance(v.version, SemVersion)
    assert str(v.version) == "2.5.1"


def test_baseversion_invalid_pep440():
    with pytest.raises(ValidationError) as exc:
        BaseVersion.model_validate(
            {"version_schema": "pep440", "version": "not_a_version"}
        )
    assert "not valid PEP 440" in str(exc.value)


def test_baseversion_invalid_semver():
    with pytest.raises(ValidationError) as exc:
        BaseVersion.model_validate(
            {"version_schema": "semver", "version": "1.0"}
        )
    assert "not valid Semantic Version" in str(exc.value)


def test_baseversion_unsupported_schema():
    with pytest.raises(ValidationError) as exc:
        BaseVersion.model_validate(
            {"version_schema": "unknown", "version": "1.0.0"}
        )
    assert "semver" in str(exc.value)
    assert "pep440" in str(exc.value)
