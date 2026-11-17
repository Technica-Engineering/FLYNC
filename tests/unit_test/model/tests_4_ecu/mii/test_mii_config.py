import pytest
from pydantic import ValidationError

from flync.core.utils.exceptions_handling import validate_with_policy
from flync.model.flync_4_ecu import ECU
from flync.model.flync_4_ecu.controller import EthernetInterface
from flync.model.flync_4_ecu.mii import MII, QSGMII, RGMII, RMII, SGMII, USGMII, USXGMII, XFI, xmii_channel_capacity
from flync.model.flync_4_ecu.port import ECUPort
from flync.model.flync_4_ecu.switch import SwitchPort
from tests.error_assertions import assert_no_findings, assert_single_error, assert_single_warning

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


def test_positive_qsgmii_four_channels():
    config = QSGMII.model_validate(
        {"mode": "phy", "channels": [{"subport_id": idx, "speed": speed} for idx, speed in enumerate((10, 100, 1000, 1000))]}
    )

    assert config.type == "qsgmii"
    assert len(config.channels) == 4
    assert config.speed is None


def test_qsgmii_single_channel_exposes_speed():
    assert QSGMII.model_validate({"mode": "mac", "channels": [{"speed": 100}]}).speed == 100


@pytest.mark.parametrize(
    "mii_config, expected",
    [
        pytest.param(MII(mode="mac"), 1, id="mii"),
        pytest.param(XFI(mode="mac"), 1, id="xfi"),
        pytest.param(USXGMII(type="usxgmii_10g_qxgmii", mode="mac", channels=[{"speed": 1000}]), 4, id="usxgmii-quad"),
        pytest.param(USGMII(type="o_usgmii", mode="mac", channels=[{"speed": 1000}]), 8, id="usgmii-octal"),
        pytest.param(QSGMII(mode="mac", channels=[{"speed": 1000}]), 4, id="qsgmii"),
    ],
)
def test_xmii_channel_capacity(mii_config, expected):
    assert xmii_channel_capacity(mii_config) == expected


def test_qsgmii_channel_count_exceeding_four_is_rejected():
    channels = [{"subport_id": idx, "speed": 1000} for idx in range(5)]

    with pytest.raises(ValidationError) as exc_info:
        QSGMII.model_validate({"mode": "mac", "channels": channels})

    assert_single_error(exc_info, "FLYNC-ECU-MAJ-VAL-428", "supports at most 4 channel")


def test_qsgmii_subport_id_out_of_range_is_rejected():
    with pytest.raises(ValidationError) as exc_info:
        QSGMII.model_validate({"mode": "mac", "channels": [{"subport_id": 4, "speed": 1000}]})

    assert_single_error(exc_info, "FLYNC-ECU-MAJ-VAL-429", "out of range")


def test_qsgmii_speed_above_one_gigabit_is_rejected():
    with pytest.raises(ValidationError) as exc_info:
        QSGMII.model_validate({"mode": "mac", "channels": [{"speed": 2500}]})

    assert_single_error(exc_info, "FLYNC-ECU-MAJ-VAL-430", "does not support speed 2500")


def test_qsgmii_duplicate_subport_id_is_rejected():
    with pytest.raises(ValidationError) as exc_info:
        QSGMII.model_validate({"mode": "mac", "channels": [{"subport_id": 0, "speed": 1000}, {"subport_id": 0, "speed": 100}]})

    assert_single_error(exc_info, "FLYNC-CMN-MAJ-UNIQ-009", "channel subport_id")


MDI_T1 = {"mode": "base_t1", "speed": 100, "role": "slave"}
MDI_T1S_HALF = {"mode": "base_t1s", "topology": "p2p", "duplex": "half"}
MDI_T1S_FULL = {"mode": "base_t1s", "topology": "p2p", "duplex": "full"}
LITE_DUPLEX_ID = "FLYNC-CMN-MAJ-CONS-432"
LITE_PAIR_ID = "FLYNC-CMN-WARN-COMP-431"
_METADATA = {"author": "t", "compatible_flync_version": {"version_schema": "semver", "version": "0.11.0"}}


def mii_data(mode, lite=None, speed=100):
    """An MII config as data; ``lite`` is left out when ``None`` so the default applies."""

    return {"type": "mii", "mode": mode, "speed": speed, **({} if lite is None else {"lite": lite})}


def opposite(mode):
    return "phy" if mode == "mac" else "mac"


