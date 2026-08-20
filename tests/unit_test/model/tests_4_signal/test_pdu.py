import pytest
from pydantic import ValidationError

from flync.model.flync_4_signal.pdu import (
    ContainedPDURef,
    ContainerPDU,
    ContainerPDUHeader,
    MultiplexedPDU,
    MuxGroup,
    PDUInstance,
    StandardPDU,
)
from flync.model.flync_4_signal.signal import (
    Signal,
    SignalDataType,
    SignalGroup,
    SignalGroupInstance,
    SignalInstance,
)
from tests.error_assertions import assert_single_error


def test_positive_pdu_instance_with_bit_position():
    pi = PDUInstance(pdu_ref="my_pdu", bit_position=0)
    assert pi.pdu_ref == "my_pdu"
    assert pi.bit_position == 0


def test_positive_pdu_instance_without_bit_position():
    pi = PDUInstance(pdu_ref="my_pdu")
    assert pi.bit_position is None


def test_positive_pdu_instance_with_update_bit():
    pi = PDUInstance(pdu_ref="my_pdu", bit_position=0, update_bit_position=1)
    assert pi.update_bit_position == 1


def test_negative_pdu_instance_negative_bit_position():
    with pytest.raises(ValidationError):
        PDUInstance(pdu_ref="my_pdu", bit_position=-1)


def test_positive_contained_pdu_ref():
    ref = ContainedPDURef(header_id=1, pdu_ref="inner_pdu")
    assert ref.header_id == 1
    assert ref.pdu_ref == "inner_pdu"


def test_positive_contained_pdu_ref_model_validate():
    ref = ContainedPDURef.model_validate({"header_id": 1, "pdu_ref": "pdu_A"})
    assert isinstance(ref, ContainedPDURef)


def test_negative_contained_pdu_ref_zero_header_id():
    """header_id must be greater than zero; zero must be rejected."""
    with pytest.raises(ValidationError):
        ContainedPDURef(header_id=0, pdu_ref="inner_pdu")


def test_positive_standard_pdu_empty():
    pdu = StandardPDU(name="empty_pdu", length=4)
    assert pdu.signals == []
    assert pdu.signal_groups == []


def test_positive_standard_pdu_with_description():
    pdu = StandardPDU(name="desc_pdu", length=8, description="Test PDU")
    assert pdu.description == "Test PDU"


def test_positive_standard_pdu_with_unplaced_signals():
    sig = Signal(name="unplaced_sig", bit_length=8, data_type=SignalDataType.UINT8)
    pdu = StandardPDU(
        name="unplaced_pdu",
        length=1,
        signals=[SignalInstance(signal=sig)],
    )
    assert len(pdu.signals) == 1


def test_positive_standard_pdu_with_placed_signal():
    sig = Signal(name="placed_sig", bit_length=8, data_type=SignalDataType.UINT8)
    pdu = StandardPDU(
        name="placed_pdu",
        length=1,
        signals=[SignalInstance(signal=sig, bit_position=0)],
    )
    assert pdu.signals[0].bit_position == 0


def test_positive_standard_pdu_two_signals_no_overlap():
    s1 = Signal(name="pdu_s1", bit_length=8, data_type=SignalDataType.UINT8)
    s2 = Signal(name="pdu_s2", bit_length=8, data_type=SignalDataType.UINT8)
    pdu = StandardPDU(
        name="two_sig_pdu",
        length=2,
        signals=[
            SignalInstance(signal=s1, bit_position=0),
            SignalInstance(signal=s2, bit_position=8),
        ],
    )
    assert len(pdu.signals) == 2


def test_positive_standard_pdu_with_signal_group():
    s1 = Signal(name="grp_s1_pdu", bit_length=8, data_type=SignalDataType.UINT8)
    sg = SignalGroup(
        name="pdu_grp1",
        signals=[SignalInstance(signal=s1, bit_position=0)],
    )
    pdu = StandardPDU(
        name="grp_pdu",
        length=1,
        signal_groups=[SignalGroupInstance(signal_group=sg, bit_position=0)],
    )
    assert len(pdu.signal_groups) == 1


def test_positive_standard_pdu_model_validate():
    data = {"name": "mv_pdu", "length": 4}
    pdu = StandardPDU.model_validate(data)
    assert isinstance(pdu, StandardPDU)
    assert pdu.type == "standard"


