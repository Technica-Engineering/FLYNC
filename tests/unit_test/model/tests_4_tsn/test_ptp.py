import pytest

from pydantic import ValidationError
from flync.model.flync_4_ecu.controller import (
    ControllerInterface,
    VirtualControllerInterface,
)
from flync.model.flync_4_tsn.timesync import PTPPort
from flync.model.flync_4_tsn.timesync import PTPConfig
from flync.model.flync_4_ecu.switch import SwitchPort


def test_positive_ptp_config_controller_time_transmitter(
    virtual_controller_interface: VirtualControllerInterface,
):
    ptp_port = {
        "domain_id": 0,
        "src_port_identity": 1,
        "sync_config": {
            "type": "time_transmitter",
            "log_tx_period": -3,
            "two_step": True,
            "tlv": None,
        },
        "pdelay_config": {"log_tx_period": 0},
    }

    controller_iface = ControllerInterface.model_validate(
        {
            "name": "iface1",
            "mac_address": "00:11:22:33:44:55",
            "mii_config": None,
            "virtual_interfaces": [virtual_controller_interface],
            "ptp_config": {
                "cmlds_linkport_enabled": False,
                "ptp_ports": [ptp_port],
            },
        }
    )

    assert isinstance(controller_iface.ptp_config, PTPConfig)
    assert isinstance(controller_iface.ptp_config.ptp_ports[0], PTPPort)


def test_positive_ptp_config_controller_time_receiver(
    virtual_controller_interface: VirtualControllerInterface,
):
    ptp_port = {
        "domain_id": 0,
        "src_port_identity": 1,
        "sync_config": {
            "type": "time_receiver",
            "sync_timeout": 3,
            "sync_followup_timeout": 10,
        },
        "pdelay_config": {"log_tx_period": 0},
    }

    controller_iface = ControllerInterface.model_validate(
        {
            "name": "iface1",
            "mac_address": "00:11:22:33:44:55",
            "mii_config": None,
            "virtual_interfaces": [virtual_controller_interface],
            "ptp_config": {
                "cmlds_linkport_enabled": False,
                "ptp_ports": [ptp_port],
            },
        }
    )

    assert isinstance(controller_iface.ptp_config, PTPConfig)
    assert isinstance(controller_iface.ptp_config.ptp_ports[0], PTPPort)


def test_positive_two_domain_different_roles(
    virtual_controller_interface: VirtualControllerInterface,
):
    ptp_port1 = {
        "domain_id": 0,
        "src_port_identity": 1,
        "sync_config": {
            "type": "time_transmitter",
            "log_tx_period": -3,
            "two_step": True,
            "tlv": None,
        },
        "pdelay_config": {"log_tx_period": 0},
    }
    ptp_port2 = {
        "domain_id": 1,
        "src_port_identity": 2,
        "sync_config": {
            "type": "time_receiver",
            "sync_timeout": 3,
            "sync_followup_timeout": 10,
        },
        "pdelay_config": {"log_tx_period": 0},
    }

    controller_iface = ControllerInterface.model_validate(
        {
            "name": "iface1",
            "mac_address": "00:11:22:33:44:55",
            "mii_config": None,
            "virtual_interfaces": [virtual_controller_interface],
            "ptp_config": {
                "cmlds_linkport_enabled": False,
                "ptp_ports": [ptp_port1, ptp_port2],
            },
        }
    )

    all_domains_valid = False
    if controller_iface.ptp_config is not None:
        for port in controller_iface.ptp_config.ptp_ports:
            if isinstance(port, PTPPort):
                all_domains_valid = True

    assert all_domains_valid


