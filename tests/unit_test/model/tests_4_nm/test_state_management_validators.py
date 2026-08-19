"""Unit tests for the state management cross-model validation rules."""

from types import SimpleNamespace

import pytest
from pydantic_core import PydanticCustomError

from flync.core.utils.exceptions import _validation_warnings
from flync.core.utils.state_management_validators import (
    collect_effective_members,
    validate_state_management,
)
from flync.model.flync_4_nm import (
    StateManagementGroup,
    StateMembershipRef,
)
from flync.model.flync_4_nm.state_management import EffectiveMember
from flync.model.flync_4_signal.pdu import (
    ContainedPDURef,
    ContainerPDU,
    ContainerPDUHeader,
    StandardPDU,
)
from flync.model.flync_4_signal.pdu_deployment import PDUReceiver, PDUSender
from flync.model.flync_4_signal.signal import (
    BitmaskFlag,
    BitmaskFlags,
    Signal,
    SignalInstance,
)

NM_PDU = "PDU_NmMessage"
NM_FRAME_ID = 0x500


# ---------------------------------------------------------------------------
# Lightweight model stubs — only the attributes the validators walk. Signal-
# layer objects (PDUs, deployments) are real because the rules isinstance
# them; entity containers are plain namespaces.
# ---------------------------------------------------------------------------


TIMING_PROFILE = "standard"


class FakeModel:
    def __init__(self, ecus=(), groups=(), pdus=(), containers=(), can_buses=(), lin_buses=(), timing_profiles=None):
        self.ecus = list(ecus)
        profiles = timing_profiles if timing_profiles is not None else [SimpleNamespace(name=TIMING_PROFILE)]
        self.communication = SimpleNamespace(
            state_management=SimpleNamespace(groups=list(groups), timing_profiles=list(profiles)),
            channels=SimpleNamespace(
                pdus=list(pdus),
                ethernet_pdu_containers=list(containers),
                can_buses=list(can_buses),
                lin_buses=list(lin_buses),
            ),
        )

    def get_ecu_by_name(self, name):
        return next((ecu for ecu in self.ecus if ecu.name == name), None)


def _group(name="VEHICLE", nm_pdu=NM_PDU, timing_profile=TIMING_PROFILE):
    return StateManagementGroup(name=name, nm_pdu=nm_pdu, timing_profile=timing_profile)


def _nm_pdu(name=NM_PDU, usage="network_management", relevance_flags=None):
    # Without relevance_flags the PDU models no bitmask vector at all, so the
    # bit-existence rule stays silent (matching the many reachability tests
    # below that only care about transport bindings). Pass relevance_flags to
    # give the PDU a relevance vector whose flags are the valid relevance bits.
    signals = []
    if relevance_flags:
        signals.append(
            SignalInstance(
                bit_position=16,
                signal=Signal(
                    name="relevance_vector",
                    bit_length=32,
                    data_type="uint32",
                    value_encoding=BitmaskFlags(flags=[BitmaskFlag(mask=1 << i, label=label) for i, label in enumerate(relevance_flags)]),
                ),
            )
        )
    return StandardPDU(name=name, length=8, pdu_usage=usage, signals=signals)


def _nm_container(name="EthNmContainer", contained=NM_PDU):
    return ContainerPDU(
        name=name,
        length=11,
        pdu_id=100,
        pdu_usage="network_management",
        header=ContainerPDUHeader(id_length_bits=16, length_field_bits=8),
        contained_pdus=[ContainedPDURef(header_id=1, pdu_ref=contained)],
    )


def _socket(*deployments):
    return SimpleNamespace(deployments=[SimpleNamespace(root=dep) for dep in deployments])


def _controller(name="ctrl", memberships=(), sockets=(), can_interfaces=()):
    eth_iface = SimpleNamespace(sockets=[SimpleNamespace(sockets=list(sockets))])
    return SimpleNamespace(
        name=name,
        state_memberships=list(memberships),
        ethernet_interfaces=[eth_iface],
        can_interfaces=list(can_interfaces),
        lin_interfaces=[],
    )


