"""Component identity and path helpers behind the multicast path computation."""

from flync.core.utils.base_utils import check_obj_in_list
from flync.core.utils.multicast.multicast_paths import compute_path
from tests.model_builders import make_ecu_with_switch, make_ethernet_ecu


def test_same_controller_interface_is_found():
    ecu = make_ethernet_ecu()
    iface = ecu.get_all_interfaces()[0]

    assert check_obj_in_list(iface, [None, iface])


def test_interface_of_another_controller_is_not_the_same_component():
    iface_a = make_ethernet_ecu(name="ECU_A").get_all_interfaces()[0]
    iface_b = make_ethernet_ecu(name="ECU_B").get_all_interfaces()[0]
    iface_b.get_controller().name = "OTHER_CTRL"

    assert not check_obj_in_list(iface_a, [iface_b])


def test_same_switch_port_and_ecu_port_are_found():
    ecu = make_ecu_with_switch()
    switch_port = ecu.get_all_switch_ports()[0]
    ecu_port = ecu.ports[0]

    assert check_obj_in_list(switch_port, [ecu_port, switch_port])
    assert check_obj_in_list(ecu_port, [switch_port, ecu_port])


def test_components_of_different_kinds_never_match():
    ecu = make_ecu_with_switch()

    assert not check_obj_in_list(ecu.ports[0], ecu.get_all_switch_ports())


def test_none_is_never_found():
    assert not check_obj_in_list(None, [None])


def test_path_without_sending_interface_is_empty():
    assert compute_path(10, None) == ([], {})