def test_negative_missing_domain_id_controller(
    virtual_controller_interface: VirtualControllerInterface,
):
    ptp_port = {
        "src_port_identity": 1,
        "sync_config": {
            "type": "time_transmitter",
            "log_tx_period": -3,
            "two_step": True,
            "tlv": None,
        },
        "pdelay_config": {"log_tx_period": 0},
    }

    with pytest.raises(ValidationError) as e:
        controller_iface = ControllerInterface.model_validate(
            {
                "name": "iface1",
                "mac_address": "00:11:22:33:44:55",
                "mii_config": None,
                "virtual_interfaces": [virtual_controller_interface],
                "ptp_config": {
                    "cmlds_linkport_enabled": False,
                    "ptp_ports": [ptp_port],
                },
            }
        )


def test_negative_wrong_src_port_identity_controller(
    virtual_controller_interface: VirtualControllerInterface,
):
    ptp_port = {
        "domain_id": 0,
        "src_port_identity": "wrong",
        "sync_config": {
            "type": "time_transmitter",
            "log_tx_period": -3,
            "two_step": True,
            "tlv": None,
        },
        "pdelay_config": {"log_tx_period": 0},
    }

    with pytest.raises(ValidationError) as e:
        controller_iface = ControllerInterface.model_validate(
            {
                "name": "iface1",
                "mac_address": "00:11:22:33:44:55",
                "mii_config": None,
                "virtual_interfaces": [virtual_controller_interface],
                "ptp_config": {
                    "cmlds_linkport_enabled": False,
                    "ptp_ports": [ptp_port],
                },
            }
        )


def test_negative_time_transmitter_no_sync_interval_controller(
    virtual_controller_interface: VirtualControllerInterface,
):
    ptp_port = {
        "domain_id": 0,
        "src_port_identity": 1,
        "sync_config": {
            "type": "time_transmitter",
            "two_step": True,
            "tlv": None,
        },
        "pdelay_config": {"log_tx_period": 0},
    }

    with pytest.raises(ValidationError) as e:
        controller_iface = ControllerInterface.model_validate(
            {
                "name": "iface1",
                "mac_address": "00:11:22:33:44:55",
                "mii_config": None,
                "virtual_interfaces": [virtual_controller_interface],
                "ptp_config": {
                    "cmlds_linkport_enabled": False,
                    "ptp_ports": [ptp_port],
                },
            }
        )


def test_negative_time_transmitter_wrong_sync_interval_controller(
    virtual_controller_interface: VirtualControllerInterface,
):
    ptp_port = {
        "domain_id": 0,
        "src_port_identity": 1,
        "sync_config": {
            "type": "time_transmitter",
            "log_tx_period": 125,
            "two_step": True,
            "tlv": None,
        },
        "pdelay_config": {"log_tx_period": 0},
    }

    with pytest.raises(ValidationError) as e:
        controller_iface = ControllerInterface.model_validate(
            {
                "name": "iface1",
                "mac_address": "00:11:22:33:44:55",
                "mii_config": None,
                "virtual_interfaces": [virtual_controller_interface],
                "ptp_config": {
                    "cmlds_linkport_enabled": False,
                    "ptp_ports": [ptp_port],
                },
            }
        )


def test_negative_time_transmitter_wrong_role_controller(
    virtual_controller_interface: VirtualControllerInterface,
):
    ptp_port = {
        "domain_id": 0,
        "src_port_identity": 1,
        "sync_config": {
            "type": "time_receiver",
            "log_tx_period": -3,
            "two_step": True,
            "tlv": None,
        },
        "pdelay_config": {"log_tx_period": 0},
    }

    with pytest.raises(ValidationError) as e:
        controller_iface = ControllerInterface.model_validate(
            {
                "name": "iface1",
                "mac_address": "00:11:22:33:44:55",
                "mii_config": None,
                "virtual_interfaces": [virtual_controller_interface],
                "ptp_config": {
                    "cmlds_linkport_enabled": False,
                    "ptp_ports": [ptp_port],
                },
            }
        )


