import pytest
from pydantic import ValidationError

from flync.model.flync_4_ecu.controller import EthernetInterface
from flync.model.flync_4_ecu.mii import MII, RGMII, RMII, SGMII, USGMII, USXGMII, XFI
from flync.model.flync_4_ecu.port import ECUPort
from flync.model.flync_4_ecu.switch import SwitchPort
from tests.error_assertions import assert_single_error

MDI_10 = {"mode": "base_t1s"}
MDI_100 = {"mode": "base_t1", "speed": 100, "role": "master"}
MDI_1000 = {"mode": "base_t1", "speed": 1000, "role": "master"}

# One accepted (mii type, speed, parsed class, matching MDI) per interface type. XFI is 10G only and no MDI in the
# model reaches that speed, so it appears in the switch-port cases alone, where no MDI is paired.
_ECU_PORT_TYPES = [
    pytest.param("mii", 100, MII, MDI_100, id="mii"),
    pytest.param("rmii", 100, RMII, MDI_100, id="rmii"),
    pytest.param("sgmii", 1000, SGMII, MDI_1000, id="sgmii"),
    pytest.param("rgmii", 1000, RGMII, MDI_1000, id="rgmii"),
]
_SWITCH_PORT_TYPES = [
    pytest.param("mii", 100, MII, id="mii"),
    pytest.param("rmii", 100, RMII, id="rmii"),
    pytest.param("sgmii", 1000, SGMII, id="sgmii"),
    pytest.param("rgmii", 1000, RGMII, id="rgmii"),
    pytest.param("xfi", 10000, XFI, id="xfi"),
]


def ecu_port_with(mii_type, mii_speed, mdi, mode="mac"):
    """Build an ECU port pairing one MII config with one MDI config."""

    return ECUPort.model_validate(
        {
            "name": "p0",
            "mii_config": {"type": mii_type, "mode": mode, "speed": mii_speed},
            "mdi_config": mdi,
        }
    )


def switch_port_with(mii_type, mii_speed, mode):
    """Build a switch port carrying one MII config."""

    return SwitchPort.model_validate(
        {
            "name": "test_switch_port",
            "mii_config": {"type": mii_type, "mode": mode, "speed": mii_speed},
            "silicon_port_no": 0,
            "default_vlan_id": 0,
        }
    )


# Positive Tests for MII Config in ECU Ports


@pytest.mark.parametrize("mii_type, mii_speed, expected_class, mdi", _ECU_PORT_TYPES)
@pytest.mark.parametrize("mode", ["mac", "phy"])
def test_positive_mii_config_ecu_port(mii_type, mii_speed, expected_class, mdi, mode):
    """Each MII interface type parses into its own class on an ECU port, on both the MAC and the PHY side."""

    ecu_port = ecu_port_with(mii_type, mii_speed, mdi, mode=mode)

    assert isinstance(ecu_port.mii_config, expected_class)
    assert ecu_port.mii_config.mode == mode


# Speed compatibility between the MDI and MII configs of one ECU port


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
    assert isinstance(port, ECUPort)


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


@pytest.mark.parametrize("mii_type, mii_speed, expected_class", _SWITCH_PORT_TYPES)
@pytest.mark.parametrize("mode", ["mac", "phy"])
def test_positive_mii_config_switch_port(mii_type, mii_speed, expected_class, mode):
    """Each MII interface type parses into its own class on a switch port, on both the MAC and the PHY side."""

    switch_port = switch_port_with(mii_type, mii_speed, mode)

    assert isinstance(switch_port.mii_config, expected_class)
    assert switch_port.mii_config.mode == mode


def test_positive_xfi_config_ethernet_interface(virtual_controller_interface):
    """An MII config is also accepted on the interface_config of an EthernetInterface."""

    eth_iface = EthernetInterface.model_validate(
        {
            "name": "iface1",
            "interface_config": {
                "mii_config": {"type": "xfi", "mode": "phy", "speed": 10000},
                "mac_address": "10:10:10:22:22:22",
                "virtual_interfaces": [virtual_controller_interface],
            },
        }
    )

    assert isinstance(eth_iface.interface_config.mii_config, XFI)


def test_positive_usxgmii_config_ecu_port():
    mii_config = {"type": "usxgmii_10g_sxgmii", "mode": "mac", "channels": [{"speed": 1000}]}

    port = ECUPort.model_validate({"name": "p0", "mii_config": mii_config, "mdi_config": MDI_1000})

    assert isinstance(port.mii_config, USXGMII)
    assert port.mii_config.speed == 1000


