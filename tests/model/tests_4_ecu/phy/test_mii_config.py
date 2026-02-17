import pytest
from pydantic import ValidationError
from flync.model.flync_4_ecu.phy import MII, RMII, SGMII, RGMII, BASET1, XFI
from flync.model.flync_4_ecu.switch import SwitchPort, ControllerInterface
from flync.model.flync_4_ecu.port import ECUPort

# Positive Tests for MII Config in ECU Ports


def test_positive_mii_config_ecu_port():
    mii_config1 = {"type": "mii", "mode": "mac", "speed": 100}
    mii_config2 = {"type": "mii", "mode": "phy", "speed": 100}

    ecu_port1 = ECUPort.model_validate(
        {
            "name": "test_ecu_port1",
            "mii_config": mii_config1,
            "mdi_config": BASET1(speed=100, role="master"),
        }
    )

    ecu_port2 = ECUPort.model_validate(
        {
            "name": "test_ecu_port2",
            "mii_config": mii_config2,
            "mdi_config": BASET1(speed=100, role="master"),
        }
    )
    assert isinstance(ecu_port1.mii_config, MII)
    assert isinstance(ecu_port2.mii_config, MII)


def test_positive_rmii_config_ecu_port():
    mii_config1 = {"type": "rmii", "mode": "mac", "speed": 100}
    mii_config2 = {"type": "rmii", "mode": "phy", "speed": 100}

    ecu_port1 = ECUPort.model_validate(
        {
            "name": "test_ecu_port1",
            "mii_config": mii_config1,
            "mdi_config": BASET1(speed=100, role="master"),
        }
    )

    ecu_port2 = ECUPort.model_validate(
        {
            "name": "test_ecu_port2",
            "mii_config": mii_config2,
            "mdi_config": BASET1(speed=100, role="master"),
        }
    )
    assert isinstance(ecu_port1.mii_config, RMII)
    assert isinstance(ecu_port2.mii_config, RMII)


def test_positive_sgmii_config_ecu_port():
    mii_config1 = {"type": "sgmii", "mode": "mac", "speed": 1000}
    mii_config2 = {"type": "sgmii", "mode": "phy", "speed": 1000}

    ecu_port1 = ECUPort.model_validate(
        {
            "name": "test_ecu_port1",
            "mii_config": mii_config1,
            "mdi_config": BASET1(speed=1000, role="master"),
        }
    )

    ecu_port2 = ECUPort.model_validate(
        {
            "name": "test_ecu_port2",
            "mii_config": mii_config2,
            "mdi_config": BASET1(speed=1000, role="master"),
        }
    )
    assert isinstance(ecu_port1.mii_config, SGMII)
    assert isinstance(ecu_port2.mii_config, SGMII)


def test_positive_rgmii_config_ecu_port():
    mii_config1 = {"type": "rgmii", "mode": "mac", "speed": 1000}
    mii_config2 = {"type": "rgmii", "mode": "phy", "speed": 1000}

    ecu_port1 = ECUPort.model_validate(
        {
            "name": "test_ecu_port1",
            "mii_config": mii_config1,
            "mdi_config": BASET1(speed=1000, role="master"),
        }
    )

    ecu_port2 = ECUPort.model_validate(
        {
            "name": "test_ecu_port2",
            "mii_config": mii_config2,
            "mdi_config": BASET1(speed=1000, role="master"),
        }
    )
    assert isinstance(ecu_port1.mii_config, RGMII)
    assert isinstance(ecu_port2.mii_config, RGMII)


def test_positive_xfi_config_ecu_port(virtual_controller_interface):
    mii_config1 = {"type": "xfi", "mode": "mac", "speed": 10000}
    mii_config2 = {"type": "xfi", "mode": "phy", "speed": 10000}

    switch_port_1 = SwitchPort.model_validate(
        {
            "name": "test_port_1",
            "mii_config": mii_config1,
            "default_vlan_id": 1,
            "silicon_port_no": 2,
        }
    )

    ctrl_iface_1 = ControllerInterface.model_validate(
        {
            "name": "test_ecu_port2",
            "mii_config": mii_config2,
            "mac_address": "10:10:10:22:22:22",
            "virtual_interfaces": [virtual_controller_interface],
        }
    )
    assert isinstance(switch_port_1.mii_config, XFI)
    assert isinstance(ctrl_iface_1.mii_config, XFI)


