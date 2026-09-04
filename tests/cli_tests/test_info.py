"""Tests for the ``flync info`` command group."""

from unittest.mock import MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

import flync_cli.commands.info as info
from flync.model.flync_4_ecu.ecu import ECU
from flync.model.flync_4_ecu.sockets import SocketUDP
from flync.model.flync_4_someip.deployment import SOMEIPServiceProvider
from flync.model.flync_model import FLYNCModel
from flync.sdk.workspace.flync_workspace import FLYNCWorkspace
from flync_cli.commands.info import (
    _parse_service_id,
    _resolve_service_by_name,
    _show_controllers,
    _show_ecus,
    _show_instances,
    _show_ip,
    _show_ports,
    _show_services,
    _show_sockets,
    _show_switches,
    _show_vlans,
    app,
)
from tests.cli_tests.cli_assertions import assert_cli_error, assert_cli_ok, assert_exits
from tests.cli_tests.rich_output import capture
from tests.model_builders import (
    make_controller,
    make_ecu_metadata,
    make_ecu_with_switch,
    make_eth_interface,
    make_ethernet_ecu,
    make_ipv4_address,
    make_model,
    make_socket_container,
    make_someip_service,
    make_vci,
)

runner = CliRunner()


def _empty_ecu(name: str = "A") -> ECU:
    """An ECU with no controllers, switches, or ports - the "nothing configured" case every report handles."""
    return ECU(name=name, controllers=[], ecu_metadata=make_ecu_metadata())


def _workspace(model: FLYNCModel) -> FLYNCWorkspace:
    """A duck-typed FLYNCWorkspace stand-in exposing only ``.flync_model`` - the CLI reads nothing else off it."""
    ws = MagicMock(spec=FLYNCWorkspace)
    ws.flync_model = model
    return ws


def _deployed_someip_model(*, service_id: int = 0x0101, major_version: int = 1) -> FLYNCModel:
    """A duck-typed FLYNCModel stand-in exposing a SOME/IP service catalog entry and a real deployed provider.

    Fully cross-validating a deployed SOME/IP service through ``FLYNCModel`` requires wiring an
    ``SDConfig``/``SOMEIPTimingProfile`` unrelated to what ``_show_services``/``_show_instances``
    test (rendering whatever the model's public API returns) - so only the top-level model is a
    spec'd double; the ECU/socket/deployment tree underneath is entirely real.
    """
    provider = SOMEIPServiceProvider(service=service_id, major_version=major_version, instance_id=5, someip_sd_timings_profile="server_default")
    sock = SocketUDP(name="s0", endpoint_address="10.0.20.5", port_no=30500, deployments=[provider])
    vci = make_vci(vlanid=10, addresses=[make_ipv4_address(address="10.0.20.5")])
    container = make_socket_container(vlan_id=10, sockets=[sock])
    iface = make_eth_interface(mac="aa:bb:cc:dd:ee:03", vcis=[vci], sockets=[container])
    ecu = make_ethernet_ecu(name="ECU1", controllers=[make_controller(name="CTRL0", ethernet_interfaces=[iface])])

    svc = make_someip_service(name="MyService", service_id=service_id, major_version=major_version)
    model = MagicMock(spec=FLYNCModel)
    model.ecus = [ecu]
    model.get_all_someip_services.return_value = [svc]
    model.get_someip_services_by_identity.return_value = {(service_id, major_version): svc}
    return model


class TestShowEcus:
    def test_lists_every_ecu_name(self):
        model = make_model(ecus=[make_ethernet_ecu(name="A"), _empty_ecu(name="B")])
        with capture(info) as out:
            _show_ecus(model)
        assert out.rows == [["Num.", "ECU Name"], ["1", "A"], ["2", "B"]]