def test_positive_usgmii_config_ecu_port():
    mii_config = {"type": "q_usgmii", "mode": "mac", "channels": [{"speed": 100}]}

    port = ECUPort.model_validate({"name": "p0", "mii_config": mii_config, "mdi_config": MDI_100})

    assert isinstance(port.mii_config, USGMII)
    assert port.mii_config.speed == 100


def test_usxgmii_channel_count_exceeding_variant_ports_is_rejected():
    """``usxgmii_10g_sxgmii`` is single-port (N=1); a second channel is rejected before subport/speed checks run."""

    with pytest.raises(ValidationError) as exc_info:
        USXGMII.model_validate(
            {
                "type": "usxgmii_10g_sxgmii",
                "mode": "mac",
                "channels": [{"subport_id": 0, "speed": 1000}, {"subport_id": 1, "speed": 1000}],
            }
        )

    assert_single_error(exc_info, "FLYNC-ECU-MAJ-VAL-377", "supports at most 1 channel")


def test_usxgmii_subport_id_out_of_range_is_rejected():
    with pytest.raises(ValidationError) as exc_info:
        USXGMII.model_validate(
            {
                "type": "usxgmii_10g_sxgmii",
                "mode": "mac",
                "channels": [{"subport_id": 1, "speed": 1000}],
            }
        )

    assert_single_error(exc_info, "FLYNC-ECU-MAJ-VAL-378", "out of range")


def test_usxgmii_speed_outside_variant_range_is_rejected():
    """5G-SXGMII tops out at 5G; 10G is only valid on the 10G variant."""

    with pytest.raises(ValidationError) as exc_info:
        USXGMII.model_validate(
            {
                "type": "usxgmii_5g_sxgmii",
                "mode": "mac",
                "channels": [{"speed": 10000}],
            }
        )

    assert_single_error(exc_info, "FLYNC-ECU-MAJ-VAL-379", "does not support speed 10000")


@pytest.mark.parametrize(
    "usxgmii_type, channel_speeds",
    [
        pytest.param("usxgmii_10g_dxgmii", [5000, 2500], id="10g-dxgmii-2-ports"),
        pytest.param("usxgmii_10g_qxgmii", [2500, 1000, 100, 10], id="10g-qxgmii-4-ports"),
    ],
)
def test_positive_usxgmii_m_multi_port_channels(usxgmii_type, channel_speeds):
    config = USXGMII.model_validate(
        {
            "type": usxgmii_type,
            "mode": "mac",
            "channels": [{"subport_id": idx, "speed": speed} for idx, speed in enumerate(channel_speeds)],
        }
    )

    assert len(config.channels) == len(channel_speeds)
    assert config.speed is None  # only defined for a single-channel link


@pytest.mark.parametrize(
    "usgmii_type, ports",
    [
        pytest.param("q_usgmii", 4, id="q-usgmii-4-ports"),
        pytest.param("o_usgmii", 8, id="o-usgmii-8-ports"),
    ],
)
def test_positive_usgmii_multi_port_channels(usgmii_type, ports):
    config = USGMII.model_validate(
        {
            "type": usgmii_type,
            "mode": "mac",
            "channels": [{"subport_id": idx, "speed": 1000} for idx in range(ports)],
        }
    )

    assert len(config.channels) == ports


def test_duplicate_subport_id_is_rejected():
    with pytest.raises(ValidationError) as exc_info:
        USXGMII.model_validate(
            {
                "type": "usxgmii_10g_qxgmii",
                "mode": "mac",
                "channels": [{"subport_id": 0, "speed": 1000}, {"subport_id": 0, "speed": 2500}],
            }
        )

    assert_single_error(exc_info, "FLYNC-CMN-MAJ-UNIQ-009", "channel subport_id")


def test_positive_pch_on_capable_variant():
    config = USXGMII.model_validate(
        {
            "type": "usxgmii_10g_dxgmii",
            "mode": "mac",
            "channels": [{"subport_id": 0, "speed": 5000}, {"subport_id": 1, "speed": 5000}],
            "pch_enabled": True,
            "pch_extension_type": "ptp",
        }
    )

    assert config.pch_enabled
    assert config.pch_extension_type == "ptp"


def test_pch_on_single_port_usxgmii_is_rejected():
    """Single-port USXGMII has no PCH support at all; this also covers the ExtType 0b10 (preemption/IET) case."""

    with pytest.raises(ValidationError) as exc_info:
        USXGMII.model_validate(
            {
                "type": "usxgmii_10g_sxgmii",
                "mode": "mac",
                "channels": [{"speed": 10000}],
                "pch_enabled": True,
            }
        )

    assert_single_error(exc_info, "FLYNC-ECU-MAJ-COMP-381", "does not support the Packet Control Header")


