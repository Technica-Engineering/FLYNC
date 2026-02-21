import pytest
from flync.model.flync_4_ecu.switch import TCAMRule


@pytest.fixture
def two_good_tcam_rules(switch_port):
    tcam_1 = TCAMRule(
        name="tcam_rule_1",
        id=1,
        match_filter={
            "vlanid": 10,
            "src_ipv4": "10.10.5.5",
            "src_port": 40,
            "dst_port": {"from_value": 4, "to_value": 10},
        },
        match_ports=[switch_port.name],
        action=[
            {"type": "mirror", "ports": [switch_port.name]},
            {"type": "vlan_overwrite", "ports": [switch_port.name]},
        ],
    )

    tcam_2 = TCAMRule(
        name="tcam_rule_2",
        id=2,
        match_filter={
            "vlanid": 10,
            "src_ipv4": "10.10.5.5",
            "src_port": 40,
            "dst_port": {"from_value": 4, "to_value": 10},
        },
        match_ports=[switch_port.name],
        action=[
            {"type": "drop", "ports": [switch_port.name]},
        ],
    )

    yield [tcam_1, tcam_2]


@pytest.fixture
def tcam_rule_invalid_match_port(switch_port):
    tcam_1 = TCAMRule(
        name="tcam_rule_1",
        id=1,
        match_filter={
            "vlanid": 10,
            "src_ipv4": "10.10.5.5",
            "src_port": 40,
            "dst_port": {"from_value": 4, "to_value": 10},
        },
        match_ports=["this_is_a_wrong_name"],
        action=[
            {"type": "drop", "ports": [switch_port.name]},
        ],
    )
    yield tcam_1


@pytest.fixture
def tcam_rule_invalid_action_port(switch_port):
    tcam_1 = TCAMRule(
        name="tcam_rule_1",
        id=1,
        match_filter={
            "vlanid": 10,
            "src_ipv4": "10.10.5.5",
            "src_port": 40,
            "dst_port": {"from_value": 4, "to_value": 10},
        },
        match_ports=[switch_port.name],
        action=[
            {"type": "drop", "ports": ["this_is_a_wrong_name"]},
        ],
    )

    yield tcam_1


@pytest.fixture
def two_tcam_rules_same_name(switch_port):
    tcam_1 = TCAMRule(
        name="tcam_rule_1",
        id=1,
        match_filter={
            "vlanid": 10,
            "src_ipv4": "10.10.5.5",
            "src_port": 40,
            "dst_port": {"from_value": 4, "to_value": 10},
        },
        match_ports=[switch_port.name],
        action=[
            {"type": "mirror", "ports": [switch_port.name]},
            {"type": "vlan_overwrite", "ports": [switch_port.name]},
        ],
    )

    tcam_2 = TCAMRule(
        name="tcam_rule_1",
        id=2,
        match_filter={
            "vlanid": 10,
            "src_ipv4": "10.10.5.5",
            "src_port": 40,
            "dst_port": {"from_value": 4, "to_value": 10},
        },
        match_ports=[switch_port.name],
        action=[
            {"type": "drop", "ports": [switch_port.name]},
        ],
    )

    yield [tcam_1, tcam_2]


@pytest.fixture
def two_tcam_rules_same_id(switch_port):
    tcam_1 = TCAMRule(
        name="tcam_rule_1",
        id=1,
        match_filter={
            "vlanid": 10,
            "src_ipv4": "10.10.5.5",
            "src_port": 40,
            "dst_port": {"from_value": 4, "to_value": 10},
        },
        match_ports=[switch_port.name],
        action=[
            {"type": "mirror", "ports": [switch_port.name]},
            {"type": "vlan_overwrite", "ports": [switch_port.name]},
        ],
    )

    tcam_2 = TCAMRule(
        name="tcam_rule_2",
        id=1,
        match_filter={
            "vlanid": 10,
            "src_ipv4": "10.10.5.5",
            "src_port": 40,
            "dst_port": {"from_value": 4, "to_value": 10},
        },
        match_ports=[switch_port.name],
        action=[
            {"type": "drop", "ports": [switch_port.name]},
        ],
    )

    yield [tcam_1, tcam_2]
