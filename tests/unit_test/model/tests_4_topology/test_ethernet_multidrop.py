"""Unit tests for the multidrop branch of the system topology."""

import pytest
from pydantic import ValidationError
from pydantic_core import PydanticCustomError

from flync.core.utils.exceptions import _validation_warnings
from flync.model.flync_4_ecu.phy import BASET1, BASET1S
from flync.model.flync_4_ecu.port import ECUPort
from flync.model.flync_4_ecu.switch import SwitchPort
from flync.model.flync_4_topology.ethernet_multidrop import (
    EthernetMultidropConnection,
    validate_multidrop_connections,
)
from flync.model.flync_4_topology.ethernet_topology import EthernetPointToPointConnection, EthernetTopology
from flync.model.flync_4_tsn.qos import CBSShaper, TrafficClass
from flync.model.flync_4_tsn.timesync import PTPConfig, PTPPort, PTPTimeTransmitterConfig
from tests.error_assertions import assert_no_findings, assert_single_error, assert_single_warning, assert_warnings

# ---------------------------------------------------------------------------
# Helpers. Ports are real objects: the rules read mdi_config off them.
# ---------------------------------------------------------------------------


def _connection(id="RearLampSegment", slots=4, nodes=(), to_timer=32):
    plca = None if slots is None else {"transmit_opportunity_count": slots, "to_timer": to_timer}
    return EthernetMultidropConnection(id=id, plca=plca, nodes=list(nodes))


def _bind(conn, phys=None):
    """Resolve the connection against ports carrying a multidrop T1S PHY unless *phys* says otherwise."""

    phys = phys or {}
    ports = {
        n.ecu_port_name: ECUPort(name=n.ecu_port_name, mdi_config=phys.get(n.ecu_port_name) or BASET1S(topology="multidrop")) for n in conn.nodes
    }
    conn.bind(ports)
    return conn


def _segment(*slots, id="RearLampSegment", count=None, phys=None):
    """One connection with a node per entry: an int claims that slot, ``None`` takes no part in PLCA."""

    nodes = [{"ecu_port": f"p{i}", **({"node_id": s} if s is not None else {})} for i, s in enumerate(slots)]
    return _bind(_connection(id=id, slots=count if count is not None else len(slots), nodes=nodes), phys)


def _assert_raises(connections, expected_error_id, fragment):
    with pytest.raises(PydanticCustomError) as exc_info:
        validate_multidrop_connections(connections)
    assert exc_info.value.context["error_id"] == expected_error_id
    assert fragment in str(exc_info.value)


def _validated(connections):
    """Run the system-wide checks and return a ``(model, findings)`` pair for the assertion helpers."""

    token = _validation_warnings.set([])
    try:
        validate_multidrop_connections(connections)
        return connections, _validation_warnings.get()
    finally:
        _validation_warnings.reset(token)


# ---------------------------------------------------------------------------
# Shape
# ---------------------------------------------------------------------------


def test_positive_coordinator_followers_and_non_participants():
    conn = _segment(0, 1, None, 2)

    assert conn.coordinator.ecu_port_name == "p0"
    assert [n.ecu_port_name for n in conn.followers] == ["p1", "p3"]
    assert [n.ecu_port_name for n in conn.participants] == ["p0", "p1", "p3"]
    assert conn.nodes[2].participates is False


def test_positive_participants_come_back_in_cycle_order():
    """The list is authored in any order; the cycle is what the order means, so the property sorts by slot."""

    conn = _segment(3, 0, 2, 1)

    assert [n.node_id for n in conn.participants] == [0, 1, 2, 3]


def test_positive_a_segment_without_plca_needs_no_slots():
    """A shared medium may arbitrate by CSMA/CD, and then there is no cycle to hand out slots from."""

    conn = _connection(slots=None, nodes=[{"ecu_port": "p0"}, {"ecu_port": "p1"}])

    assert conn.plca is None
    assert conn.coordinator is None
    assert conn.participants == []


def test_negative_a_slot_without_a_cycle_to_sit_in():
    with pytest.raises(ValidationError) as exc_info:
        _connection(slots=None, nodes=[{"ecu_port": "p0", "node_id": 0}])

    assert_single_error(exc_info, "FLYNC-TOP-MAJ-CONS-334", "declares no 'plca' cycle")


def test_negative_burst_timer_at_the_interframe_gap():
    """A burst timer at or below the gap ends the burst before the next frame starts, so the burst count buys nothing."""

    with pytest.raises(ValidationError) as exc_info:
        _connection(nodes=[{"ecu_port": "p0", "node_id": 0, "burst_count": 3, "burst_timer": 96}])

    assert_single_error(exc_info, "FLYNC-TOP-MAJ-VAL-336", "interframe gap")


