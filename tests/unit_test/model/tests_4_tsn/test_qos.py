import pytest
from pydantic import ValidationError

from flync.model.flync_4_ecu.switch import Switch, SwitchPort
from flync.model.flync_4_tsn.qos import (
    ATSInstance,
    ATSShaper,
    CBSShaper,
    DoubleRateThreeColorMarker,
    SingleRateThreeColorMarker,
    SingleRateTwoColorMarker,
    Stream,
    TrafficClass,
    HTBInstance,
)
from flync.core.datatypes import ValueRange


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
    traffic_class_example = {
        "name": "Low_Priority_Traffic",
        "priority": 10,
        "internal_priority_values": [0, 1],
        "selection_mechanisms": CBSShaper_entry,
    }
    with pytest.raises(ValidationError) as e:
        switch_port = SwitchPort.model_validate(
            {
                "name": "Ingress_port_A",
                "silicon_port_no": 1,
                "default_vlan_id": 35,
                "traffic_classes": [traffic_class_example],
            }
        )


def test_negative_cbs_shaper_idle_slope():
    cbs_shaper_example = {
        "type": "cbs",
        "idleslope": 2000000000,
        "hilimit": 400000,
        "lolimit": -100000,
    }
    with pytest.raises(ValidationError) as e:
        traffic_class_example = TrafficClass.model_validate(
            {
                "name": "Low_Priority_Traffic",
                "priority": 1,
                "internal_priority_values": [0, 1],
                "selection_mechanisms": cbs_shaper_example,
            }
        )


def test_negative_cbs_shaper_hi_limit():
    cbs_shaper_example = {
        "type": "cbs",
        "idleslope": 200000,
        "hilimit": 4000000000,
        "lolimit": -100000,
    }
    with pytest.raises(ValidationError) as e:
        traffic_class_example = TrafficClass.model_validate(
            {
                "name": "Low_Priority_Traffic",
                "priority": 1,
                "internal_priority_values": [0, 1],
                "selection_mechanisms": cbs_shaper_example,
            }
        )


def test_negative_cbs_shaper_lo_limit():
    cbs_shaper_example = {
        "type": "cbs",
        "idleslope": 200000,
        "hilimit": 400000,
        "lolimit": 100000,
    }
    with pytest.raises(ValidationError) as e:
        traffic_class_example = TrafficClass.model_validate(
            {
                "name": "Low_Priority_Traffic",
                "priority": 1,
                "internal_priority_values": [0, 1],
                "selection_mechanisms": cbs_shaper_example,
            }
        )


def test_negative_max_sdu_size():
    cbs_shaper_example = {
        "type": "cbs",
        "idleslope": 200000,
        "hilimit": 400000,
        "lolimit": 100000,
    }
    with pytest.raises(ValidationError) as e:
        traffic_class_example = TrafficClass.model_validate(
            {
                "name": "Low_Priority_Traffic",
                "priority": 1,
                "internal_priority_values": [0, 1],
                "selection_mechanisms": cbs_shaper_example,
            }
        )


def test_negative_cbs_shaper_lo_limit():
    cbs_shaper_example = {
        "type": "cbs",
        "idleslope": 200000,
        "hilimit": 400000,
        "lolimit": 100000,
    }
    with pytest.raises(ValidationError) as e:
        traffic_class_example = TrafficClass.model_validate(
            {
                "name": "Low_Priority_Traffic",
                "priority": 1,
                "internal_priority_values": [0, 1],
                "selection_mechanisms": cbs_shaper_example,
            }
        )


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


def test_negative_cbs_shaper_idleslope_greater_than_link_speed(
    metadata_entry, vlan_entry, MII_entry
):
    cbs_shaper_example = {
        "type": "cbs",
        "idleslope": 2000000,
    }
    traffic_class_example = {
        "name": "Low_Priority_Traffic",
        "priority": 1,
        "internal_priority_values": [0, 1],
        "selection_mechanisms": cbs_shaper_example,
    }

    with pytest.raises(ValidationError) as e:
        SwitchPort(
            name="Ingress_port_A",
            silicon_port_no=1,
            default_vlan_id=35,
            mii_config=MII_entry,
            traffic_classes=[traffic_class_example],
        )


def test_positive_hilimit_lolimit_differenece_greater_than_max_frame_size(
    embedded_metadata_entry, vlan_entry, MII_entry
):
    cbs_shaper_example = {
        "type": "cbs",
        "idleslope": 10000,
    }
    traffic_class_example = {
        "name": "Low_Priority_Traffic",
        "priority": 1,
        "frame_priority_values": [0, 1],
        "selection_mechanisms": cbs_shaper_example,
    }
    ports = SwitchPort(
        name="Ingress_port_A",
        silicon_port_no=1,
        default_vlan_id=35,
        mii_config=MII_entry,
        traffic_classes=[traffic_class_example],
    )
    switch_example = Switch.model_validate(
        {
            "meta": embedded_metadata_entry,
            "name": "switch1",
            "ports": [ports],
            "vlans": [vlan_entry],
        }
    )


