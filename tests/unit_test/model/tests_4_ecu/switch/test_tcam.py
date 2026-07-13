import pytest
from pydantic import ValidationError

from flync.model.flync_4_ecu.switch import FrameMask, Switch, TCAMRule


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


class Test_FrameMask_TCAM:

    @pytest.mark.parametrize(
        "data_in, mask_in, data_out, mask_out",
        [
            ("0x0800", "0xFFFF", "0x0800", "0xFFFF"),  # hex, already canonical
            ("0xffff", "0xff00", "0xFFFF", "0xFF00"),  # hex lower-case -> upper
            ("0x08_00", "0xFF FF", "0x0800", "0xFFFF"),  # separators stripped
            ("0x08004500", "0xFFFFFFFF", "0x08004500", "0xFFFFFFFF"),  # multi-byte hex
            ("100101010111", "111111111111", "100101010111", "111111111111"),  # binary, verbatim
            ("0000100000000000", "1111111111111111", "0000100000000000", "1111111111111111"),  # binary leading zeros
            ("0x0800", "0000100000000000", "0x0800", "0000100000000000"),  # mixed formats, equal bit width
        ],
    )
    def test_positive_data_mask_normalization(self, data_in, mask_in, data_out, mask_out):
        """Both formats are accepted; hex is upper-cased, binary kept as is."""
        fm = FrameMask(offset=0, data=data_in, mask=mask_in)
        assert (fm.data, fm.mask) == (data_out, mask_out)

    @pytest.mark.parametrize(
        "data_in, expected_bits",
        [
            ("0x0800", "0000100000000000"),
            ("0xF", "1111"),
            ("100101010111", "100101010111"),
        ],
    )
    def test_positive_bits_property(self, data_in, expected_bits):
        """``bits`` exposes a unified binary view regardless of input format."""
        fm = FrameMask(offset=0, data=data_in, mask="1" * len(expected_bits))
        assert fm.bits == expected_bits

    @pytest.mark.parametrize("offset", [0, 10, 94])
    def test_positive_valid_offsets(self, offset):
        """Offsets anywhere inside the inspectable window are accepted."""
        fm = FrameMask(offset=offset, data="0x0800", mask="0xFFFF")
        assert fm.offset == offset

    def test_positive_frame_mask_in_tcam_and_switch(self, embedded_metadata_entry, vlan_entry, switch_port, frame_mask_valid):
        """A frame_mask is accepted as a TCAM rule's match criterion and validates at Switch level."""
        switch = Switch.model_validate(
            {
                "meta": embedded_metadata_entry,
                "name": "switch_example",
                "vlans": [vlan_entry],
                "ports": [switch_port],
                "tcam_rules": [
                    {
                        "name": "tcam_mask_rule",
                        "id": 1,
                        "frame_mask": frame_mask_valid,
                        "match_ports": [switch_port.name],
                        "action": [{"type": "drop", "ports": [switch_port.name]}],
                    }
                ],
            }
        )
        rule = switch.tcam_rules[0]
        assert isinstance(rule.frame_mask, FrameMask)
        assert rule.match_filter is None
        assert (rule.frame_mask.data, rule.frame_mask.mask) == ("0x0800", "0xFFFF")

    @pytest.mark.parametrize(
        "kwargs, error",
        [
            ({"offset": -1, "data": "0x0800", "mask": "0xFFFF"}, "offset must be between"),
            ({"offset": 96, "data": "0x0800", "mask": "0xFFFF"}, "offset must be between"),
            ({"offset": 95, "data": "0x0000", "mask": "0xFFFF"}, "max inspectable frame position"),
            ({"offset": 0, "data": 2048, "mask": "0xFFFF"}, "must be a quoted string"),
            ({"offset": 0, "data": "0800", "mask": "0xFFFF"}, "0x-hex literal"),
            ({"offset": 0, "data": "0xZZ", "mask": "0xFFFF"}, "0x-hex literal"),
            ({"offset": 0, "data": "1021", "mask": "0x0FFF"}, "0x-hex literal"),
            ({"offset": 0, "data": "0x0800", "mask": "0xFF"}, "same number of bits"),
            ({"offset": 0, "data": "0x0800", "mask": "11111111"}, "same number of bits"),
        ],
    )
    def test_negative_frame_mask_validation(self, kwargs, error):
        """Invalid offsets, widths, types and formats are rejected with a clear error."""
        with pytest.raises(ValidationError) as e:
            FrameMask(**kwargs)
        assert error in str(e.value)

    @pytest.mark.parametrize(
        "include_filter, include_mask, error",
        [
            (True, False, None),  # only match_filter -> valid
            (False, True, None),  # only frame_mask -> valid
            (True, True, "Cannot specify both match_filter and frame_mask"),  # both -> rejected
            (False, False, "Must specify either match_filter or frame_mask"),  # neither -> rejected
        ],
    )
    def test_match_filter_or_mask_exclusive(self, switch_port, tcam_match_filter, frame_mask_valid, include_filter, include_mask, error):
        """TCAMRule.validate_match_filter_or_mask_exclusive: exactly one of
        match_filter or frame_mask must be provided."""
        rule = {
            "name": "tcam_rule",
            "id": 1,
            "match_ports": [switch_port.name],
            "action": [{"type": "drop", "ports": [switch_port.name]}],
        }
        if include_filter:
            rule["match_filter"] = tcam_match_filter
        if include_mask:
            rule["frame_mask"] = frame_mask_valid

        if error is None:
            assert isinstance(TCAMRule.model_validate(rule), TCAMRule)
        else:
            with pytest.raises(ValidationError) as e:
                TCAMRule.model_validate(rule)
            assert error in str(e.value)

    @pytest.mark.parametrize(
        "data_in, mask_in",
        [
            ("0x0800", "0xFFFF"),
            ("100101010111", "111111111111"),
        ],
    )
    def test_positive_serialization_roundtrip(self, data_in, mask_in):
        """model_dump emits the canonical strings and re-validating is idempotent."""
        fm = FrameMask(offset=0, data=data_in, mask=mask_in)
        dumped = fm.model_dump()
        assert (dumped["data"], dumped["mask"]) == (fm.data, fm.mask)
        assert FrameMask.model_validate(dumped).model_dump() == dumped
