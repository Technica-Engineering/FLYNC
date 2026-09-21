"""
Negative system tests: FLYNC-dependent validation rules, only observable through .bind().
"""

import pytest
from pydantic_core import PydanticCustomError

from flync.model.flync_4_ecu import VirtualControllerInterface
from flync.model.flync_4_measurements import MeasurementSystem
from tests.error_assertions import assert_bind_error


def _system(interface_data: dict) -> MeasurementSystem:
    interface_data = {"name": "tap1", **interface_data}
    return MeasurementSystem(measurement_points=[interface_data])


def test_bind_rejects_unresolved_bus_ref(flync_model):
    """bind() must reject a bus_ref that does not resolve to a real CANBus/LINBus in the bound FLYNC model."""
    measurement_system = _system({"interface_id": 1, "payload_types": ["can"], "observes": ["NoSuchBus"]})

    with pytest.raises(PydanticCustomError) as exc_info:
        measurement_system.bind(flync_model)
    assert_bind_error(exc_info, "FLYNC-MEA-MAJ-REF-344", "observes unknown FLYNC element 'NoSuchBus'")


def test_bind_rejects_unresolved_ethernet_interface_ref(flync_model):
    """bind() must reject an ethernet_interface_ref that does not resolve to a real EthernetInterface in the bound FLYNC model."""
    measurement_system = _system({"interface_id": 1, "payload_types": ["ethernet"], "observes": ["no_such_iface"]})

    with pytest.raises(PydanticCustomError) as exc_info:
        measurement_system.bind(flync_model)
    assert_bind_error(exc_info, "FLYNC-MEA-MAJ-REF-344", "observes unknown FLYNC element 'no_such_iface'")


def test_bind_rejects_payload_type_bus_kind_mismatch(flync_model):
    """bind() must reject a bus_ref resolving to "BodyLIN", which is a real LINBus, not a CANBus.

    The reference is structurally valid for payload_type "can" (the field is set), but the
    resolved FLYNC object is the wrong kind - only .bind() can catch this.
    """
    measurement_system = _system({"interface_id": 1, "payload_types": ["can"], "observes": ["BodyLIN"]})

    with pytest.raises(PydanticCustomError) as exc_info:
        measurement_system.bind(flync_model)
    assert_bind_error(exc_info, "FLYNC-MEA-MAJ-COMP-345", "observes 'BodyLIN' (a LINBus), but declares no payload_type able to carry it")


def test_bind_rejects_can_fd_on_non_fd_enabled_bus(flync_model):
    """bind() must reject can_fd payload on a bus that exists as a CANBus but is not fd_enabled ("BodyCAN")."""
    measurement_system = _system({"interface_id": 1, "payload_types": ["can_fd"], "observes": ["BodyCAN"]})

    with pytest.raises(PydanticCustomError) as exc_info:
        measurement_system.bind(flync_model)
    assert_bind_error(exc_info, "FLYNC-MEA-MAJ-COMP-347", "declares payload_type 'can_fd' but bus 'BodyCAN' does not have fd_enabled=True")


def test_bind_rejects_unresolved_vlan_name(flync_model):
    measurement_system = _system({"interface_id": 1, "payload_types": ["ethernet"], "observes": ["no_such_vlan"]})

    with pytest.raises(PydanticCustomError) as exc_info:
        measurement_system.bind(flync_model)
    assert_bind_error(exc_info, "FLYNC-MEA-MAJ-REF-344", "observes unknown FLYNC element 'no_such_vlan'")


def test_bind_reports_a_colliding_vlan_name_as_ambiguous_not_unknown(flync_model):
    """A VLAN sub-interface name declared more than once anywhere in the FLYNC model has no single
    correct resolution, so it is excluded from the resolvable set entirely. Naming one must be
    reported as *ambiguous* - telling an author the name is "unknown" sends them looking for a typo
    that is not there.

    This is a live condition in the repo's own reference topology, not a constructed one:
    `hpc_c1_i1_viface2` is declared on both `hpc_controller1/.../hpc_c1_iface1` and
    `hpc_controller2/.../hpc_c2_iface1`.
    """
    measurement_system = _system({"interface_id": 1, "payload_types": ["ethernet"], "observes": ["hpc_c1_i1_viface2"]})

    with pytest.raises(PydanticCustomError) as exc_info:
        measurement_system.bind(flync_model)
    assert_bind_error(exc_info, "FLYNC-MEA-MAJ-REF-343", "observes 'hpc_c1_i1_viface2', which is ambiguous")


def test_bind_still_reports_a_genuinely_absent_vlan_name_as_unknown(flync_model):
    """The control for the test above: a name that appears nowhere is still "unknown"."""
    measurement_system = _system({"interface_id": 1, "payload_types": ["ethernet"], "observes": ["no_such_viface"]})

    with pytest.raises(PydanticCustomError) as exc_info:
        measurement_system.bind(flync_model)
    assert_bind_error(exc_info, "FLYNC-MEA-MAJ-REF-344", "observes unknown FLYNC element 'no_such_viface'")


def test_bind_resolves_a_vlan_sub_interface_by_name(flync_model):
    """A VLAN sub-interface name that is not ambiguous resolves to that VirtualControllerInterface
    directly, distinguishable from its physical parent interface."""
    measurement_system = _system({"interface_id": 1, "payload_types": ["ethernet"], "observes": ["z2_c1_i2_viface1"]})

    measurement_system.bind(flync_model)

    interface = measurement_system.measurement_points[0]
    assert isinstance(interface.observed[0], VirtualControllerInterface)
    assert interface.observed[0].name == "z2_c1_i2_viface1"
