import pytest
from pydantic import ValidationError

from flync.model.flync_4_ecu.controller import EthernetInterface
from flync.model.flync_4_ecu.phy import BASET1, MII, RGMII, RMII, SGMII, XFI
from flync.model.flync_4_ecu.port import ECUPort
from flync.model.flync_4_ecu.switch import SwitchPort
from tests.error_assertions import assert_single_error

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

    eth_iface_1 = EthernetInterface.model_validate(
        {
            "name": "iface1",
            "interface_config": {
                "mii_config": mii_config2,
                "mac_address": "10:10:10:22:22:22",
                "virtual_interfaces": [virtual_controller_interface],
            },
        }
    )
    assert isinstance(switch_port_1.mii_config, XFI)
    assert isinstance(eth_iface_1.interface_config.mii_config, XFI)


# Speed compatibility between the MDI and MII configs of one ECU port

MDI_10 = {"mode": "base_t1s"}
MDI_100 = {"mode": "base_t1", "speed": 100, "role": "master"}
MDI_1000 = {"mode": "base_t1", "speed": 1000, "role": "master"}


def ecu_port_with(mii_type, mii_speed, mdi):
    """Build an ECU port pairing one MII config with one MDI config."""

    return ECUPort.model_validate(
        {
            "name": "p0",
            "mii_config": {"type": mii_type, "mode": "mac", "speed": mii_speed},
            "mdi_config": mdi,
        }
    )


@pytest.mark.parametrize(
    "mii_type, mii_speed, mdi",
    [
        pytest.param("mii", 100, MDI_100, id="mii-equal"),
        pytest.param("mii", 100, MDI_10, id="mii-over-slower-mdi"),
        pytest.param("rmii", 100, MDI_10, id="rmii-over-slower-mdi"),
        pytest.param("rgmii", 1000, MDI_1000, id="rgmii-equal"),
        pytest.param("rgmii", 1000, MDI_100, id="rgmii-over-slower-mdi"),
        pytest.param("sgmii", 1000, MDI_100, id="sgmii-over-slower-mdi"),
        pytest.param("sgmii", 2500, MDI_1000, id="sgmii-2500-over-1000-mdi"),
    ],
)
def test_mdi_speed_at_or_below_mii_speed_is_accepted(mii_type, mii_speed, mdi):
    """MII, RMII, SGMII and RGMII each cover a range of speeds, so the MDI may run at or below the MII speed."""

    port = ecu_port_with(mii_type, mii_speed, mdi)

    assert port.mii_config.speed == mii_speed
    assert port.mdi_config.speed <= mii_speed


@pytest.mark.parametrize(
    "mii_type, mii_speed, mdi",
    [
        pytest.param("mii", 10, MDI_100, id="mii-under-faster-mdi"),
        pytest.param("rmii", 10, MDI_100, id="rmii-under-faster-mdi"),
        pytest.param("rgmii", 100, MDI_1000, id="rgmii-under-faster-mdi"),
        pytest.param("sgmii", 100, MDI_1000, id="sgmii-under-faster-mdi"),
        pytest.param("xfi", 10000, MDI_1000, id="xfi-needs-an-exact-match"),
    ],
)
def test_mdi_speed_the_mii_cannot_carry_is_rejected(mii_type, mii_speed, mdi):
    """An MDI above the MII speed is rejected, and XFI is 10G only so any other MDI speed is rejected too."""

    with pytest.raises(ValidationError) as exc_info:
        ecu_port_with(mii_type, mii_speed, mdi)

    assert_single_error(exc_info, "FLYNC-ECU-MAJ-CONS-081", "compatible speed in ECU Ports. Port p0")


def test_speed_outside_the_interface_range_is_rejected():
    """A speed the interface type does not define fails on its own literal, before the compatibility rule runs."""

    with pytest.raises(ValidationError) as exc_info:
        ecu_port_with("rmii", 1000, MDI_100)

    assert_single_error(exc_info, None, "speed")


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
