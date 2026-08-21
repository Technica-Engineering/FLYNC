import pytest
from pydantic import ValidationError

from flync.model.flync_4_ecu.switch import FrameMask, Switch, SwitchConfig, TCAMRule


def _make_switch(meta, name, vlans, ports, tcam_rules=None, **kwargs):
    """Helper to build Switch using the new switch_config structure."""
    cfg = {"meta": meta, "ports": ports, "vlans": vlans}
    if tcam_rules is not None:
        cfg["tcam_rules"] = tcam_rules
    return Switch.model_validate(
        {
            "name": name,
            "switch_config": cfg,
            **kwargs,
        }
    )


def test_positive_tcam_entries(embedded_metadata_entry, vlan_entry, switch_port, two_good_tcam_rules):
    _make_switch(
        embedded_metadata_entry,
        "switch_example",
        [vlan_entry],
        [switch_port],
        tcam_rules=two_good_tcam_rules,
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

    switch = _make_switch(
        embedded_metadata_entry,
        "switch_example",
        [vlan_entry],
        [switch_port],
        tcam_rules=[rule],
    )
    assert switch.tcam_rules[0].match_ports == [switch_port.name]


def test_negative_match_port_not_a_switch_port_tcam(
    embedded_metadata_entry,
    vlan_entry,
    switch_port,
    tcam_rule_invalid_match_port,
):
    with pytest.raises(ValidationError) as e:
        _make_switch(
            embedded_metadata_entry,
            "switch_example",
            [vlan_entry],
            [switch_port],
            tcam_rules=[tcam_rule_invalid_match_port],
        )
    assert "TCAM Ports must exist on the Switch." in str(e.value)


def test_negative_action_port_not_a_switch_port_tcam(
    embedded_metadata_entry,
    vlan_entry,
    switch_port,
    tcam_rule_invalid_action_port,
):
    with pytest.raises(ValidationError) as e:
        _make_switch(
            embedded_metadata_entry,
            "switch_example",
            [vlan_entry],
            [switch_port],
            tcam_rules=[tcam_rule_invalid_action_port],
        )
    assert "TCAM Ports must exist on the Switch." in str(e.value)


def test_negative_two_rules_having_same_name(embedded_metadata_entry, vlan_entry, switch_port, two_tcam_rules_same_name):

    with pytest.raises(ValidationError) as e:
        _make_switch(
            embedded_metadata_entry,
            "switch_example",
            [vlan_entry],
            [switch_port],
            tcam_rules=two_tcam_rules_same_name,
        )
    assert "Duplicates found in tcam_rules (name):" in str(e.value)


def test_negative_two_rules_having_same_id(embedded_metadata_entry, vlan_entry, switch_port, two_tcam_rules_same_id):

    with pytest.raises(ValidationError) as e:
        _make_switch(
            embedded_metadata_entry,
            "switch_example",
            [vlan_entry],
            [switch_port],
            tcam_rules=two_tcam_rules_same_id,
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


# ── Vehicle-state tests ──────────────────────────────────────────────


def _vehicle_state_rule(switch_port, tcam_match_filter, vehicle_state=None, vehicle_state_mask=None):
    """Build a raw TCAM rule dict with optional vehicle-state fields."""
    d = {
        "name": "vs_rule",
        "id": 1,
        "match_filter": tcam_match_filter,
        "match_ports": [switch_port.name],
        "action": [{"type": "drop", "ports": [switch_port.name]}],
    }
    if vehicle_state is not None:
        d["vehicle_state"] = vehicle_state
    if vehicle_state_mask is not None:
        d["vehicle_state_mask"] = vehicle_state_mask
    return d


@pytest.mark.parametrize(
    "vehicle_state, expected_mask",
    [
        ({"data": 0x0F, "mask": 0x0F}, 0x0F),  # stored as given
        ({"data": 0x0F}, 0xFF),  # an omitted mask defaults to all bits of the register
    ],
)
def test_positive_vehicle_state(switch_port, tcam_match_filter, vehicle_state, expected_mask):
    """A vehicle state is stored as given, with an omitted mask covering the whole byte."""
    rule = TCAMRule.model_validate(_vehicle_state_rule(switch_port, tcam_match_filter, vehicle_state=vehicle_state))
    assert (rule.vehicle_state.data, rule.vehicle_state.mask) == (0x0F, expected_mask)


def test_positive_no_vehicle_state(switch_port, tcam_match_filter):
    """Omitting the vehicle state leaves it as None, i.e. the rule is not gated on it."""
    rule = TCAMRule.model_validate(_vehicle_state_rule(switch_port, tcam_match_filter))
    assert rule.vehicle_state is None


@pytest.mark.parametrize(
    "vehicle_state, error",
    [
        ({"mask": 0x0F}, "data\n  Field required"),  # a mask on its own is not a vehicle state
        ({"data": 0x10, "mask": 0x0F}, "'data' has bits set outside 'mask'"),
        ({"data": -1, "mask": 1}, "Input should be greater than or equal to 0"),
        ({"data": 1, "mask": 0}, "Input should be greater than or equal to 1"),  # a zero mask matches everything
        ({"data": "0x0100", "mask": "0xFFFF"}, "data and mask must each be <= 0xFF (255)"),  # wider than the 8-bit register
    ],
)
def test_negative_vehicle_state(switch_port, tcam_match_filter, vehicle_state, error):
    """A vehicle state must be a byte-wide pattern whose data bits all lie inside its mask."""
    rule = _vehicle_state_rule(switch_port, tcam_match_filter, vehicle_state=vehicle_state)

    with pytest.raises(ValidationError) as e:
        TCAMRule.model_validate(rule)
    assert error in str(e.value)


def _frame_mask_rule(switch_port, masks, frame_window=None):
    """Build a minimal valid TCAM rule dict matching on ``masks``, given as ``(offset, data)`` pairs."""
    rule = {
        "name": "tcam_rule_1",
        "id": 1,
        "frame_mask": [{"offset": offset, "data": data} for offset, data in masks],
        "match_ports": [switch_port.name],
        "action": [{"type": "drop", "ports": [switch_port.name]}],
    }
    if frame_window is not None:
        rule["frame_window"] = frame_window
    return rule


class Test_FrameMask_TCAM:

    @pytest.mark.parametrize(
        "data_in, mask_in, expected_data, expected_bits",
        [
            ("0x0800", "0xFFFF", 0x0800, "0000100000000000"),  # quoted hex
            (0x0800, 0xFFFF, 0x0800, "0000100000000000"),  # unquoted hex, resolved to an int by the YAML loader
            ("0x 08 00", "0xff ff", 0x0800, "0000100000000000"),  # whitespace groups bytes, case is irrelevant
            ("0b100101010111", "0b111111111111", 0b100101010111, "100101010111"),  # binary keeps its exact bit width
        ],
    )
    def test_positive_literal_formats(self, data_in, mask_in, expected_data, expected_bits):
        """Hex and binary literals parse to the same int, and ``bits`` reports the literal's full width."""
        fm = FrameMask(offset=0, data=data_in, mask=mask_in)
        assert (fm.data, fm.bits, fm.byte_length) == (expected_data, expected_bits, -(-len(expected_bits) // 8))

    def test_positive_default_mask_covers_all_data_bits(self):
        """An omitted mask defaults to all bits of the data literal."""
        assert FrameMask(offset=0, data="0x0800").mask == 0xFFFF

    @pytest.mark.parametrize(
        "kwargs, error",
        [
            ({"offset": 0, "data": "0xZZ"}, "hexadecimal literal"),
            ({"offset": 0, "data": "0800"}, "hexadecimal literal"),  # the 0x/0b prefix is mandatory
            ({"offset": 0, "data": 1.5}, "hexadecimal literal"),
            ({"offset": 0, "data": "0x0800", "mask": "0b11111111"}, "same number of bits"),
            ({"offset": 0, "data": "0x0800", "mask": "0x0700"}, "bits set outside 'mask'"),
            ({"offset": 0, "data": "0x0800", "mask": "0x0000"}, "greater than or equal to 1"),  # a zero mask matches everything
            ({"offset": -1, "data": "0x0800"}, "greater than or equal to 0"),
        ],
    )
    def test_negative_frame_mask(self, kwargs, error):
        """Unparsable literals, mismatching widths, data outside the mask and negative offsets are rejected."""
        with pytest.raises(ValidationError) as e:
            FrameMask(**kwargs)
        assert error in str(e.value)

    @pytest.mark.parametrize(
        "data_in, dumped_data",
        [
            ("0x0800", "0x0800"),  # width and notation are kept
            (0x0800, "0x0800"),  # an int is widened to whole bytes
            ("0b100101010111", "0b100101010111"),  # binary is not normalized to hex
        ],
    )
    def test_positive_serialization_roundtrip(self, data_in, dumped_data):
        """A dump keeps the literal as written and re-validates unchanged; the defaulted mask is not dumped."""
        fm = FrameMask(offset=0, data=data_in)
        dumped = fm.model_dump(exclude_unset=True)
        assert dumped["data"] == dumped_data
        assert "mask" not in dumped
        assert FrameMask.model_validate(dumped).model_dump() == fm.model_dump()

    def test_positive_frame_masks_in_tcam_and_switch(self, embedded_metadata_entry, vlan_entry, switch_port, frame_mask_valid):
        """Frame masks are accepted as a TCAM rule's match criterion and validate at Switch level."""
        switch = _make_switch(
            embedded_metadata_entry,
            "switch_example",
            [vlan_entry],
            [switch_port],
            tcam_rules=[_frame_mask_rule(switch_port, [(12, "0x0800")], frame_window=96)],
        )
        rule = switch.tcam_rules[0]
        assert rule.match_filter is None
        assert [(mask.offset, mask.data, mask.mask) for mask in rule.frame_mask] == [(12, 0x0800, 0xFFFF)]

    @pytest.mark.parametrize(
        "masks, frame_window, error",
        [
            ([(2, "0x0800"), (0, "0x0800")], None, None),  # adjacent 2-byte masks, given out of order
            ([(0, "0x0800"), (1, "0x0800")], None, "must not overlap"),
            ([(12, "0x0800")], 14, None),  # the mask ends exactly at the window boundary
            ([(12, "0x0800")], 13, "exceeds the frame_window"),
            ([(1, "0b101")], 1, "exceeds the frame_window"),  # a sub-byte pattern still occupies a whole byte
            ([], 96, None),  # a frame_window without masks is pointless, but only warns
        ],
    )
    def test_frame_mask_offsets_and_window(self, switch_port, masks, frame_window, error):
        """Frame masks of one rule must cover disjoint bytes and stay inside ``frame_window``."""
        rule = _frame_mask_rule(switch_port, masks, frame_window)

        if error is None:
            assert isinstance(TCAMRule.model_validate(rule), TCAMRule)
        else:
            with pytest.raises(ValidationError) as e:
                TCAMRule.model_validate(rule)
            assert error in str(e.value)

    @pytest.mark.parametrize(
        "include_filter, include_mask, error",
        [
            (True, False, None),  # only match_filter -> valid
            (False, True, None),  # only frame_mask -> valid
            (False, False, None),  # neither -> valid, the rule matches on every frame
            (True, True, "Cannot specify both match_filter and frame_mask"),
        ],
    )
    def test_match_filter_or_mask_exclusive(self, switch_port, tcam_match_filter, frame_mask_valid, include_filter, include_mask, error):
        """A rule matches either on layers (match_filter) or on raw bytes (frame_mask), never on both."""
        rule = {
            "name": "tcam_rule",
            "id": 1,
            "match_ports": [switch_port.name],
            "action": [{"type": "drop", "ports": [switch_port.name]}],
        }
        if include_filter:
            rule["match_filter"] = tcam_match_filter
        if include_mask:
            rule["frame_mask"] = [frame_mask_valid]

        if error is None:
            assert isinstance(TCAMRule.model_validate(rule), TCAMRule)
        else:
            with pytest.raises(ValidationError) as e:
                TCAMRule.model_validate(rule)
            assert error in str(e.value)

    def test_negative_single_frame_mask_mapping(self, switch_port):
        """A single mapping instead of a list is rejected with the shared 'did you forget - ' hint."""
        rule = _frame_mask_rule(switch_port, [(0, "0x0800")])
        rule["frame_mask"] = rule["frame_mask"][0]

        with pytest.raises(ValidationError) as e:
            TCAMRule.model_validate(rule)
        assert "must be a list of items" in str(e.value)
