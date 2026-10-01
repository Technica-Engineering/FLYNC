"""System-level SDK negative tests for the FLYNC Ethernet Layer 2 feature."""

import shutil

from flync.sdk.helpers.validation_helpers import validate_workspace

from .helper import (
    INTERFACE_VIFACE1,
    INTERFACE_VIFACE2,
    PORT_P0_MDI100_MII100,
    add_controller_interface,
    add_switch,
    copy_example,
    update_yaml_content,
    write_ecu_ports,
)


def _assert_workspace_error(result, expected_error_id: str, message_fragment: str) -> None:
    """Assert the SDK reported exactly one error with the expected FLYNC id and message.

    SDK validation returns a :class:`~flync.sdk.context.diagnostics_result.DiagnosticsResult`
    instead of raising, so this mirrors ``tests.error_assertions.assert_single_error``:
    it pins the exact ``FLYNC-...`` error id and message fragment so a negative test
    stays tied to the single rule it is named for.
    """
    assert result.workspace is not None, "SDK did not reach workspace validation"
    matches = [err for errs in result.errors.values() for err in errs if (err.get("ctx") or {}).get("error_id") == expected_error_id]
    assert len(matches) == 1, f"expected exactly one error {expected_error_id}, got {len(matches)}"
    msg = matches[0].get("msg") or ""
    assert message_fragment in msg, f"expected message fragment {message_fragment!r} in: {msg}"


def _cleanup(destination_folder) -> None:
    if destination_folder.exists():
        shutil.rmtree(destination_folder)


"""
============================================================
TEST NAME: MDI/MII speed mismatch is rejected
RULE / CONSTRAINT: a Layer-2 port joining a PHY
    (MDI) and a MAC-side interface (MII) must use the same
    link speed; a mismatch is invalid.
============================================================

       FLYNCWORKSPACE (copy of examples/flync_example)
            |
         ECU ecu_l2
            |  ports=[p0]  <-- INVALID (injected)
        ECUPort p0
            +-- mdi_config=BASE-T1 speed 1000  (corrupted to 1000)
            +-- mii_config=RMII   speed 100  (mismatch)
"""


def test_ecu_port_mdi_mii_speed_mismatch(tmp_path):
    destination_folder = copy_example(tmp_path)
    try:
        write_ecu_ports(destination_folder, PORT_P0_MDI100_MII100)
        update_yaml_content(
            destination_folder / "ecus/ecu_l2/ports.flync.yaml",
            "      mode: base_t1\n      speed: 100",
            "      mode: base_t1\n      speed: 1000",
        )
        result = validate_workspace(destination_folder)
        _assert_workspace_error(result, "FLYNC-ECU-MAJ-CONS-081", "MII and MDI config should have a compatible speed in ECU Ports. Port p0")
    finally:
        _cleanup(destination_folder)


"""
============================================================
TEST NAME: VLAN ID above the 802.1Q range is rejected
RULE / CONSTRAINT: VLAN IDs are limited to 0-4094
    (IEEE 802.1Q 12-bit VID); a value above 4094 is invalid.
============================================================

       FLYNCWORKSPACE (copy of examples/flync_example)
            |
         ECU ecu_l2
            |  switches=[sw1]  <-- INVALID (injected)
        Switch sw1
            |  vlans=[VLANEntry(id=4096)]
"""


def test_switch_vlan_id_above_range(tmp_path):
    destination_folder = copy_example(tmp_path)
    try:
        add_switch(destination_folder)
        update_yaml_content(
            destination_folder / "ecus/ecu_l2/switches/sw1/switch.flync.yaml",
            "  - name: VLAN10\n    id: 10",
            "  - name: VLAN10\n    id: 4096",
        )
        result = validate_workspace(destination_folder)
        _assert_workspace_error(result, "FLYNC-CMN-MIN-VAL-002", "VLAN ID must be in the range 0-4094")
    finally:
        _cleanup(destination_folder)


"""
============================================================
TEST NAME: negative VLAN ID is rejected
RULE / CONSTRAINT: VLAN IDs cannot be negative; a
    negative value is outside the IEEE 802.1Q 12-bit VID space.
============================================================

       FLYNCWORKSPACE (copy of examples/flync_example)
            |
         ECU ecu_l2
            |  switches=[sw1]  <-- INVALID (injected)
        Switch sw1
            |  vlans=[VLANEntry(id=-1)]
"""


def test_switch_vlan_id_below_range(tmp_path):
    destination_folder = copy_example(tmp_path)
    try:
        add_switch(destination_folder)
        update_yaml_content(
            destination_folder / "ecus/ecu_l2/switches/sw1/switch.flync.yaml",
            "  - name: VLAN10\n    id: 10",
            "  - name: VLAN10\n    id: -1",
        )
        result = validate_workspace(destination_folder)
        _assert_workspace_error(result, "FLYNC-CMN-MIN-VAL-002", "got -1")
    finally:
        _cleanup(destination_folder)


