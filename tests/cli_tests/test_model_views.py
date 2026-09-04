"""Tests for the shared FLYNC model traversal helpers used by ``flync info`` reports.

The ``ecu``/``model`` doubles below are ``MagicMock(spec=...)`` - these tests exercise the
traversal helpers' duck-typed walk over ``.controllers``/``.get_all_switches()``/``.ecus``, not
ECU-level cross-validation (ports wired to every switch port, one internal topology entry per
interface), which is a different concern already covered in ``tests/system_test/model/``.
Everything the doubles' attributes point to - controllers, switches, interfaces, virtual
interfaces, sockets, deployments - is a real, independently validated Pydantic model, so a field
rename in any of them fails these tests exactly as it would fail the real CLI.
"""

from unittest.mock import MagicMock

from flync.core.datatypes.ipaddress import IPv4AddressEntry, IPv6AddressEntry
from flync.model.flync_4_ecu.controller import ComputeNodes
from flync.model.flync_4_ecu.ecu import ECU
from flync.model.flync_4_ecu.sockets import SocketUDP
from flync.model.flync_4_signal.pdu_deployment import PDUSender
from flync.model.flync_4_someip.deployment import SOMEIPServiceProvider
from flync.model.flync_model import FLYNCModel
from flync_cli.utils.model_views import (
    ecus_for,
    iter_ecu_controllers,
    iter_ecu_interfaces,
    iter_virtual_interfaces,
    require_ecu,
    socket_endpoints_for_ecu,
    someip_deployments_by_service,
    subnet_for,
    vlan_members,
)
from tests.cli_tests.cli_assertions import assert_exits
from tests.model_builders import (
    make_controller,
    make_eth_interface,
    make_ipv4_address,
    make_socket_container,
    make_switch,
    make_vci,
    make_vlan_entry,
)


def _ecu_double(*, controllers=None, switches=None) -> ECU:
    """A duck-typed ECU stand-in for the traversal helpers - see the module docstring."""
    ecu = MagicMock(spec=ECU)
    ecu.controllers = controllers if controllers is not None else [make_controller()]
    ecu.get_all_switches.return_value = switches or []
    return ecu


def _model_double(*, ecus: list) -> FLYNCModel:
    """A duck-typed FLYNCModel stand-in exposing only ``.ecus`` and ``.get_ecu_by_name``."""
    model = MagicMock(spec=FLYNCModel)
    model.ecus = ecus
    return model


class TestRequireEcu:
    def test_returns_matching_ecu(self):
        ecu = _ecu_double()
        model = _model_double(ecus=[ecu])
        model.get_ecu_by_name.return_value = ecu
        assert require_ecu(model, "ECU1") is ecu

    def test_exits_when_missing(self):
        model = _model_double(ecus=[])
        model.get_ecu_by_name.return_value = None
        with assert_exits(1):
            require_ecu(model, "MISSING")


class TestEcusFor:
    def test_returns_all_ecus_without_filter(self):
        ecus = [_ecu_double(), _ecu_double()]
        model = _model_double(ecus=ecus)
        assert ecus_for(model, None) == ecus

    def test_returns_single_ecu_with_filter(self):
        ecu = _ecu_double()
        model = _model_double(ecus=[ecu])
        model.get_ecu_by_name.return_value = ecu
        assert ecus_for(model, "A") == [ecu]


class TestIterEcuControllers:
    def test_includes_controllers_and_switch_host_controllers(self):
        ctrl = make_controller(name="C1")
        host = make_controller(name="HOST")
        switch = make_switch(host_controller=host)
        ecu = _ecu_double(controllers=[ctrl], switches=[switch])
        assert list(iter_ecu_controllers(ecu)) == [ctrl, host]

    def test_deduplicates_a_controller_that_is_also_a_host_controller(self):
        ctrl = make_controller(name="C1")
        switch = make_switch(host_controller=ctrl)
        ecu = _ecu_double(controllers=[ctrl], switches=[switch])
        assert list(iter_ecu_controllers(ecu)) == [ctrl]

    def test_skips_switches_without_a_host_controller(self):
        ctrl = make_controller(name="C1")
        switch = make_switch(host_controller=None)
        ecu = _ecu_double(controllers=[ctrl], switches=[switch])
        assert list(iter_ecu_controllers(ecu)) == [ctrl]


class TestIterEcuInterfaces:
    def test_yields_controller_and_interface_pairs(self):
        iface = make_eth_interface(name="ETH0")
        ctrl = make_controller(name="C1", ethernet_interfaces=[iface])
        ecu = _ecu_double(controllers=[ctrl])
        assert list(iter_ecu_interfaces(ecu)) == [(ctrl, iface)]


class TestIterVirtualInterfaces:
    def test_yields_direct_vcis_with_the_interface_mac(self):
        vci = make_vci()
        cfg = make_eth_interface(mac="aa:bb:cc:dd:ee:01", vcis=[vci]).interface_config
        assert list(iter_virtual_interfaces(cfg)) == [(vci, "aa:bb:cc:dd:ee:01")]

    def test_yields_compute_node_vcis_with_the_node_mac(self):
        node_vci = make_vci(name="node_vi")
        node = ComputeNodes(name="node0", mac_address="11:22:33:44:55:66", virtual_interfaces=[node_vci])
        cfg = make_eth_interface(mac="aa:bb:cc:dd:ee:01", vcis=[], compute_nodes=[node]).interface_config
        assert list(iter_virtual_interfaces(cfg)) == [(node_vci, "11:22:33:44:55:66")]