def test_negative_standard_pdu_signal_overflow():
    sig = Signal(name="overflow_sig", bit_length=8, data_type=SignalDataType.UINT8)
    instance = SignalInstance(signal=sig, bit_position=1)

    with pytest.raises(ValidationError):
        StandardPDU(name="overflow_pdu", length=1, signals=[instance])


def test_negative_standard_pdu_signal_overlap():
    s1 = Signal(name="olap_s1", bit_length=8, data_type=SignalDataType.UINT8)
    s2 = Signal(name="olap_s2", bit_length=8, data_type=SignalDataType.UINT8)
    instances = [SignalInstance(signal=s1, bit_position=0), SignalInstance(signal=s2, bit_position=4)]

    with pytest.raises(ValidationError):
        StandardPDU(name="overlap_pdu", length=2, signals=instances)


def test_negative_standard_pdu_zero_length():
    with pytest.raises(ValidationError):
        StandardPDU(name="zero_len_pdu", length=0)


def test_positive_standard_pdu_signals_adjacent_no_overlap():
    """Two signals whose ranges touch at the boundary must not be flagged as overlapping."""
    s1 = Signal(name="adj_s1", bit_length=4, data_type=SignalDataType.UINT8)
    s2 = Signal(name="adj_s2", bit_length=4, data_type=SignalDataType.UINT8)
    pdu = StandardPDU(
        name="adjacent_pdu",
        length=1,
        signals=[
            SignalInstance(signal=s1, bit_position=0),
            SignalInstance(signal=s2, bit_position=4),
        ],
    )
    assert len(pdu.signals) == 2


def test_positive_standard_pdu_signal_fits_exactly_at_end():
    """A signal ending exactly at the last PDU bit must be accepted."""
    sig = Signal(name="boundary_sig", bit_length=8, data_type=SignalDataType.UINT8)
    pdu = StandardPDU(
        name="boundary_pdu",
        length=2,
        signals=[SignalInstance(signal=sig, bit_position=8)],
    )
    assert pdu.signals[0].bit_position == 8


def test_positive_standard_pdu_mixed_placed_and_unplaced_signals():
    """Unplaced signals (bit_position=None) must be skipped during overlap/overflow checks."""
    placed = Signal(name="placed_mix", bit_length=8, data_type=SignalDataType.UINT8)
    unplaced = Signal(name="unplaced_mix", bit_length=8, data_type=SignalDataType.UINT8)
    pdu = StandardPDU(
        name="mixed_placement_pdu",
        length=1,
        signals=[
            SignalInstance(signal=placed, bit_position=0),
            SignalInstance(signal=unplaced),
        ],
    )
    assert len(pdu.signals) == 2


def test_positive_standard_pdu_signal_and_signal_group_no_overlap():
    """A signal and a signal group placed side by side must not be flagged as overlapping."""
    sig = Signal(name="mix_sig", bit_length=8, data_type=SignalDataType.UINT8)
    grp_sig = Signal(name="mix_grp_inner", bit_length=8, data_type=SignalDataType.UINT8)
    grp = SignalGroup(
        name="mix_grp",
        signals=[SignalInstance(signal=grp_sig, bit_position=0)],
    )
    pdu = StandardPDU(
        name="mix_pdu",
        length=2,
        signals=[SignalInstance(signal=sig, bit_position=0)],
        signal_groups=[SignalGroupInstance(signal_group=grp, bit_position=8)],
    )
    assert len(pdu.signals) == 1
    assert len(pdu.signal_groups) == 1


def test_negative_standard_pdu_signals_identical_position():
    """Two signals at the same bit_position must be flagged as overlapping."""
    s1 = Signal(name="same_pos_s1", bit_length=8, data_type=SignalDataType.UINT8)
    s2 = Signal(name="same_pos_s2", bit_length=8, data_type=SignalDataType.UINT8)
    instances = [SignalInstance(signal=s1, bit_position=0), SignalInstance(signal=s2, bit_position=0)]

    with pytest.raises(ValidationError) as exc_info:
        StandardPDU(name="same_pos_pdu", length=1, signals=instances)
    assert_single_error(exc_info, "FLYNC-CMN-MIN-CONS-030", "overlap")