def test_negative_time_receiver_wrong_role_controller(
    virtual_controller_interface: VirtualControllerInterface,
):
    ptp_port = {
        "domain_id": 0,
        "src_port_identity": 1,
        "sync_config": {
            "type": "time_transmitter",
            "sync_timeout": 3,
            "sync_followup_timeout": 10,
        },
        "pdelay_config": {"log_tx_period": 0},
    }

    with pytest.raises(ValidationError) as e:
        controller_iface = ControllerInterface.model_validate(
            {
                "name": "iface1",
                "mac_address": "00:11:22:33:44:55",
                "mii_config": None,
                "virtual_interfaces": [virtual_controller_interface],
                "ptp_config": {
                    "cmlds_linkport_enabled": False,
                    "ptp_ports": [ptp_port],
                },
            }
        )


def test_negative_no_sync_config_controller(
    virtual_controller_interface: VirtualControllerInterface,
):
    ptp_port = {
        "domain_id": 0,
        "src_port_identity": 1,
        "pdelay_config": {"log_tx_period": 0},
    }

    with pytest.raises(ValidationError) as e:
        controller_iface = ControllerInterface.model_validate(
            {
                "name": "iface1",
                "mac_address": "00:11:22:33:44:55",
                "mii_config": None,
                "virtual_interfaces": [virtual_controller_interface],
                "ptp_config": {
                    "cmlds_linkport_enabled": False,
                    "ptp_ports": [ptp_port],
                },
            }
        )


def test_negative_wrong_pdelay_config_controller(
    virtual_controller_interface: VirtualControllerInterface,
):
    ptp_port = {
        "domain_id": 0,
        "src_port_identity": 1,
        "sync_config": {
            "type": "time_transmitter",
            "log_tx_period": -3,
            "two_step": True,
            "tlv": None,
        },
        "pdelay_config": {"log_tx_period": 0.3},
    }

    with pytest.raises(ValidationError) as e:
        controller_iface = ControllerInterface.model_validate(
            {
                "name": "iface1",
                "mac_address": "00:11:22:33:44:55",
                "mii_config": None,
                "virtual_interfaces": [virtual_controller_interface],
                "ptp_config": {
                    "cmlds_linkport_enabled": False,
                    "ptp_ports": [ptp_port],
                },
            }
        )


#### SWITCH PORTS


def test_positive_ptp_config_switch_time_transmitter():
    ptp_port = {
        "domain_id": 0,
        "src_port_identity": 1,
        "sync_config": {
            "type": "time_transmitter",
            "log_tx_period": -3,
            "two_step": True,
            "tlv": None,
        },
        "pdelay_config": {"log_tx_period": 0},
    }

    switch_port = SwitchPort.model_validate(
        {
            "name": "port1",
            "silicon_port_no": 1,
            "default_vlan_id": 10,
            "mii_config": None,
            "ptp_config": {
                "cmlds_linkport_enabled": False,
                "ptp_ports": [ptp_port],
            },
        }
    )

    assert isinstance(switch_port.ptp_config, PTPConfig)
    assert isinstance(switch_port.ptp_config.ptp_ports[0], PTPPort)


def test_positive_ptp_config_switch_time_receiver():
    ptp_port = {
        "domain_id": 0,
        "src_port_identity": 1,
        "sync_config": {
            "type": "time_receiver",
            "sync_timeout": 3,
            "sync_followup_timeout": 10,
        },
        "pdelay_config": {"log_tx_period": 0},
    }

    switch_port = SwitchPort.model_validate(
        {
            "name": "port1",
            "silicon_port_no": 1,
            "default_vlan_id": 10,
            "mii_config": None,
            "ptp_config": {
                "cmlds_linkport_enabled": False,
                "ptp_ports": [ptp_port],
            },
        }
    )

    assert isinstance(switch_port.ptp_config, PTPConfig)
    assert isinstance(switch_port.ptp_config.ptp_ports[0], PTPPort)