def test_pch_extension_type_without_pch_enabled_is_rejected():
    with pytest.raises(ValidationError) as exc_info:
        USXGMII.model_validate(
            {
                "type": "usxgmii_10g_dxgmii",
                "mode": "mac",
                "channels": [{"subport_id": 0, "speed": 5000}, {"subport_id": 1, "speed": 5000}],
                "pch_extension_type": "ptp",
            }
        )

    assert_single_error(exc_info, "FLYNC-ECU-MAJ-CONS-380", "pch_extension_type without pch_enabled")


def test_usgmii_channel_count_exceeding_variant_ports_is_rejected():
    """``q_usgmii`` is 4-port; a fifth channel is rejected before subport/speed checks run."""

    with pytest.raises(ValidationError) as exc_info:
        USGMII.model_validate(
            {
                "type": "q_usgmii",
                "mode": "mac",
                "channels": [
                    {"subport_id": 0, "speed": 1000},
                    {"subport_id": 1, "speed": 1000},
                    {"subport_id": 2, "speed": 1000},
                    {"subport_id": 3, "speed": 1000},
                    {"subport_id": 4, "speed": 1000},
                ],
            }
        )

    assert_single_error(exc_info, "FLYNC-ECU-MAJ-VAL-404", "supports at most 4 channel")


def test_usgmii_subport_id_out_of_range_is_rejected():
    with pytest.raises(ValidationError) as exc_info:
        USGMII.model_validate({"type": "q_usgmii", "mode": "mac", "channels": [{"subport_id": 4, "speed": 1000}]})

    assert_single_error(exc_info, "FLYNC-ECU-MAJ-VAL-405", "out of range")


def test_usgmii_speed_outside_variant_range_is_rejected():
    """USGMII channels top out at 1G."""

    with pytest.raises(ValidationError) as exc_info:
        USGMII.model_validate({"type": "q_usgmii", "mode": "mac", "channels": [{"speed": 2500}]})

    assert_single_error(exc_info, "FLYNC-ECU-MAJ-VAL-406", "does not support speed 2500")


def test_usgmii_duplicate_subport_id_is_rejected():
    with pytest.raises(ValidationError) as exc_info:
        USGMII.model_validate(
            {
                "type": "q_usgmii",
                "mode": "mac",
                "channels": [{"subport_id": 0, "speed": 1000}, {"subport_id": 0, "speed": 100}],
            }
        )

    assert_single_error(exc_info, "FLYNC-CMN-MAJ-UNIQ-009", "channel subport_id")


def test_positive_usgmii_pch_enabled():
    config = USGMII.model_validate(
        {
            "type": "q_usgmii",
            "mode": "mac",
            "channels": [{"subport_id": 0, "speed": 1000}],
            "pch_enabled": True,
            "pch_extension_type": "ptp",
        }
    )

    assert config.pch_enabled
    assert config.pch_extension_type == "ptp"


def test_usgmii_pch_extension_type_without_pch_enabled_is_rejected():
    with pytest.raises(ValidationError) as exc_info:
        USGMII.model_validate({"type": "q_usgmii", "mode": "mac", "channels": [{"speed": 1000}], "pch_extension_type": "ptp"})

    assert_single_error(exc_info, "FLYNC-ECU-MAJ-CONS-407", "pch_extension_type without pch_enabled")


def test_positive_fec_with_valid_alignment_marker_interval():
    config = USXGMII.model_validate(
        {
            "type": "usxgmii_10g_dxgmii",
            "mode": "mac",
            "channels": [{"subport_id": 0, "speed": 5000}, {"subport_id": 1, "speed": 5000}],
            "fec_enabled": True,
            "alignment_marker_interval": 1596,  # 80*20 - 4
        }
    )

    assert config.fec_enabled
    assert config.alignment_marker_interval == 1596


def test_fec_with_invalid_alignment_marker_interval_is_rejected():
    with pytest.raises(ValidationError) as exc_info:
        USXGMII.model_validate(
            {
                "type": "usxgmii_10g_dxgmii",
                "mode": "mac",
                "channels": [{"subport_id": 0, "speed": 5000}, {"subport_id": 1, "speed": 5000}],
                "fec_enabled": True,
                "alignment_marker_interval": 16400,  # the non-FEC default does not satisfy 80n-4
            }
        )

    assert_single_error(exc_info, "FLYNC-ECU-MAJ-VAL-382", "must satisfy 80 * n - 4")
