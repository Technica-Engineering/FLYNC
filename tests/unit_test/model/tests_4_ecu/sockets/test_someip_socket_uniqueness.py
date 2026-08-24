"""Tests for SOME/IP service-instance uniqueness *within a single socket*."""

import pytest
from pydantic import ValidationError

from flync.model.flync_4_ecu.sockets import SocketUDP
from tests.error_assertions import assert_single_error
from tests.unit_test.model.tests_4_ecu.conftest import INSTANCE_ID, MAJOR_VERSION, SERVICE_ID

SOCKET_NAME = "my_socket"

DUPLICATE_ON_SOCKET_ERROR_ID = "FLYNC-ECU-MAJ-UNIQ-244"

#: Each way a second deployment can differ from the first while staying a *different* service instance.
DISTINCT_INSTANCES = [
    pytest.param(dict(instance_id=INSTANCE_ID + 1), id="different_instance_id"),
    pytest.param(dict(major_version=MAJOR_VERSION + 1), id="different_major_version"),
    pytest.param(dict(service=SERVICE_ID + 1), id="different_service"),
]


@pytest.mark.parametrize("role", ["provider", "consumer"])
def test_duplicate_service_instance_on_same_socket_rejected(role, someip_deployment, udp_socket_data):
    """Two deployments of one role for the same service instance on one socket are rejected."""

    socket_data = udp_socket_data(name=SOCKET_NAME, deployments=[someip_deployment(role), someip_deployment(role)])

    with pytest.raises(ValidationError) as exc_info:
        SocketUDP.model_validate(socket_data)
    assert_single_error(exc_info, DUPLICATE_ON_SOCKET_ERROR_ID, SOCKET_NAME)


@pytest.mark.parametrize("difference", DISTINCT_INSTANCES)
@pytest.mark.parametrize("roles", [("provider", "provider"), ("consumer", "consumer"), ("provider", "consumer")])
def test_distinct_service_instances_on_same_socket_allowed(roles, difference, someip_deployment, udp_socket_data):
    """Sanity check: two deployments naming different service instances share a socket, whatever their roles."""

    first_role, second_role = roles
    socket_data = udp_socket_data(
        name=SOCKET_NAME,
        deployments=[someip_deployment(first_role), someip_deployment(second_role, **difference)],
    )

    assert len(SocketUDP.model_validate(socket_data).deployments) == 2