def test_negative_burst_without_a_slot():
    """Bursting is a PLCA feature; with no slot the node competes by CSMA/CD and has nothing to burst inside."""

    with pytest.raises(ValidationError) as exc_info:
        _connection(nodes=[{"ecu_port": "p0", "burst_count": 3}])

    assert_single_error(exc_info, "FLYNC-TOP-MAJ-CONS-335", "no node_id")


def test_positive_burst_defaults_need_no_slot():
    """A node that takes no part in PLCA competes by CSMA/CD; only non-default burst values demand a slot."""

    _connection(nodes=[{"ecu_port": "p0"}, {"ecu_port": "p1", "node_id": 0}])


def test_positive_the_union_discriminates_on_type():
    """An existing point-to-point entry has to load unchanged beside a multidrop one."""

    topology = EthernetTopology(
        connections=[
            {"type": "ecu_port_to_ecu_port", "id": "c1", "ecu1_port": "a", "ecu2_port": "b"},
            {"type": "ethernet_multidrop", "id": "seg", "plca": {"transmit_opportunity_count": 1}, "nodes": [{"ecu_port": "p0"}]},
        ]
    )

    assert isinstance(topology.connections[0], EthernetPointToPointConnection)
    assert isinstance(topology.connections[1], EthernetMultidropConnection)


def test_positive_point_to_point_connection_without_type_loads():
    """A pointer-to-point entry never named its ``type`` under the old single-connection model, so it has to keep loading."""

    topology = EthernetTopology(connections=[{"id": "c1", "ecu1_port": "a", "ecu2_port": "b"}])

    assert isinstance(topology.connections[0], EthernetPointToPointConnection)


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------


def test_negative_two_coordinators():
    """Two nodes emitting BEACONs collide, so this is an error where a missing coordinator is only a warning."""

    _assert_raises([_segment(0, 0)], "FLYNC-TOP-MAJ-CONS-325", "exactly one coordinator")


def test_negative_two_nodes_on_one_slot():
    _assert_raises([_segment(0, 1, 1)], "FLYNC-TOP-MAJ-UNIQ-327", "both claim transmit opportunity 1")


def test_negative_slot_outside_the_cycle():
    """Separate from the count: slots 0 and 7 with a cycle of 2 pass any count check while slot 7 never comes round."""

    _assert_raises([_segment(0, 7, count=2)], "FLYNC-TOP-MAJ-CONS-320", "outside the cycle")


@pytest.mark.parametrize(
    "phy, error_id, fragment",
    [
        pytest.param(BASET1(speed=100, role="slave"), "FLYNC-TOP-MAJ-CONS-331", "multidrop-capable PHY", id="not_a_multidrop_phy"),
        pytest.param(BASET1S(topology="p2p"), "FLYNC-TOP-MAJ-CONS-332", "declares topology 'p2p'", id="point_to_point_port"),
    ],
)
def test_negative_port_phy_cannot_sit_on_a_shared_medium(phy, error_id, fragment):
    _assert_raises([_segment(0, phys={"p0": phy})], error_id, fragment)


def test_negative_port_on_two_segments():
    """One port carries one PHY, so it sits on one segment - checked across connections, since each sees the port once."""

    first = _bind(_connection(id="s1", slots=1, nodes=[{"ecu_port": "shared", "node_id": 0}]))
    second = _bind(_connection(id="s2", slots=1, nodes=[{"ecu_port": "shared", "node_id": 0}]))

    _assert_raises([first, second], "FLYNC-TOP-MAJ-UNIQ-333", "claimed by two multidrop connections")


def test_negative_unknown_port():
    conn = _connection(slots=1, nodes=[{"ecu_port": "nowhere", "node_id": 0}])

    with pytest.raises(PydanticCustomError) as exc_info:
        conn.bind({})
    assert exc_info.value.context["error_id"] == "FLYNC-TOP-MAJ-REF-329"


def test_warning_no_coordinator():
    """Nothing emits the BEACON, so PLCA never starts - the segment still works, at CSMA/CD performance."""

    # The 326 rule needs slot 0 unclaimed, which always leaves a spare slot, and that spare fires 330
    # (`_warn_unused_opportunities`) on the same pass - so both co-fire and must be pinned together.
    assert_warnings(_validated([_segment(1, 2, count=3)]), "FLYNC-TOP-WARN-CONS-326", "FLYNC-TOP-WARN-CONS-330")


def test_warning_node_outside_the_cycle_on_a_plca_segment():
    """A mixed segment is allowed; what it costs is bounded access time, and it costs it for every node."""

    # count=1 keeps the cycle full (1 participant, 1 slot), so this is the only warning that fires.
    assert_single_warning(_validated([_segment(0, None, count=1)]), "FLYNC-TOP-WARN-CONS-328", "hold no transmit opportunity")


