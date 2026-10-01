import pytest
from pydantic import ValidationError

from flync.model.flync_4_ecu.controller import EthernetInterface, VirtualControllerInterface
from flync.model.flync_4_ecu.switch import SwitchPort
from flync.model.flync_4_tsn.timesync import PTPConfig, PTPPort
from tests.error_assertions import assert_single_error


def _ptp_port(**overrides):
    """Build a valid :class:`PTPPort` mapping, applying *overrides* on top."""
    port = {
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
    port.update(overrides)
    return port


def _without(port, *keys):
    """Copy *port* dropping *keys*, for required-field negative tests."""
    return {key: value for key, value in port.items() if key not in keys}


def _assert_ptp_error(port, message_fragment):
    with pytest.raises(ValidationError) as exc_info:
        PTPPort.model_validate(port)
    assert_single_error(exc_info, None, message_fragment)


# POSITIVE TESTS


def test_positive_time_transmitter():
    port = PTPPort.model_validate(_ptp_port())

    assert isinstance(port, PTPPort)
    assert port.sync_config.type == "time_transmitter"
    assert port.sync_config.log_tx_period == -3


def test_positive_time_receiver():
    port = PTPPort.model_validate(
        _ptp_port(
            sync_config={
                "type": "time_receiver",
                "sync_timeout": 3,
                "sync_followup_timeout": 10,
            }
        )
    )

    assert isinstance(port, PTPPort)
    assert port.sync_config.type == "time_receiver"
    assert port.sync_config.sync_timeout == 3


def test_positive_two_domains_different_roles():
    ptp_config = PTPConfig.model_validate(
        {
            "cmlds_linkport_enabled": False,
            "ptp_ports": [
                _ptp_port(domain_id=0, src_port_identity=1),
                _ptp_port(
                    domain_id=1,
                    src_port_identity=2,
                    sync_config={
                        "type": "time_receiver",
                        "sync_timeout": 3,
                        "sync_followup_timeout": 10,
                    },
                ),
            ],
        }
    )

    assert len(ptp_config.ptp_ports) == 2
    assert {port.domain_id for port in ptp_config.ptp_ports} == {0, 1}
    assert {port.sync_config.type for port in ptp_config.ptp_ports} == {
        "time_transmitter",
        "time_receiver",
    }


@pytest.mark.parametrize(
    "log_tx_period",
    [
        pytest.param(-7, id="lower bound"),
        pytest.param(1, id="upper bound"),
    ],
)
def test_positive_time_transmitter_log_tx_period_boundaries(log_tx_period):
    port = PTPPort.model_validate(_ptp_port(sync_config={"type": "time_transmitter", "log_tx_period": log_tx_period}))

    assert port.sync_config.log_tx_period == log_tx_period


@pytest.mark.parametrize(
    "log_tx_period",
    [
        pytest.param(-4, id="lower bound"),
        pytest.param(3, id="upper bound"),
    ],
)
def test_positive_pdelay_log_tx_period_boundaries(log_tx_period):
    port = PTPPort.model_validate(_ptp_port(pdelay_config={"log_tx_period": log_tx_period}))

    assert port.pdelay_config.log_tx_period == log_tx_period


def test_positive_pdelay_optional():
    port = PTPPort.model_validate(_without(_ptp_port(), "pdelay_config"))

    assert port.pdelay_config is None


def test_positive_zero_identifiers():
    port = PTPPort.model_validate(_ptp_port(domain_id=0, src_port_identity=0))

    assert port.domain_id == 0
    assert port.src_port_identity == 0


def test_positive_ptp_config_on_controller(virtual_controller_interface: VirtualControllerInterface):
    eth_iface = EthernetInterface.model_validate(
        {
            "name": "iface1",
            "interface_config": {
                "mac_address": "00:11:22:33:44:55",
                "mii_config": None,
                "virtual_interfaces": [virtual_controller_interface],
                "ptp_config": {
                    "cmlds_linkport_enabled": False,
                    "ptp_ports": [_ptp_port()],
                },
            },
        }
    )

    assert isinstance(eth_iface.interface_config.ptp_config, PTPConfig)
    assert isinstance(eth_iface.interface_config.ptp_config.ptp_ports[0], PTPPort)


def test_positive_ptp_config_on_switch():
    switch_port = SwitchPort.model_validate(
        {
            "name": "port1",
            "silicon_port_no": 1,
            "default_vlan_id": 10,
            "mii_config": None,
            "ptp_config": {"cmlds_linkport_enabled": False, "ptp_ports": [_ptp_port()]},
        }
    )

    assert isinstance(switch_port.ptp_config, PTPConfig)
    assert isinstance(switch_port.ptp_config.ptp_ports[0], PTPPort)


def test_positive_ptp_config_cmlds_linkport_enabled():
    switch_port = SwitchPort.model_validate(
        {
            "name": "port1",
            "silicon_port_no": 1,
            "default_vlan_id": 10,
            "mii_config": None,
            "ptp_config": {"cmlds_linkport_enabled": True, "ptp_ports": [_ptp_port()]},
        }
    )

    assert switch_port.ptp_config.cmlds_linkport_enabled is True


def test_positive_ptp_config_cmlds_linkport_default_false():
    switch_port = SwitchPort.model_validate(
        {
            "name": "port1",
            "silicon_port_no": 1,
            "default_vlan_id": 10,
            "mii_config": None,
            "ptp_config": {"ptp_ports": [_ptp_port()]},
        }
    )

    assert switch_port.ptp_config.cmlds_linkport_enabled is False


# NEGATIVE TESTS

# required fields


@pytest.mark.parametrize(
    "port,message_fragment",
    [
        pytest.param(_without(_ptp_port(), "domain_id"), "Field required", id="missing domain id"),
        pytest.param(_without(_ptp_port(), "sync_config"), "Field required", id="missing sync config"),
        pytest.param(
            _ptp_port(sync_config={"type": "time_transmitter"}),
            "Field required",
            id="time transmitter missing log_tx_period",
        ),
        pytest.param(
            _ptp_port(sync_config={"type": "time_receiver", "sync_followup_timeout": 10}),
            "Field required",
            id="time receiver missing sync_timeout",
        ),
        pytest.param(
            _ptp_port(sync_config={"type": "time_receiver", "sync_timeout": 3}),
            "Field required",
            id="time receiver missing sync_followup_timeout",
        ),
    ],
)
def test_negative_missing_required_field(port, message_fragment):
    _assert_ptp_error(port, message_fragment)


# value ranges


@pytest.mark.parametrize(
    "port,message_fragment",
    [
        pytest.param(_ptp_port(domain_id=-1), "greater than or equal to 0", id="negative domain id"),
        pytest.param(
            _ptp_port(src_port_identity=-1),
            "greater than or equal to 0",
            id="negative src_port_identity",
        ),
        pytest.param(
            _ptp_port(sync_config={"type": "time_transmitter", "log_tx_period": 125}),
            "less than or equal to 1",
            id="time transmitter log_tx_period too high",
        ),
        pytest.param(
            _ptp_port(sync_config={"type": "time_transmitter", "log_tx_period": -8}),
            "greater than or equal to -7",
            id="time transmitter log_tx_period too low",
        ),
        pytest.param(
            _ptp_port(pdelay_config={"log_tx_period": -5}),
            "greater than or equal to -4",
            id="pdelay log_tx_period too low",
        ),
        pytest.param(
            _ptp_port(pdelay_config={"log_tx_period": 4}),
            "less than or equal to 3",
            id="pdelay log_tx_period too high",
        ),
    ],
)
def test_negative_log_tx_period_out_of_range(port, message_fragment):
    _assert_ptp_error(port, message_fragment)


@pytest.mark.parametrize(
    "port,message_fragment",
    [
        pytest.param(
            _ptp_port(pdelay_config={"log_tx_period": 0.3}),
            "valid integer",
            id="non-integer pdelay log_tx_period",
        ),
        pytest.param(
            _ptp_port(src_port_identity="wrong"),
            "valid integer",
            id="non-integer src_port_identity",
        ),
    ],
)
def test_negative_non_integer_values(port, message_fragment):
    _assert_ptp_error(port, message_fragment)


# sync configuration role


@pytest.mark.parametrize(
    "port,message_fragment",
    [
        pytest.param(
            _ptp_port(sync_config={"type": "bogus", "log_tx_period": -3}),
            "does not match any of the expected tags",
            id="unknown sync config type",
        ),
        pytest.param(
            _ptp_port(
                sync_config={
                    "type": "time_transmitter",
                    "log_tx_period": -3,
                    "two_step": True,
                    "tlv": None,
                    "sync_timeout": 3,
                }
            ),
            "Extra inputs are not permitted",
            id="receiver-only field in time transmitter",
        ),
        pytest.param(
            _ptp_port(
                sync_config={
                    "type": "time_receiver",
                    "sync_timeout": 3,
                    "sync_followup_timeout": 10,
                    "log_tx_period": -3,
                }
            ),
            "Extra inputs are not permitted",
            id="transmitter-only field in time receiver",
        ),
    ],
)
def test_negative_invalid_sync_config(port, message_fragment):
    _assert_ptp_error(port, message_fragment)
