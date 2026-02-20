from pydantic import ValidationError
from flync.model.flync_4_ecu.switch import Switch
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
