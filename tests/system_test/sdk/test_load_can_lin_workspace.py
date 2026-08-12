"""Integration tests for loading a CAN/LIN-only (non-Ethernet) workspace and its derived bus topology."""

from pathlib import Path

from flync.sdk.workspace.flync_workspace import FLYNCWorkspace

# The can_lin_example is a deliberately non-Ethernet workspace: its single ECU has no ports.flync.yaml,
# no internal topology.flync.yaml, and the workspace has no topology/ folder. It exercises the CAN/LIN
# bus-topology derivation and the optional-Ethernet handling on the load path.
CAN_LIN_EXAMPLE = Path(__file__).parents[3] / "examples" / "can_lin_example"


def test_can_lin_only_workspace_loads():
    """A CAN/LIN-only workspace loads without a fatal error despite having no Ethernet ports/topology."""
    ws = FLYNCWorkspace.load_workspace("can_lin_example", CAN_LIN_EXAMPLE)
    assert ws is not None
    assert ws.flync_model is not None
    assert ws.flync_model.ecus


def test_can_lin_only_ecu_has_no_ethernet_hardware():
    """The CAN/LIN-only ECU loads with no ports and no internal topology (both optional)."""
    ws = FLYNCWorkspace.load_workspace("can_lin_example", CAN_LIN_EXAMPLE)
    ecu = ws.flync_model.ecus[0]
    assert not ecu.get_all_ports()
    assert ecu.get_internal_topology() is None


def test_can_lin_workspace_has_no_ethernet_topology():
    """No topology/ folder means the (optional) ethernet topology is absent, but the container still exists."""
    ws = FLYNCWorkspace.load_workspace("can_lin_example", CAN_LIN_EXAMPLE)
    assert ws.flync_model.topology is not None
    assert ws.flync_model.topology.ethernet_topology is None


def test_can_bus_topology_is_derived():
    """The DiagCAN bus is derived from the ECU's CAN interface(s)."""
    ws = FLYNCWorkspace.load_workspace("can_lin_example", CAN_LIN_EXAMPLE)
    topo = ws.flync_model.get_can_bus_topology("DiagCAN")
    assert topo is not None
    assert topo.bus_type == "can"
    assert len(topo.attachments) >= 1
    assert all(a.role == "can_node" for a in topo.attachments)


def test_lin_bus_topology_is_present_in_model():
    """The declared BodyLIN bus is seeded into the derived LIN topology even with no attachment."""
    ws = FLYNCWorkspace.load_workspace("can_lin_example", CAN_LIN_EXAMPLE)
    topo = ws.flync_model.get_lin_bus_topology("BodyLIN")
    assert topo is not None
    assert topo.bus_type == "lin"


def test_unknown_bus_topology_lookup_returns_none():
    ws = FLYNCWorkspace.load_workspace("can_lin_example", CAN_LIN_EXAMPLE)
    assert ws.flync_model.get_can_bus_topology("DoesNotExist") is None
