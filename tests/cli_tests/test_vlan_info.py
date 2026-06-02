"""Tests for the vlan_info CLI command and helper functions."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from flync_cli.commands.vlan_info import (
    app,
    check_switch_host_controller,
    get_interfaces_for_vlan,
    get_ips_per_interface,
    get_switch_ports_per_vlan,
    print_vlan_tables,
)

from .helpers import make_ecu, make_interface, make_virtual_iface

runner = CliRunner()


def _make_ws(ecu=None):
    ws = MagicMock()
    ecu = ecu or make_ecu()
    ws.flync_model.get_all_ecus.return_value = [ecu.name]
    ws.flync_model.get_ecu_by_name.return_value = ecu
    return ws, ecu


class TestGetIpsPerInterface:
    def test_returns_ips_for_matching_vlan(self):
        iface = make_interface(vlan_id=10, ips=["10.0.0.1"])
        result = get_ips_per_interface(iface, 10)
        assert "10.0.0.1" in result

    def test_returns_empty_for_nonmatching_vlan(self):
        iface = make_interface(vlan_id=10, ips=["10.0.0.1"])
        result = get_ips_per_interface(iface, 99)
        assert result == []


class TestGetInterfacesForVlan:
    def test_returns_matching_interfaces(self):
        iface = make_interface(vlan_id=20)
        result = get_interfaces_for_vlan([iface], 20)
        assert iface in result

    def test_returns_empty_for_no_match(self):
        iface = make_interface(vlan_id=20)
        result = get_interfaces_for_vlan([iface], 99)
        assert result == []


class TestGetSwitchPortsPerVlan:
    def test_returns_ports_for_matching_vlan(self):
        ecu = make_ecu()
        sw = MagicMock()
        vlan = MagicMock()
        vlan.id = 10
        vlan.ports = ["PORT0", "PORT1"]
        sw.vlans = [vlan]
        ecu.get_all_switches.return_value = [sw]
        result = get_switch_ports_per_vlan(ecu, 10)
        assert result == ["PORT0", "PORT1"]

    def test_returns_empty_for_no_match(self):
        ecu = make_ecu()
        sw = MagicMock()
        vlan = MagicMock()
        vlan.id = 10
        vlan.ports = ["PORT0"]
        sw.vlans = [vlan]
        ecu.get_all_switches.return_value = [sw]
        result = get_switch_ports_per_vlan(ecu, 99)
        assert result == []


class TestCheckSwitchHostController:
    def test_returns_name_and_ips_when_present(self):
        ecu = make_ecu()
        sw = MagicMock()
        host_ctrl = make_interface(vlan_id=10, ips=["192.168.1.100"])
        host_ctrl.name = "HOST_CTRL"
        sw.host_controller = host_ctrl
        ecu.get_all_switches.return_value = [sw]
        name, ips = check_switch_host_controller(ecu, 10)
        assert name == "HOST_CTRL"
        assert "192.168.1.100" in ips

    def test_returns_none_when_no_ips(self):
        ecu = make_ecu()
        sw = MagicMock()
        host_ctrl = make_interface(vlan_id=99)
        host_ctrl.name = "HOST_CTRL"
        sw.host_controller = host_ctrl
        ecu.get_all_switches.return_value = [sw]
        name, ips = check_switch_host_controller(ecu, 10)
        assert name is None

    def test_returns_none_when_no_host_controller(self):
        ecu = make_ecu()
        sw = MagicMock()
        sw.host_controller = None
        ecu.get_all_switches.return_value = [sw]
        name, ips = check_switch_host_controller(ecu, 10)
        assert name is None


class TestPrintVlanTables:
    def test_runs_without_error(self):
        ecu = make_ecu()
        model = MagicMock()
        model.get_ecu_by_name.return_value = ecu
        print_vlan_tables([ecu.name], 10, model)


class TestDisplayVlanInfoCommand:
    def test_exits_zero_without_ecu_name(self, tmp_path):
        ws, _ = _make_ws()
        with patch("flync_cli.commands.vlan_info.run_validation", return_value=ws):
            result = runner.invoke(app, ["10", str(tmp_path)])
        assert result.exit_code == 0

    def test_exits_zero_with_ecu_name(self, tmp_path):
        ws, ecu = _make_ws()
        with patch("flync_cli.commands.vlan_info.run_validation", return_value=ws):
            result = runner.invoke(app, ["10", str(tmp_path), "--ecu-name", ecu.name])
        assert result.exit_code == 0

    def test_validate_failure_exits(self, tmp_path):
        with patch("flync_cli.commands.vlan_info.run_validation", return_value=None):
            result = runner.invoke(app, ["10", str(tmp_path)])
        assert result.exit_code != 0

    def test_invalid_vlan_id_rejected(self, tmp_path):
        result = runner.invoke(app, ["not-an-int", str(tmp_path)])
        assert result.exit_code != 0
