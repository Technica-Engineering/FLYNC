import pytest
from pydantic import ValidationError

from flync.core.datatypes import Ethertype, ValueRange
from flync.model.flync_4_ecu.switch import Switch, SwitchPort
from flync.model.flync_4_tsn.qos import (
    ATSInstance,
    ATSShaper,
    CBSShaper,
    DoubleRateThreeColorMarker,
    FrameFilter,
    HTBInstance,
    SingleRateThreeColorMarker,
    SingleRateTwoColorMarker,
    Stream,
    TrafficClass,
)
from tests.error_assertions import assert_single_error


def test_positive_traffic_class_definition_cbs_shaper(
    CBSShaper_entry: CBSShaper,
):
    traffic_class_example = {
        "name": "Low_Priority_Traffic",
        "priority": 1,
        "internal_priority_values": [0, 1],
        "selection_mechanisms": CBSShaper_entry,
    }
    switch_port = SwitchPort(
        name="Ingress_port_A",
        silicon_port_no=1,
        default_vlan_id=35,
        traffic_classes=[traffic_class_example],
    )
    assert isinstance(switch_port.traffic_classes[0], TrafficClass)


def test_positive_traffic_class_definition_ATSShaper(
    ATSShaper_entry: ATSShaper,
):
    traffic_class_example = {
        "name": "Low_Priority_Traffic",
        "priority": 1,
        "internal_priority_values": [0, 1],
        "selection_mechanisms": ATSShaper_entry,
    }
    switch_port = SwitchPort(
        name="Ingress_port_A",
        silicon_port_no=1,
        default_vlan_id=35,
        traffic_classes=[traffic_class_example],
    )
    assert isinstance(switch_port.traffic_classes[0], TrafficClass)


def test_negative_traffic_class_priority(CBSShaper_entry: CBSShaper):
    with pytest.raises(ValidationError) as exc_info:
        TrafficClass.model_validate(
            {
                "name": "Low_Priority_Traffic",
                "priority": 10,
                "internal_priority_values": [0, 1],
                "selection_mechanisms": CBSShaper_entry,
            }
        )
    assert_single_error(exc_info, None, "less than or equal to 7")


def test_negative_cbs_shaper_idle_slope():
    with pytest.raises(ValidationError) as exc_info:
        TrafficClass.model_validate(
            {
                "name": "Low_Priority_Traffic",
                "priority": 1,
                "internal_priority_values": [0, 1],
                "selection_mechanisms": {"type": "cbs", "idleslope": 2000000000},
            }
        )
    assert_single_error(exc_info, None, "less than or equal to 1000000")


def test_positive_SingleRateTwoColorMarker(
    SingleRateTwoColorMarker_entry: SingleRateTwoColorMarker,
    ATSInstance_entry: ATSInstance,
):
    stream_example = {
        "name": "Stream1",
        "stream_identification": [],
        "drop_at_ingress": False,
        "max_sdu_size": 1400,
        "policer": SingleRateTwoColorMarker_entry,
        "ipv": 5,
        "ats": ATSInstance_entry,
    }
    switch_port = SwitchPort(
        name="Ingress_port_A",
        silicon_port_no=1,
        default_vlan_id=35,
        ingress_streams=[stream_example],
    )
    assert isinstance(switch_port.ingress_streams[0], Stream)


def test_positive_SingleRateThreeColorMarker(
    SingleRateThreeColorMarker_entry: SingleRateThreeColorMarker,
    ATSInstance_entry: ATSInstance,
):
    stream_example = {
        "name": "Stream1",
        "stream_identification": [],
        "drop_at_ingress": False,
        "max_sdu_size": 1400,
        "policer": SingleRateThreeColorMarker_entry,
        "ipv": 5,
        "ats": ATSInstance_entry,
    }
    switch_port = SwitchPort(
        name="Ingress_port_A",
        silicon_port_no=1,
        default_vlan_id=35,
        ingress_streams=[stream_example],
    )
    assert isinstance(switch_port.ingress_streams[0], Stream)