def test_negative_standard_pdu_signal_range_contained_in_other():
    """A signal whose range is fully contained inside another signal's range must overlap."""
    outer = Signal(name="outer_sig", bit_length=16, data_type=SignalDataType.UINT16)
    inner = Signal(name="inner_sig", bit_length=4, data_type=SignalDataType.UINT8)
    instances = [SignalInstance(signal=outer, bit_position=0), SignalInstance(signal=inner, bit_position=4)]

    with pytest.raises(ValidationError) as exc_info:
        StandardPDU(name="contained_pdu", length=2, signals=instances)
    assert_single_error(exc_info, "FLYNC-CMN-MIN-CONS-030", "overlap")


def test_negative_standard_pdu_signal_starts_at_pdu_end():
    """A signal placed exactly at the PDU's last bit must overflow (length is half-open)."""
    sig = Signal(name="at_end_sig", bit_length=1, data_type=SignalDataType.UINT8)
    instance = SignalInstance(signal=sig, bit_position=8)

    with pytest.raises(ValidationError) as exc_info:
        StandardPDU(name="at_end_pdu", length=1, signals=[instance])
    assert_single_error(exc_info, "FLYNC-CMN-MIN-VAL-029", "overflows")


def test_negative_standard_pdu_signal_group_overflows_pdu():
    """A signal group whose footprint exceeds the PDU must overflow."""
    s1 = Signal(name="grp_over_s1", bit_length=8, data_type=SignalDataType.UINT8)
    s2 = Signal(name="grp_over_s2", bit_length=8, data_type=SignalDataType.UINT8)
    grp = SignalGroup(
        name="grp_over",
        signals=[
            SignalInstance(signal=s1, bit_position=0),
            SignalInstance(signal=s2, bit_position=8),
        ],
    )
    group_instance = SignalGroupInstance(signal_group=grp, bit_position=0)

    with pytest.raises(ValidationError) as exc_info:
        StandardPDU(name="grp_over_pdu", length=1, signal_groups=[group_instance])
    assert_single_error(exc_info, "FLYNC-CMN-MIN-VAL-029", "overflows")


def test_negative_standard_pdu_signal_overlaps_signal_group():
    """A signal placed inside a signal-group's range must be flagged as overlapping."""
    sig = Signal(name="mix_overlap_sig", bit_length=8, data_type=SignalDataType.UINT8)
    grp_s1 = Signal(name="mix_overlap_grp_s1", bit_length=8, data_type=SignalDataType.UINT8)
    grp_s2 = Signal(name="mix_overlap_grp_s2", bit_length=8, data_type=SignalDataType.UINT8)
    grp = SignalGroup(
        name="mix_overlap_grp",
        signals=[
            SignalInstance(signal=grp_s1, bit_position=0),
            SignalInstance(signal=grp_s2, bit_position=8),
        ],
    )
    instance = SignalInstance(signal=sig, bit_position=8)
    group_instance = SignalGroupInstance(signal_group=grp, bit_position=0)

    with pytest.raises(ValidationError) as exc_info:
        StandardPDU(name="mix_overlap_pdu", length=2, signals=[instance], signal_groups=[group_instance])
    assert_single_error(exc_info, "FLYNC-CMN-MIN-CONS-030", "overlap")


def test_negative_standard_pdu_signal_groups_overlap_each_other():
    """Two signal groups whose ranges intersect must be flagged as overlapping."""
    a1 = Signal(name="grp_a_s1", bit_length=8, data_type=SignalDataType.UINT8)
    a2 = Signal(name="grp_a_s2", bit_length=8, data_type=SignalDataType.UINT8)
    b1 = Signal(name="grp_b_s1", bit_length=8, data_type=SignalDataType.UINT8)
    b2 = Signal(name="grp_b_s2", bit_length=8, data_type=SignalDataType.UINT8)
    grp_a = SignalGroup(
        name="grp_a",
        signals=[
            SignalInstance(signal=a1, bit_position=0),
            SignalInstance(signal=a2, bit_position=8),
        ],
    )
    grp_b = SignalGroup(
        name="grp_b",
        signals=[
            SignalInstance(signal=b1, bit_position=0),
            SignalInstance(signal=b2, bit_position=8),
        ],
    )
    group_instances = [SignalGroupInstance(signal_group=grp_a, bit_position=0), SignalGroupInstance(signal_group=grp_b, bit_position=8)]

    with pytest.raises(ValidationError) as exc_info:
        StandardPDU(name="two_groups_overlap_pdu", length=3, signal_groups=group_instances)
    assert_single_error(exc_info, "FLYNC-CMN-MIN-CONS-030", "overlap")


