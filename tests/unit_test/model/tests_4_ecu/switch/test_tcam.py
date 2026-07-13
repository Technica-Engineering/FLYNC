import pytest
from pydantic import ValidationError

from flync.model.flync_4_ecu.switch import Switch, TCAMRule


def test_positive_tcam_entries(embedded_metadata_entry, vlan_entry, switch_port, two_good_tcam_rules):
    Switch.model_validate(
        {
            "meta": embedded_metadata_entry,
            "name": "switch_example",
            "vlans": [vlan_entry],
            "ports": [switch_port],
            "tcam_rules": two_good_tcam_rules,
        }
    )


@pytest.mark.parametrize("match_ports", [None, [], "omit"])
def test_positive_empty_match_ports_binds_all_switch_ports(
    embedded_metadata_entry,
    vlan_entry,
    switch_port,
    tcam_match_filter,
    match_ports,
):
    """An empty or undefined match_ports binds the rule to all switch ports."""
    rule = {
        "name": "tcam_rule_1",
        "id": 1,
        "match_filter": tcam_match_filter,
        "action": [{"type": "drop", "ports": [switch_port.name]}],
    }
    if match_ports != "omit":
        rule["match_ports"] = match_ports

    switch = Switch.model_validate(
        {
            "meta": embedded_metadata_entry,
            "name": "switch_example",
            "vlans": [vlan_entry],
            "ports": [switch_port],
            "tcam_rules": [rule],
        }
    )
    assert switch.tcam_rules[0].match_ports == [switch_port.name]


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


def test_negative_two_rules_having_same_name(embedded_metadata_entry, vlan_entry, switch_port, two_tcam_rules_same_name):

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


def test_negative_two_rules_having_same_id(embedded_metadata_entry, vlan_entry, switch_port, two_tcam_rules_same_id):

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
def test_negative_exclusive_drop_force_mirror_same_port(switch_port, tcam_match_filter, first_action, second_action):
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


def test_positive_drop_and_mirror_on_different_ports(switch_port, tcam_match_filter):
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


def test_positive_drop_and_vlan_overwrite_on_same_port(switch_port, tcam_match_filter):
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


def test_negative_exclusive_vlan_action_same_port(switch_port, tcam_match_filter):
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


def test_positive_remove_vlan_and_vlan_overwrite_on_different_ports(switch_port, tcam_match_filter):
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


def _vehicle_state_rule(switch_port, tcam_match_filter, **vehicle_state_fields):
    """Build a minimal valid TCAM rule dict, overlaying vehicle-state fields."""
    rule = {
        "name": "tcam_rule_1",
        "id": 1,
        "match_filter": tcam_match_filter,
        "match_ports": [switch_port.name],
        "action": [{"type": "drop", "ports": [switch_port.name]}],
    }
    rule.update(vehicle_state_fields)
    return rule


def test_positive_vehicle_state_with_mask(switch_port, tcam_match_filter):
    """vehicle_state together with a valid mask is stored as given."""
    rule = TCAMRule.model_validate(_vehicle_state_rule(switch_port, tcam_match_filter, vehicle_state=0x0F, vehicle_state_mask=0x0F))
    assert rule.vehicle_state == 0x0F
    assert rule.vehicle_state_mask == 0x0F


def test_positive_vehicle_state_without_mask_defaults_to_all_bits(switch_port, tcam_match_filter):
    """A vehicle_state without a mask defaults the mask to 0xFF (all bits)."""
    rule = TCAMRule.model_validate(_vehicle_state_rule(switch_port, tcam_match_filter, vehicle_state=0x0F))
    assert rule.vehicle_state == 0x0F
    assert rule.vehicle_state_mask == 0xFF


def test_positive_no_vehicle_state_fields(switch_port, tcam_match_filter):
    """Omitting both vehicle-state fields leaves them as None (rule not gated)."""
    rule = TCAMRule.model_validate(_vehicle_state_rule(switch_port, tcam_match_filter))
    assert rule.vehicle_state is None
    assert rule.vehicle_state_mask is None


def test_negative_vehicle_state_mask_without_value(switch_port, tcam_match_filter):
    """A mask without a vehicle_state value must raise."""
    with pytest.raises(ValidationError) as e:
        TCAMRule.model_validate(_vehicle_state_rule(switch_port, tcam_match_filter, vehicle_state_mask=0x0F))
    assert "vehicle_state_mask requires vehicle_state" in str(e.value)


def test_negative_vehicle_state_bits_outside_mask(switch_port, tcam_match_filter):
    """A vehicle_state that sets bits the mask ignores must raise."""
    with pytest.raises(ValidationError) as e:
        TCAMRule.model_validate(_vehicle_state_rule(switch_port, tcam_match_filter, vehicle_state=0x10, vehicle_state_mask=0x0F))
    assert "bits set outside vehicle_state_mask" in str(e.value)


@pytest.mark.parametrize(
    "vehicle_state, vehicle_state_mask, error",
    [
        (-1, 1, "Input should be greater than or equal to 0"),
        (1, 0, "Input should be greater than 0"),
        (256, 1, "Input should be less than or equal to 255"),
        (1, 256, "Input should be less than or equal to 255"),
    ],
)
def test_negative_vehicle_state_out_of_range(switch_port, tcam_match_filter, vehicle_state, vehicle_state_mask, error):
    """vehicle_state must be within the 8-bit range 0-255."""
    with pytest.raises(ValidationError) as e:
        TCAMRule.model_validate(
            _vehicle_state_rule(switch_port, tcam_match_filter, vehicle_state=vehicle_state, vehicle_state_mask=vehicle_state_mask)
        )
    assert error in str(e.value)
