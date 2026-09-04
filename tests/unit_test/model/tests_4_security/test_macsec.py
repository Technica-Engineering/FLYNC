import pytest
from pydantic import ValidationError

from flync.core.datatypes import Ethertype
from flync.core.utils.exceptions_handling import validate_with_policy
from flync.model.flync_4_ecu.controller import EthernetInterface
from flync.model.flync_4_security.macsec import (
    IntegrityWithConfidentiality,
    IntegrityWithoutConfidentiality,
    MACsecConfig,
)
from tests.error_assertions import assert_no_findings, assert_single_error, assert_single_warning


def test_macsec_positive_vlan_bypass_entry(virtual_controller_interface):
    macsec_example = {
        "vlan_bypass": [1, 2, 3],
        "ckn": "0123456789abcdef0123456789abcdef",
        "mka_enabled": True,
        "hello_time": 1000,
        "bounded_hello_time": 2000,
        "life_time": 100000,
        "sak_retire_time": 20000,
        "macsec_mode": "integrity",
        "kay_on": True,
        "key_role": "key_server_always",
        "delay_protect": False,
        "participant_activation": "always",
    }

    eth_iface = EthernetInterface.model_validate(
        {
            "name": "iface1",
            "interface_config": {
                "mac_address": "00:11:22:33:44:55",
                "mii_config": None,
                "virtual_interfaces": [virtual_controller_interface],
                "macsec_config": macsec_example,
            },
        }
    )

    assert isinstance(eth_iface.interface_config.macsec_config, MACsecConfig)


def test_negative_vlan_bypass_entry(virtual_controller_interface):
    macsec_example = {
        "vlan_bypass": [10000, 2, 3],
        "ckn": "0123456789abcdef0123456789abcdef",
        "mka_enabled": True,
        "hello_time": 1000,
        "bounded_hello_time": 2000,
        "life_time": 100000,
        "sak_retire_time": 20000,
        "macsec_mode": "integrity",
        "kay_on": True,
        "key_role": "key_server_always",
        "delay_protect": False,
        "participant_activation": "always",
    }
    with pytest.raises(ValidationError) as e:
        EthernetInterface.model_validate(
            {
                "name": "iface1",
                "interface_config": {
                    "mac_address": "00:11:22:33:44:55",
                    "mii_config": None,
                    "virtual_interfaces": [virtual_controller_interface],
                    "macsec_config": macsec_example,
                },
            }
        )


def test_positive_cipher_preference_integrity_without_confidentiality(integrity_without_confidentiality_entry, virtual_controller_interface):
    macsec_example = {
        "vlan_bypass": [1, 2, 3],
        "ckn": "0123456789abcdef0123456789abcdef",
        "mka_enabled": True,
        "hello_time": 1000,
        "bounded_hello_time": 2000,
        "life_time": 100000,
        "sak_retire_time": 20000,
        "macsec_mode": "integrity",
        "kay_on": True,
        "key_role": "key_server_always",
        "delay_protect": False,
        "participant_activation": "always",
        "cipher_preference": [integrity_without_confidentiality_entry],
    }
    eth_iface = EthernetInterface.model_validate(
        {
            "name": "iface1",
            "interface_config": {
                "mac_address": "00:11:22:33:44:55",
                "mii_config": None,
                "virtual_interfaces": [virtual_controller_interface],
                "macsec_config": macsec_example,
            },
        }
    )
    assert isinstance(eth_iface.interface_config.macsec_config, MACsecConfig)


def test_positive_cipher_preference_integrity_with_confidentiality(integrity_with_confidentiality_entry, virtual_controller_interface):
    macsec_example = {
        "vlan_bypass": [1, 2, 3],
        "ckn": "0123456789abcdef0123456789abcdef",
        "mka_enabled": True,
        "hello_time": 1000,
        "bounded_hello_time": 2000,
        "life_time": 100000,
        "sak_retire_time": 20000,
        "macsec_mode": "integrity",
        "kay_on": True,
        "key_role": "key_server_always",
        "delay_protect": False,
        "participant_activation": "always",
        "cipher_preference": [integrity_with_confidentiality_entry],
    }

    eth_iface = EthernetInterface.model_validate(
        {
            "name": "iface1",
            "interface_config": {
                "mac_address": "00:11:22:33:44:55",
                "mii_config": None,
                "virtual_interfaces": [virtual_controller_interface],
                "macsec_config": macsec_example,
            },
        }
    )
    assert isinstance(eth_iface.interface_config.macsec_config, MACsecConfig)