def _can_iface(bus_ref, sender_ids=(), receiver_ids=()):
    def refs(ids):
        return [SimpleNamespace(bus_ref=bus_ref, frame_ref=frame_id) for frame_id in ids]

    return SimpleNamespace(bus_ref=bus_ref, sender_frames=refs(sender_ids), receiver_frames=refs(receiver_ids))


def _ecu(name, memberships=(), controllers=()):
    state_memberships = list(memberships)
    effective = _resolve_state_effective(state_memberships, "ecu", name, name)
    for ctrl in controllers:
        effective += _resolve_state_effective(list(ctrl.state_memberships or []), "controller", f"{name}/{ctrl.name}", name)
    return SimpleNamespace(
        name=name,
        state_memberships=state_memberships,
        controllers=list(controllers),
        _state_effective_members=effective,
    )


def _resolve_state_effective(refs, kind, path, ecu_name):
    """Mirror ECU.__add_effective_state_member for test SimpleNamespace ECUs."""
    result = []
    for ref in refs:
        if ref.role == "observer":
            result.append(EffectiveMember(ref.group, kind, path, ecu_name, ref.role, None))
        else:
            bits = ref.relevance_bits or [path.rsplit("/", 1)[-1]]
            for bit in bits:
                result.append(EffectiveMember(ref.group, kind, path, ecu_name, ref.role, bit))
    return result


def _can_frame(can_id=NM_FRAME_ID, pdu_refs=(NM_PDU,), length=8, cyclic_s=None):
    timing = SimpleNamespace(cyclic_timings=[SimpleNamespace(cycle=cyclic_s)]) if cyclic_s is not None else None
    return SimpleNamespace(
        name=f"frame_{can_id:#x}",
        can_id=can_id,
        length=length,
        timing=timing,
        packed_pdus=[SimpleNamespace(pdu_ref=ref) for ref in pdu_refs],
    )


def _bus(name="DiagCAN", frames=(), memberships=(), baud_rate=500_000):
    return SimpleNamespace(name=name, frames=list(frames), state_memberships=list(memberships), baud_rate=baud_rate)


@pytest.fixture
def captured_warnings():
    token = _validation_warnings.set([])
    try:
        yield _validation_warnings.get()
    finally:
        _validation_warnings.reset(token)


def test_positive_collect_members_bit_defaults():
    model = FakeModel(
        ecus=[
            _ecu(
                "GatewayEcu",
                memberships=[StateMembershipRef(group="G")],
                controllers=[_controller("can_1", memberships=[StateMembershipRef(group="G")])],
            )
        ],
        can_buses=[_bus("BodyCan", memberships=[StateMembershipRef(group="G")])],
    )
    members = {(m.entity_kind, m.entity_path): m for m in collect_effective_members(model)["G"]}
    assert members[("ecu", "GatewayEcu")].relevance_bit == "GatewayEcu"
    assert members[("controller", "GatewayEcu/can_1")].relevance_bit == "can_1"
    assert members[("bus", "BodyCan")].relevance_bit == "BodyCan"
    assert members[("bus", "BodyCan")].ecu_name is None


def test_positive_collect_members_explicit_bit():
    model = FakeModel(ecus=[_ecu("E", memberships=[StateMembershipRef(group="G", relevance_bits=["PowerDist"])])])
    assert collect_effective_members(model)["G"][0].relevance_bit == "PowerDist"


def test_positive_empty_model_is_noop():
    validate_state_management(FakeModel())


def test_unknown_group_reference_negative():
    model = FakeModel(ecus=[_ecu("E", memberships=[StateMembershipRef(group="GHOST")])])
    with pytest.raises(PydanticCustomError, match="undefined state management group 'GHOST'"):
        validate_state_management(model)


def test_group_without_members_negative():
    model = FakeModel(groups=[_group()], pdus=[_nm_pdu()])
    with pytest.raises(PydanticCustomError, match="has no participant"):
        validate_state_management(model)


def test_group_with_only_observers_negative():
    ecu = _ecu("E", memberships=[StateMembershipRef(group="VEHICLE", role="observer")])
    model = FakeModel(ecus=[ecu], groups=[_group()], pdus=[_nm_pdu()])
    with pytest.raises(PydanticCustomError, match="has no participant"):
        validate_state_management(model)