def test_positive_mux_group_empty():
    mg = MuxGroup(
        selector_value=0,
        pdu=PDUInstance(pdu_ref="mg_empty_pdu"),
    )
    assert mg.selector_value == 0
    assert mg.pdu.pdu_ref == "mg_empty_pdu"


def test_positive_mux_group_with_bit_position():
    mg = MuxGroup(
        selector_value=1,
        pdu=PDUInstance(pdu_ref="mg_sig_pdu", bit_position=8),
    )
    assert mg.selector_value == 1
    assert mg.pdu.pdu_ref == "mg_sig_pdu"
    assert mg.pdu.bit_position == 8


def test_positive_mux_group_negative_selector_value_is_rejected():
    with pytest.raises(ValidationError):
        MuxGroup(selector_value=-1, pdu=PDUInstance(pdu_ref="mg_neg_pdu"))


def _make_selector_signal(name="mux_sel", bit_length=4):
    sig = Signal(name=name, bit_length=bit_length, data_type=SignalDataType.UINT8)
    return SignalInstance(signal=sig, bit_position=0)


def _make_mux_group(selector_value, pdu_ref="mux_payload"):
    return MuxGroup(
        selector_value=selector_value,
        pdu=PDUInstance(pdu_ref=pdu_ref),
    )


def test_positive_multiplexed_pdu_single_mux_group():
    sel = _make_selector_signal("mp_sel_1")
    mg = _make_mux_group(0, "mp_payload_1")
    pdu = MultiplexedPDU(
        name="mp_pdu_1",
        length=4,
        selector_signal=sel,
        mux_groups=[mg],
    )
    assert pdu.type == "multiplexed"
    assert len(pdu.mux_groups) == 1


def test_positive_multiplexed_pdu_multiple_mux_groups():
    sel = _make_selector_signal("mp_sel_2")
    mg0 = _make_mux_group(0, "mp_pay_2a")
    mg1 = _make_mux_group(1, "mp_pay_2b")
    pdu = MultiplexedPDU(
        name="mp_pdu_2",
        length=4,
        selector_signal=sel,
        mux_groups=[mg0, mg1],
    )
    assert len(pdu.mux_groups) == 2


def test_positive_multiplexed_pdu_with_static_signals():
    sel = _make_selector_signal("mp_sel_3")
    mg = _make_mux_group(0, "mp_pay_3")
    pdu = MultiplexedPDU(
        name="mp_pdu_3",
        length=4,
        selector_signal=sel,
        mux_groups=[mg],
        static_group=[PDUInstance(pdu_ref="mp_pdu_3_static", bit_position=16)],
    )
    assert pdu.static_group == [PDUInstance(pdu_ref="mp_pdu_3_static", bit_position=16)]


def test_positive_multiplexed_pdu_multiple_static_pdus():
    sel = _make_selector_signal("mp_sel_3b")
    mg = _make_mux_group(0, "mp_pay_3b")
    pdu = MultiplexedPDU(
        name="mp_pdu_3b",
        length=4,
        selector_signal=sel,
        mux_groups=[mg],
        static_group=[PDUInstance(pdu_ref="mp_pdu_3b_static_1"), PDUInstance(pdu_ref="mp_pdu_3b_static_2")],
    )
    assert [inst.pdu_ref for inst in pdu.static_group] == ["mp_pdu_3b_static_1", "mp_pdu_3b_static_2"]


def test_positive_multiplexed_pdu_static_group_default_none():
    sel = _make_selector_signal("mp_sel_3c")
    mg = _make_mux_group(0, "mp_pay_3c")
    pdu = MultiplexedPDU(
        name="mp_pdu_3c",
        length=4,
        selector_signal=sel,
        mux_groups=[mg],
    )
    assert pdu.static_group is None


def test_positive_multiplexed_pdu_static_group_single_instance_coerced():
    # static_group used to be a single PDUInstance; an unwrapped mapping is coerced into a list.
    pdu = MultiplexedPDU.model_validate(
        {
            "name": "mp_pdu_3d",
            "length": 4,
            "selector_signal": {"signal": {"name": "mp_sel_3d", "bit_length": 4, "data_type": "uint8"}},
            "mux_groups": [{"selector_value": 0, "pdu": {"pdu_ref": "mp_pay_3d"}}],
            "static_group": {"pdu_ref": "mp_pdu_3d_static"},
        }
    )
    assert [inst.pdu_ref for inst in pdu.static_group] == ["mp_pdu_3d_static"]