class TestShowControllersAndSwitches:
    def test_controllers_all_ecus(self):
        model = make_model()
        with capture(info) as out:
            _show_controllers(model, ecu_name=None)
        assert out.rows == [["Num.", "ECU Name", "Controller Name"], ["1", "ECU1", "CTRL0"]]

    def test_controllers_one_ecu(self):
        model = make_model()
        with capture(info) as out:
            _show_controllers(model, ecu_name="ECU1")
        assert out.rows == [["ECU Name", "Controller Name"], ["ECU1", "CTRL0"]]

    def test_controllers_missing_ecu_exits(self):
        model = make_model()
        with assert_exits(1):
            _show_controllers(model, ecu_name="MISSING")

    def test_switches_all_ecus(self):
        model = make_model(ecus=[make_ecu_with_switch()])
        with capture(info) as out:
            _show_switches(model, ecu_name=None)
        assert out.rows == [["Num.", "ECU Name", "Switch Name"], ["1", "ECU1", "SW0"]]


class TestShowPorts:
    def test_groups_by_ecu(self):
        ecu = make_ethernet_ecu(
            name="A",
            controllers=[
                make_controller(name="C1", ethernet_interfaces=[make_eth_interface(name="ETH0", mac="aa:bb:cc:dd:ee:01")]),
                make_controller(name="C2", ethernet_interfaces=[make_eth_interface(name="ETH0", mac="aa:bb:cc:dd:ee:02")]),
            ],
        )
        model = make_model(ecus=[ecu])
        with capture(info) as out:
            _show_ports(model, ecu_name=None)
        assert out.rows == [["Port Name"], ["C1_ETH0_port"], ["C2_ETH0_port"]]

    def test_ecu_with_no_ports_prints_message(self):
        model = make_model(ecus=[_empty_ecu()])
        with capture(info) as out:
            _show_ports(model, ecu_name="A")
        assert "ECU 'A' has no ports configured" in out.plain

    def test_ecu_without_ports_is_skipped_silently_when_unfiltered(self):
        model = make_model(ecus=[_empty_ecu()])
        with capture(info) as out:
            _show_ports(model, ecu_name=None)
        assert out.plain == ""


class TestShowIp:
    def test_lists_ip_vlan_and_subnet(self):
        model = make_model()
        with capture(info) as out:
            _show_ip(model, ecu_name=None)
        assert out.rows[1] == ["ECU1", "CTRL0", "ETH0", "vi10", "10", "10.0.20.5/24"]

    def test_empty_workspace_prints_message(self):
        model = make_model(ecus=[_empty_ecu()])
        with capture(info) as out:
            _show_ip(model, ecu_name=None)
        assert "No IP addresses configured in this workspace" in out.plain


class TestShowSockets:
    def test_groups_by_vlan_for_one_ecu(self):
        vci10 = make_vci(name="vi10", vlanid=10, addresses=[make_ipv4_address(address="10.0.0.10")])
        vci20 = make_vci(name="vi20", vlanid=20, addresses=[make_ipv4_address(address="10.0.0.20")])
        c10 = make_socket_container(vlan_id=10, sockets=[SocketUDP(name="s10", endpoint_address="10.0.0.10", port_no=30500)])
        c20 = make_socket_container(vlan_id=20, sockets=[SocketUDP(name="s20", endpoint_address="10.0.0.20", port_no=30510)])
        iface = make_eth_interface(mac="aa:bb:cc:dd:ee:01", vcis=[vci10, vci20], sockets=[c10, c20])
        ecu = make_ethernet_ecu(name="A", controllers=[make_controller(ethernet_interfaces=[iface])])
        model = make_model(ecus=[ecu])

        with capture(info) as out:
            _show_sockets(model, ecu_name="A")

        assert out.tables == [
            [
                ["Interface", "Virtual Interface", "MAC", "IP", "Protocol", "Port", "Socket"],
                ["ETH0", "vi10", "aa:bb:cc:dd:ee:01", "10.0.0.10/24", "UDP", "30500", "s10"],
            ],
            [
                ["Interface", "Virtual Interface", "MAC", "IP", "Protocol", "Port", "Socket"],
                ["ETH0", "vi20", "aa:bb:cc:dd:ee:01", "10.0.0.20/24", "UDP", "30510", "s20"],
            ],
        ]

    def test_ecu_with_no_sockets_prints_message(self):
        model = make_model(ecus=[make_ethernet_ecu(name="A")])
        with capture(info) as out:
            _show_sockets(model, ecu_name="A")
        assert "ECU 'A' has no socket endpoints configured" in out.plain

    def test_workspace_with_no_sockets_prints_message_when_unfiltered(self):
        model = make_model(ecus=[make_ethernet_ecu(name="A")])
        with capture(info) as out:
            _show_sockets(model, ecu_name=None)
        assert "No socket endpoints configured in this workspace" in out.plain