def test_positive_cipher_preference_mix(
    integrity_with_confidentiality_entry,
    integrity_without_confidentiality_entry,
    virtual_controller_interface,
):
    macsec_example = {
        "vlan_bypass": [1, 2, 3],
        "ckn": "0123456789abcdef0123456789abcdef",
        "mka_enabled": True,
        "hello_time": 1000,
        "bounded_hello_time": 2000,
        "life_time": 100000,
        "sak_retire_time": 20000,
        "macsec_mode": "integrity",
        "kay_on": True,
        "key_role": "key_server_always",
        "delay_protect": False,
        "participant_activation": "always",
        "cipher_preference": [
            integrity_with_confidentiality_entry,
            integrity_without_confidentiality_entry,
        ],
    }

    eth_iface = EthernetInterface.model_validate(
        {
            "name": "iface1",
            "interface_config": {
                "mac_address": "00:11:22:33:44:55",
                "mii_config": None,
                "virtual_interfaces": [virtual_controller_interface],
                "macsec_config": macsec_example,
            },
        }
    )
    assert isinstance(eth_iface.interface_config.macsec_config, MACsecConfig)


def test_positive_integrity_with_confidentiality():
    integrity_with_confidentiality = {
        "type": "integrity_with_confidentiality",
        "confidentiality_offset": 0,
        "cipher_suite": "GCM-AES-XPN-256",
    }
    macsec_example = MACsecConfig.model_validate(
        {
            "vlan_bypass": [1, 2, 3],
            "ckn": "0123456789abcdef0123456789abcdef",
            "mka_enabled": True,
            "hello_time": 1000,
            "bounded_hello_time": 2000,
            "life_time": 100000,
            "sak_retire_time": 20000,
            "macsec_mode": "integrity",
            "kay_on": True,
            "key_role": "key_server_always",
            "delay_protect": False,
            "participant_activation": "always",
            "cipher_preference": [integrity_with_confidentiality],
        }
    )
    assert isinstance(macsec_example.cipher_preference[0], IntegrityWithConfidentiality)


def test_negative_integrity_with_confidentiality():
    integrity_with_confidentiality = {
        "type": "integrity_with_confidentiality",
        "confidentiality_offset": 40,
    }
    with pytest.raises(ValidationError) as e:
        macsec_example = MACsecConfig.model_validate(
            {
                "vlan_bypass": [1, 2, 3],
                "ckn": "0123456789abcdef0123456789abcdef",
                "mka_enabled": True,
                "hello_time": 1000,
                "bounded_hello_time": 2000,
                "life_time": 100000,
                "sak_retire_time": 20000,
                "macsec_mode": "integrity",
                "kay_on": True,
                "key_role": "key_server_always",
                "delay_protect": False,
                "participant_activation": "always",
                "cipher_preference": [integrity_with_confidentiality],
            }
        )


def test_positive_integrity_without_confidentiality():
    integrity_without_confidentiality = {
        "type": "integrity_without_confidentiality",
        "confidentiality_offset": 0,
    }
    macsec_example = MACsecConfig.model_validate(
        {
            "vlan_bypass": [1, 2, 3],
            "ckn": "0123456789abcdef0123456789abcdef",
            "mka_enabled": True,
            "hello_time": 1000,
            "bounded_hello_time": 2000,
            "life_time": 100000,
            "sak_retire_time": 20000,
            "macsec_mode": "integrity",
            "kay_on": True,
            "key_role": "key_server_always",
            "delay_protect": False,
            "participant_activation": "always",
            "cipher_preference": [integrity_without_confidentiality],
        }
    )
    assert isinstance(macsec_example.cipher_preference[0], IntegrityWithoutConfidentiality)


def test_negative_integrity_with_confidentiality():
    integrity_without_confidentiality = {
        "type": "integrity_without_confidentiality",
        "confidentiality_offset": 30,
    }
    with pytest.raises(ValidationError) as e:
        macsec_example = MACsecConfig.model_validate(
            {
                "vlan_bypass": [1, 2, 3],
                "ckn": "0123456789abcdef0123456789abcdef",
                "mka_enabled": True,
                "hello_time": 1000,
                "bounded_hello_time": 2000,
                "life_time": 100000,
                "sak_retire_time": 20000,
                "macsec_mode": "integrity",
                "kay_on": True,
                "key_role": "key_server_always",
                "delay_protect": False,
                "participant_activation": "always",
                "cipher_preference": [integrity_without_confidentiality],
            }
        )