# Negative Tests for MII Config in ECU Ports


def test_negative_speed_for_mii_ecu_port():
    mii_config1 = {"type": "mii", "mode": "mac", "speed": 1000}
    mii_config2 = {"type": "mii", "mode": "phy", "speed": 1000}

    with pytest.raises(ValidationError) as val_error_port1:
        ecu_port1 = ECUPort.model_validate(
            {
                "name": "test_ecu_port1",
                "mii_config": mii_config1,
                "mdi_config": BASET1(speed=100, role="master"),
            }
        )

    with pytest.raises(ValidationError) as val_error_port2:
        ecu_port2 = ECUPort.model_validate(
            {
                "name": "test_ecu_port2",
                "mii_config": mii_config2,
                "mdi_config": BASET1(speed=100, role="master"),
            }
        )


def test_negative_speed_for_rmii_ecu_port():
    mii_config1 = {"type": "rmii", "mode": "mac", "speed": 1000}
    mii_config2 = {"type": "rmii", "mode": "phy", "speed": 1000}

    with pytest.raises(ValidationError) as val_error_port1:
        ecu_port1 = ECUPort.model_validate(
            {
                "name": "test_ecu_port1",
                "mii_config": mii_config1,
                "mdi_config": BASET1(speed=100, role="master"),
            }
        )

    with pytest.raises(ValidationError) as val_error_port2:
        ecu_port2 = ECUPort.model_validate(
            {
                "name": "test_ecu_port2",
                "mii_config": mii_config2,
                "mdi_config": BASET1(speed=100, role="master"),
            }
        )


def test_negative_speed_for_sgmii_ecu_port():
    mii_config1 = {"type": "sgmii", "mode": "mac", "speed": 10000}
    mii_config2 = {"type": "sgmii", "mode": "phy", "speed": 10000}

    with pytest.raises(ValidationError) as val_error_port1:
        ecu_port1 = ECUPort.model_validate(
            {
                "name": "test_ecu_port1",
                "mii_config": mii_config1,
                "mdi_config": BASET1(speed=100, role="master"),
            }
        )

    with pytest.raises(ValidationError) as val_error_port2:
        ecu_port2 = ECUPort.model_validate(
            {
                "name": "test_ecu_port2",
                "mii_config": mii_config2,
                "mdi_config": BASET1(speed=100, role="master"),
            }
        )


def test_negative_speed_for_rgmii_ecu_port():
    mii_config1 = {"type": "rgmii", "mode": "mac", "speed": 10000}
    mii_config2 = {"type": "rgmii", "mode": "phy", "speed": 10000}

    with pytest.raises(ValidationError) as val_error_port1:
        ecu_port1 = ECUPort.model_validate(
            {
                "name": "test_ecu_port1",
                "mii_config": mii_config1,
                "mdi_config": BASET1(speed=100, role="master"),
            }
        )

    with pytest.raises(ValidationError) as val_error_port2:
        ecu_port2 = ECUPort.model_validate(
            {
                "name": "test_ecu_port2",
                "mii_config": mii_config2,
                "mdi_config": BASET1(speed=100, role="master"),
            }
        )


def test_negative_speed_for_xfi_ecu_port():
    mii_config1 = {"type": "xfi", "mode": "mac", "speed": 1000}
    mii_config2 = {"type": "xfi", "mode": "phy", "speed": 1000}

    with pytest.raises(ValidationError) as val_error_port1:
        ecu_port1 = ECUPort.model_validate(
            {
                "name": "test_ecu_port1",
                "mii_config": mii_config1,
                "mdi_config": BASET1(speed=100, role="master"),
            }
        )

    with pytest.raises(ValidationError) as val_error_port2:
        ecu_port2 = ECUPort.model_validate(
            {
                "name": "test_ecu_port2",
                "mii_config": mii_config2,
                "mdi_config": BASET1(speed=100, role="master"),
            }
        )