def ecu_link_data(ecu_port_mii, switch_port_mii, mdi=MDI_T1):
    """An ECU whose port ``a`` (holding ``mdi``) is connected to the port ``b`` of its switch; ``None`` leaves an MII config out."""

    ecu_port = {"name": "a", "mdi_config": mdi, **({} if ecu_port_mii is None else {"mii_config": ecu_port_mii})}
    switch_port = {"name": "b", "silicon_port_no": 1, "default_vlan_id": 0, **({} if switch_port_mii is None else {"mii_config": switch_port_mii})}
    return {
        "name": "test_ecu",
        "ports": [ecu_port],
        "controllers": [],
        "switches": [
            {
                "name": "sw",
                "switch_config": {"meta": {"type": "embedded", "target_system": "t", **_METADATA}, "ports": [switch_port], "vlans": []},
            }
        ],
        "topology": {"connections": [{"type": "ecu_port_to_switch_port", "id": "1", "ecu_port": "a", "switch_port": "b"}]},
        "ecu_metadata": _METADATA,
    }


@pytest.mark.parametrize(
    "extra, expected",
    [
        pytest.param({}, False, id="omitted-defaults-to-false"),
        pytest.param({"lite": False}, False, id="explicit-false"),
        pytest.param({"lite": True}, True, id="explicit-true"),
    ],
)
def test_mii_lite_flag_parsing(extra, expected):
    assert MII.model_validate({"mode": "mac", **extra}).lite is expected


@pytest.mark.parametrize("mii_type", ["rmii", "rgmii", "sgmii"])
def test_lite_is_a_field_of_mii_only(mii_type):
    mii_config = {"type": mii_type, "mode": "mac", "speed": 100, "lite": True}

    with pytest.raises(ValidationError) as exc_info:
        ECUPort.model_validate({"name": "p0", "mii_config": mii_config, "mdi_config": MDI_100})

    assert_single_error(exc_info, None, "lite")


@pytest.mark.parametrize(
    "ecu_side_lite, switch_side_lite",
    [
        pytest.param(True, True, id="lite-vs-lite"),
        pytest.param(False, False, id="full-vs-full"),
        pytest.param(None, None, id="flag-omitted-on-both-ends"),
    ],
)
@pytest.mark.parametrize("ecu_side_mode", ["mac", "phy"])
def test_matching_mii_lite_ends_do_not_warn(ecu_side_mode, ecu_side_lite, switch_side_lite):
    data = ecu_link_data(mii_data(ecu_side_mode, ecu_side_lite), mii_data(opposite(ecu_side_mode), switch_side_lite))

    assert_no_findings(validate_with_policy(ECU, data, path=None))


@pytest.mark.parametrize(
    "ecu_side_lite, switch_side_lite",
    [
        pytest.param(True, False, id="lite-ecu-full-switch"),
        pytest.param(False, True, id="full-ecu-lite-switch"),
        pytest.param(None, True, id="flag-omitted-ecu-lite-switch"),
    ],
)
@pytest.mark.parametrize("ecu_side_mode", ["mac", "phy"])
def test_mii_lite_paired_with_full_mii_warns_once(ecu_side_mode, ecu_side_lite, switch_side_lite):
    data = ecu_link_data(mii_data(ecu_side_mode, ecu_side_lite), mii_data(opposite(ecu_side_mode), switch_side_lite))

    result = validate_with_policy(ECU, data, path=None)

    assert_single_warning(result, LITE_PAIR_ID, "is paired with full MII on")


@pytest.mark.parametrize(
    "ecu_side, switch_side, error_id, fragment",
    [
        pytest.param(mii_data("mac", True), mii_data("mac", True), "FLYNC-CMN-MAJ-COMP-013", "Incompatible MII Mode", id="same-mode"),
        pytest.param(mii_data("mac", True, 100), mii_data("phy", True, 10), "FLYNC-CMN-MAJ-COMP-014", "Incompatible MII Speed", id="speed"),
        pytest.param(mii_data("mac", True), {"type": "rmii", "mode": "phy"}, "FLYNC-CMN-MAJ-COMP-015", "Incompatible MII Type", id="type"),
    ],
)
def test_existing_pair_errors_still_fire_with_mii_lite(ecu_side, switch_side, error_id, fragment):
    data = ecu_link_data(ecu_side, switch_side)

    with pytest.raises(ValidationError) as exc_info:
        ECU.model_validate(data)

    assert_single_error(exc_info, error_id, fragment)


_LITE_DUPLEX_CASES = [
    pytest.param(True, MDI_T1, id="lite-base-t1"),
    pytest.param(True, MDI_T1S_FULL, id="lite-base-t1s-full-p2p"),
    pytest.param(False, MDI_T1S_HALF, id="full-mii-base-t1s-half"),
    pytest.param(None, MDI_T1S_HALF, id="flag-omitted-base-t1s-half"),
]