def test_positive_ethertype_bypass():
    macsec_example = {
        "vlan_bypass": [1, 2, 3],
        "ckn": "0123456789abcdef0123456789abcdef",
        "ethertype_bypass": ["AVTP", "0x0800", Ethertype.LLDP],
        "mka_enabled": True,
        "hello_time": 1000,
        "bounded_hello_time": 2000,
        "life_time": 100000,
        "sak_retire_time": 20000,
        "macsec_mode": "integrity",
        "kay_on": True,
        "key_role": "key_server_always",
        "delay_protect": False,
        "participant_activation": "always",
    }
    config = MACsecConfig.model_validate(macsec_example)
    assert config.ethertype_bypass == [Ethertype.AVTP, Ethertype.IPv4, Ethertype.LLDP]


def test_negative_ethertype_bypass():
    macsec_example = {
        "vlan_bypass": [1, 2, 3],
        "ckn": "0123456789abcdef0123456789abcdef",
        "ethertype_bypass": ["NOT_AN_ETHERTYPE"],
        "mka_enabled": True,
        "hello_time": 1000,
        "bounded_hello_time": 2000,
        "life_time": 100000,
        "sak_retire_time": 20000,
        "macsec_mode": "integrity",
        "kay_on": True,
        "key_role": "key_server_always",
        "delay_protect": False,
        "participant_activation": "always",
    }
    with pytest.raises(ValidationError):
        MACsecConfig.model_validate(macsec_example)


@pytest.mark.parametrize(
    "cipher_suite, expected_xpn",
    [
        ("GCM-AES-XPN-128", True),
        ("GCM-AES-XPN-256", True),
        ("GCM-AES-128", False),
        ("GCM-AES-256", False),
    ],
    ids=["xpn-128", "xpn-256", "aes-128", "aes-256"],
)
def test_cipher_suite_xpn(cipher_suite, expected_xpn):
    config = IntegrityWithConfidentiality(type="integrity_with_confidentiality", cipher_suite=cipher_suite)
    assert config.xpn() is expected_xpn


def test_cipher_suite_default_is_xpn_256():
    config = IntegrityWithoutConfidentiality(type="integrity_without_confidentiality")
    assert config.cipher_suite == "GCM-AES-XPN-256"
    assert config.xpn() is True


@pytest.mark.parametrize(
    "cipher_suite",
    ["GCM-AES-XPN-128", "GCM-AES-XPN-256"],
    ids=["aes-xpn-128", "aes-xpn-256"],
)
def test_positive_integrity_with_confidentiality_xpn_offset_0(cipher_suite):
    config = IntegrityWithConfidentiality(
        type="integrity_with_confidentiality",
        cipher_suite=cipher_suite,
        confidentiality_offset=0,
    )
    assert config.xpn() is True
    assert config.confidentiality_offset == 0


@pytest.mark.parametrize(
    "cipher_suite",
    ["GCM-AES-XPN-128", "GCM-AES-XPN-256"],
    ids=["aes-xpn-128", "aes-xpn-256"],
)
def test_negative_integrity_with_confidentiality_xpn_offset_30(cipher_suite):
    with pytest.raises(ValidationError) as exc_info:
        IntegrityWithConfidentiality(
            type="integrity_with_confidentiality",
            cipher_suite=cipher_suite,
            confidentiality_offset=30,
        )
    assert_single_error(exc_info, "FLYNC-SEC-MIN-CONS-253", "XPN Ciphers do not support Confidentiality Offset other than 0")


def _macsec_config(overrides=None):
    kwargs = {
        "vlan_bypass": [1, 2, 3],
        "ckn": "0123456789abcdef0123456789abcdef",
        "mka_enabled": True,
        "hello_time": 1000,
        "bounded_hello_time": 2000,
        "life_time": 100000,
        "sak_retire_time": 20000,
        "macsec_mode": "integrity",
        "kay_on": True,
        "key_role": "key_server_always",
        "delay_protect": False,
        "participant_activation": "always",
    }
    if overrides:
        kwargs.update(overrides)
    return kwargs


def test_mka_disabled_with_non_disabled_macsec_mode_warns():
    result = validate_with_policy(MACsecConfig, _macsec_config({"mka_enabled": False, "macsec_mode": "integrity"}), path=None)
    assert_single_warning(result, "FLYNC-SEC-WARN-CONS-100", "If MACsec is enabled, you should also enable MKA")