def test_negative_hilimit_ceil(vlan_entry, MII_entry):
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
    with pytest.raises(ValidationError) as e:
        switch_example = Switch.model_validate(
            {"name": "switch1", "ports": [ports], "vlans": [vlan_entry]}
        )


def test_negative_lolimit_ceil(vlan_entry, MII_entry):
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
    with pytest.raises(ValidationError) as e:
        switch_example = Switch.model_validate(
            {"name": "switch1", "ports": [ports], "vlans": [vlan_entry]}
        )


def test_negative_traffic_class_containing_ipv_should_be_defined_on_atleast_one_ingress_stream(
    vlan_entry, MII_entry
):
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
    with pytest.raises(ValidationError) as e:
        switch_example = Switch.model_validate(
            {"name": "switch1", "ports": [ports], "vlans": [vlan_entry]}
        )


def test_negative_ats_instance_for_traffic_class(vlan_entry, MII_entry):
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
    with pytest.raises(ValidationError) as e:
        switch_example = Switch.model_validate(
            {"name": "switch1", "ports": [ports], "vlans": [vlan_entry]}
        )


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
            "meta": embedded_metadata_entry,
            "name": "switch1",
            "ports": [ports],
            "vlans": [vlan_entry],
        }
    )


def test_negative_frame_filter_has_atleast_one_field(
    ATSInstance_entry, vlan_entry, MII_entry
):
    stream_example = {
        "name": "Stream1",
        "stream_identification": [{"vlanid": None}],
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
        traffic_classes=[],
        ingress_streams=[stream_example],
    )
    with pytest.raises(ValidationError) as e:
        switch_example = Switch.model_validate(
            {"name": "switch1", "ports": [ports], "vlans": [vlan_entry]}
        )


def test_negative_protocol_for_source_port_frame_filter(
    ATSInstance_entry, vlan_entry, MII_entry
):

    stream_example = {
        "name": "Stream1",
        "stream_identification": [{"src_port": -20}],
        "drop_at_ingress": False,
        "max_sdu_size": 1400,
        "ipv": 5,
        "ats": ATSInstance_entry,
        "policer": None,
    }
    with pytest.raises(ValidationError) as e:
        ports = SwitchPort.model_validate(
            {
                "name": "Ingress_port_A",
                "silicon_port_no": 1,
                "default_vlan_id": 35,
                "mii_config": MII_entry,
                "traffic_classes": [],
                "ingress_streams": [stream_example],
            }
        )


def test_negative_protocol_for_destination_port_frame_filter(
    ATSInstance_entry, vlan_entry, MII_entry
):

    stream_example = {
        "name": "Stream1",
        "stream_identification": [{"dst_port": -100}],
        "drop_at_ingress": False,
        "max_sdu_size": 1400,
        "ipv": 5,
        "ats": ATSInstance_entry,
        "policer": None,
    }
    with pytest.raises(ValidationError) as e:
        ports = SwitchPort.model_validate(
            {
                "name": "Ingress_port_A",
                "silicon_port_no": 1,
                "default_vlan_id": 35,
                "mii_config": MII_entry,
                "traffic_classes": [],
                "ingress_streams": [stream_example],
            }
        )


def test_negative_pcp_for_frame_filter(
    ATSInstance_entry, vlan_entry, MII_entry
):

    stream_example = {
        "name": "Stream1",
        "stream_identification": [{"pcp": 10}],
        "drop_at_ingress": False,
        "max_sdu_size": 1400,
        "ipv": 5,
        "ats": ATSInstance_entry,
        "policer": None,
    }
    with pytest.raises(ValidationError) as e:
        ports = SwitchPort.model_validate(
            {
                "name": "Ingress_port_A",
                "silicon_port_no": 1,
                "default_vlan_id": 35,
                "mii_config": MII_entry,
                "traffic_classes": [],
                "ingress_streams": [stream_example],
            }
        )


def test_negative_pcp_list_for_frame_filter(
    ATSInstance_entry, vlan_entry, MII_entry
):

    stream_example = {
        "name": "Stream1",
        "stream_identification": [{"pcp": [1, 8]}],
        "drop_at_ingress": False,
        "max_sdu_size": 1400,
        "ipv": 5,
        "ats": ATSInstance_entry,
        "policer": None,
    }
    with pytest.raises(ValidationError) as e:
        ports = SwitchPort.model_validate(
            {
                "name": "Ingress_port_A",
                "silicon_port_no": 1,
                "default_vlan_id": 35,
                "mii_config": MII_entry,
                "traffic_classes": [],
                "ingress_streams": [stream_example],
            }
        )