def _participant_with_tx(group="VEHICLE"):
    controller = _controller(sockets=[_socket(PDUSender(pdu_ref=NM_PDU), PDUReceiver(pdu_ref=NM_PDU))])
    return _ecu("E", memberships=[StateMembershipRef(group=group)], controllers=[controller])


def test_unknown_nm_pdu_negative():
    model = FakeModel(ecus=[_participant_with_tx()], groups=[_group(nm_pdu="PDU_Ghost")])
    with pytest.raises(PydanticCustomError, match="nm_pdu 'PDU_Ghost' not found"):
        validate_state_management(model)


def test_wrong_pdu_usage_negative():
    model = FakeModel(ecus=[_participant_with_tx()], groups=[_group()], pdus=[_nm_pdu(usage="application")])
    with pytest.raises(PydanticCustomError, match="expected 'network_management'"):
        validate_state_management(model)


def test_unknown_timing_profile_negative():
    model = FakeModel(
        ecus=[_participant_with_tx()],
        groups=[_group(timing_profile="ghost_profile")],
        pdus=[_nm_pdu()],
    )
    with pytest.raises(PydanticCustomError, match="timing_profile 'ghost_profile' not found"):
        validate_state_management(model)


def _participant_with_bits(relevance_bits, group="VEHICLE"):
    controller = _controller(sockets=[_socket(PDUSender(pdu_ref=NM_PDU), PDUReceiver(pdu_ref=NM_PDU))])
    return _ecu("E", memberships=[StateMembershipRef(group=group, relevance_bits=relevance_bits)], controllers=[controller])


def test_positive_relevance_bit_in_pdu_vector():
    # 'Comfort' is a flag of the NM PDU's relevance vector, so the bit resolves.
    model = FakeModel(
        ecus=[_participant_with_bits(["Comfort"])],
        groups=[_group()],
        pdus=[_nm_pdu(relevance_flags=["AutonomousDriving", "OnlineCommunication", "Comfort"])],
    )
    validate_state_management(model)


def test_unknown_relevance_bit_negative():
    # 'Nonexistent' is not a flag of the relevance vector -> the typo is caught.
    model = FakeModel(
        ecus=[_participant_with_bits(["Nonexistent"])],
        groups=[_group()],
        pdus=[_nm_pdu(relevance_flags=["Comfort"])],
    )
    with pytest.raises(PydanticCustomError, match="claims relevance bit 'Nonexistent' which is not a flag of NM PDU"):
        validate_state_management(model)


def test_positive_default_bit_matches_pdu_vector():
    # No relevance_bits declared -> the bit defaults to the entity name, which
    # here names a declared flag of the relevance vector, so it resolves.
    controller = _controller(sockets=[_socket(PDUSender(pdu_ref=NM_PDU), PDUReceiver(pdu_ref=NM_PDU))])
    ecu = _ecu("Comfort", memberships=[StateMembershipRef(group="VEHICLE")], controllers=[controller])
    model = FakeModel(ecus=[ecu], groups=[_group()], pdus=[_nm_pdu(relevance_flags=["Comfort"])])
    validate_state_management(model)


def test_default_bit_not_in_pdu_vector_negative():
    # No relevance_bits declared -> the bit defaults to the entity name 'E',
    # which is not a flag of the modelled relevance vector -> caught.
    model = FakeModel(
        ecus=[_participant_with_tx()],
        groups=[_group()],
        pdus=[_nm_pdu(relevance_flags=["Comfort"])],
    )
    with pytest.raises(PydanticCustomError, match="claims relevance bit 'E' which is not a flag of NM PDU"):
        validate_state_management(model)


def test_participant_without_tx_path_negative():
    ecu = _ecu("E", memberships=[StateMembershipRef(group="VEHICLE")], controllers=[_controller()])
    model = FakeModel(ecus=[ecu], groups=[_group()], pdus=[_nm_pdu()])
    with pytest.raises(PydanticCustomError, match="no TX path.*neither a pdu_sender socket deployment nor a CAN/LIN sender_frames"):
        validate_state_management(model)


