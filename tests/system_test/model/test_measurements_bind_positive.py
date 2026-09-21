"""
Positive system tests: the bundled flync_example workspace's own measurement overlay
(examples/flync_example/measurements/measurement_points.flync.yaml), already loaded and bound as
part of the `flync_model` fixture.
"""


def _interfaces_by_id(flync_model):
    return {iface.interface_id: iface for iface in flync_model.measurements.measurement_points}


def test_flync_example_measurements_are_loaded_and_bound(flync_model):
    """Bus-level measurement points (CAN, CAN FD, LIN) - each resolving its `observes` entry to the
    real FLYNC bus it names."""
    assert flync_model.measurements is not None

    interfaces = _interfaces_by_id(flync_model)

    assert [e.name for e in interfaces[0x00020001].observed] == ["BodyCAN"]
    assert interfaces[0x00020001].payload_types == ["can"]
    assert interfaces[0x00020001].name == "body_can_tap"

    assert [e.name for e in interfaces[0x00020002].observed] == ["DiagCAN"]
    assert interfaces[0x00020002].payload_types == ["can", "can_fd"]
    assert interfaces[0x00020002].name == "diagnostics_can_fd_tap"

    assert [e.name for e in interfaces[0x00020003].observed] == ["BodyLIN"]
    assert interfaces[0x00020003].payload_types == ["lin"]
    assert interfaces[0x00020003].name == "body_lin_tap"


def test_flync_example_measurements_cover_ethernet_and_vlan(flync_model):
    """Ethernet-level measurement points: a physical interface and a VLAN sub-interface, both on
    the zonal gateway."""
    interfaces = _interfaces_by_id(flync_model)

    assert [e.name for e in interfaces[0x00010001].observed] == ["zgw_c1_iface1"]
    assert interfaces[0x00010001].payload_types == ["ethernet"]
    assert interfaces[0x00010001].name == "gateway_backbone_tap"

    assert [e.name for e in interfaces[0x00010003].observed] == ["zgw_c1_i1_viface1"]
    assert interfaces[0x00010003].payload_types == ["ethernet"]
    assert interfaces[0x00010003].name == "gateway_vlan40_tap"
