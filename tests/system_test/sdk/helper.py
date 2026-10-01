import shutil
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


# ---------------------------------------------------------------------------
# Ethernet Layer 2 (L2) test support
# ---------------------------------------------------------------------------
# The Ethernet Layer 2 tests build their workspace dynamically: they copy the
# bundled ``examples/flync_example`` into a temporary directory, add a dedicated
# ``ecu_l2`` ECU that exercises the Layer-2 rule under test, and (for the
# negative cases) corrupt that copy with :func:`update_yaml_content`. The
# permanent ``examples/flync_example`` is never modified.

# Reusable ``ecu_l2`` ECU metadata (version aligned with the L2 scenarios).
ECU_L2_METADATA = """compatible_flync_version:
    version_schema: semver
    version: 0.13.0
author: Dev
"""

# Default controller metadata used by the controller-interface L2 scenarios.
CONTROLLER_METADATA = """controller_metadata:
  type: embedded
  author: Dev
  compatible_flync_version:
    version_schema: semver
    version: 0.13.0
  target_system: flync_os
"""

# Common ``p0`` port used by every switch / controller L2 scenario.
PORT_P0_MDI100 = """ports:
  - name: p0
    mdi_config:
      mode: base_t1
      speed: 100
      duplex: full
      role: slave
      autonegotiation: false
"""

# Port with a matching MDI (BASE-T1 100) + MII (RMII 100) pair (RULE-L2-004).
# The negative speed-mismatch test starts from here and then corrupts it.
PORT_P0_MDI100_MII100 = """ports:
  - name: p0
    mdi_config:
      mode: base_t1
      speed: 100
      duplex: full
      role: slave
      autonegotiation: false
    mii_config:
      type: rmii
      speed: 100
      mode: phy
"""

# Default switch ``sw1`` with two member ports and a single VLAN10.
SWITCH_DEFAULT_YAML = """meta:
  author: Dev
  compatible_flync_version:
    version_schema: semver
    version: 0.13.0
  target_system: flync_os
ports:
  - name: sp0
    silicon_port_no: 0
    default_vlan_id: 1
  - name: sp1
    silicon_port_no: 1
    default_vlan_id: 1

vlans:
  - name: VLAN10
    id: 10
    default_priority: 0
    ports:
      - sp0
      - sp1
"""

# Switch variant hosting two independent VLAN broadcast domains (VLAN10, VLAN20).
SWITCH_TWO_VLANS_YAML = """meta:
  author: Dev
  compatible_flync_version:
    version_schema: semver
    version: 0.13.0
  target_system: flync_os
ports:
  - name: sp0
    silicon_port_no: 0
    default_vlan_id: 1
  - name: sp1
    silicon_port_no: 1
    default_vlan_id: 1

vlans:
  - name: VLAN10
    id: 10
    default_priority: 0
    ports:
      - sp0
      - sp1
  - name: VLAN20
    id: 20
    default_priority: 0
    ports:
      - sp0
"""

# Switch variant whose first port ``sp0`` carries an MII RMII interface.
SWITCH_PORT_MII_YAML = """meta:
  author: Dev
  compatible_flync_version:
    version_schema: semver
    version: 0.13.0
  target_system: flync_os
ports:
  - name: sp0
    silicon_port_no: 0
    default_vlan_id: 1
    mii_config:
      type: rmii
      speed: 100
      mode: mac
  - name: sp1
    silicon_port_no: 1
    default_vlan_id: 1

vlans:
  - name: VLAN10
    id: 10
    default_priority: 0
    ports:
      - sp0
      - sp1
"""

# Internal topology wiring an ECU port ``p0`` to switch port ``sp0``.
TOPOLOGY_ECU_TO_SWITCH = """connections:
  - type: ecu_port_to_switch_port
    id: conn1
    ecu_port: p0
    switch_port: sp0
"""

