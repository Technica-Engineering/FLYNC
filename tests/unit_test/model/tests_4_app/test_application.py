"""Tests for provider/consumer overlap within a single application."""

import pytest

from flync.core.utils.exceptions_handling import validate_with_policy
from flync.model.flync_4_app import App
from tests.error_assertions import assert_no_findings, assert_single_warning
from tests.unit_test.model.tests_4_app.conftest import SERVICE_REFERENCE

SELF_CONSUMED_INSTANCE_WARNING_ID = "FLYNC-CMN-WARN-CONS-242"


def test_app_referencing_same_service_instance_as_consumer_and_provider_emits_warning(app_data):
    """An app that provides the exact instance it consumes loads, but is warned about."""

    result = validate_with_policy(App, app_data(), path=None)

    assert_single_warning(result, SELF_CONSUMED_INSTANCE_WARNING_ID, f"{SERVICE_REFERENCE['service_id']:#06x}")


@pytest.mark.parametrize(
    "provider_difference",
    [
        pytest.param(dict(service_id=SERVICE_REFERENCE["service_id"] + 1), id="different_service_id"),
        pytest.param(dict(instance_id=SERVICE_REFERENCE["instance_id"] + 1), id="different_instance_id"),
        pytest.param(dict(major_version=SERVICE_REFERENCE["major_version"] + 1), id="different_major_version"),
    ],
)
def test_app_with_distinct_provider_and_consumer_refs_is_unaffected(provider_difference, app_data):
    """Sanity check: a provider reference differing in any part of the triple raises no warning."""

    result = validate_with_policy(App, app_data(**provider_difference), path=None)

    assert_no_findings(result)
