from pydantic import ValidationError
from flync.model.flync_4_ecu.switch import Switch, TCAMRule
import pytest


def test_positive_tcam_entries(
    embedded_metadata_entry, vlan_entry, switch_port, two_good_tcam_rules
):
    Switch.model_validate(
        {
            "meta": embedded_metadata_entry,
            "name": "switch_example",
            "vlans": [vlan_entry],
            "ports": [switch_port],
            "tcam_rules": two_good_tcam_rules,
        }
    )


def test_negative_match_port_not_a_switch_port_tcam(
    embedded_metadata_entry,
    vlan_entry,
    switch_port,
    tcam_rule_invalid_match_port,
):
    with pytest.raises(ValidationError) as e:
        Switch.model_validate(
            {
                "meta": embedded_metadata_entry,
                "name": "switch_example",
                "vlans": [vlan_entry],
                "ports": [switch_port],
                "tcam_rules": [tcam_rule_invalid_match_port],
            }
        )
    assert "TCAM Ports must exist on the Switch." in str(e.value)


def test_negative_action_port_not_a_switch_port_tcam(
    embedded_metadata_entry,
    vlan_entry,
    switch_port,
    tcam_rule_invalid_action_port,
):
    with pytest.raises(ValidationError) as e:
        Switch.model_validate(
            {
                "meta": embedded_metadata_entry,
                "name": "switch_example",
                "vlans": [vlan_entry],
                "ports": [switch_port],
                "tcam_rules": [tcam_rule_invalid_action_port],
            }
        )
    assert "TCAM Ports must exist on the Switch." in str(e.value)


def test_negative_two_rules_having_same_name(
    embedded_metadata_entry, vlan_entry, switch_port, two_tcam_rules_same_name
):

    with pytest.raises(ValidationError) as e:
        Switch.model_validate(
            {
                "meta": embedded_metadata_entry,
                "name": "switch_example",
                "vlans": [vlan_entry],
                "ports": [switch_port],
                "tcam_rules": two_tcam_rules_same_name,
            }
        )
    assert "Duplicates found in tcam_rules (name):" in str(e.value)


def test_negative_two_rules_having_same_id(
    embedded_metadata_entry, vlan_entry, switch_port, two_tcam_rules_same_id
):

    with pytest.raises(ValidationError) as e:
        Switch.model_validate(
            {
                "meta": embedded_metadata_entry,
                "name": "switch_example",
                "vlans": [vlan_entry],
                "ports": [switch_port],
                "tcam_rules": two_tcam_rules_same_id,
            }
        )
    assert "Duplicates found in tcam_rules (id):" in str(e.value)


@pytest.mark.parametrize(
    "first_action, second_action",
    [
        ("drop", "mirror"),
        ("drop", "force_egress"),
        ("mirror", "force_egress"),
    ],
)
def test_negative_exclusive_drop_force_mirror_same_port(
    switch_port, tcam_match_filter, first_action, second_action
):
    """A TCAM rule must not combine drop, force_egress, and mirror on the
    same port. Any pair on the same port must raise a ValidationError."""
    with pytest.raises(ValidationError) as e:
        TCAMRule.model_validate(
            {
                "name": "tcam_rule_1",
                "id": 1,
                "match_filter": tcam_match_filter,
                "match_ports": [switch_port.name],
                "action": [
                    {"type": first_action, "ports": [switch_port.name]},
                    {"type": second_action, "ports": [switch_port.name]},
                ],
            }
        )
    assert "drop OR force egress OR mirror" in str(e.value)


def test_positive_drop_and_mirror_on_different_ports(
    switch_port, tcam_match_filter
):
    """drop and mirror on disjoint ports must validate successfully."""
    rule = TCAMRule.model_validate(
        {
            "name": "tcam_rule_1",
            "id": 1,
            "match_filter": tcam_match_filter,
            "match_ports": [switch_port.name],
            "action": [
                {"type": "drop", "ports": [switch_port.name]},
                {"type": "mirror", "ports": ["other_port"]},
            ],
        }
    )
    assert isinstance(rule, TCAMRule)


def test_positive_drop_and_vlan_overwrite_on_same_port(
    switch_port, tcam_match_filter
):
    """drop combined with a vlan action on the same port is allowed because
    they are evaluated by different exclusivity groups."""
    rule = TCAMRule.model_validate(
        {
            "name": "tcam_rule_1",
            "id": 1,
            "match_filter": tcam_match_filter,
            "match_ports": [switch_port.name],
            "action": [
                {"type": "drop", "ports": [switch_port.name]},
                {"type": "vlan_overwrite", "ports": [switch_port.name]},
            ],
        }
    )
    assert isinstance(rule, TCAMRule)


def test_negative_exclusive_vlan_action_same_port(
    switch_port, tcam_match_filter
):
    """A TCAM rule must not combine remove_vlan and vlan_overwrite on the
    same port."""
    with pytest.raises(ValidationError) as e:
        TCAMRule.model_validate(
            {
                "name": "tcam_rule_1",
                "id": 1,
                "match_filter": tcam_match_filter,
                "match_ports": [switch_port.name],
                "action": [
                    {"type": "remove_vlan", "ports": [switch_port.name]},
                    {"type": "vlan_overwrite", "ports": [switch_port.name]},
                ],
            }
        )
    assert "remove OR" in str(e.value) and "overwrite a vlan" in str(e.value)


def test_positive_remove_vlan_and_vlan_overwrite_on_different_ports(
    switch_port, tcam_match_filter
):
    """remove_vlan and vlan_overwrite on disjoint ports must validate."""
    rule = TCAMRule.model_validate(
        {
            "name": "tcam_rule_1",
            "id": 1,
            "match_filter": tcam_match_filter,
            "match_ports": [switch_port.name],
            "action": [
                {"type": "remove_vlan", "ports": [switch_port.name]},
                {"type": "vlan_overwrite", "ports": ["other_port"]},
            ],
        }
    )
    assert isinstance(rule, TCAMRule)
