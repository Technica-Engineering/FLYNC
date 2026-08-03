"""Workspace-level tests for state management in flync_example (the NM showcase)."""

from typing import get_origin

from flync.core.utils.state_management_validators import (
    collect_effective_members,
)
from flync.model import FLYNCModel
from flync.model.flync_4_nm import StateMembershipRef
from flync.sdk.helpers.generation_helpers import dump_flync_workspace
from flync.sdk.utils.model_dependencies import get_model_dependency_graph
from flync.sdk.workspace.flync_workspace import FLYNCWorkspace


def _membership_view(model):
    """Flatten the derived member sets into comparable tuples."""

    return sorted(
        (
            (member.group, member.entity_kind, member.entity_path, member.role, member.relevance_bit)
            for members in collect_effective_members(model).values()
            for member in members
        ),
        key=lambda t: tuple("" if x is None else x for x in t),
    )


def test_state_management_example_loads(loaded_workspace_without_object_map):
    model = loaded_workspace_without_object_map.flync_model
    config = model.communication.state_management
    assert [group.name for group in config.groups] == ["VEHICLE"]
    vehicle = config.groups[0]
    assert vehicle.nm_pdu == "PDU_NmMessage"
    assert vehicle.timing_profile == "standard"
    assert vehicle.extensions == {"parameter_a": "value_a", "parameter_b": "value_b"}
    profiles = {profile.name: profile for profile in config.timing_profiles}
    assert profiles["standard"].cycle_time_ms == 500

    # Relevance bits are vehicle FUNCTIONS, not node names; the LIN bus
    # participates as one bit with no NM frame (master-as-proxy).
    assert _membership_view(model) == [
        ("VEHICLE", "bus", "BodyLIN", "participant", "Comfort"),
        ("VEHICLE", "controller", "high_performance_compute/hpc_controller2", "participant", "AutonomousDriving"),
        ("VEHICLE", "controller", "high_performance_compute/hpc_controller2", "participant", "OnlineCommunication"),
        ("VEHICLE", "controller", "zonal_platform2/z2_controller2", "observer", None),
        ("VEHICLE", "ecu", "can_node_1", "participant", "Comfort"),
        ("VEHICLE", "ecu", "can_node_2", "participant", "Comfort"),
        ("VEHICLE", "ecu", "zonal_gateway", "participant", "Comfort"),
    ]

    warnings = [
        error
        for error in loaded_workspace_without_object_map.load_errors
        if "experimental" not in error["msg"]
        and "is not connected in the internal topology" not in error["msg"]
        and "is not connected in the system topology" not in error["msg"]
    ]
    assert warnings == []


def test_state_management_multi_function_membership(loaded_workspace_without_object_map):
    # The central compute controller owns two function bits in one group.
    members = collect_effective_members(loaded_workspace_without_object_map.flync_model)["VEHICLE"]
    hpc_bits = {m.relevance_bit for m in members if m.entity_path == "high_performance_compute/hpc_controller2"}
    assert hpc_bits == {"AutonomousDriving", "OnlineCommunication"}
    # Comfort is a shared function bit across several members.
    comfort = {m.entity_path for m in members if m.role == "participant" and m.relevance_bit == "Comfort"}
    assert comfort == {"zonal_gateway", "can_node_1", "can_node_2", "BodyLIN"}


def test_state_management_pdu_bits_match_derived_members(loaded_workspace_without_object_map):
    model = loaded_workspace_without_object_map.flync_model
    members = collect_effective_members(model)
    pdus = {p.name: p for p in model.communication.channels.pdus}
    for group in model.communication.state_management.groups:
        pdu = pdus[group.nm_pdu]
        vector = next(s.signal for s in pdu.signals if s.signal.name == "relevance_vector")
        flag_labels = {flag.label for flag in vector.value_encoding.flags}
        assert flag_labels == {m.relevance_bit for m in members[group.name] if m.role == "participant"}
        assert any(s.signal.name == "control_vector" for s in pdu.signals)


def test_state_management_workspace_roundtrip(loaded_workspace_without_object_map, tmp_path):
    model = loaded_workspace_without_object_map.flync_model
    output_path = tmp_path / "roundtrip"
    dump_flync_workspace(model, output_path, workspace_name="roundtrip")

    reloaded = FLYNCWorkspace.load_workspace("roundtrip", output_path).flync_model
    assert _membership_view(reloaded) == _membership_view(model)

    original_groups = [group.model_dump() for group in model.communication.state_management.groups]
    reloaded_groups = [group.model_dump() for group in reloaded.communication.state_management.groups]
    assert reloaded_groups == original_groups

    original_profiles = [profile.model_dump() for profile in model.communication.state_management.timing_profiles]
    reloaded_profiles = [profile.model_dump() for profile in reloaded.communication.state_management.timing_profiles]
    assert reloaded_profiles == original_profiles

    # The LIN bus participates with no NM frame on it (master-as-proxy).
    body_lin = next(bus for bus in reloaded.communication.channels.lin_buses if bus.name == "BodyLIN")
    assert [(ref.group, ref.relevance_bits) for ref in body_lin.state_memberships] == [("VEHICLE", ["Comfort"])]

    # DiagCAN is a plain transfer diagnostics bus again — it carries the vehicle NM PDU but is not a member.
    diag_can = next(bus for bus in reloaded.communication.channels.can_buses if bus.name == "DiagCAN")
    assert diag_can.state_memberships == []


def test_rebuild_type_prefers_external_parent():
    """state_memberships lives on ECU / Controller (External SINGLE_FILE) and on the bus classes (inline).

    The dependency graph must reconstruct the on-disk dict wrapper from the external parents; if an
    inline parent won the (set-ordered) lookup instead, entity-level membership files would be
    validated against the bare element type and silently dropped.
    """

    graph = get_model_dependency_graph(FLYNCModel)
    rebuilt = graph.rebuild_type_from_parent(StateMembershipRef, "state_memberships")
    assert get_origin(rebuilt) is dict