def test_participant_with_rx_only_negative():
    # A receiver deployment is not enough for a participant — TX is required.
    controller = _controller(sockets=[_socket(PDUReceiver(pdu_ref=NM_PDU))])
    ecu = _ecu("E", memberships=[StateMembershipRef(group="VEHICLE")], controllers=[controller])
    model = FakeModel(ecus=[ecu], groups=[_group()], pdus=[_nm_pdu()])
    with pytest.raises(PydanticCustomError, match="participant 'E' has no TX path"):
        validate_state_management(model)


def test_observer_without_rx_path_negative():
    # A sender deployment is not enough for an observer — RX is required.
    tx_controller = _controller(name="tx", sockets=[_socket(PDUSender(pdu_ref=NM_PDU))])
    observer = _ecu("Obs", memberships=[StateMembershipRef(group="VEHICLE", role="observer")], controllers=[tx_controller])
    participant = _participant_with_tx()
    model = FakeModel(ecus=[participant, observer], groups=[_group()], pdus=[_nm_pdu()])
    with pytest.raises(PydanticCustomError, match="observer 'Obs' has no RX path.*pdu_receiver socket deployment nor a CAN/LIN receiver_frames"):
        validate_state_management(model)


def test_participant_without_rx_path_negative():
    # A sender deployment alone is not enough — a participant must also
    # observe the group state, otherwise it could never sleep correctly.
    controller = _controller(sockets=[_socket(PDUSender(pdu_ref=NM_PDU))])
    ecu = _ecu("E", memberships=[StateMembershipRef(group="VEHICLE")], controllers=[controller])
    model = FakeModel(ecus=[ecu], groups=[_group()], pdus=[_nm_pdu()])
    with pytest.raises(PydanticCustomError, match="participant 'E' has no RX path"):
        validate_state_management(model)


def test_positive_participant_via_ethernet_sender():
    model = FakeModel(ecus=[_participant_with_tx()], groups=[_group()], pdus=[_nm_pdu()])
    validate_state_management(model)


def test_positive_participant_via_container_indirection():
    controller = _controller(sockets=[_socket(PDUSender(pdu_ref="EthNmContainer"), PDUReceiver(pdu_ref="EthNmContainer"))])
    ecu = _ecu("E", memberships=[StateMembershipRef(group="VEHICLE")], controllers=[controller])
    model = FakeModel(ecus=[ecu], groups=[_group()], pdus=[_nm_pdu()], containers=[_nm_container()])
    validate_state_management(model)


def test_positive_participant_via_can_sender_frames():
    controller = _controller(can_interfaces=[_can_iface("DiagCAN", sender_ids=[NM_FRAME_ID], receiver_ids=[NM_FRAME_ID])])
    ecu = _ecu("E", memberships=[StateMembershipRef(group="VEHICLE")], controllers=[controller])
    model = FakeModel(ecus=[ecu], groups=[_group()], pdus=[_nm_pdu()], can_buses=[_bus(frames=[_can_frame()])])
    validate_state_management(model)


def test_positive_observer_via_can_receiver_frames():
    observer_controller = _controller(name="rx", can_interfaces=[_can_iface("DiagCAN", receiver_ids=[NM_FRAME_ID])])
    observer = _ecu("Obs", memberships=[StateMembershipRef(group="VEHICLE", role="observer")], controllers=[observer_controller])
    participant = _participant_with_tx()
    model = FakeModel(ecus=[participant, observer], groups=[_group()], pdus=[_nm_pdu()], can_buses=[_bus(frames=[_can_frame()])])
    validate_state_management(model)


def test_positive_participant_via_lin_sender_frames():
    # Real-model shape: a LIN master interface carries sender_frames only, so
    # the participant's TX path is the LIN frame and its RX path an Ethernet
    # socket (it cannot receive on the LIN side).
    controller = _controller(sockets=[_socket(PDUReceiver(pdu_ref=NM_PDU))])
    controller.lin_interfaces = [_lin_master("BodyLin", sender_ids=[62])]
    ecu = _ecu("LinMaster", memberships=[StateMembershipRef(group="VEHICLE")], controllers=[controller])
    lin_frame = SimpleNamespace(name="Frame_Nm_Lin", lin_id=62, packed_pdus=[SimpleNamespace(pdu_ref=NM_PDU)])
    lin_bus = SimpleNamespace(name="BodyLin", frames=[lin_frame], state_memberships=[])
    model = FakeModel(ecus=[ecu], groups=[_group()], pdus=[_nm_pdu()], lin_buses=[lin_bus])
    validate_state_management(model)


