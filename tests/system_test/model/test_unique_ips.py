"""Tests for the FLYNCModel.validate_unique_ips validator.

The validator emits a warning whenever the same IP address is configured on
two different addresses in the system, except for the dynamic IPs
``0.0.0.0`` (IPv4) and ``::`` (IPv6) which are treated as placeholders and
allowed to repeat.

The tests load the example workspace, optionally mutate one or more YAML
files to introduce duplicate IPs, and inspect ``load_errors`` for the
expected warning entry.
"""

import shutil
from pathlib import Path

import pytest

from flync.sdk.workspace.flync_workspace import FLYNCWorkspace
from tests.system_test.sdk.helper_load_ws import update_yaml_content

absolute_path = Path(__file__).parents[3] / "examples" / "flync_example"


def _ip_repeat_warnings(load_errors):
    """Return only the duplicate-IP warnings emitted by validate_unique_ips."""
    return [
        e
        for e in load_errors
        if e.get("type") == "warning"
        and "is repeated in ECU" in e.get("msg", "")
    ]


def _load_example(tmpdir, name="copy"):
    destination_folder = Path(tmpdir) / name
    shutil.copytree(absolute_path, destination_folder)
    return destination_folder


def _eth_ecu_iface_config(workspace_root):
    return (
        workspace_root
        / "ecus"
        / "eth_ecu"
        / "controllers"
        / "eth_ecu_controller1"
        / "ethernet_interfaces"
        / "eth_ecu_c1_iface1"
        / "interface_config.flync.yaml"
    )


def test_unique_ips_no_warning_on_clean_workspace(tmpdir):
    """The example workspace has unique IPs and must not warn."""
    destination_folder = _load_example(tmpdir)
    loaded_ws = FLYNCWorkspace.load_workspace(
        "flync_example", destination_folder
    )
    assert _ip_repeat_warnings(loaded_ws.load_errors) == []
    if destination_folder.exists():
        shutil.rmtree(destination_folder)


def test_unique_ips_duplicate_ipv4_across_ecus(tmpdir):
    """Same IPv4 in two different ECUs must emit a warning."""
    destination_folder = _load_example(tmpdir)
    # 10.0.50.1 already exists in zonal_platform1/z1_c1_i1_viface2.
    # Replace 10.0.50.7 in eth_ecu so the IP appears in two ECUs.
    update_yaml_content(
        _eth_ecu_iface_config(destination_folder), "10.0.50.7", "10.0.50.1"
    )

    loaded_ws = FLYNCWorkspace.load_workspace(
        "flync_example", destination_folder
    )
    warnings = _ip_repeat_warnings(loaded_ws.load_errors)
    assert len(warnings) == 1
    assert "10.0.50.1" in warnings[0]["msg"]
    # Warning is reported for the second ECU that contains the duplicate.
    assert "repeated in" in warnings[0]["msg"]
    if destination_folder.exists():
        shutil.rmtree(destination_folder)


def test_unique_ips_duplicate_ipv4_within_same_ecu(tmpdir):
    """Same IPv4 in two virtual interfaces of the same ECU must warn."""
    destination_folder = _load_example(tmpdir)
    # eth_ecu_vm1 already declares 10.0.40.7 in vlan 40.  Set the second
    # compute node's address to the same IP to trigger an in-ECU clash.
    update_yaml_content(
        _eth_ecu_iface_config(destination_folder), "10.0.50.7", "10.0.40.7"
    )

    loaded_ws = FLYNCWorkspace.load_workspace(
        "flync_example", destination_folder
    )
    warnings = _ip_repeat_warnings(loaded_ws.load_errors)
    assert len(warnings) == 1
    assert "10.0.40.7" in warnings[0]["msg"]
    assert "repeated in" in warnings[0]["msg"]
    if destination_folder.exists():
        shutil.rmtree(destination_folder)


def test_unique_ips_duplicate_ipv6_across_ecus(tmpdir):
    """Duplicate IPv6 addresses across ECUs must emit a warning."""
    destination_folder = _load_example(tmpdir)
    # eth_ecu uses 2001:db8:85a3::8a2e:370:7334.
    # zonal_platform2/z2_c2_iface2 uses 2001:db8:85a3::8a2e:370:7335.
    # Align the second one so they collide.
    file_to_update = (
        destination_folder
        / "ecus"
        / "zonal_platform2"
        / "controllers"
        / "z2_controller2"
        / "ethernet_interfaces"
        / "z2_c2_iface2"
        / "interface_config.flync.yaml"
    )
    update_yaml_content(
        file_to_update,
        "2001:db8:85a3::8a2e:370:7335",
        "2001:db8:85a3::8a2e:370:7334",
    )

    loaded_ws = FLYNCWorkspace.load_workspace(
        "flync_example", destination_folder
    )
    warnings = _ip_repeat_warnings(loaded_ws.load_errors)
    assert len(warnings) == 1
    assert "2001:db8:85a3::8a2e:370:7334" in warnings[0]["msg"]
    if destination_folder.exists():
        shutil.rmtree(destination_folder)


def test_unique_ips_dynamic_ipv4_zero_address_is_allowed(tmpdir):
    """0.0.0.0 (dynamic IPv4) is exempted and may repeat without warning."""
    destination_folder = _load_example(tmpdir)
    iface = _eth_ecu_iface_config(destination_folder)
    # Both compute_node IPs become 0.0.0.0; even though they collide, no
    # warning must be raised.
    update_yaml_content(iface, "10.0.40.7", "0.0.0.0")
    update_yaml_content(iface, "10.0.50.7", "0.0.0.0")

    loaded_ws = FLYNCWorkspace.load_workspace(
        "flync_example", destination_folder
    )
    warnings = _ip_repeat_warnings(loaded_ws.load_errors)
    assert all("0.0.0.0" not in w["msg"] for w in warnings)
    if destination_folder.exists():
        shutil.rmtree(destination_folder)


def test_unique_ips_multiple_duplicates_each_emit_a_warning(tmpdir):
    """Two independent duplicates must yield two separate warnings."""
    destination_folder = _load_example(tmpdir)
    iface = _eth_ecu_iface_config(destination_folder)
    # Two unrelated collisions in eth_ecu against zonal_platform1 IPs:
    #   10.0.40.7 -> 10.0.40.1 (collides with z1_c1_i1_viface3)
    #   10.0.50.7 -> 10.0.50.1 (collides with z1_c1_i1_viface2)
    update_yaml_content(iface, "10.0.40.7", "10.0.40.1")
    update_yaml_content(iface, "10.0.50.7", "10.0.50.1")

    loaded_ws = FLYNCWorkspace.load_workspace(
        "flync_example", destination_folder
    )
    warnings = _ip_repeat_warnings(loaded_ws.load_errors)
    messages = " | ".join(w["msg"] for w in warnings)
    assert "10.0.40.1" in messages
    assert "10.0.50.1" in messages
    assert len(warnings) == 2
    if destination_folder.exists():
        shutil.rmtree(destination_folder)
