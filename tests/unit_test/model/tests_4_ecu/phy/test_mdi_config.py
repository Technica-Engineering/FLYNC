import pytest
from pydantic import ValidationError

from flync.core.utils.exceptions_handling import validate_with_policy
from flync.model.flync_4_ecu.phy import BASET1, BASET1S, MII, SGMII
from flync.model.flync_4_ecu.port import ECUPort
from tests.error_assertions import assert_single_error, assert_single_warning

# Positive MDI Tests


@pytest.mark.parametrize(
    "speed, mii_config",
    [
        pytest.param(100, MII(mode="phy"), id="100baset1"),
        pytest.param(1000, SGMII(mode="phy"), id="1000baset1"),
    ],
)
def test_positive_baset1_config(speed, mii_config):
    ecu_port = ECUPort.model_validate(
        {
            "name": "test_ecu_port",
            "mii_config": mii_config,
            "mdi_config": {
                "mode": "base_t1",
                "speed": speed,
                "autonegotiation": False,
                "duplex": "full",
                "role": "master",
            },
        }
    )
    assert isinstance(ecu_port.mdi_config, BASET1)
    assert ecu_port.mdi_config.speed == speed


def test_positive_10baset1s_multidrop_config():
    """A multidrop node is half duplex; which slot of the cycle it owns is stated on the connection, not here."""

    mdi_config = {
        "mode": "base_t1s",
        "speed": 10,
        "duplex": "half",
        "topology": "multidrop",
    }

    ecu_port = ECUPort.model_validate(
        {
            "name": "test_ecu_port",
            "mii_config": MII(mode="phy", speed=10),
            "mdi_config": mdi_config,
        }
    )
    assert isinstance(ecu_port.mdi_config, BASET1S)
    assert ecu_port.mdi_config.topology == "multidrop"
    assert ecu_port.mdi_config.duplex == "half"


def test_positive_10baset1s_point_to_point_full_duplex():
    """A point-to-point T1S link may run full duplex and needs no PLCA profile."""

    ecu_port = ECUPort.model_validate(
        {
            "name": "test_ecu_port",
            "mii_config": MII(mode="phy", speed=10),
            "mdi_config": {"mode": "base_t1s", "topology": "p2p", "duplex": "full"},
        }
    )
    assert isinstance(ecu_port.mdi_config, BASET1S)


def test_positive_10baset1s_legacy_role_fields_are_dropped():
    """A pre-migration payload carrying ``role`` loads without it, and keeps ``autonegotiation``."""

    result = validate_with_policy(
        ECUPort,
        {
            "name": "test_ecu_port",
            "mii_config": MII(mode="phy", speed=10),
            "mdi_config": {
                "mode": "base_t1s",
                "speed": 10,
                "duplex": "half",
                "topology": "multidrop",
                "role": "master",
                "autonegotiation": False,
            },
        },
        path=None,
    )
    ecu_port = result[0]
    assert ecu_port is not None
    mdi = ecu_port.mdi_config
    assert isinstance(mdi, BASET1S)
    assert "role" not in type(mdi).model_fields
    assert mdi.role is None
    assert mdi.autonegotiation is False

    assert_single_warning(result, "FLYNC-ECU-WARN-LIFE-338", "'role'")


def test_positive_legacy_payload_without_topology_defaults_to_point_to_point():
    """
    The migration case that matters most: a configuration written before ``topology`` existed still loads.

    Such a payload names no topology and carries no PLCA profile.  Defaulting to multidrop would demand one and reject the file, so the
    default is p2p, which is what the old model described anyway.
    """

    ecu_port = ECUPort.model_validate(
        {
            "name": "test_ecu_port",
            "mdi_config": {"mode": "base_t1s", "speed": 10, "duplex": "half", "role": "slave", "autonegotiation": False},
        }
    )
    assert ecu_port.mdi_config.topology == "p2p"


def test_negative_autonegotiation_on_a_multidrop_segment():
    """A shared medium has no peer to negotiate with: autonegotiation runs between the two ends of a link."""

    with pytest.raises(ValidationError) as exc_info:
        ECUPort.model_validate(
            {
                "name": "test_ecu_port",
                "mdi_config": {
                    "mode": "base_t1s",
                    "topology": "multidrop",
                    "autonegotiation": True,
                },
            }
        )
    assert_single_error(exc_info, "FLYNC-ECU-MAJ-CONS-319", "10BASE-T1S PHY on a multidrop segment does not support autoneg")


def test_negative_10baset1s_full_duplex_on_multidrop():
    """Full duplex contradicts a shared medium, which is half duplex by construction."""

    mii_config = MII(mode="phy", speed=10)
    with pytest.raises(ValidationError) as exc_info:
        ECUPort.model_validate(
            {
                "name": "test_ecu_port",
                "mii_config": mii_config,
                "mdi_config": {
                    "mode": "base_t1s",
                    "duplex": "full",
                    "topology": "multidrop",
                },
            }
        )
    assert_single_error(exc_info, "FLYNC-ECU-MAJ-CONS-324", "duplex 'full' on topology 'multidrop'")


@pytest.mark.parametrize(
    "speed",
    [100, 1000],
    ids=["100", "1000"],
)
def test_negative_10baset1s_rejects_speeds_other_than_10(speed):
    """10BASE-T1S is fixed at 10 Mbit/s, so pydantic's Literal rejects anything else before any FLYNC rule runs."""

    mii_config = MII(mode="phy")
    with pytest.raises(ValidationError) as exc_info:
        ECUPort.model_validate(
            {
                "name": "test_ecu_port",
                "mii_config": mii_config,
                "mdi_config": {
                    "mode": "base_t1s",
                    "speed": speed,
                    "topology": "multidrop",
                },
            }
        )
    assert_single_error(exc_info, None, "Input should be 10")


def test_negative_baset1_rejects_speed_10():
    """BASE-T1 runs at 100 or 1000 Mbit/s; 10 Mbit/s belongs to BASE-T1S."""

    mii_config = MII(mode="phy")
    with pytest.raises(ValidationError) as exc_info:
        ECUPort.model_validate(
            {
                "name": "test_ecu_port",
                "mii_config": mii_config,
                "mdi_config": {
                    "mode": "base_t1",
                    "speed": 10,
                    "autonegotiation": False,
                    "duplex": "full",
                    "role": "master",
                },
            }
        )
    assert_single_error(exc_info, None, "Input should be 100 or 1000")


@pytest.mark.parametrize(
    "speed",
    [100, 1000],
    ids=["100", "1000"],
)
def test_negative_baset1_rejects_half_duplex(speed):
    """BASE-T1 is full duplex only."""

    mii_config = MII(mode="phy")
    with pytest.raises(ValidationError) as exc_info:
        ECUPort.model_validate(
            {
                "name": "test_ecu_port",
                "mii_config": mii_config,
                "mdi_config": {
                    "mode": "base_t1",
                    "speed": speed,
                    "autonegotiation": False,
                    "duplex": "half",
                    "role": "master",
                },
            }
        )
    assert_single_error(exc_info, None, "Input should be 'full'")


def test_negative_unknown_mdi_mode_is_rejected():
    """The ``mode`` discriminator accepts only the declared PHY variants; anything else is rejected before a field is looked at."""

    mii_config = MII(mode="phy")
    with pytest.raises(ValidationError) as exc_info:
        ECUPort.model_validate(
            {
                "name": "test_ecu_port",
                "mii_config": mii_config,
                "mdi_config": {"mode": "base_t9000", "speed": 10},
            }
        )
    assert_single_error(exc_info, None, "mdi_config")
