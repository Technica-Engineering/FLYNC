"""
End-to-end test of a multidrop segment built from Python, not ``flync_example``.

The segment is assembled as a real FLYNC model, dumped to disk, reloaded through the full workspace loader and validated - so it
covers the file layout and the whole validator chain in order.  What each rule reports is pinned in independent objects in
``tests_4_topology/test_ethernet_multidrop.py``.
"""

import pytest

from flync.sdk.context.diagnostics_result import WorkspaceState
from flync.sdk.helpers.validation_helpers import validate_workspace
from flync.sdk.workspace.flync_workspace import FLYNCWorkspace
from tests.multidrop_workspace import SEGMENT, build_multidrop_model


@pytest.fixture(scope="module")
def validation(tmp_path_factory):
    """Load the synthetic segment through the real workspace loader once; no test here mutates it."""
    root = tmp_path_factory.mktemp("t1s") / "ws"
    FLYNCWorkspace.load_model(flync_model=build_multidrop_model(), workspace_name="t1s", file_path=root).generate_configs()
    return validate_workspace(root)


@pytest.fixture(scope="module")
def connection(validation):
    return validation.model.get_multidrop_connection(SEGMENT)


def _messages(validation):
    return [detail["msg"] for details in validation.errors.values() for detail in details]


def test_the_segment_loads_as_one_connection_with_four_nodes(connection):
    assert connection is not None
    assert connection.type == "ethernet_multidrop"
    assert len(connection.nodes) == 4
    assert connection.plca.transmit_opportunity_count == 4
    assert connection.plca.to_timer == 32


def test_the_cycle_reads_back_in_order(connection):
    """Authoring order is not cycle order, and the cycle is what the slots mean."""

    assert connection.coordinator.ecu_port_name == "z1_p2"
    assert [n.ecu_port_name for n in connection.participants] == [
        "z1_p2",
        "rear_lamp_left_p1",
        "rear_lamp_center_p1",
        "rear_lamp_right_p1",
    ]


def test_every_node_resolves_to_a_multidrop_port_on_its_own_ecu(connection):
    """``bind`` has to reach the real ports: every rule after it reads the PHY off them."""

    for node in connection.nodes:
        assert node.ecu_port is not None, node.ecu_port_name
        assert node.ecu_port.mdi_config.mode == "base_t1s"
        assert node.ecu_port.mdi_config.topology == "multidrop"
        assert node.ecu_name is not None


def test_the_phy_mirrors_each_nodes_slot_and_burst(connection):
    """The PHY reflects the connection node, because that is the one place the segment declares the PLCA timing."""

    for node in connection.nodes:
        phy = node.ecu_port.mdi_config
        assert phy.node_id == node.node_id
        assert phy.burst_count == node.burst_count
        assert phy.burst_timer == node.burst_timer
        # node_id/burst are mirrored properties, not input fields: nothing to set in the PHY's own YAML.
        assert "node_id" not in type(phy).model_fields


def test_segment_ports_are_joined_to_one_another(connection):
    """
    A segment is a connection with more than two ends, so its ports have to see each other the way two ends of a link do.

    Everything that walks the topology reads ``connected_components``.  Without this the segment is a hole in the graph.
    """

    ports = {n.ecu_port_name: n.ecu_port for n in connection.nodes}

    assert len(ports) == 4
    for name, port in ports.items():
        peers = {c.name for c in port.connected_components if c.type == "ecu_port"}
        assert peers == set(ports) - {name}, f"{name} sees {peers}"


def test_the_workspace_loads_clean(validation):
    """
    ``VALID`` is the strict state: a workspace with non-fatal findings loads as ``WARNING``.

    The ``VALID`` bar keeps the segment usable as a starting point for derived workspaces, since each would inherit any findings here.
    """

    messages = _messages(validation)
    assert not [m for m in messages if "cannot be reached" in m], messages
    assert validation.state == WorkspaceState.VALID, messages
