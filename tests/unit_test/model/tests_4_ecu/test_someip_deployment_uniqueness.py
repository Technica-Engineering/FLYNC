"""Tests for SOME/IP service-instance uniqueness *across the sockets of one ECU*."""

import pytest
from pydantic import ValidationError

from flync.core.utils.exceptions_handling import validate_with_policy
from flync.model.flync_4_ecu.ecu import ECU
from tests.error_assertions import assert_no_findings, assert_single_error, assert_single_warning
from tests.unit_test.model.tests_4_ecu.conftest import INSTANCE_ID, MAJOR_VERSION, SERVICE_ID

DUPLICATE_CONSUMER_WARNING_ID = "FLYNC-ECU-WARN-UNIQ-241"
DUPLICATE_PROVIDER_ERROR_ID = "FLYNC-ECU-MAJ-UNIQ-243"

#: The reported message must identify the repeated instance; that is all these tests pin of the wording.
INSTANCE_MESSAGE_FRAGMENT = f"instance_id={INSTANCE_ID}"

#: Each way the second socket's deployment can differ while staying a *different* service instance.
DISTINCT_INSTANCES = [
    pytest.param(dict(instance_id=INSTANCE_ID + 1), id="different_instance_id"),
    pytest.param(dict(major_version=MAJOR_VERSION + 1), id="different_major_version"),
    pytest.param(dict(service=SERVICE_ID + 1), id="different_service"),
]


@pytest.fixture
def two_socket_ecu_kwargs(someip_deployment, udp_socket_data, minimal_ecu_kwargs):
    """Return a factory for ECU kwargs whose two sockets each deploy one instance of the given *role*.

    ``difference`` is applied to the second socket's deployment, so a caller flips between "same instance
    twice" (the default, no difference) and a neighbouring instance that must stay unaffected.
    """

    def _build(role: str, **difference) -> dict:
        sockets = [
            udp_socket_data(name="socket_a", port_no=30500, deployments=[someip_deployment(role)]),
            udp_socket_data(name="socket_b", port_no=30501, deployments=[someip_deployment(role, **difference)]),
        ]
        return minimal_ecu_kwargs(sockets)

    return _build


def test_ecu_consuming_same_instance_twice_emits_warning(two_socket_ecu_kwargs):
    """Consuming one service instance on two sockets of one ECU loads, but is warned about."""

    result = validate_with_policy(ECU, two_socket_ecu_kwargs("consumer"), path=None)

    assert_single_warning(result, DUPLICATE_CONSUMER_WARNING_ID, INSTANCE_MESSAGE_FRAGMENT)


def test_ecu_providing_same_instance_twice_rejected(two_socket_ecu_kwargs):
    """Providing one service instance on two sockets of one ECU is a hard conflict."""

    ecu_kwargs = two_socket_ecu_kwargs("provider")
    with pytest.raises(ValidationError) as exc_info:
        ECU.model_validate(ecu_kwargs)

    assert_single_error(exc_info, DUPLICATE_PROVIDER_ERROR_ID, INSTANCE_MESSAGE_FRAGMENT)


@pytest.mark.parametrize("difference", DISTINCT_INSTANCES)
@pytest.mark.parametrize("role", ["provider", "consumer"])
def test_ecu_deploying_distinct_instances_is_unaffected(role, difference, two_socket_ecu_kwargs):
    """Sanity check: two sockets deploying different service instances raise neither warning nor error."""

    result = validate_with_policy(ECU, two_socket_ecu_kwargs(role, **difference), path=None)

    assert_no_findings(result)
