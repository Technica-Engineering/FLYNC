import pytest
from pydantic import ValidationError

from flync.model.flync_4_ecu.controller import ControllerInterface
from flync.model.flync_4_ecu.switch import SwitchPort
from flync.model.flync_4_security.macsec import (
    IntegrityWithConfidentiality,
    IntegrityWithoutConfidentiality,
    MACsecConfig,
)


def test_macsec_positive_vlan_bypass_entry(virtual_controller_interface):
    macsec_example = {
        "vlan_bypass": [1, 2, 3],
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

    controller_iface = ControllerInterface.model_validate(
        {
            "name": "iface1",
            "mac_address": "00:11:22:33:44:55",
            "mii_config": None,
            "virtual_interfaces": [virtual_controller_interface],
            "macsec_config": macsec_example,
        }
    )

    assert isinstance(controller_iface.macsec_config, MACsecConfig)


def test_negative_vlan_bypass_entry(virtual_controller_interface):
    macsec_example = {
        "vlan_bypass": [10000, 2, 3],
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
        controller_iface = ControllerInterface.model_validate(
            {
                "name": "iface1",
                "mac_address": "00:11:22:33:44:55",
                "mii_config": None,
                "virtual_interfaces": [virtual_controller_interface],
                "macsec_config": macsec_example,
            }
        )


def test_positive_cipher_preference_integrity_without_confidentiality(
    integrity_without_confidentiality_entry, virtual_controller_interface
):
    macsec_example = {
        "vlan_bypass": [1, 2, 3],
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
    controller_iface = ControllerInterface.model_validate(
        {
            "name": "iface1",
            "mac_address": "00:11:22:33:44:55",
            "mii_config": None,
            "virtual_interfaces": [virtual_controller_interface],
            "macsec_config": macsec_example,
        }
    )
    assert isinstance(controller_iface.macsec_config, MACsecConfig)


def test_positive_cipher_preference_integrity_with_confidentiality(
    integrity_with_confidentiality_entry, virtual_controller_interface
):
    macsec_example = {
        "vlan_bypass": [1, 2, 3],
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

    controller_iface = ControllerInterface.model_validate(
        {
            "name": "iface1",
            "mac_address": "00:11:22:33:44:55",
            "mii_config": None,
            "virtual_interfaces": [virtual_controller_interface],
            "macsec_config": macsec_example,
        }
    )
    assert isinstance(controller_iface.macsec_config, MACsecConfig)


def test_positive_cipher_preference_mix(
    integrity_with_confidentiality_entry,
    integrity_without_confidentiality_entry,
    virtual_controller_interface,
):
    macsec_example = {
        "vlan_bypass": [1, 2, 3],
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

    controller_iface = ControllerInterface.model_validate(
        {
            "name": "iface1",
            "mac_address": "00:11:22:33:44:55",
            "mii_config": None,
            "virtual_interfaces": [virtual_controller_interface],
            "macsec_config": macsec_example,
        }
    )
    assert isinstance(controller_iface.macsec_config, MACsecConfig)


def test_positive_integrity_with_confidentiality():
    integrity_with_confidentiality = {
        "type": "integrity_with_confidentiality",
        "offset_preference": 30,
    }
    macsec_example = MACsecConfig.model_validate(
        {
            "vlan_bypass": [1, 2, 3],
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
    assert isinstance(
        macsec_example.cipher_preference[0], IntegrityWithConfidentiality
    )


def test_negative_integrity_with_confidentiality():
    integrity_with_confidentiality = {
        "type": "integrity_with_confidentiality",
        "offset_preference": 40,
    }
    with pytest.raises(ValidationError) as e:
        macsec_example = MACsecConfig.model_validate(
            {
                "vlan_bypass": [1, 2, 3],
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
        "offset_preference": 0,
    }
    macsec_example = MACsecConfig.model_validate(
        {
            "vlan_bypass": [1, 2, 3],
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
    assert isinstance(
        macsec_example.cipher_preference[0], IntegrityWithoutConfidentiality
    )


def test_negative_integrity_with_confidentiality():
    integrity_without_confidentiality = {
        "type": "integrity_without_confidentiality",
        "offset_preference": 30,
    }
    with pytest.raises(ValidationError) as e:
        macsec_example = MACsecConfig.model_validate(
            {
                "vlan_bypass": [1, 2, 3],
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