def test_positive_multiplexed_pdu_selector_no_position():
    sig = Signal(name="mp_sel_nopos", bit_length=4, data_type=SignalDataType.UINT8)
    sel = SignalInstance(signal=sig)
    mg = _make_mux_group(0, "mp_pay_nopos")
    pdu = MultiplexedPDU(
        name="mp_nopos_pdu",
        length=4,
        selector_signal=sel,
        mux_groups=[mg],
    )
    assert pdu.selector_signal.bit_position is None


def test_negative_multiplexed_pdu_duplicate_selector_values():
    sel = _make_selector_signal("dup_sel")
    mg0 = _make_mux_group(0, "dup_pay_a")
    mg1 = _make_mux_group(0, "dup_pay_b")
    with pytest.raises(ValidationError):
        MultiplexedPDU(
            name="dup_sel_pdu",
            length=4,
            selector_signal=sel,
            mux_groups=[mg0, mg1],
        )


def test_negative_multiplexed_pdu_selector_value_out_of_range():
    sel = _make_selector_signal("oor_sel", bit_length=4)
    mg = MuxGroup(
        selector_value=16,
        pdu=PDUInstance(pdu_ref="mg_oor_pdu"),
    )
    with pytest.raises(ValidationError) as exc_info:
        MultiplexedPDU(
            name="oor_sel_pdu",
            length=4,
            selector_signal=sel,
            mux_groups=[mg],
        )
    assert_single_error(exc_info, "FLYNC-SIG-MIN-VAL-108", "out-of-range")


def test_negative_multiplexed_pdu_empty_mux_groups():
    sel = _make_selector_signal("empty_mux_sel")
    with pytest.raises(ValidationError):
        MultiplexedPDU(
            name="empty_mux_pdu",
            length=4,
            selector_signal=sel,
            mux_groups=[],
        )


def test_positive_container_pdu_16bit_id_8bit_length_empty():
    pdu = ContainerPDU(
        name="ctr_empty_sh",
        pdu_id=1,
        length=4,
        header=ContainerPDUHeader(id_length_bits=16, length_field_bits=8),
    )
    assert pdu.type == "container"
    assert pdu.header.id_length_bits == 16
    assert pdu.header.length_field_bits == 8
    assert pdu.contained_pdus == []


def test_positive_container_pdu_32bit_id_16bit_length_empty():
    pdu = ContainerPDU(
        name="ctr_empty_lh",
        pdu_id=2,
        length=4,
        header=ContainerPDUHeader(id_length_bits=32, length_field_bits=16),
    )
    assert pdu.header.id_length_bits == 32
    assert pdu.header.length_field_bits == 16


def test_positive_container_pdu_16bit_id_8bit_length_with_refs():
    pdu = ContainerPDU(
        name="ctr_sh_refs",
        pdu_id=3,
        length=10,
        header=ContainerPDUHeader(id_length_bits=16, length_field_bits=8),
        contained_pdus=[
            ContainedPDURef(header_id=1, pdu_ref="inner_a"),
            ContainedPDURef(header_id=2, pdu_ref="inner_b"),
        ],
    )
    assert len(pdu.contained_pdus) == 2


def test_positive_container_pdu_32bit_id_16bit_length_exact_minimum():
    # overhead = (32+16)//8 = 6 bytes per slot; 1 slot => minimum = 6
    pdu = ContainerPDU(
        name="ctr_lh_exact",
        pdu_id=4,
        length=6,
        header=ContainerPDUHeader(id_length_bits=32, length_field_bits=16),
        contained_pdus=[ContainedPDURef(header_id=1, pdu_ref="inner_c")],
    )
    assert pdu.length == 6


def test_positive_container_pdu_16bit_id_8bit_length_exact_minimum():
    # overhead = (16+8)//8 = 3 bytes per slot; 1 slot => minimum = 3
    pdu = ContainerPDU(
        name="ctr_sh_exact",
        pdu_id=5,
        length=3,
        header=ContainerPDUHeader(id_length_bits=16, length_field_bits=8),
        contained_pdus=[ContainedPDURef(header_id=1, pdu_ref="inner_d")],
    )
    assert pdu.length == 3


def test_positive_container_pdu_model_validate():
    data = {
        "name": "ctr_mv",
        "pdu_id": 6,
        "length": 20,
        "header": {"id_length_bits": 16, "length_field_bits": 8},
    }
    pdu = ContainerPDU.model_validate(data)
    assert isinstance(pdu, ContainerPDU)


