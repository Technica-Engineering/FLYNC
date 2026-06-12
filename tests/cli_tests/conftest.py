"""Shared pytest fixtures for flync_cli tests."""

from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from .helpers import make_ecu, make_interface


@pytest.fixture
def cli_runner():
    return CliRunner()


@pytest.fixture
def mock_ecu():
    return make_ecu()


@pytest.fixture
def mock_model(mock_ecu):
    model = MagicMock()
    model.ecus = [mock_ecu]
    model.get_all_ecus.return_value = [mock_ecu.name]
    model.get_ecu_by_name.return_value = mock_ecu
    service = MagicMock()
    service.name = "TestService"
    model.communication.someip_config.services = [service]
    model.topology.system_topology.connections = []
    return model


@pytest.fixture
def mock_workspace(mock_model):
    ws = MagicMock()
    ws.flync_model = mock_model
    return ws