# Positive Tests for MII Config in Switch Ports


def test_positive_mii_config_switch_port():
    mii_config1 = {"type": "mii", "mode": "mac", "speed": 100}
    mii_config2 = {"type": "mii", "mode": "phy", "speed": 100}

    switch_port1 = SwitchPort.model_validate(
        {
            "name": "test_switch_port1",
            "mii_config": mii_config1,
            "silicon_port_no": 0,
            "default_vlan_id": 0,
        }
    )
    switch_port2 = SwitchPort.model_validate(
        {
            "name": "test_switch_port2",
            "mii_config": mii_config2,
            "silicon_port_no": 1,
            "default_vlan_id": 0,
        }
    )

    assert isinstance(switch_port1.mii_config, MII)
    assert isinstance(switch_port2.mii_config, MII)


def test_positive_rmii_config_switch_port():
    mii_config1 = {"type": "rmii", "mode": "mac", "speed": 100}
    mii_config2 = {"type": "rmii", "mode": "phy", "speed": 100}

    switch_port1 = SwitchPort.model_validate(
        {
            "name": "test_switch_port1",
            "mii_config": mii_config1,
            "silicon_port_no": 0,
            "default_vlan_id": 0,
        }
    )
    switch_port2 = SwitchPort.model_validate(
        {
            "name": "test_switch_port2",
            "mii_config": mii_config2,
            "silicon_port_no": 1,
            "default_vlan_id": 0,
        }
    )

    assert isinstance(switch_port1.mii_config, RMII)
    assert isinstance(switch_port2.mii_config, RMII)


def test_positive_sgmii_config_switch_port():
    mii_config1 = {"type": "sgmii", "mode": "mac", "speed": 1000}
    mii_config2 = {"type": "sgmii", "mode": "phy", "speed": 1000}

    switch_port1 = SwitchPort.model_validate(
        {
            "name": "test_switch_port1",
            "mii_config": mii_config1,
            "silicon_port_no": 0,
            "default_vlan_id": 0,
        }
    )
    switch_port2 = SwitchPort.model_validate(
        {
            "name": "test_switch_port2",
            "mii_config": mii_config2,
            "silicon_port_no": 1,
            "default_vlan_id": 0,
        }
    )

    assert isinstance(switch_port1.mii_config, SGMII)
    assert isinstance(switch_port2.mii_config, SGMII)


def test_positive_rgmii_config_switch_port():
    mii_config1 = {"type": "rgmii", "mode": "mac", "speed": 1000}
    mii_config2 = {"type": "rgmii", "mode": "phy", "speed": 1000}

    switch_port1 = SwitchPort.model_validate(
        {
            "name": "test_switch_port1",
            "mii_config": mii_config1,
            "silicon_port_no": 0,
            "default_vlan_id": 0,
        }
    )
    switch_port2 = SwitchPort.model_validate(
        {
            "name": "test_switch_port2",
            "mii_config": mii_config2,
            "silicon_port_no": 1,
            "default_vlan_id": 0,
        }
    )

    assert isinstance(switch_port1.mii_config, RGMII)
    assert isinstance(switch_port2.mii_config, RGMII)


def test_positive_xfi_config_switch_port():
    mii_config1 = {"type": "xfi", "mode": "mac", "speed": 10000}
    mii_config2 = {"type": "xfi", "mode": "phy", "speed": 10000}

    switch_port1 = SwitchPort.model_validate(
        {
            "name": "test_switch_port1",
            "mii_config": mii_config1,
            "silicon_port_no": 0,
            "default_vlan_id": 0,
        }
    )
    switch_port2 = SwitchPort.model_validate(
        {
            "name": "test_switch_port2",
            "mii_config": mii_config2,
            "silicon_port_no": 1,
            "default_vlan_id": 0,
        }
    )

    assert isinstance(switch_port1.mii_config, XFI)
    assert isinstance(switch_port2.mii_config, XFI)