class TestShowServicesAndInstances:
    def test_no_someip_config_prints_message(self):
        model = MagicMock(spec=FLYNCModel)
        model.get_all_someip_services.return_value = []
        with capture(info) as out:
            _show_services(model)
        assert "No SOME/IP configuration" in out.plain

    def test_lists_services(self):
        model = _deployed_someip_model()
        with capture(info) as out:
            _show_services(model)
        assert out.rows[1] == ["MyService", "0x0101", "1", "ECU1", "-"]

    def test_instances_found(self):
        model = _deployed_someip_model()
        with capture(info) as out:
            _show_instances(model, 0x0101, 1)
        assert out.rows[1] == ["ECU1", "CTRL0", "ETH0", "Provider", "10", "10.0.20.5/24", "30500", "5"]

    def test_instances_not_found_lists_alternatives(self):
        model = _deployed_someip_model()
        with capture(info) as out, assert_exits(1):
            _show_instances(model, 0xDEAD, 9)
        assert "No SOME/IP service" in out.plain
        assert "MyService" in out.plain

    def test_instances_not_found_with_no_services_at_all(self):
        model = MagicMock(spec=FLYNCModel)
        model.get_all_someip_services.return_value = []
        model.get_someip_services_by_identity.return_value = {}
        with assert_exits(1):
            _show_instances(model, 0x0101, 1)


class TestParseServiceId:
    @pytest.mark.parametrize("raw, expected", [("257", 257), ("0x0101", 0x0101)], ids=["decimal", "hex"])
    def test_accepts_decimal_and_hex(self, raw, expected):
        assert _parse_service_id(raw) == expected

    def test_rejects_garbage(self):
        with pytest.raises(typer.BadParameter):
            _parse_service_id("not-a-number")


class TestResolveServiceByName:
    def test_resolves_by_name(self):
        model = MagicMock(spec=FLYNCModel)
        model.get_all_someip_services.return_value = [make_someip_service(name="MyService", service_id=0x0101, major_version=1)]
        assert _resolve_service_by_name(model, "MyService") == (0x0101, 1)

    def test_exits_when_not_found(self):
        model = MagicMock(spec=FLYNCModel)
        model.get_all_someip_services.return_value = []
        with assert_exits(1):
            _resolve_service_by_name(model, "MyService")


class TestShowVlans:
    def test_groups_by_vlan(self):
        model = make_model()
        with capture(info) as out:
            _show_vlans(model, ecu_name=None, vlan_id=None)
        assert out.rows[1] == ["ECU1", "CTRL0/ETH0", "Controller Interface", "10.0.20.5/24"]

    def test_filters_to_one_vlan(self):
        model = make_model()
        with capture(info) as out:
            _show_vlans(model, ecu_name=None, vlan_id=10)
        assert out.rows[1] == ["ECU1", "CTRL0/ETH0", "Controller Interface", "10.0.20.5/24"]

    def test_unknown_vlan_exits(self):
        model = make_model()
        with assert_exits(1):
            _show_vlans(model, ecu_name=None, vlan_id=9999)

    def test_no_vlans_at_all_prints_message(self):
        model = make_model(ecus=[_empty_ecu()])
        with capture(info) as out:
            _show_vlans(model, ecu_name=None, vlan_id=None)
        assert "No VLANs configured" in out.plain


