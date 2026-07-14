from pathlib import Path

from flync.sdk.context.diagnostics_result import WorkspaceState
from flync.sdk.workspace.flync_workspace import FLYNCWorkspace


def update_yaml_content(yaml_file, old_text, new_text):
    with open(yaml_file, "r+") as file:
        content = file.read()
        content = content.replace(old_text, new_text)
        file.seek(0)
        file.write(content)
        file.truncate()


def append_yaml_content(yaml_file, new_text):
    with open(yaml_file, "a") as file:
        file.write(new_text)


def model_has_socket(loaded_ws: FLYNCWorkspace):
    return any(
        address.sockets
        for ecu in loaded_ws.flync_model.ecus
        for controller in ecu.controllers
        for eth_iface in controller.ethernet_interfaces
        for vlan in eth_iface.interface_config.virtual_interfaces
        for address in vlan.addresses
    )


absolute_path = Path(__file__).parents[3] / "examples" / "flync_example"


def assert_valid_result(result):
    """Asserts that a validation result has a 'VALID' workspace state.

    Args:
        result: The 'DiagnosticsResult' returned by the SDK.

    Raises:
        AssertionError: If any of the conditions is not met.
    """
    assert result.workspace is not None
    assert result.state == WorkspaceState.VALID
    assert result.model is not None
    assert not result.errors


def assert_broken_result(result):
    """Asserts that a validation result has a 'BROKEN' workspace state.

    Args:
        result: The 'DiagnosticsResult' returned by the SDK.

    Raises:
        AssertionError: If any of the conditions is not met.
    """
    assert result.workspace is None
    assert result.state == WorkspaceState.BROKEN
    assert result.model is None
    assert not result.errors


def assert_valid_or_warning_result(result):
    """Asserts that a validation result has either 'VALID' or 'WARNING' workspace state.

    Useful for external-node validations where non-fatal warnings may be reported
    by the loader but the model is still usable.
    """
    assert result.workspace is not None
    assert result.state in (WorkspaceState.VALID, WorkspaceState.WARNING)
    assert result.model is not None


def assert_not_broken_result(result):
    """Asserts that the validation did not fail with a BROKEN workspace state.

    This is useful for broad discovery tests where some nodes may be INVALID
    (require additional context) but the loader still returned a diagnostics
    object rather than a fatal error.
    """
    assert result is not None
    assert result.state != WorkspaceState.BROKEN
    # workspace may be None for INVALID states; no further checks here.
