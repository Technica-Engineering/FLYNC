import pytest

from pydantic import ValidationError
from flync.model.flync_4_ecu.switch import MulticastGroup
import flync.core.utils.base_utils as utils


@pytest.mark.parametrize(
    "input_value,expected_test_result",
    [("01:00:5E:00:00:00", True), ("abcde", False)],
)
def test_mac_address_helper(input_value, expected_test_result):
    is_mac, _ = utils.is_mac_address(input_value)
    assert is_mac == expected_test_result


@pytest.mark.parametrize(
    "input_value,expected_test_result",
    [("00:11:22:33:44:55", True), ("01:00:5E:00:00:00", False)],
)
def test_mac_unicast_helper(input_value, expected_test_result):
    is_unicast, _ = utils.is_mac_unicast(input_value)
    assert is_unicast == expected_test_result


@pytest.mark.parametrize(
    "input_value,expected_test_result",
    [("01:00:5E:00:00:00", True), ("00:11:22:33:44:55", False)],
)
def test_mac_multicast_helper(input_value, expected_test_result):
    is_mcast, _ = utils.is_mac_multicast(input_value)
    assert is_mcast == expected_test_result


@pytest.mark.parametrize(
    "input_value,expected_test_result",
    [
        ("10.10.10.10", True),
        ("2001:db8:85a3:0:0:8a2e:370:7334", True),
        ("asdfasdf", False),
        ("00:11:22:33:44:55", False),
    ],
)
def test_ip_address_helper(input_value, expected_test_result):
    is_ip, _ = utils.is_ip_address(input_value)
    assert is_ip == expected_test_result


@pytest.mark.parametrize(
    "input_value,expected_test_result",
    [
        ("239.1.1.39", True),
        ("FF02::1", True),
        ("10.10.10.10", False),
        ("2001:db8:85a3:0:0:8a2e:370:7334", False),
    ],
)
def test_ip_multicast_helper(input_value, expected_test_result):
    is_mcast, _ = utils.is_ip_multicast(input_value)
    assert is_mcast == expected_test_result


def test_positive_multicast_group_ipv4():
    m_cast1 = {"address": "224.0.0.1", "ports": ["port1", "port2"]}
    m_cast1 = MulticastGroup.model_validate(m_cast1)
    assert isinstance(m_cast1, MulticastGroup)


def test_negative_multicast_group_ipv4():
    m_cast1 = {"address": "10.0.0.1", "ports": ["port1", "port2"]}
    with pytest.raises(ValidationError) as e:
        m_cast1 = MulticastGroup.model_validate(m_cast1)


def test_positive_multicast_group_ipv6():
    m_cast1 = {"address": "ff02::1", "ports": ["port1", "port2"]}
    m_cast1 = MulticastGroup.model_validate(m_cast1)
    assert isinstance(m_cast1, MulticastGroup)


def test_negative_multicast_group_ipv6():
    m_cast1 = {
        "address": "2001:0db8:85a3:0000:0000:8a2e:0370:7334",
        "ports": ["port1", "port2"],
    }
    with pytest.raises(ValidationError) as e:
        m_cast1 = MulticastGroup.model_validate(m_cast1)


def test_positive_multicast_group_mac():
    m_cast1 = {"address": "01:00:5E:00:00:00", "ports": ["port1", "port2"]}
    m_cast1 = MulticastGroup.model_validate(m_cast1)
    assert isinstance(m_cast1, MulticastGroup)


def test_negative_multicast_group_mac():
    m_cast1 = {"address": "00:00:5E:00:00:00", "ports": ["port1", "port2"]}
    with pytest.raises(ValidationError) as e:
        m_cast1 = MulticastGroup.model_validate(m_cast1)
