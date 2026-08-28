from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import yaml

from flync.sdk.context.diagnostics_result import WorkspaceState
from flync.sdk.workspace.flync_workspace import FLYNCWorkspace


@contextmanager
def patch_yaml(yaml_file) -> Iterator[Any]:
    """Edit a YAML file structurally: parse it, mutate the yielded data, write it back.

    Use this for every mutation that is expressible on the parsed document — dropping a
    key, changing a value, removing a list entry. The edit addresses nodes by key and
    list position instead of by raw text, so it does not depend on the file's
    indentation, comments, or where a value happens to be repeated.

    Args:
        yaml_file: Path of the YAML file to rewrite in place.

    Yields:
        Any: The parsed document, to be mutated in place by the caller.

    Example:
        >>> with patch_yaml(switch_file) as switch:                     # doctest: +SKIP
        ...     entry_named(switch["vlans"], "VLAN40")["ports"].remove("hpc_s1_p3")
    """
    with open(yaml_file, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file)
    yield data
    with open(yaml_file, "w", encoding="utf-8") as file:
        yaml.safe_dump(data, file, sort_keys=False, default_flow_style=False)


def entry_named(entries: list, name: str) -> Any:
    """Return the one entry of a YAML list whose ``name`` equals `name`.

    Args:
        entries: List of mappings as parsed from YAML (ports, sockets, vlans, ...).
        name: Value of the ``name`` key to look for.

    Returns:
        Any: The matching entry, so callers can mutate it in place.

    Raises:
        AssertionError: If the list holds no entry with that name, or more than one.
    """
    matches = [entry for entry in entries if isinstance(entry, dict) and entry.get("name") == name]
    assert len(matches) == 1, f"expected exactly one entry named {name!r}, found {len(matches)}"
    return matches[0]


def update_yaml_content(yaml_file, old_text, new_text):
    """Replace raw text in a file, for injecting YAML that no longer parses.

    Reserved for tests that deliberately corrupt the document structure (broken
    indentation, a missing list marker, a duplicate key) — anything a YAML dumper
    could not produce. For edits on well-formed YAML use `patch_yaml` instead:
    text replacement silently hits every occurrence and breaks on re-indentation.

    Args:
        yaml_file: Path of the file to rewrite in place.
        old_text: Text to replace; every occurrence is replaced.
        new_text: Replacement text.
    """
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