def test_positive_mka_disabled_with_disabled_macsec_mode():
    config = MACsecConfig.model_validate(_macsec_config({"mka_enabled": False, "macsec_mode": "disabled"}))
    assert config.mka_enabled is False
    assert config.macsec_mode == "disabled"


def test_positive_mka_enabled_with_non_disabled_macsec_mode():
    config = MACsecConfig.model_validate(_macsec_config({"mka_enabled": True, "macsec_mode": "integrity"}))
    assert config.mka_enabled is True
    assert config.macsec_mode == "integrity"


def test_negative_life_time_less_than_hello_time():
    with pytest.raises(ValidationError) as exc_info:
        MACsecConfig.model_validate(_macsec_config({"life_time": 100, "hello_time": 1000}))
    assert_single_error(exc_info, "FLYNC-SEC-MIN-CONS-101", "Life time should be greater than hello time")


@pytest.mark.parametrize(
    "life_time, hello_time",
    [(1000, 1000), (2000, 1000)],
    ids=["equal", "greater"],
)
def test_positive_life_time_at_least_hello_time(life_time, hello_time):
    config = MACsecConfig.model_validate(_macsec_config({"life_time": life_time, "hello_time": hello_time}))
    assert config.life_time >= config.hello_time


def test_replay_protection_window_defaults_to_zero_no_finding():
    result = validate_with_policy(MACsecConfig, _macsec_config(), path=None)
    assert_no_findings(result)


def test_replay_protection_window_non_zero_warns():
    result = validate_with_policy(MACsecConfig, _macsec_config({"replay_protection_window": 1}), path=None)
    assert_single_warning(result, "FLYNC-SEC-WARN-VAL-251", "replay_protection_window")


def test_positive_mac_address_bypass_defaults_to_empty():
    config = MACsecConfig.model_validate(_macsec_config())
    assert config.src_mac_address_bypass == []
    assert config.dest_mac_address_bypass == []


def test_positive_mac_address_bypass():
    config = MACsecConfig.model_validate(
        _macsec_config(
            {
                "src_mac_address_bypass": ["00:11:22:33:44:55"],
                "dest_mac_address_bypass": ["0A:0B:0C:0D:0E:0F", "10:11:12:13:14:15"],
            }
        )
    )
    assert [str(mac) for mac in config.src_mac_address_bypass] == ["00:11:22:33:44:55"]
    assert [str(mac) for mac in config.dest_mac_address_bypass] == [
        "0a:0b:0c:0d:0e:0f",
        "10:11:12:13:14:15",
    ]


@pytest.mark.parametrize(
    "field",
    ["src_mac_address_bypass", "dest_mac_address_bypass"],
    ids=["src", "dest"],
)
def test_negative_mac_address_bypass_invalid_mac(field):
    with pytest.raises(ValidationError):
        MACsecConfig.model_validate(_macsec_config({field: ["not-a-mac"]}))


def test_cn_required_missing_rejected():
    kwargs = _macsec_config()
    kwargs.pop("ckn")
    with pytest.raises(ValidationError):
        MACsecConfig.model_validate(kwargs)


@pytest.mark.parametrize("ckn", ["a", "a" * 32, "abcdefghijklmnopqrstuvwxyz012345"], ids=["min-1", "max-32", "a-z0-5"])
def test_positive_ckn(ckn):
    config = MACsecConfig.model_validate(_macsec_config({"ckn": ckn}))
    assert config.ckn == ckn


@pytest.mark.parametrize("ckn", ["", "a" * 33], ids=["empty", "over-32"])
def test_negative_ckn_length(ckn):
    with pytest.raises(ValidationError):
        MACsecConfig.model_validate(_macsec_config({"ckn": ckn}))


def test_negative_ckn_non_octet():
    with pytest.raises(ValidationError) as exc_info:
        MACsecConfig.model_validate(_macsec_config({"ckn": "\u0101" * 4}))
    assert_single_error(exc_info, "FLYNC-SEC-MIN-FMT-252", "ckn")


def test_positive_ckn_allows_utf8_boundary_octet():
    config = MACsecConfig.model_validate(_macsec_config({"ckn": "\u00ff"}))
    config.ckn == "\u00ff"


def test_ckn_to_byte_array():
    config = MACsecConfig.model_validate(_macsec_config({"ckn": "AB\u00ff"}))
    assert config.ckn_to_byte_array() == bytearray([0x41, 0x42, 0xFF])