def test_negative_vlanid_int_for_frame_filter(
    ATSInstance_entry, vlan_entry, MII_entry
):

    stream_example = {
        "name": "Stream1",
        "stream_identification": [{"vlanid": 4096}],
        "drop_at_ingress": False,
        "max_sdu_size": 1400,
        "ipv": 5,
        "ats": ATSInstance_entry,
        "policer": None,
    }
    with pytest.raises(ValidationError) as e:
        ports = SwitchPort.model_validate(
            {
                "name": "Ingress_port_A",
                "silicon_port_no": 1,
                "default_vlan_id": 35,
                "mii_config": MII_entry,
                "traffic_classes": [],
                "ingress_streams": [stream_example],
            }
        )


def test_negative_vlanid_valuerange_for_frame_filter(
    ATSInstance_entry, vlan_entry, MII_entry
):

    stream_example = {
        "name": "Stream1",
        "stream_identification": [
            {"vlanid": ValueRange(from_value=4095, to_value=4097)}
        ],
        "drop_at_ingress": False,
        "max_sdu_size": 1400,
        "ipv": 5,
        "ats": ATSInstance_entry,
        "policer": None,
    }
    with pytest.raises(ValidationError) as e:
        ports = SwitchPort.model_validate(
            {
                "name": "Ingress_port_A",
                "silicon_port_no": 1,
                "default_vlan_id": 35,
                "mii_config": MII_entry,
                "traffic_classes": [],
                "ingress_streams": [stream_example],
            }
        )


def test_negative_vlanid_list_of_vlanid_or_int_for_frame_filter(
    ATSInstance_entry, vlan_entry, MII_entry
):

    stream_example = {
        "name": "Stream1",
        "stream_identification": [
            {"vlanid": [1, ValueRange(from_value=4095, to_value=4097)]}
        ],
        "drop_at_ingress": False,
        "max_sdu_size": 1400,
        "ipv": 5,
        "ats": ATSInstance_entry,
        "policer": None,
    }
    with pytest.raises(ValidationError) as e:
        ports = SwitchPort.model_validate(
            {
                "name": "Ingress_port_A",
                "silicon_port_no": 1,
                "default_vlan_id": 35,
                "mii_config": MII_entry,
                "traffic_classes": [],
                "ingress_streams": [stream_example],
            }
        )


def test_negative_pcp_for_frame_filter(
    ATSInstance_entry, vlan_entry, MII_entry
):

    stream_example = {
        "name": "Stream1",
        "stream_identification": [{"pcp": 10}],
        "drop_at_ingress": False,
        "max_sdu_size": 1400,
        "ipv": 5,
        "ats": ATSInstance_entry,
        "policer": None,
    }
    with pytest.raises(ValidationError) as e:
        ports = SwitchPort.model_validate(
            {
                "name": "Ingress_port_A",
                "silicon_port_no": 1,
                "default_vlan_id": 35,
                "mii_config": MII_entry,
                "traffic_classes": [],
                "ingress_streams": [stream_example],
            }
        )


def test_negative_pcp_list_for_frame_filter(
    ATSInstance_entry, vlan_entry, MII_entry
):

    stream_example = {
        "name": "Stream1",
        "stream_identification": [{"pcp": [1, 8]}],
        "drop_at_ingress": False,
        "max_sdu_size": 1400,
        "ipv": 5,
        "ats": ATSInstance_entry,
        "policer": None,
    }
    with pytest.raises(ValidationError) as e:
        ports = SwitchPort.model_validate(
            {
                "name": "Ingress_port_A",
                "silicon_port_no": 1,
                "default_vlan_id": 35,
                "mii_config": MII_entry,
                "traffic_classes": [],
                "ingress_streams": [stream_example],
            }
        )


def test_negative_vlanid_int_for_frame_filter(
    ATSInstance_entry, vlan_entry, MII_entry
):

    stream_example = {
        "name": "Stream1",
        "stream_identification": [{"vlanid": 4096}],
        "drop_at_ingress": False,
        "max_sdu_size": 1400,
        "ipv": 5,
        "ats": ATSInstance_entry,
        "policer": None,
    }
    with pytest.raises(ValidationError) as e:
        ports = SwitchPort.model_validate(
            {
                "name": "Ingress_port_A",
                "silicon_port_no": 1,
                "default_vlan_id": 35,
                "mii_config": MII_entry,
                "traffic_classes": [],
                "ingress_streams": [stream_example],
            }
        )