class TestInfoCommandsCli:
    """Thin wiring tests over ``load_workspace``: the reports' own content is covered by the ``_show_*`` tests above."""

    @pytest.mark.parametrize(
        "args",
        [
            ["ecus"],
            ["controllers"],
            ["switches"],
            ["ports"],
            ["ip"],
            ["sockets"],
            ["services"],
        ],
        ids=["ecus", "controllers", "switches", "ports", "ip", "sockets", "services"],
    )
    def test_exits_zero(self, tmp_path, args):
        ws = _workspace(make_model())
        with patch("flync_cli.commands.info.load_workspace", return_value=ws):
            result = runner.invoke(app, [*args, str(tmp_path)])
        assert_cli_ok(result)

    def test_ecu_name_filter(self, tmp_path):
        ws = _workspace(make_model())
        with patch("flync_cli.commands.info.load_workspace", return_value=ws):
            result = runner.invoke(app, ["controllers", str(tmp_path), "--ecu-name", "ECU1"])
        assert_cli_ok(result)

    def test_unknown_ecu_name_exits_nonzero(self, tmp_path):
        ws = _workspace(make_model())
        with patch("flync_cli.commands.info.load_workspace", return_value=ws):
            result = runner.invoke(app, ["controllers", str(tmp_path), "--ecu-name", "does-not-exist"])
        assert_cli_error(result, 1, "ECU 'does-not-exist' does not exist")

    def test_instances_command(self, tmp_path):
        ws = _workspace(_deployed_someip_model())
        with patch("flync_cli.commands.info.load_workspace", return_value=ws):
            result = runner.invoke(app, ["instances", "0x0101", "1", str(tmp_path)])
        assert_cli_ok(result)

    def test_instances_command_bad_id_exits_nonzero(self, tmp_path):
        ws = _workspace(make_model())
        with patch("flync_cli.commands.info.load_workspace", return_value=ws):
            result = runner.invoke(app, ["instances", "not-an-int", "1", str(tmp_path)])
        assert result.exit_code == 2  # a Typer/Click argument-parsing failure, distinct from a command-level typer.Exit

    def test_vlans_command(self, tmp_path):
        ws = _workspace(make_model())
        with patch("flync_cli.commands.info.load_workspace", return_value=ws):
            result = runner.invoke(app, ["vlans", str(tmp_path)])
        assert_cli_ok(result)

    def test_validate_failure_exits(self, tmp_path):
        with patch("flync_cli.commands.info.load_workspace", side_effect=typer.Exit(code=1)):
            result = runner.invoke(app, ["ecus", str(tmp_path)])
        assert_cli_error(result, 1, "")


class TestDeprecatedInfoAliases:
    @pytest.mark.parametrize(
        "old, new",
        [
            ("list-ecus", "ecus"),
            ("list-controllers", "controllers"),
            ("list-switches", "switches"),
            ("list-ports", "ports"),
            ("list-ips", "ip"),
            ("list-sockets", "sockets"),
            ("list-services", "services"),
        ],
    )
    def test_alias_runs_and_warns(self, tmp_path, old, new):
        ws = _workspace(make_model())
        with patch("flync_cli.commands.info.load_workspace", return_value=ws):
            result = runner.invoke(app, [old, str(tmp_path)])
        assert_cli_ok(result)
        assert new in result.output

    def test_aliases_are_hidden_from_help(self):
        result = runner.invoke(app, ["--help"])
        for old in ("list-ecus", "list-controllers", "list-switches", "list-ports", "list-ips", "list-sockets", "list-services"):
            assert old not in result.output