def test_positive_two_domain_switch_different_roles():
    ptp_port1 = {
        "domain_id": 0,
        "src_port_identity": 1,
        "sync_config": {
            "type": "time_transmitter",
            "log_tx_period": -3,
            "two_step": True,
            "tlv": None,
        },
        "pdelay_config": {"log_tx_period": 0},
    }
    ptp_port2 = {
        "domain_id": 1,
        "src_port_identity": 2,
        "sync_config": {
            "type": "time_receiver",
            "sync_timeout": 3,
            "sync_followup_timeout": 10,
        },
        "pdelay_config": {"log_tx_period": 0},
    }

    switch_port = SwitchPort.model_validate(
        {
            "name": "port1",
            "silicon_port_no": 1,
            "default_vlan_id": 10,
            "mii_config": None,
            "ptp_config": {
                "cmlds_linkport_enabled": False,
                "ptp_ports": [ptp_port1, ptp_port2],
            },
        }
    )

    all_domains_valid = False

    if switch_port.ptp_config is not None:
        for port in switch_port.ptp_config.ptp_ports:
            if isinstance(port, PTPPort):
                all_domains_valid = True

    assert all_domains_valid


def test_negative_missing_domain_id_switch():
    ptp_port = {
        "src_port_identity": 1,
        "sync_config": {
            "type": "time_transmitter",
            "log_tx_period": -3,
            "two_step": True,
            "tlv": None,
        },
        "pdelay_config": {"log_tx_period": 0},
    }

    with pytest.raises(ValidationError) as e:
        switch_port = SwitchPort.model_validate(
            {
                "name": "port1",
                "silicon_port_no": 1,
                "default_vlan_id": 10,
                "mii_config": None,
                "ptp_config": {
                    "cmlds_linkport_enabled": False,
                    "ptp_ports": [ptp_port],
                },
            }
        )


def test_negative_wrong_src_port_identity_switch():
    ptp_port = {
        "domain_id": 0,
        "src_port_identity": "two",
        "sync_config": {
            "type": "time_transmitter",
            "log_tx_period": -3,
            "two_step": True,
            "tlv": None,
        },
        "pdelay_config": {"log_tx_period": 0},
    }

    with pytest.raises(ValidationError) as e:
        switch_port = SwitchPort.model_validate(
            {
                "name": "port1",
                "silicon_port_no": 1,
                "default_vlan_id": 10,
                "mii_config": None,
                "ptp_config": {
                    "cmlds_linkport_enabled": False,
                    "ptp_ports": [ptp_port],
                },
            }
        )


def test_negative_time_transmitter_no_sync_interval_switch():
    ptp_port = {
        "domain_id": 0,
        "src_port_identity": 1,
        "sync_config": {
            "type": "time_transmitter",
            "two_step": True,
            "tlv": None,
        },
        "pdelay_config": {"log_tx_period": 0},
    }

    with pytest.raises(ValidationError) as e:
        switch_port = SwitchPort.model_validate(
            {
                "name": "port1",
                "silicon_port_no": 1,
                "default_vlan_id": 10,
                "mii_config": None,
                "ptp_config": {
                    "cmlds_linkport_enabled": False,
                    "ptp_ports": [ptp_port],
                },
            }
        )


def test_negative_time_transmitter_wrong_sync_interval_switch():
    ptp_port = {
        "domain_id": 0,
        "src_port_identity": 1,
        "sync_config": {
            "type": "time_transmitter",
            "log_tx_period": 125,
            "two_step": True,
            "tlv": None,
        },
        "pdelay_config": {"log_tx_period": 0},
    }

    with pytest.raises(ValidationError) as e:
        switch_port = SwitchPort.model_validate(
            {
                "name": "port1",
                "silicon_port_no": 1,
                "default_vlan_id": 10,
                "mii_config": None,
                "ptp_config": {
                    "cmlds_linkport_enabled": False,
                    "ptp_ports": [ptp_port],
                },
            }
        )


