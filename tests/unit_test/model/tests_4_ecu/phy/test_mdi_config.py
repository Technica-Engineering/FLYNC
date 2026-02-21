import pytest
from pydantic import ValidationError

from flync.model.flync_4_ecu.phy import BASET1, BASET1S, MII
from flync.model.flync_4_ecu.port import ECUPort

# Positive MDI Tests


def test_positive_100baset1_config():
    mdi_config = {
        "mode": "base_t1",
        "speed": 100,
        "autonegotiation": False,
        "duplex": "full",
        "role": "master",
    }

    ecu_port = ECUPort.model_validate(
        {
            "name": "test_ecu_port",
            "mii_config": MII(mode="phy"),
            "mdi_config": mdi_config,
        }
    )
    assert isinstance(ecu_port.mdi_config, BASET1)


def test_positive_1000baset1_config():
    mdi_config = {
        "mode": "base_t1",
        "speed": 100,
        "autonegotiation": False,
        "duplex": "full",
        "role": "master",
    }
    ecu_port = ECUPort.model_validate(
        {
            "name": "test_ecu_port",
            "mii_config": MII(mode="phy"),
            "mdi_config": mdi_config,
        }
    )
    assert isinstance(ecu_port.mdi_config, BASET1)


def test_positive_10baset1s_config():
    mdi_config = {
        "mode": "base_t1s",
        "speed": 10,
        "autonegotiation": False,
        "duplex": "half",
        "role": "master",
    }

    ecu_port = ECUPort.model_validate(
        {
            "name": "test_ecu_port",
            "mii_config": MII(mode="phy", speed=10),
            "mdi_config": mdi_config,
        }
    )
    assert isinstance(ecu_port.mdi_config, BASET1S)


# Negative MDI Tests
def test_negative_mode_config():
    mdi_100_config = {
        "mode": "base_t1s",
        "speed": 100,
        "autonegotiation": False,
        "duplex": "full",
        "role": "master",
    }
    mdi_1000_config = {
        "mode": "base_t1s",
        "speed": 1000,
        "autonegotiation": False,
        "duplex": "full",
        "role": "master",
    }
    mdi_10_config = {
        "mode": "base_t1",
        "speed": 10,
        "autonegotiation": False,
        "duplex": "half",
        "role": "master",
    }

    with pytest.raises(ValidationError) as val100:
        ecu_port_100 = ECUPort.model_validate(
            {
                "name": "test_ecu_port100",
                "mii_config": MII(mode="phy"),
                "mdi_config": mdi_100_config,
            }
        )
    with pytest.raises(ValidationError) as val1000:
        ecu_port_1000 = ECUPort.model_validate(
            {
                "name": "test_ecu_port1000",
                "mii_config": MII(mode="phy"),
                "mdi_config": mdi_1000_config,
            }
        )
    with pytest.raises(ValidationError) as val10:
        ecu_port_10 = ECUPort.model_validate(
            {
                "name": "test_ecu_port10",
                "mii_config": MII(mode="phy"),
                "mdi_config": mdi_10_config,
            }
        )


def test_negative_speed_config():
    mdi_baset1 = {
        "mode": "base_t1",
        "speed": 10,
        "autonegotiation": False,
        "duplex": "full",
        "role": "master",
    }
    mdi_baset1s = {
        "mode": "base_t1s",
        "speed": 100,
        "autonegotiation": False,
        "duplex": "half",
        "role": "master",
    }

    with pytest.raises(ValidationError) as valt1:
        ecu_port1 = ECUPort.model_validate(
            {
                "name": "test_ecu_port1",
                "mii_config": MII(mode="phy"),
                "mdi_config": mdi_baset1,
            }
        )
    with pytest.raises(ValidationError) as valt1s:
        ecu_port1s = ECUPort.model_validate(
            {
                "name": "test_ecu_port1",
                "mii_config": MII(mode="phy"),
                "mdi_config": mdi_baset1s,
            }
        )


def test_negative_duplex_config():
    mdi_100baset1 = {
        "mode": "base_t1",
        "speed": 100,
        "autonegotiation": False,
        "duplex": "half",
        "role": "master",
    }
    mdi_1000baset1 = {
        "mode": "base_t1",
        "speed": 1000,
        "autonegotiation": False,
        "duplex": "half",
        "role": "master",
    }
    mdi_10baset1s = {
        "mode": "base_t1s",
        "speed": 100,
        "autonegotiation": False,
        "duplex": "full",
        "role": "master",
    }

    with pytest.raises(ValidationError) as val100:
        ecu_port100 = ECUPort.model_validate(
            {
                "name": "test_ecu_port1",
                "mii_config": MII(mode="phy"),
                "mdi_config": mdi_100baset1,
            }
        )
    with pytest.raises(ValidationError) as val1000:
        ecu_port100 = ECUPort.model_validate(
            {
                "name": "test_ecu_port1",
                "mii_config": MII(mode="phy"),
                "mdi_config": mdi_1000baset1,
            }
        )
    with pytest.raises(ValidationError) as val10:
        ecu_port1s = ECUPort.model_validate(
            {
                "name": "test_ecu_port1",
                "mii_config": MII(mode="phy"),
                "mdi_config": mdi_10baset1s,
            }
        )