def test_bus_without_frame_binding_negative():
    bus = _bus(frames=[_can_frame(pdu_refs=("PDU_Other",))], memberships=[StateMembershipRef(group="VEHICLE")])
    model = FakeModel(ecus=[_participant_with_tx()], groups=[_group()], pdus=[_nm_pdu()], can_buses=[bus])
    with pytest.raises(PydanticCustomError, match="no frame carrying NM PDU.*nobody feeds NM into"):
        validate_state_management(model)


def test_bus_without_nm_sender_negative():
    # The NM frame exists on the bus, but no attached ECU sends it.
    bus = _bus(frames=[_can_frame()], memberships=[StateMembershipRef(group="VEHICLE")])
    rx_only = _controller(can_interfaces=[_can_iface("DiagCAN", receiver_ids=[NM_FRAME_ID])])
    ecu = _ecu("RxOnly", controllers=[rx_only])
    model = FakeModel(ecus=[ecu, _participant_with_tx()], groups=[_group()], pdus=[_nm_pdu()], can_buses=[bus])
    with pytest.raises(PydanticCustomError, match="no ECU attached to bus participant 'DiagCAN' sends.*nobody feeds NM into"):
        validate_state_management(model)


def test_positive_bus_with_binding_and_sender():
    bus = _bus(frames=[_can_frame()], memberships=[StateMembershipRef(group="VEHICLE", relevance_bits=["DiagCan"])])
    sender = _controller(can_interfaces=[_can_iface("DiagCAN", sender_ids=[NM_FRAME_ID])])
    ecu = _ecu("E", controllers=[sender])
    model = FakeModel(ecus=[ecu], groups=[_group()], pdus=[_nm_pdu()], can_buses=[bus])
    validate_state_management(model)


def _lin_master(bus_ref, sender_ids=()):
    # Mirrors the real LINMasterInterface shape: sender_frames only — a LIN
    # master has no receiver_frames field (receiving is the slave side).
    return SimpleNamespace(
        bus_ref=bus_ref,
        node_type="master",
        sender_frames=[SimpleNamespace(bus_ref=bus_ref, frame_ref=frame_id) for frame_id in sender_ids],
    )


def _lin_bus(name="BodyLIN", memberships=()):
    # A LIN bus carries no NM frame.
    return SimpleNamespace(name=name, frames=[], state_memberships=list(memberships))


def test_positive_lin_bus_via_master_proxy():
    # The LIN bus has no NM frame; its master ECU reaches the NM PDU on Ethernet.
    master_ctrl = _controller(name="lin_ctrl", sockets=[_socket(PDUReceiver(pdu_ref=NM_PDU))])
    master_ctrl.lin_interfaces = [_lin_master("BodyLIN")]
    ecu = _ecu("LinMaster", controllers=[master_ctrl])
    lin_bus = _lin_bus(memberships=[StateMembershipRef(group="VEHICLE", relevance_bits=["Comfort"])])
    model = FakeModel(ecus=[ecu], groups=[_group()], pdus=[_nm_pdu()], lin_buses=[lin_bus])
    validate_state_management(model)


def test_lin_bus_master_without_nm_reach_negative():
    # Master exists but its ECU never reaches the NM PDU on any binding.
    master_ctrl = _controller(name="lin_ctrl")
    master_ctrl.lin_interfaces = [_lin_master("BodyLIN")]
    ecu = _ecu("LinMaster", controllers=[master_ctrl])
    lin_bus = _lin_bus(memberships=[StateMembershipRef(group="VEHICLE", relevance_bits=["Comfort"])])
    # a separate participant keeps the group valid (>=1 participant with a real path)
    model = FakeModel(ecus=[ecu, _participant_with_tx()], groups=[_group()], pdus=[_nm_pdu()], lin_buses=[lin_bus])
    with pytest.raises(PydanticCustomError, match="LIN bus participant 'BodyLIN' has no master whose ECU receives or sends"):
        validate_state_management(model)