@pytest.mark.parametrize("lite, mdi", _LITE_DUPLEX_CASES)
def test_mii_lite_duplex_accepted_on_ecu_port(lite, mdi):
    data = {"name": "p0", "mii_config": mii_data("mac", lite, mdi.get("speed", 10)), "mdi_config": mdi}

    assert_no_findings(validate_with_policy(ECUPort, data, path=None))


def test_mii_lite_with_half_duplex_mdi_is_rejected_on_ecu_port():
    data = {"name": "p0", "mii_config": mii_data("mac", True, 10), "mdi_config": MDI_T1S_HALF}

    with pytest.raises(ValidationError) as exc_info:
        ECUPort.model_validate(data)

    assert_single_error(exc_info, LITE_DUPLEX_ID, "ECU Ports 'p0' has an MII-Lite config, which cannot carry a half-duplex MDI")


@pytest.mark.parametrize("lite, mdi", _LITE_DUPLEX_CASES)
def test_mii_lite_duplex_accepted_on_switch_port(lite, mdi):
    """Both ends carry the same ``lite`` value, so the pair raises no warning; the switch port's MDI arrives through the topology."""

    speed = mdi.get("speed", 10)
    data = ecu_link_data(mii_data("phy", lite, speed), mii_data("mac", lite, speed), mdi)

    assert_no_findings(validate_with_policy(ECU, data, path=None))


def test_mii_lite_with_half_duplex_mdi_is_rejected_on_switch_port():
    """The ECU port is full MII, so only the switch port's check can fire (the pair merely warns, which is not an error)."""

    data = ecu_link_data(mii_data("phy", False, 10), mii_data("mac", True, 10), MDI_T1S_HALF)

    with pytest.raises(ValidationError) as exc_info:
        ECU.model_validate(data)

    assert_single_error(exc_info, LITE_DUPLEX_ID, "Switch Ports 'b' has an MII-Lite config")


def ecu_iface_link_data(ecu_port_mii, iface_mii, mdi):
    """An ECU whose port ``a`` (holding ``mdi``) is connected to the Ethernet interface ``b`` of its controller."""

    iface = {"name": "b", "interface_config": {"mac_address": "10:10:10:22:22:22", "mii_config": iface_mii}}
    return {
        "name": "test_ecu",
        "ports": [{"name": "a", "mii_config": ecu_port_mii, "mdi_config": mdi}],
        "controllers": [
            {"name": "ctrl", "controller_metadata": {"type": "embedded", "target_system": "t", **_METADATA}, "ethernet_interfaces": [iface]}
        ],
        "switches": [],
        "topology": {"connections": [{"type": "ecu_port_to_controller_interface", "id": "1", "ecu_port": "a", "controller_interface": "b"}]},
        "ecu_metadata": _METADATA,
    }


@pytest.mark.parametrize("lite, mdi", _LITE_DUPLEX_CASES)
def test_mii_lite_duplex_accepted_on_controller_interface(lite, mdi):
    """Both ends carry the same ``lite`` value, so the pair raises no warning; the MDI sits on the ECU port across the MII."""

    speed = mdi.get("speed", 10)
    data = ecu_iface_link_data(mii_data("phy", lite, speed), mii_data("mac", lite, speed), mdi)

    assert_no_findings(validate_with_policy(ECU, data, path=None))


def test_mii_lite_with_half_duplex_mdi_is_rejected_on_controller_interface():
    """The ECU port is full MII, so only the controller interface's check can fire (the pair merely warns, which is not an error)."""

    data = ecu_iface_link_data(mii_data("phy", False, 10), mii_data("mac", True, 10), MDI_T1S_HALF)

    with pytest.raises(ValidationError) as exc_info:
        ECU.model_validate(data)

    assert_single_error(exc_info, LITE_DUPLEX_ID, "Controller Interfaces 'b' has an MII-Lite config")


def test_mii_lite_controller_interface_with_full_duplex_t1s_only_warns():
    """A full-duplex point-to-point 10BASE-T1S link needs no CRS/COL, so a Lite MAC on a full-MII PHY only gets the pair warning."""

    data = ecu_iface_link_data(mii_data("phy", False, 10), mii_data("mac", True, 10), MDI_T1S_FULL)

    assert_single_warning(validate_with_policy(ECU, data, path=None), LITE_PAIR_ID, "is paired with full MII on")