def test_positive_DoubleRateThreeColorMarker(
    DoubleRateThreeColorMarker_entry: DoubleRateThreeColorMarker,
    ATSInstance_entry: ATSInstance,
):
    stream_example = {
        "name": "Stream1",
        "stream_identification": [],
        "drop_at_ingress": False,
        "max_sdu_size": 1400,
        "policer": DoubleRateThreeColorMarker_entry,
        "ipv": 5,
        "ats": ATSInstance_entry,
    }
    switch_port = SwitchPort(
        name="Ingress_port_A",
        silicon_port_no=1,
        default_vlan_id=35,
        ingress_streams=[stream_example],
    )
    assert isinstance(switch_port.ingress_streams[0], Stream)


def test_negative_cbs_shaper_idleslope_greater_than_link_speed(metadata_entry, vlan_entry, MII_entry):
    cbs_shaper_example = {
        "type": "cbs",
        "idleslope": 200000,
    }
    traffic_class_example = {
        "name": "Low_Priority_Traffic",
        "priority": 1,
        "internal_priority_values": [0, 1],
        "selection_mechanisms": cbs_shaper_example,
    }

    with pytest.raises(ValidationError) as exc_info:
        SwitchPort(
            name="Ingress_port_A",
            silicon_port_no=1,
            default_vlan_id=35,
            mii_config=MII_entry,
            traffic_classes=[traffic_class_example],
        )
    assert_single_error(exc_info, "FLYNC-CMN-MAJ-CONS-011", "cannot be higher than the link speed")


def test_negative_traffic_class_containing_ipv_should_be_defined_on_atleast_one_ingress_stream(embedded_metadata_entry, vlan_entry, MII_entry):
    cbs_shaper_example = {
        "type": "cbs",
        "idleslope": 100000,
    }
    traffic_class_example = {
        "name": "Low_Priority_Traffic",
        "priority": 1,
        "internal_priority_values": [0, 1],
        "selection_mechanisms": cbs_shaper_example,
    }
    ports = SwitchPort(
        name="Ingress_port_A",
        silicon_port_no=1,
        default_vlan_id=35,
        mii_config=MII_entry,
        traffic_classes=[traffic_class_example],
    )
    with pytest.raises(ValidationError) as exc_info:
        Switch.model_validate(
            {
                "name": "switch1",
                "switch_config": {
                    "meta": embedded_metadata_entry,
                    "ports": [ports],
                    "vlans": [vlan_entry],
                },
            }
        )
    assert_single_error(exc_info, "FLYNC-ECU-MIN-REF-090", "Not able to find any streams")


def test_negative_ats_instance_for_traffic_class(embedded_metadata_entry, vlan_entry, MII_entry):
    ats_shaper_example = {"type": "ats"}
    traffic_class_example = {
        "name": "Low_Priority_Traffic",
        "priority": 1,
        "frame_priority_values": [0, 1],
        "selection_mechanisms": ats_shaper_example,
    }
    ports = SwitchPort(
        name="Ingress_port_A",
        silicon_port_no=1,
        default_vlan_id=35,
        mii_config=MII_entry,
        traffic_classes=[traffic_class_example],
    )
    with pytest.raises(ValidationError) as exc_info:
        Switch.model_validate(
            {
                "name": "switch1",
                "switch_config": {
                    "meta": embedded_metadata_entry,
                    "ports": [ports],
                    "vlans": [vlan_entry],
                },
            }
        )
    assert_single_error(exc_info, "FLYNC-ECU-MIN-REF-091", "No ATS Instance found")


def test_positive_ats_instance_for_traffic_class(
    embedded_metadata_entry,
    vlan_entry,
    MII_entry,
    ATSInstance_entry: ATSInstance,
):
    ats_shaper_example = {"type": "ats"}
    traffic_class_example = {
        "name": "Low_Priority_Traffic",
        "priority": 1,
        "frame_priority_values": [0, 1],
        "selection_mechanisms": ats_shaper_example,
    }
    stream_example = {
        "name": "Stream1",
        "stream_identification": [],
        "drop_at_ingress": False,
        "max_sdu_size": 1400,
        "ipv": 5,
        "ats": ATSInstance_entry,
        "policer": None,
    }
    ports = SwitchPort(
        name="Ingress_port_A",
        silicon_port_no=1,
        default_vlan_id=35,
        mii_config=MII_entry,
        traffic_classes=[traffic_class_example],
        ingress_streams=[stream_example],
    )
    switch_example = Switch.model_validate(
        {
            "name": "switch1",
            "switch_config": {
                "meta": embedded_metadata_entry,
                "ports": [ports],
                "vlans": [vlan_entry],
            },
        }
    )
    assert isinstance(switch_example.ports[0].traffic_classes[0], TrafficClass)