def test_negative_container_pdu_too_small_3byte_header():
    # overhead = (16+8)//8 = 3 bytes; 2 slots => minimum = 6; length=5 < 6
    header = ContainerPDUHeader(id_length_bits=16, length_field_bits=8)
    contained_pdus = [ContainedPDURef(header_id=1, pdu_ref="p1"), ContainedPDURef(header_id=2, pdu_ref="p2")]

    with pytest.raises(ValidationError):
        ContainerPDU(name="ctr_small_sh", pdu_id=10, length=5, header=header, contained_pdus=contained_pdus)


def test_negative_container_pdu_too_small_6byte_header():
    # overhead = (32+16)//8 = 6 bytes; 1 slot => minimum = 6; length=5 < 6
    header = ContainerPDUHeader(id_length_bits=32, length_field_bits=16)
    contained_pdus = [ContainedPDURef(header_id=1, pdu_ref="p1")]

    with pytest.raises(ValidationError):
        ContainerPDU(name="ctr_small_lh", pdu_id=11, length=5, header=header, contained_pdus=contained_pdus)


def test_negative_container_pdu_non_byte_aligned_id_length():
    with pytest.raises(ValidationError):
        ContainerPDUHeader(id_length_bits=12, length_field_bits=8)


def test_negative_container_pdu_non_byte_aligned_length_length():
    with pytest.raises(ValidationError):
        ContainerPDUHeader(id_length_bits=16, length_field_bits=4)


def test_negative_container_pdu_zero_length():
    header = ContainerPDUHeader(id_length_bits=16, length_field_bits=8)

    with pytest.raises(ValidationError):
        ContainerPDU(name="ctr_zero_len", pdu_id=12, length=0, header=header)


def test_positive_container_pdu_headerless_with_one_pdu():
    """Header-less (both fields 0) with exactly one contained PDU must be accepted."""
    pdu = ContainerPDU(
        name="ctr_headerless_one",
        pdu_id=20,
        length=4,
        header=ContainerPDUHeader(id_length_bits=0, length_field_bits=0),
        contained_pdus=[ContainedPDURef(header_id=1, pdu_ref="inner_hl")],
    )
    assert len(pdu.contained_pdus) == 1


def test_positive_container_pdu_headerless_no_contained_pdus_raises():
    """Header-less with zero contained PDUs must be rejected (not exactly one)."""
    header = ContainerPDUHeader(id_length_bits=0, length_field_bits=0)

    with pytest.raises(ValidationError) as exc_info:
        ContainerPDU(name="ctr_headerless_empty", pdu_id=21, length=4, header=header, contained_pdus=[])
    assert_single_error(exc_info, "FLYNC-SIG-MIN-CONS-111", "one contained PDU")


def test_negative_container_pdu_headerless_multiple_contained_pdus():
    """Header-less with more than one contained PDU must be rejected."""
    header = ContainerPDUHeader(id_length_bits=0, length_field_bits=0)
    contained_pdus = [ContainedPDURef(header_id=1, pdu_ref="inner_a"), ContainedPDURef(header_id=2, pdu_ref="inner_b")]

    with pytest.raises(ValidationError) as exc_info:
        ContainerPDU(name="ctr_headerless_multi", pdu_id=22, length=4, header=header, contained_pdus=contained_pdus)
    assert_single_error(exc_info, "FLYNC-SIG-MIN-CONS-111", "one contained PDU")


def test_negative_container_pdu_only_id_length_zero():
    """id_length_bits=0 with non-zero length_field_bits must be rejected."""
    header = ContainerPDUHeader(id_length_bits=0, length_field_bits=8)

    with pytest.raises(ValidationError) as exc_info:
        ContainerPDU(name="ctr_id_zero_only", pdu_id=23, length=4, header=header)
    assert_single_error(exc_info, "FLYNC-SIG-MIN-CONS-112", "Both or None")


def test_negative_container_pdu_only_length_field_zero():
    """length_field_bits=0 with non-zero id_length_bits must be rejected."""
    header = ContainerPDUHeader(id_length_bits=16, length_field_bits=0)

    with pytest.raises(ValidationError) as exc_info:
        ContainerPDU(name="ctr_len_zero_only", pdu_id=24, length=4, header=header)
    assert_single_error(exc_info, "FLYNC-SIG-MIN-CONS-112", "Both or None")