# ``iface1`` interface config with a single VLAN-tagged virtual interface
# ``viface1`` (vlanid 10). MAC/IP are chosen to be unique across ``flync_example``.
INTERFACE_VIFACE1 = """mac_address: 00:11:03:02:02:02
mii_config:
  type: rmii
  speed: 100
  mode: phy
virtual_interfaces:
  - name: viface1
    vlanid: 10
    addresses:
      - address: 10.0.20.1
        ipv4netmask: 255.255.255.0
"""

# Second virtual interface appended to build the duplicate-VLAN-id negative.
INTERFACE_VIFACE2 = """  - name: viface2
    vlanid: 10
    addresses:
      - address: 10.0.20.2
        ipv4netmask: 255.255.255.0
"""


def copy_example(tmp_path) -> Path:
    """Copy the bundled ``examples/flync_example`` into a temporary folder.

    Returns the path to the copy so tests can reshape it without ever touching
    the original example.

    Args:
        tmp_path: A pytest fixture providing the temporary directory.
    """
    destination_folder = Path(tmp_path) / "copy"
    shutil.copytree(absolute_path, destination_folder)
    return destination_folder


def _ecu_l2_dir(destination_folder) -> Path:
    """Create and return the ``ecu_l2`` ECU directory inside the copied workspace."""
    ecu_dir = destination_folder / "ecus" / "ecu_l2"
    (ecu_dir / "controllers").mkdir(parents=True, exist_ok=True)
    (ecu_dir / "ecu_metadata.flync.yaml").write_text(ECU_L2_METADATA, encoding="utf-8")
    return ecu_dir


def write_ecu_ports(destination_folder, ports_yaml: str, topology_yaml=None) -> None:
    """Write an ``ecu_l2`` ECU with the given ``ports.flync.yaml``.

    Args:
        destination_folder: Copied workspace root.
        ports_yaml: Content of ``ports.flync.yaml``.
        topology_yaml: Optional content of ``topology.flync.yaml``; when omitted
            no topology file is written (matching the ECU-port-only scenarios).
    """
    ecu_dir = _ecu_l2_dir(destination_folder)
    (ecu_dir / "ports.flync.yaml").write_text(ports_yaml, encoding="utf-8")
    if topology_yaml is not None:
        (ecu_dir / "topology.flync.yaml").write_text(topology_yaml, encoding="utf-8")


def add_switch(destination_folder, switch_yaml: str = SWITCH_DEFAULT_YAML) -> None:
    """Add an ``ecu_l2`` ECU hosting switch ``sw1``.

    The ECU carries the shared ``p0`` port and an empty internal topology, as in
    the original switch L2 scenarios.
    """
    write_ecu_ports(destination_folder, PORT_P0_MDI100, topology_yaml="connections: []\n")
    switch_dir = _ecu_l2_dir(destination_folder) / "switches" / "sw1"
    switch_dir.mkdir(parents=True, exist_ok=True)
    (switch_dir / "switch.flync.yaml").write_text(switch_yaml, encoding="utf-8")


def add_controller_interface(destination_folder, interface_yaml: str) -> None:
    """Add an ``ecu_l2`` ECU with controller ``ctrl1`` / Ethernet interface ``iface1``."""
    write_ecu_ports(destination_folder, PORT_P0_MDI100, topology_yaml="connections: []\n")
    ecu_dir = _ecu_l2_dir(destination_folder)
    controller_dir = ecu_dir / "controllers" / "ctrl1"
    controller_dir.mkdir(parents=True, exist_ok=True)
    (controller_dir / "controller_metadata.flync.yaml").write_text(CONTROLLER_METADATA, encoding="utf-8")
    iface_dir = controller_dir / "ethernet_interfaces" / "iface1"
    iface_dir.mkdir(parents=True, exist_ok=True)
    (iface_dir / "interface_config.flync.yaml").write_text(interface_yaml, encoding="utf-8")