def test_negative_protocol_for_source_port_frame_filter():
    with pytest.raises(ValidationError) as exc_info:
        FrameFilter(src_port=-20)
    assert_single_error(exc_info, "FLYNC-TSN-MIN-VAL-152", "Protocol port must be greater than 0")


def test_negative_protocol_for_destination_port_frame_filter():
    with pytest.raises(ValidationError) as exc_info:
        FrameFilter(dst_port=-100)
    assert_single_error(exc_info, "FLYNC-TSN-MIN-VAL-152", "Protocol port must be greater than 0")


def test_negative_pcp_for_frame_filter():
    with pytest.raises(ValidationError) as exc_info:
        FrameFilter(pcp=10)
    assert_single_error(exc_info, "FLYNC-TSN-MIN-VAL-150", "pcp value must be greater than or equal to 0")


def test_negative_pcp_list_for_frame_filter():
    with pytest.raises(ValidationError) as exc_info:
        FrameFilter(pcp=[1, 8])
    assert_single_error(exc_info, "FLYNC-TSN-MIN-VAL-150", "pcp value must be greater than or equal to 0")


def test_negative_vlanid_int_for_frame_filter():
    with pytest.raises(ValidationError) as exc_info:
        FrameFilter(vlanid=4096)
    assert_single_error(exc_info, "FLYNC-CMN-MIN-VAL-002", "range 0-4094")


def test_negative_vlanid_valuerange_for_frame_filter():
    with pytest.raises(ValidationError) as exc_info:
        FrameFilter(vlanid=ValueRange(from_value=4095, to_value=4097))
    assert_single_error(exc_info, "FLYNC-CMN-MIN-VAL-002", "range 0-4094")


def test_negative_vlanid_list_of_vlanid_or_int_for_frame_filter():
    with pytest.raises(ValidationError) as exc_info:
        FrameFilter(vlanid=[1, ValueRange(from_value=4095, to_value=4097)])
    assert_single_error(exc_info, "FLYNC-CMN-MIN-VAL-002", "range 0-4094")


@pytest.mark.parametrize(
    "values_field,value",
    [
        pytest.param("internal_priority_values", 9, id="internal value too high"),
        pytest.param("internal_priority_values", -1, id="internal value too low"),
        pytest.param("frame_priority_values", 8, id="frame value too high"),
        pytest.param("frame_priority_values", -1, id="frame value too low"),
    ],
)
def test_negative_priority_values_out_of_range(values_field, value):
    with pytest.raises(ValidationError) as exc_info:
        TrafficClass.model_validate(
            {
                "name": "Low_Priority_Traffic",
                "priority": 1,
                values_field: [value],
            }
        )
    assert_single_error(exc_info, "FLYNC-TSN-MIN-VAL-153", "Priority value out of range")


def test_negative_no_priority_values_provided():
    with pytest.raises(ValidationError) as exc_info:
        TrafficClass.model_validate({"name": "Low_Priority_Traffic", "priority": 1})
    assert_single_error(
        exc_info,
        "FLYNC-TSN-MIN-REQ-154",
        "At least one of frame_priority_values or internal_priority_values must be provided",
    )


def test_positive_priority_values_boundary():
    traffic_class = TrafficClass(
        name="Low_Priority_Traffic",
        priority=1,
        internal_priority_values=[0, 7],
        frame_priority_values=[0, 7],
    )
    assert isinstance(traffic_class, TrafficClass)


def test_positive_single_priority_values_list():
    traffic_class = TrafficClass(
        name="Low_Priority_Traffic",
        priority=1,
        internal_priority_values=[2],
    )
    assert isinstance(traffic_class, TrafficClass)