def test_warning_slots_nobody_uses():
    assert_single_warning(_validated([_segment(0, 1, count=5)]), "FLYNC-TOP-WARN-CONS-330", "3 nobody uses")


def test_positive_a_full_cycle_warns_about_nothing():
    """The happy path: one coordinator, every slot handed out, every node taking part."""

    assert_no_findings(_validated([_segment(0, 1, 2, 3)]))


# ---------------------------------------------------------------------------
# Switch-backed rules: what sits behind a port inside its own ECU, not the segment walk.
# A switch port carries the shaper and the gPTP config, so the rules read it the same way a real ECU would.
# ---------------------------------------------------------------------------


def _segment_with_switch(switch_port, who=0):
    """A segment whose node *who* is wired to *switch_port* inside its own ECU."""

    conn = _segment(0, 1)
    conn.nodes[who].ecu_port._connected_components.append(switch_port)
    return conn


def _segment_with_two_switches(switch_a, switch_b):
    """Two nodes on one segment, each behind its own switch port."""

    conn = _segment(0, 1)
    conn.nodes[0].ecu_port._connected_components.append(switch_a)
    conn.nodes[1].ecu_port._connected_components.append(switch_b)
    return conn


def _shaped_switch_port(traffic_class_name="LatencyClass"):
    return SwitchPort(
        name="SW_PORT_1",
        default_vlan_id=1,
        silicon_port_no=1,
        traffic_classes=[
            TrafficClass(
                name=traffic_class_name,
                priority=5,
                frame_priority_values=[5],
                selection_mechanisms=CBSShaper(type="cbs", idleslope=200000),
            )
        ],
    )


def _ptp_switch_port(*, cmlds=False, two_step=True, domain_id=0):
    return SwitchPort(
        name="SW_PORT_1",
        default_vlan_id=1,
        silicon_port_no=1,
        ptp_config=PTPConfig(
            cmlds_linkport_enabled=cmlds,
            ptp_ports=[
                PTPPort(
                    domain_id=domain_id,
                    src_port_identity=1,
                    sync_config=PTPTimeTransmitterConfig(log_tx_period=-3, two_step=two_step),
                )
            ],
        ),
    )


def test_warning_shaper_on_a_switch_port_leading_onto_a_segment():
    """On a sharet medium the cycle, not the shaper, sets the latency bound; the shaper keeps prioritising within the queue."""

    assert_single_warning(_validated([_segment_with_switch(_shaped_switch_port())]), "FLYNC-TOP-WARN-CONS-318", "CBS")


def test_positive_switch_port_without_a_shaper_does_not_warn():
    """A traffic class without a selection mechanism only classifies, so it promises nothing the segment breaks."""

    unshaped = SwitchPort(
        name="SW_PORT_1",
        default_vlan_id=1,
        silicon_port_no=1,
        traffic_classes=[TrafficClass(name="BestEffort", priority=0, frame_priority_values=[0])],
    )
    assert_no_findings(_validated([_segment_with_switch(unshaped)]))


def test_negative_cmlds_enabled_on_a_multidrop_port():
    """CMLDS is not qualified for a half duplex Ethernet link, so enabling it on a shared medium has to be refused."""

    conn = _segment_with_switch(_ptp_switch_port(cmlds=True))

    _assert_raises([conn], "FLYNC-TOP-MAJ-COMP-321", "cmlds_linkport_enabled")


def test_negative_one_step_time_transmitter_on_a_multidrop_port():
    """One step transport is not qualified for a half duplex MAC, so the transmitter has to advertise two step."""

    conn = _segment_with_switch(_ptp_switch_port(two_step=False))

    _assert_raises([conn], "FLYNC-TOP-MAJ-COMP-322", "two_step false")


def test_warning_two_time_transmitters_in_one_gptp_domain():
    """Several time transmitters on one medium have to claim different domains; two in one domain race each other."""

    assert_single_warning(_validated([_segment_with_two_switches(_ptp_switch_port(), _ptp_switch_port())]), "FLYNC-TOP-WARN-CONS-323", "domain 0")


def test_positive_two_time_transmitters_in_separate_domains():
    """Two transmitters are fine as long as they do not both claim the same domain."""

    assert_no_findings(_validated([_segment_with_two_switches(_ptp_switch_port(domain_id=0), _ptp_switch_port(domain_id=1))]))


def test_positive_default_ptp_config_on_a_multidrop_port():
    """The defaults are already the qualified combination - CMLDS off, two step on - so neither 321 nor 322 fires."""

    assert_no_findings(_validated([_segment_with_switch(_ptp_switch_port())]))
