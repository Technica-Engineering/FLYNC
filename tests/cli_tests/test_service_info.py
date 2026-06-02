"""Tests for the service_info CLI command and helper functions."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from flync_cli.commands.service_info import (
    add_consumers_and_providers,
    app,
    get_ctrl_for_address,
    print_table,
)

from .helpers import make_controller, make_ecu

runner = CliRunner()


def _make_ws():
    ws = MagicMock()
    ecu = make_ecu()
    ws.flync_model.ecus = [ecu]
    return ws, ecu


class TestGetCtrlForAddress:
    def test_returns_controller_name_for_matching_ip(self):
        ecu = make_ecu()
        ctrl = MagicMock()
        ctrl.name = "ETH_CTRL"
        ctrl.get_all_ips.return_value = ["192.168.1.1"]
        ecu.get_all_controllers.return_value = [ctrl]
        assert get_ctrl_for_address(ecu, "192.168.1.1") == "ETH_CTRL"

    def test_returns_zero_float_when_not_found(self):
        ecu = make_ecu()
        ctrl = MagicMock()
        ctrl.get_all_ips.return_value = ["10.0.0.1"]
        ecu.get_all_controllers.return_value = [ctrl]
        assert get_ctrl_for_address(ecu, "192.168.99.99") == 0.0


class TestAddConsumersAndProviders:
    def _make_socket(self, deployment_type, service_name, address="192.168.1.1", port=1234):
        socket = MagicMock()
        socket.endpoint_address = address
        socket.port_no = port
        dep = MagicMock()
        dep.root.deployment_type = deployment_type
        dep.root.service.name = service_name
        dep.root.instance_id = 1
        dep.root.major_version = 1
        socket.deployments = [dep]
        return socket

    def test_appends_consumer_for_matching_service(self):
        ecu = make_ecu()
        socket = self._make_socket("someip_consumer", "MyService")
        someip_list = []
        add_consumers_and_providers(socket, ecu, "MyService", someip_list)
        assert len(someip_list) == 1
        assert someip_list[0][2] == "Consumer"

    def test_appends_provider_for_matching_service(self):
        ecu = make_ecu()
        socket = self._make_socket("someip_provider", "MyService")
        someip_list = []
        add_consumers_and_providers(socket, ecu, "MyService", someip_list)
        assert len(someip_list) == 1
        assert someip_list[0][2] == "Provider"

    def test_does_not_append_for_different_service(self):
        ecu = make_ecu()
        socket = self._make_socket("someip_consumer", "OtherService")
        someip_list = []
        add_consumers_and_providers(socket, ecu, "MyService", someip_list)
        assert len(someip_list) == 0


class TestPrintTable:
    def test_runs_without_error(self):
        rows = [["ECU1", "CTRL1", "Consumer", "192.168.1.1", 1234, 1, 1]]
        print_table(rows, "MyService")

    def test_runs_with_empty_list(self):
        print_table([], "EmptyService")


class TestDisplayServiceInfoCommand:
    def test_exits_zero_with_service(self, tmp_path):
        ws, ecu = _make_ws()
        ecu.sockets = []
        with patch("flync_cli.commands.service_info.run_validation", return_value=ws):
            result = runner.invoke(app, ["MyService", str(tmp_path)])
        assert result.exit_code == 0

    def test_validate_failure_exits(self, tmp_path):
        with patch("flync_cli.commands.service_info.run_validation", return_value=None):
            result = runner.invoke(app, ["MyService", str(tmp_path)])
        assert result.exit_code != 0