def test_htb():
    htb_instance = {
        "root_id": "1:",
        "default_class": 13,
        "child_classes": [
            {
                "classid": 11,
                "rate": 5,
                "ceil": 10,
                "priority": 1,
                "filter": [{"src_ipv4": "19.2.2.2", "filter_priority": 0}],
                "child_classes": [
                    {"classid": 13, "rate": 2, "ceil": 5, "priority": 3},
                    {"classid": 2, "rate": 2, "ceil": 5, "priority": 4},
                ],
            },
            {
                "classid": 12,
                "rate": 5,
                "ceil": 10,
                "priority": 2,
                "filter": [{"src_ipv4": "19.2.2.1", "filter_priority": 1}],
                # No child classes for this entry – keep an empty list
                "child_classes": [],
            },
        ],
    }

    assert HTBInstance.model_validate(htb_instance)


class Test_FrameFilter_Ethertype:

    @pytest.mark.parametrize(
        "ethertype",
        [
            pytest.param(Ethertype.AVTP, id="enum value"),
            pytest.param(0x22F0, id="numeric value"),
            pytest.param("AVTP", id="string_name"),
            pytest.param("0x22F0", id="hex_string"),
        ],
    )
    def test_positive_framefilter_ethertype(self, ethertype):
        """Test FrameFilter accepts Ethertypes enum value directly."""
        frame_filter = FrameFilter(ethertype=ethertype)
        assert frame_filter.ethertype == Ethertype.AVTP

    @pytest.mark.parametrize(
        "ethertype",
        [
            pytest.param(0x000, id="Zero"),
            pytest.param(0x1111, id="Invalid hex"),
            pytest.param("XYZINVALID", id="wrong string name"),
            pytest.param("0x1111", id="invlid hex string"),
        ],
    )
    def test_negative_framefilter_ethertype(self, ethertype):
        """Test FrameFilter rejects invalid Ethertype values."""
        with pytest.raises(ValidationError) as exc_info:
            FrameFilter(ethertype=ethertype)
        assert_single_error(exc_info, None, "Invalid ethertype value")

    @pytest.mark.parametrize(
        "ethertype,assert_type",
        [
            pytest.param([Ethertype.AVTP, Ethertype.PTP], [Ethertype.AVTP, Ethertype.PTP], id="enum list"),
            pytest.param([Ethertype.AVTP, "PTP", 0x0806], [Ethertype.AVTP, Ethertype.PTP, Ethertype.ARP], id="mixed list"),
        ],
    )
    def test_positive_framefilter_ethertype_list(self, ethertype, assert_type):
        """Test FrameFilter accepts list of Ethertypes enum values."""
        frame_filter = FrameFilter(ethertype=ethertype)

        assert len(frame_filter.ethertype) == len(assert_type)
        for i in range(len(assert_type)):
            assert frame_filter.ethertype[i] == assert_type[i]

    @pytest.mark.parametrize(
        "ethertype, assert_serialized",
        [
            pytest.param(Ethertype.AVTP, "0x22F0", id="enum value"),
            pytest.param(0x88CC, "0x88CC", id="numeric value"),
            pytest.param("LLDP", "0x88CC", id="string_name"),
            pytest.param("0x22F0", "0x22F0", id="hex_string"),
            pytest.param([Ethertype.AVTP, Ethertype.PTP, Ethertype.ARP], ["0x22F0", "0x88F7", "0x0806"], id="list enums"),
        ],
    )
    def test_positive_framefilter_ethertype_serialization(self, ethertype, assert_serialized):
        """Test FrameFilter serializes single Ethertypes enum value to its name."""
        frame_filter = FrameFilter(ethertype=ethertype)
        serialized = frame_filter.model_dump()
        assert serialized["ethertype"] == assert_serialized

    def test_positive_framefilter_ethertype_optional_none(self):
        """Test FrameFilter allows ethertype to be None (optional)."""
        frame_filter = FrameFilter(ethertype=None)
        assert frame_filter.ethertype is None

    def test_positive_framefilter_ethertype_not_specified(self):
        """Test FrameFilter defaults ethertype to None when not specified."""
        frame_filter = FrameFilter()
        assert frame_filter.ethertype is None