def test_negative_time_transmitter_wrong_role_switch():
    ptp_port = {
        "domain_id": 0,
        "src_port_identity": 1,
        "sync_config": {
            "type": "time_receiver",
            "log_tx_period": -3,
            "two_step": True,
            "tlv": None,
        },
        "pdelay_config": {"log_tx_period": 0},
    }

    with pytest.raises(ValidationError) as e:
        switch_port = SwitchPort.model_validate(
            {
                "name": "port1",
                "silicon_port_no": 1,
                "default_vlan_id": 10,
                "mii_config": None,
                "ptp_config": {
                    "cmlds_linkport_enabled": False,
                    "ptp_ports": [ptp_port],
                },
            }
        )


def test_negative_time_receiver_wrong_role_switch():
    ptp_port = {
        "domain_id": 0,
        "src_port_identity": 1,
        "sync_config": {
            "type": "time_transmitter",
            "sync_timeout": 3,
            "sync_followup_timeout": 10,
        },
        "pdelay_config": {"log_tx_period": 0},
    }

    with pytest.raises(ValidationError) as e:
        switch_port = SwitchPort.model_validate(
            {
                "name": "port1",
                "silicon_port_no": 1,
                "default_vlan_id": 10,
                "mii_config": None,
                "ptp_config": {
                    "cmlds_linkport_enabled": False,
                    "ptp_ports": [ptp_port],
                },
            }
        )


def test_negative_no_sync_config_switch():
    ptp_port = {
        "domain_id": 0,
        "src_port_identity": 1,
        "pdelay_config": {"log_tx_period": 0},
    }

    with pytest.raises(ValidationError) as e:
        switch_port = SwitchPort.model_validate(
            {
                "name": "port1",
                "silicon_port_no": 1,
                "default_vlan_id": 10,
                "mii_config": None,
                "ptp_config": {
                    "cmlds_linkport_enabled": False,
                    "ptp_ports": [ptp_port],
                },
            }
        )


def test_negative_wrong_pdelay_config_switch():
    ptp_port = {
        "domain_id": 0,
        "src_port_identity": 1,
        "sync_config": {
            "type": "time_transmitter",
            "log_tx_period": -3,
            "two_step": True,
            "tlv": None,
        },
        "pdelay_config": {"log_tx_period": 0.3},
    }

    with pytest.raises(ValidationError) as e:
        switch_port = SwitchPort.model_validate(
            {
                "name": "port1",
                "silicon_port_no": 1,
                "default_vlan_id": 10,
                "mii_config": None,
                "ptp_config": {
                    "cmlds_linkport_enabled": False,
                    "ptp_ports": [ptp_port],
                },
            }
        )


def test_positive_ptp_config_with_cmlds_enabled():
    ptp_port = {
        "domain_id": 0,
        "src_port_identity": 1,
        "sync_config": {
            "type": "time_transmitter",
            "log_tx_period": -3,
            "two_step": True,
            "tlv": None,
        },
        "pdelay_config": {"log_tx_period": 0},
    }

    ptp_config = {"cmlds_linkport_enabled": True, "ptp_ports": [ptp_port]}

    switch_port = SwitchPort.model_validate(
        {
            "name": "port1",
            "silicon_port_no": 1,
            "default_vlan_id": 10,
            "mii_config": None,
            "ptp_config": ptp_config,
        }
    )

    assert isinstance(switch_port.ptp_config.ptp_ports[0], PTPPort)
    assert switch_port.ptp_config.cmlds_linkport_enabled is True


def test_negative_cmlds_enabled_missing():
    ptp_port = {
        "domain_id": 0,
        "src_port_identity": 1,
        "sync_config": {
            "type": "time_transmitter",
            "log_tx_period": -3,
            "two_step": True,
            "tlv": None,
        },
        "pdelay_config": {"log_tx_period": 0},
    }

    ptp_config = {"ptp_ports": [ptp_port]}

    switch_port_data = {
        "name": "port1",
        "silicon_port_no": 1,
        "default_vlan_id": 10,
        "mii_config": None,
        "ptp_config": ptp_config,
    }

    result = SwitchPort.model_validate(switch_port_data)

    assert result.ptp_config.cmlds_linkport_enabled is False