"""
============================================================
TEST NAME: duplicate switch port names are rejected
RULE / CONSTRAINT: Layer-2 switch ports must be
    uniquely identified by name; duplicates are invalid.
============================================================

       FLYNCWORKSPACE (copy of examples/flync_example)
            |
         ECU ecu_l2
            |  switches=[sw1]  <-- INVALID (injected)
        Switch sw1
            |  ports=[sp0, sp0]  (duplicate name)
"""


def test_switch_duplicate_port_names(tmp_path):
    destination_folder = copy_example(tmp_path)
    try:
        add_switch(destination_folder)
        update_yaml_content(
            destination_folder / "ecus/ecu_l2/switches/sw1/switch.flync.yaml",
            "  - name: sp1\n    silicon_port_no: 1",
            "  - name: sp0\n    silicon_port_no: 1",
        )
        result = validate_workspace(destination_folder)
        _assert_workspace_error(result, "FLYNC-CMN-MAJ-UNIQ-009", "Duplicates found in Switch Ports (name)")
    finally:
        _cleanup(destination_folder)


"""
============================================================
TEST NAME: duplicate silicon port numbers are rejected
RULE / CONSTRAINT: Layer-2 switch ports must be
    uniquely identified by silicon hardware port number;
    duplicate numbers are invalid.
============================================================

       FLYNCWORKSPACE (copy of examples/flync_example)
            |
         ECU ecu_l2
            |  switches=[sw1]  <-- INVALID (injected)
        Switch sw1
            |  ports=[sp0(silicon 0), sp1(silicon 0)]  (duplicate)
"""


def test_switch_duplicate_silicon_ports(tmp_path):
    destination_folder = copy_example(tmp_path)
    try:
        add_switch(destination_folder)
        update_yaml_content(
            destination_folder / "ecus/ecu_l2/switches/sw1/switch.flync.yaml",
            "  - name: sp1\n    silicon_port_no: 1",
            "  - name: sp1\n    silicon_port_no: 0",
        )
        result = validate_workspace(destination_folder)
        _assert_workspace_error(result, "FLYNC-CMN-MAJ-UNIQ-009", "Duplicates found in Switch Ports (silicon_port_number)")
    finally:
        _cleanup(destination_folder)


"""
============================================================
TEST NAME: duplicate VLAN IDs on one interface are rejected
RULE / CONSTRAINT: VLAN IDs on one Ethernet
    interface must be unique; duplicates are invalid.
============================================================

       FLYNCWORKSPACE (copy of examples/flync_example)
            |
         ECU ecu_l2
            |  controllers=[ctrl1]  <-- INVALID (injected)
        Controller ctrl1
            |  ethernet_interfaces=[iface1]
        iface1: virtual_interfaces: viface1(vlan 10), viface2(vlan 10)
"""


def test_interface_duplicate_vlan_ids(tmp_path):
    destination_folder = copy_example(tmp_path)
    try:
        add_controller_interface(destination_folder, INTERFACE_VIFACE1)
        update_yaml_content(
            destination_folder / "ecus/ecu_l2/controllers/ctrl1/ethernet_interfaces/iface1/interface_config.flync.yaml",
            "        ipv4netmask: 255.255.255.0",
            "        ipv4netmask: 255.255.255.0\n" + INTERFACE_VIFACE2,
        )
        result = validate_workspace(destination_folder)
        _assert_workspace_error(result, "FLYNC-CMN-MAJ-UNIQ-009", "Duplicates found in VLAN IDs of virtual Controller Interface")
    finally:
        _cleanup(destination_folder)


"""
============================================================
TEST NAME: VLAN referencing a non-existent switch port
RULE / CONSTRAINT: a Layer-2 VLAN must map only
    to ports that exist on the switch (OA L2 §5.3 VLAN testing:
    frames are forwarded to the expected ports of the VLAN).
============================================================

       FLYNCWORKSPACE (copy of examples/flync_example)
            |
         ECU ecu_l2                  <-- INVALID
            |  switches=[sw1]
        Switch sw1
            |  ports=[sp0, sp1]
            |  vlans=[VLAN10(ports sp0, no_such_port)]
"""


def test_switch_vlan_missing_port(tmp_path):
    destination_folder = copy_example(tmp_path)
    try:
        add_switch(destination_folder)
        update_yaml_content(
            destination_folder / "ecus/ecu_l2/switches/sw1/switch.flync.yaml",
            "      - sp0\n      - sp1",
            "      - sp0\n      - no_such_port",
        )
        result = validate_workspace(destination_folder)
        _assert_workspace_error(result, "FLYNC-CMN-MAJ-VAL-025", "VLAN Ports must exist on the Switch. Invalid values: ['no_such_port'].")
    finally:
        _cleanup(destination_folder)