def test_positive_lin_bus_master_as_source():
    # A master whose ECU SENDS the group's NM PDU elsewhere is a source of the
    # group state (e.g. a central gateway) — it needs no other bus to learn it
    # from, so the LIN bus membership is valid.
    master_ctrl = _controller(name="lin_ctrl", sockets=[_socket(PDUSender(pdu_ref=NM_PDU))])
    master_ctrl.lin_interfaces = [_lin_master("BodyLIN")]
    ecu = _ecu("LinMaster", controllers=[master_ctrl])
    lin_bus = _lin_bus(memberships=[StateMembershipRef(group="VEHICLE", relevance_bits=["Comfort"])])
    model = FakeModel(ecus=[ecu, _participant_with_tx()], groups=[_group()], pdus=[_nm_pdu()], lin_buses=[lin_bus])
    validate_state_management(model)


def test_positive_entity_registered_in_multiple_groups_union():
    # Union sleep: one ECU registered in two groups is derived into BOTH member
    # sets (it may sleep only once every group has released it).
    ecu = _ecu(
        "MultiFunction",
        memberships=[
            StateMembershipRef(group="COMFORT", relevance_bits=["Comfort"]),
            StateMembershipRef(group="DRIVE", relevance_bits=["AutonomousDriving"]),
        ],
        controllers=[_controller(sockets=[_socket(PDUSender(pdu_ref=NM_PDU), PDUReceiver(pdu_ref=NM_PDU))])],
    )
    model = FakeModel(ecus=[ecu], groups=[_group("COMFORT"), _group("DRIVE")], pdus=[_nm_pdu()])
    members = collect_effective_members(model)
    assert {m.relevance_bit for m in members["COMFORT"]} == {"Comfort"}
    assert {m.relevance_bit for m in members["DRIVE"]} == {"AutonomousDriving"}
    validate_state_management(model)  # both groups valid: the ECU is a participant with a TX+RX path in each


def test_redundant_controller_under_whole_ecu_participant_warns(captured_warnings):
    controller = _controller(
        name="ctrl",
        memberships=[StateMembershipRef(group="VEHICLE")],
        sockets=[_socket(PDUSender(pdu_ref=NM_PDU), PDUReceiver(pdu_ref=NM_PDU))],
    )
    ecu = _ecu("E", memberships=[StateMembershipRef(group="VEHICLE")], controllers=[controller])
    model = FakeModel(ecus=[ecu], groups=[_group()], pdus=[_nm_pdu()])
    validate_state_management(model)
    assert any("'E/ctrl' is redundant" in w["msg"] and "whole-ECU participant" in w["msg"] for w in captured_warnings)


def test_bus_and_ecu_membership_on_same_bus_errors():
    bus = _bus(frames=[_can_frame()], memberships=[StateMembershipRef(group="VEHICLE")])
    sender = _controller(can_interfaces=[_can_iface("DiagCAN", sender_ids=[NM_FRAME_ID], receiver_ids=[NM_FRAME_ID])])
    ecu = _ecu("E", memberships=[StateMembershipRef(group="VEHICLE")], controllers=[sender])
    model = FakeModel(ecus=[ecu], groups=[_group()], pdus=[_nm_pdu()], can_buses=[bus])
    with pytest.raises(PydanticCustomError, match="choose one variant per bus"):
        validate_state_management(model)


def test_bus_and_controller_membership_on_same_bus_errors():
    bus = _bus(frames=[_can_frame()], memberships=[StateMembershipRef(group="VEHICLE")])
    ctrl = _controller(
        memberships=[StateMembershipRef(group="VEHICLE")],
        can_interfaces=[_can_iface("DiagCAN", sender_ids=[NM_FRAME_ID], receiver_ids=[NM_FRAME_ID])],
    )
    ecu = _ecu("E", controllers=[ctrl])
    model = FakeModel(ecus=[ecu], groups=[_group()], pdus=[_nm_pdu()], can_buses=[bus])
    with pytest.raises(PydanticCustomError, match="choose one variant per bus"):
        validate_state_management(model)


