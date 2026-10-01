"""Tests for SOME/IP service-instance uniqueness *across the sockets of one ECU*."""

import pytest

from flync.core.utils.exceptions_handling import validate_with_policy
from flync.model.flync_4_ecu.ecu import ECU
from tests.error_assertions import assert_no_findings, assert_single_warning
from tests.unit_test.model.tests_4_ecu.conftest import INSTANCE_ID, MAJOR_VERSION, SERVICE_ID

DUPLICATE_CONSUMER_WARNING_ID = "FLYNC-ECU-WARN-UNIQ-241"
DUPLICATE_PROVIDER_WARNING_ID = "FLYNC-ECU-WARN-UNIQ-243"

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


@pytest.mark.parametrize(
    ("role", "expected_warning_id"),
    [
        pytest.param("consumer", DUPLICATE_CONSUMER_WARNING_ID, id="consumer"),
        pytest.param("provider", DUPLICATE_PROVIDER_WARNING_ID, id="provider"),
    ],
)
def test_ecu_deploying_same_instance_twice_emits_warning(role, expected_warning_id, two_socket_ecu_kwargs):
    """Deploying one service instance on two sockets of one ECU loads, but is warned about - for either role.

    The provider case is deliberately only a warning until FLYNC models variants (see
    ``ECU.validate_unique_someip_service_instances``). It has to be checked through ``validate_with_policy``:
    ``warn`` is a no-op outside that context, so a bare ``ECU.model_validate`` reports nothing at all.
    """

    result = validate_with_policy(ECU, two_socket_ecu_kwargs(role), path=None)

    assert_single_warning(result, expected_warning_id, INSTANCE_MESSAGE_FRAGMENT)


@pytest.mark.parametrize("difference", DISTINCT_INSTANCES)
@pytest.mark.parametrize("role", ["provider", "consumer"])
def test_ecu_deploying_distinct_instances_is_unaffected(role, difference, two_socket_ecu_kwargs):
    """Sanity check: two sockets deploying different service instances raise neither warning nor error."""

    result = validate_with_policy(ECU, two_socket_ecu_kwargs(role, **difference), path=None)

    assert_no_findings(result)


@pytest.fixture
def two_interface_ecu_kwargs(someip_deployment, udp_socket_data, minimal_ecu_kwargs):
    """Return a factory for an ECU whose two sockets sit on *different* Ethernet interfaces (IP stacks).

    ``role`` and ``difference`` apply to the deployment placed on the second interface, mirroring
    ``two_socket_ecu_kwargs`` but splitting it across two IP stacks instead of two sockets on one.
    """

    def _build(role: str, **difference) -> dict:
        iface_1 = [udp_socket_data(name="socket_a", port_no=30500, deployments=[someip_deployment(role)])]
        iface_2 = [udp_socket_data(name="socket_b", port_no=30501, deployments=[someip_deployment(role, **difference)])]
        return minimal_ecu_kwargs(sockets=None, interfaces=[iface_1, iface_2])

    return _build


def test_consumer_same_instance_on_different_ip_stacks_is_unaffected(two_interface_ecu_kwargs):
    """Two IP stacks of one ECU consuming the same service instance independently is not a conflict.

    The consumer (241) rule is scoped per Ethernet interface, so the same instance consumed once on each of two
    interfaces must load cleanly.
    """

    result = validate_with_policy(ECU, two_interface_ecu_kwargs("consumer"), path=None)

    assert_no_findings(result)


@pytest.mark.parametrize(
    ("role", "expected_warning_id"),
    [
        pytest.param("consumer", DUPLICATE_CONSUMER_WARNING_ID, id="consumer"),
        pytest.param("provider", DUPLICATE_PROVIDER_WARNING_ID, id="provider"),
    ],
)
def test_duplicate_instance_across_different_ip_stacks_warns(role, expected_warning_id, two_interface_ecu_kwargs):
    """The *provider* (243) rule stays ECU-wide: repeating an instance across two IP stacks is still warned.

    The consumer (241) rule, by contrast, is scoped per IP stack and will not fire here - it is covered by the
    distinct-interface test above.
    """

    result = validate_with_policy(ECU, two_interface_ecu_kwargs(role), path=None)

    if role == "provider":
        assert_single_warning(result, expected_warning_id, INSTANCE_MESSAGE_FRAGMENT)
    else:
        assert_no_findings(result)