class TestSocketEndpointsForEcu:
    def test_matches_socket_container_to_the_vlan_scoped_vci(self):
        vci = make_vci(vlanid=20, name="vi20")
        container = make_socket_container(vlan_id=20, sockets=[SocketUDP(name="s0", endpoint_address="10.0.0.1", port_no=1234)])
        iface = make_eth_interface(mac="aa:bb:cc:dd:ee:01", vcis=[vci], sockets=[container])
        ctrl = make_controller(ethernet_interfaces=[iface])
        ecu = _ecu_double(controllers=[ctrl])

        endpoints = list(socket_endpoints_for_ecu(ecu))

        assert len(endpoints) == 1
        assert endpoints[0].vci is vci
        assert endpoints[0].mac == "aa:bb:cc:dd:ee:01"
        assert endpoints[0].socket is container.sockets[0]

    def test_falls_back_to_interface_mac_when_no_vci_matches_the_vlan(self):
        container = make_socket_container(vlan_id=20, sockets=[SocketUDP(name="s0", endpoint_address="10.0.0.1", port_no=1234)])
        iface = make_eth_interface(mac="aa:bb:cc:dd:ee:01", vcis=[make_vci(vlanid=99)], sockets=[container])
        ctrl = make_controller(ethernet_interfaces=[iface])
        ecu = _ecu_double(controllers=[ctrl])

        endpoints = list(socket_endpoints_for_ecu(ecu))

        assert endpoints[0].vci is None
        assert endpoints[0].mac == "aa:bb:cc:dd:ee:01"

    def test_empty_ecu_yields_nothing(self):
        iface = make_eth_interface(sockets=[])
        ctrl = make_controller(ethernet_interfaces=[iface])
        ecu = _ecu_double(controllers=[ctrl])
        assert list(socket_endpoints_for_ecu(ecu)) == []


class TestVlanMembers:
    def test_groups_controller_interfaces_by_vlan(self):
        vci = make_vci(vlanid=10, addresses=[make_ipv4_address(address="10.0.0.1")])
        iface = make_eth_interface(vcis=[vci])
        ctrl = make_controller(ethernet_interfaces=[iface])
        ecu = _ecu_double(controllers=[ctrl])
        model = _model_double(ecus=[ecu])

        grouped = vlan_members(model)

        assert grouped[10][0].ecu is ecu
        assert grouped[10][0].component_type == "Controller Interface"
        assert grouped[10][0].ips == ["10.0.0.1/24"]

    def test_reports_every_switch_and_every_port_no_early_return(self):
        """Regression: the old ``get_switch_ports_per_vlan`` returned inside its loop, dropping every switch but the first."""
        from tests.model_builders import make_switch_port

        switch_a = make_switch(name="SWA", ports=[make_switch_port(name="PA0")], vlans=[make_vlan_entry(vlan_id=10, ports=("PA0",))])
        switch_b = make_switch(name="SWB", ports=[make_switch_port(name="PB0")], vlans=[make_vlan_entry(vlan_id=10, ports=("PB0",))])
        ecu = _ecu_double(controllers=[], switches=[switch_a, switch_b])
        model = _model_double(ecus=[ecu])

        grouped = vlan_members(model)
        port_names = {m.component_name for m in grouped[10]}

        assert port_names == {"PA0", "PB0"}

    def test_includes_switch_host_controller_interfaces(self):
        vci = make_vci(vlanid=30, addresses=[make_ipv4_address(address="10.0.30.9")])
        host = make_controller(name="HOST", ethernet_interfaces=[make_eth_interface(vcis=[vci])])
        switch = make_switch(host_controller=host)
        ecu = _ecu_double(controllers=[], switches=[switch])
        model = _model_double(ecus=[ecu])

        grouped = vlan_members(model)

        assert grouped[30][0].ips == ["10.0.30.9/24"]


class TestSomeipDeploymentsByService:
    def test_groups_by_service_and_major_version(self):
        provider = SOMEIPServiceProvider(service=0x0101, major_version=1, instance_id=5, someip_sd_timings_profile="server_default")
        sock = SocketUDP(name="s0", endpoint_address="10.0.0.1", port_no=1234, deployments=[provider])
        container = make_socket_container(sockets=[sock])
        iface = make_eth_interface(sockets=[container])
        ctrl = make_controller(ethernet_interfaces=[iface])
        ecu = _ecu_double(controllers=[ctrl])
        model = _model_double(ecus=[ecu])

        grouped = someip_deployments_by_service(model)

        assert (0x0101, 1) in grouped
        endpoint, dep = grouped[(0x0101, 1)][0]
        assert dep is provider
        assert endpoint.socket is sock

    def test_ignores_non_someip_deployments(self):
        sock = SocketUDP(name="s0", endpoint_address="10.0.0.1", port_no=1234, deployments=[PDUSender(pdu_ref="SomePdu")])
        container = make_socket_container(sockets=[sock])
        iface = make_eth_interface(sockets=[container])
        ctrl = make_controller(ethernet_interfaces=[iface])
        ecu = _ecu_double(controllers=[ctrl])
        model = _model_double(ecus=[ecu])

        assert someip_deployments_by_service(model) == {}


class TestSubnetFor:
    def test_ipv4_subnet_from_dotted_netmask(self):
        entry = IPv4AddressEntry(address="10.0.20.5", ipv4netmask="255.255.255.0")
        assert subnet_for(entry) == "10.0.20.0/24"

    def test_ipv6_subnet_from_prefix_length(self):
        entry = IPv6AddressEntry(address="2001:db8::5", ipv6prefix=64)
        assert subnet_for(entry) == "2001:db8::/64"
