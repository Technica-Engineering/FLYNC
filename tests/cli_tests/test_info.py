"""Tests for the info CLI command and its helper functions."""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from flync_cli.commands.info import (
    _COL_CONTROLLER_NAME,
    _COL_IP_ADDRESS,
    _COL_PORT_NAME,
    _COL_SWITCH_NAME,
    app,
    print_ips,
    print_list_ecu,
    print_list_ecu_wise,
    print_list_per_ecu,
)

from .helpers import make_ecu

runner = CliRunner()


def _make_ws():
    ws = MagicMock()
    ecu = make_ecu()
    ws.flync_model.get_all_ecus.return_value = [ecu.name]
    ws.flync_model.get_ecu_by_name.return_value = ecu
    ws.flync_model.ecus = [ecu]
    service = MagicMock()
    service.name = "TestService"
    ws.flync_model.communication.someip_config.services = [service]
    return ws, ecu


class TestPrintListEcu:
    def test_runs_without_error(self):
        print_list_ecu(["A", "B"], "Name")

    def test_empty_list(self):
        print_list_ecu([], "Name")


class TestPrintListEcuWise:
    def test_controllers_tag(self):
        print_list_ecu_wise([make_ecu()], _COL_CONTROLLER_NAME)

    def test_switches_tag(self):
        print_list_ecu_wise([make_ecu()], _COL_SWITCH_NAME)

    def test_ports_tag(self):
        print_list_ecu_wise([make_ecu()], _COL_PORT_NAME)

    def test_unknown_tag_uses_empty_items(self):
        print_list_ecu_wise([make_ecu()], "UnknownTag")


class TestPrintListPerEcu:
    def test_controllers(self):
        model = MagicMock()
        ecu = make_ecu()
        model.get_ecu_by_name.return_value = ecu
        print_list_per_ecu(model, _COL_CONTROLLER_NAME, ecu.name)

    def test_switches(self):
        model = MagicMock()
        ecu = make_ecu()
        model.get_ecu_by_name.return_value = ecu
        print_list_per_ecu(model, _COL_SWITCH_NAME, ecu.name)

    def test_ports(self):
        model = MagicMock()
        ecu = make_ecu()
        model.get_ecu_by_name.return_value = ecu
        print_list_per_ecu(model, _COL_PORT_NAME, ecu.name)

    def test_ips(self):
        model = MagicMock()
        ecu = make_ecu()
        model.get_ecu_by_name.return_value = ecu
        print_list_per_ecu(model, _COL_IP_ADDRESS, ecu.name)

    def test_missing_ecu_exits(self):
        model = MagicMock()
        model.get_ecu_by_name.return_value = None
        with pytest.raises(SystemExit):
            print_list_per_ecu(model, _COL_CONTROLLER_NAME, "MISSING")


class TestPrintIps:
    def test_all_ecus(self):
        model = MagicMock()
        ecu = make_ecu()
        model.get_all_ecus.return_value = [ecu.name]
        model.get_ecu_by_name.return_value = ecu
        print_ips(model, ecu_name=None)

    def test_specific_ecu(self):
        model = MagicMock()
        ecu = make_ecu()
        model.get_ecu_by_name.return_value = ecu
        print_ips(model, ecu_name=ecu.name)


class TestDisplayInfoCommand:
    def test_list_ecus_exits_zero(self, tmp_path):
        ws, _ = _make_ws()
        with patch("flync_cli.commands.info.run_validation", return_value=ws):
            result = runner.invoke(app, ["list-ecus", str(tmp_path)])
        assert result.exit_code == 0

    def test_list_controllers_exits_zero(self, tmp_path):
        ws, _ = _make_ws()
        with patch("flync_cli.commands.info.run_validation", return_value=ws):
            result = runner.invoke(app, ["list-controllers", str(tmp_path)])
        assert result.exit_code == 0

    def test_list_switches_exits_zero(self, tmp_path):
        ws, _ = _make_ws()
        with patch("flync_cli.commands.info.run_validation", return_value=ws):
            result = runner.invoke(app, ["list-switches", str(tmp_path)])
        assert result.exit_code == 0

    def test_list_ports_exits_zero(self, tmp_path):
        ws, _ = _make_ws()
        with patch("flync_cli.commands.info.run_validation", return_value=ws):
            result = runner.invoke(app, ["list-ports", str(tmp_path)])
        assert result.exit_code == 0

    def test_list_ips_exits_zero(self, tmp_path):
        ws, _ = _make_ws()
        with patch("flync_cli.commands.info.run_validation", return_value=ws):
            result = runner.invoke(app, ["list-ips", str(tmp_path)])
        assert result.exit_code == 0

    def test_list_services_exits_zero(self, tmp_path):
        ws, _ = _make_ws()
        with patch("flync_cli.commands.info.run_validation", return_value=ws):
            result = runner.invoke(app, ["list-services", str(tmp_path)])
        assert result.exit_code == 0

    def test_invalid_component_rejected(self, tmp_path):
        result = runner.invoke(app, ["not-a-component", str(tmp_path)])
        assert result.exit_code != 0

    def test_validate_failure_exits(self, tmp_path):
        with patch("flync_cli.commands.info.run_validation", return_value=None):
            result = runner.invoke(app, ["list-ecus", str(tmp_path)])
        assert result.exit_code != 0

    def test_list_controllers_with_ecu_name(self, tmp_path):
        ws, ecu = _make_ws()
        with patch("flync_cli.commands.info.run_validation", return_value=ws):
            result = runner.invoke(app, ["list-controllers", str(tmp_path), "--ecu-name", ecu.name])
        assert result.exit_code == 0

    def test_list_switches_with_ecu_name(self, tmp_path):
        ws, ecu = _make_ws()
        with patch("flync_cli.commands.info.run_validation", return_value=ws):
            result = runner.invoke(app, ["list-switches", str(tmp_path), "--ecu-name", ecu.name])
        assert result.exit_code == 0

    def test_list_ports_with_ecu_name(self, tmp_path):
        ws, ecu = _make_ws()
        with patch("flync_cli.commands.info.run_validation", return_value=ws):
            result = runner.invoke(app, ["list-ports", str(tmp_path), "--ecu-name", ecu.name])
        assert result.exit_code == 0

    def test_list_ips_with_ecu_name(self, tmp_path):
        ws, ecu = _make_ws()
        with patch("flync_cli.commands.info.run_validation", return_value=ws):
            result = runner.invoke(app, ["list-ips", str(tmp_path), "--ecu-name", ecu.name])
        assert result.exit_code == 0