def test_negative_vlanid_valuerange_for_frame_filter(
    ATSInstance_entry, vlan_entry, MII_entry
):

    stream_example = {
        "name": "Stream1",
        "stream_identification": [
            {"vlanid": ValueRange(from_value=4095, to_value=4097)}
        ],
        "drop_at_ingress": False,
        "max_sdu_size": 1400,
        "ipv": 5,
        "ats": ATSInstance_entry,
        "policer": None,
    }
    with pytest.raises(ValidationError) as e:
        ports = SwitchPort.model_validate(
            {
                "name": "Ingress_port_A",
                "silicon_port_no": 1,
                "default_vlan_id": 35,
                "mii_config": MII_entry,
                "traffic_classes": [],
                "ingress_streams": [stream_example],
            }
        )


def test_negative_vlanid_list_of_vlanid_or_int_for_frame_filter(
    ATSInstance_entry, vlan_entry, MII_entry
):

    stream_example = {
        "name": "Stream1",
        "stream_identification": [
            {"vlanid": [1, ValueRange(from_value=4095, to_value=4097)]}
        ],
        "drop_at_ingress": False,
        "max_sdu_size": 1400,
        "ipv": 5,
        "ats": ATSInstance_entry,
        "policer": None,
    }
    with pytest.raises(ValidationError) as e:
        ports = SwitchPort.model_validate(
            {
                "name": "Ingress_port_A",
                "silicon_port_no": 1,
                "default_vlan_id": 35,
                "mii_config": MII_entry,
                "traffic_classes": [],
                "ingress_streams": [stream_example],
            }
        )


def test_positive_cbs_should_be_greater_than_max_frame_size(
    embedded_metadata_entry, SingleRateTwoColorMarker_entry, vlan_entry
):

    stream_example = {
        "name": "Stream1",
        "stream_identification": [],
        "drop_at_ingress": False,
        "max_sdu_size": 900,
        "policer": SingleRateTwoColorMarker_entry,
        "ipv": 5,
        "ats": None,
    }
    ports = SwitchPort(
        name="Ingress_port_A",
        silicon_port_no=1,
        default_vlan_id=35,
        ingress_streams=[stream_example],
    )
    switch_example = Switch.model_validate(
        {
            "meta": embedded_metadata_entry,
            "name": "switch1",
            "ports": [ports],
            "vlans": [vlan_entry],
        }
    )


def test_positive_ebs_should_be_greater_than_max_frame_size(
    embedded_metadata_entry, DoubleRateThreeColorMarker_entry, vlan_entry
):

    stream_example = {
        "name": "Stream1",
        "stream_identification": [],
        "drop_at_ingress": False,
        "max_sdu_size": 900,
        "policer": DoubleRateThreeColorMarker_entry,
        "ipv": 5,
        "ats": None,
    }
    ports = SwitchPort(
        name="Ingress_port_A",
        silicon_port_no=1,
        default_vlan_id=35,
        ingress_streams=[stream_example],
    )
    switch_example = Switch.model_validate(
        {
            "meta": embedded_metadata_entry,
            "name": "switch1",
            "ports": [ports],
            "vlans": [vlan_entry],
        }
    )


def test_negative_ebs_greater_than_cbs(vlan_entry):

    DoubleRateThreeColorMarker_entry = DoubleRateThreeColorMarker(
        type="double_rate_three_color",
        cir=2000,
        cbs=2000,
        ebs=1000,
        eir=1000,
        coupling=False,
    )
    stream_example = {
        "name": "Stream1",
        "stream_identification": [],
        "drop_at_ingress": False,
        "max_sdu_size": 900,
        "policer": DoubleRateThreeColorMarker_entry,
        "ipv": 5,
        "ats": None,
    }
    ports = SwitchPort(
        name="Ingress_port_A",
        silicon_port_no=1,
        default_vlan_id=35,
        ingress_streams=[stream_example],
    )
    with pytest.raises(ValidationError) as e:
        switch_example = Switch.model_validate(
            {"name": "switch1", "ports": [ports], "vlans": [vlan_entry]}
        )


def test_htb():
    htb_instance = {
        "root_id": "1:",
        "default_class": 13,
        "child_classes": [
            {
                "classid": 11,
                "rate": 5,
                "ceil": 10,
                "filter": [{"src_ipv4": "19.2.2.2", "prio": 0}],
                "child_classes": [
                    {"classid": 13, "rate": 2, "ceil": 5},
                    {"classid": 2, "rate": 2, "ceil": 5},
                ],
            },
            {
                "classid": 12,
                "rate": 5,
                "ceil": 10,
                "filter": [{"src_ipv4": "19.2.2.1", "prio": 1}],
                # No child classes for this entry – keep an empty list
                "child_classes": [],
            },
        ],
    }

    assert HTBInstance.model_validate(htb_instance)