def test_positive_lin_master_with_own_membership_same_group():
    # A LIN master may hold its OWN membership in the group its LIN bus joins
    # bus-level: LIN has no per-node NM, so the master's participation is
    # necessarily about another transport (its Ethernet side) — not a variant
    # mix. The central-gateway case: it drives the bus AND participates itself.
    ctrl = _controller(name="lin_ctrl", sockets=[_socket(PDUReceiver(pdu_ref=NM_PDU), PDUSender(pdu_ref=NM_PDU))])
    ctrl.lin_interfaces = [_lin_master("BodyLIN")]
    ecu = _ecu("LinMaster", memberships=[StateMembershipRef(group="VEHICLE", relevance_bits=["AutonomousDriving"])], controllers=[ctrl])
    lin_bus = _lin_bus(memberships=[StateMembershipRef(group="VEHICLE", relevance_bits=["Comfort"])])
    model = FakeModel(ecus=[ecu], groups=[_group()], pdus=[_nm_pdu()], lin_buses=[lin_bus])
    validate_state_management(model)


def test_no_warning_without_redundancy(captured_warnings):
    model = FakeModel(ecus=[_participant_with_tx()], groups=[_group()], pdus=[_nm_pdu()])
    validate_state_management(model)
    assert captured_warnings == []


def _timing_model(cycle_time_ms, baud_rate, frame_cyclic_s=None):
    # A valid participant reaching the NM PDU over CAN sender/receiver frames, on
    # a CAN bus that carries the NM frame at `baud_rate`, with a timing profile
    # whose cycle_time_ms is `cycle_time_ms`. `frame_cyclic_s` optionally gives
    # the NM frame a configured cyclic timing (seconds).
    controller = _controller(can_interfaces=[_can_iface("DiagCAN", sender_ids=[NM_FRAME_ID], receiver_ids=[NM_FRAME_ID])])
    ecu = _ecu("E", memberships=[StateMembershipRef(group="VEHICLE")], controllers=[controller])
    return FakeModel(
        ecus=[ecu],
        groups=[_group()],
        pdus=[_nm_pdu()],
        can_buses=[_bus(frames=[_can_frame(cyclic_s=frame_cyclic_s)], baud_rate=baud_rate)],
        timing_profiles=[SimpleNamespace(name=TIMING_PROFILE, cycle_time_ms=cycle_time_ms)],
    )


def test_positive_timing_feasible_no_warning(captured_warnings):
    # 500 ms cycle at 500 kbit/s: an 8-byte NM frame needs well under 1 ms, so
    # the cycle comfortably fits the frame and nothing is flagged.
    validate_state_management(_timing_model(cycle_time_ms=500, baud_rate=500_000))
    assert captured_warnings == []


def test_timing_infeasible_warns(captured_warnings):
    # 1 ms cycle on a slow 50 kbit/s bus: the ~2 ms NM frame cannot be sent in
    # time, so the physically-implausible cadence is warned about.
    validate_state_management(_timing_model(cycle_time_ms=1, baud_rate=50_000))
    assert any("cycle_time_ms (1) is shorter than" in w["msg"] and "NM frame" in w["msg"] for w in captured_warnings)


def test_positive_frame_cycle_matches_group_no_warning(captured_warnings):
    # The NM frame's configured cyclic timing (0.5 s) matches the group's
    # cycle_time_ms (500) -> consistent, nothing is flagged.
    validate_state_management(_timing_model(cycle_time_ms=500, baud_rate=500_000, frame_cyclic_s=0.5))
    assert captured_warnings == []


def test_frame_cycle_mismatch_warns(captured_warnings):
    # The NM frame claims a 100 ms cyclic timing while the group's profile says
    # 500 ms — the two describe the same cadence, so the contradiction warns.
    validate_state_management(_timing_model(cycle_time_ms=500, baud_rate=500_000, frame_cyclic_s=0.1))
    assert any("does not match the group's cycle_time_ms" in w["msg"] for w in captured_warnings)


def test_frame_own_cycle_infeasible_warns(captured_warnings):
    # The frame's OWN configured cadence (1 ms) matches the profile, but a
    # 50 kbit/s bus needs ~2.2 ms per frame — physically infeasible.
    validate_state_management(_timing_model(cycle_time_ms=1, baud_rate=50_000, frame_cyclic_s=0.001))
    assert any("configured cyclic timing (1) is shorter than" in w["msg"] for w in captured_warnings)
