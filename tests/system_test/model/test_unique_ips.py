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

from flync.sdk.workspace.flync_workspace import FLYNCWorkspace
from tests.system_test.sdk.helper import entry_named, patch_yaml


def _ip_repeat_warnings(load_errors):
    """Return only the duplicate-IP warnings emitted by validate_unique_ips."""
    return [e for e in load_errors if e.get("type") == "warning" and "is repeated in ECU" in e.get("msg", "")]


def _load_example(tmpdir, example_experimental_workspace_path, name="copy"):
    destination_folder = Path(tmpdir) / name
    shutil.copytree(example_experimental_workspace_path, destination_folder)
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


def _set_viface_ip(iface_config, compute_node, viface, old_ip, new_ip):
    """Repoint one address of one virtual interface at `new_ip`.

    Args:
        iface_config: Path of the ``interface_config.flync.yaml`` to patch.
        compute_node: Name of the compute node owning the virtual interface.
        viface: Name of the virtual interface whose address is changed.
        old_ip: Address currently configured, used to pick the right entry.
        new_ip: Address to write instead.
    """
    with patch_yaml(iface_config) as config:
        addresses = entry_named(entry_named(config["compute_nodes"], compute_node)["virtual_interfaces"], viface)["addresses"]
        entries = [address for address in addresses if address["address"] == old_ip]
        assert len(entries) == 1, f"expected exactly one address {old_ip!r} on {viface}, found {len(entries)}"
        entries[0]["address"] = new_ip


def test_unique_ips_no_warning_on_clean_workspace(tmpdir, example_experimental_workspace_path):
    """The example workspace has unique IPs and must not warn."""
    destination_folder = _load_example(tmpdir, example_experimental_workspace_path)
    loaded_ws = FLYNCWorkspace.load_workspace("flync_example", destination_folder)
    assert _ip_repeat_warnings(loaded_ws.load_errors) == []
    if destination_folder.exists():
        shutil.rmtree(destination_folder)


def test_unique_ips_duplicate_ipv4_across_ecus(tmpdir, example_experimental_workspace_path):
    """Same IPv4 in two different ECUs must emit a warning."""
    destination_folder = _load_example(tmpdir, example_experimental_workspace_path)
    # 10.0.50.1 already exists in zonal_platform1/z1_c1_i1_viface2.
    # Replace 10.0.50.7 in eth_ecu so the IP appears in two ECUs.
    _set_viface_ip(_eth_ecu_iface_config(destination_folder), "eth_ecu_vm2", "eth_ecu_vm2_viface1", "10.0.50.7", "10.0.50.1")

    loaded_ws = FLYNCWorkspace.load_workspace("flync_example", destination_folder)
    warnings = _ip_repeat_warnings(loaded_ws.load_errors)
    assert len(warnings) == 1
    assert "10.0.50.1" in warnings[0]["msg"]
    # Warning is reported for the second ECU that contains the duplicate.
    assert "repeated in" in warnings[0]["msg"]
    if destination_folder.exists():
        shutil.rmtree(destination_folder)


def test_unique_ips_duplicate_ipv4_within_same_ecu(tmpdir, example_experimental_workspace_path):
    """Same IPv4 in two virtual interfaces of the same ECU must warn."""
    destination_folder = _load_example(tmpdir, example_experimental_workspace_path)
    # eth_ecu_vm1 already declares 10.0.40.7 in vlan 40.  Set the second
    # compute node's address to the same IP to trigger an in-ECU clash.
    _set_viface_ip(_eth_ecu_iface_config(destination_folder), "eth_ecu_vm2", "eth_ecu_vm2_viface1", "10.0.50.7", "10.0.40.7")

    loaded_ws = FLYNCWorkspace.load_workspace("flync_example", destination_folder)
    warnings = _ip_repeat_warnings(loaded_ws.load_errors)
    assert len(warnings) == 1
    assert "10.0.40.7" in warnings[0]["msg"]
    assert "repeated in" in warnings[0]["msg"]
    if destination_folder.exists():
        shutil.rmtree(destination_folder)


def test_unique_ips_duplicate_ipv6_across_ecus(tmpdir, example_experimental_workspace_path):
    """Duplicate IPv6 addresses across ECUs must emit a warning."""
    destination_folder = _load_example(tmpdir, example_experimental_workspace_path)
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
    with patch_yaml(file_to_update) as config:
        addresses = entry_named(config["virtual_interfaces"], "z2_c2_i2_viface1")["addresses"]
        ipv6 = [address for address in addresses if "ipv6prefix" in address]
        assert len(ipv6) == 1
        ipv6[0]["address"] = "2001:db8:85a3::8a2e:370:7334"

    loaded_ws = FLYNCWorkspace.load_workspace("flync_example", destination_folder)
    warnings = _ip_repeat_warnings(loaded_ws.load_errors)
    assert len(warnings) == 1
    assert "2001:db8:85a3::8a2e:370:7334" in warnings[0]["msg"]
    if destination_folder.exists():
        shutil.rmtree(destination_folder)


def test_unique_ips_dynamic_ipv4_zero_address_is_allowed(tmpdir, example_experimental_workspace_path):
    """0.0.0.0 (dynamic IPv4) is exempted and may repeat without warning."""
    destination_folder = _load_example(tmpdir, example_experimental_workspace_path)
    iface = _eth_ecu_iface_config(destination_folder)
    # Both compute_node IPs become 0.0.0.0; even though they collide, no
    # warning must be raised.
    _set_viface_ip(iface, "eth_ecu_vm1", "eth_ecu_vm1_viface1", "10.0.40.7", "0.0.0.0")
    _set_viface_ip(iface, "eth_ecu_vm2", "eth_ecu_vm2_viface1", "10.0.50.7", "0.0.0.0")

    loaded_ws = FLYNCWorkspace.load_workspace("flync_example", destination_folder)
    warnings = _ip_repeat_warnings(loaded_ws.load_errors)
    assert all("0.0.0.0" not in w["msg"] for w in warnings)
    if destination_folder.exists():
        shutil.rmtree(destination_folder)


def test_unique_ips_multiple_duplicates_each_emit_a_warning(tmpdir, example_experimental_workspace_path):
    """Two independent duplicates must yield two separate warnings."""
    destination_folder = _load_example(tmpdir, example_experimental_workspace_path)
    iface = _eth_ecu_iface_config(destination_folder)
    # Two unrelated collisions in eth_ecu against zonal_platform1 IPs:
    #   10.0.40.7 -> 10.0.40.1 (collides with z1_c1_i1_viface3)
    #   10.0.50.7 -> 10.0.50.1 (collides with z1_c1_i1_viface2)
    _set_viface_ip(iface, "eth_ecu_vm1", "eth_ecu_vm1_viface1", "10.0.40.7", "10.0.40.1")
    _set_viface_ip(iface, "eth_ecu_vm2", "eth_ecu_vm2_viface1", "10.0.50.7", "10.0.50.1")

    loaded_ws = FLYNCWorkspace.load_workspace("flync_example", destination_folder)
    warnings = _ip_repeat_warnings(loaded_ws.load_errors)
    messages = " | ".join(w["msg"] for w in warnings)
    assert "10.0.40.1" in messages
    assert "10.0.50.1" in messages
    assert len(warnings) == 2
    if destination_folder.exists():
        shutil.rmtree(destination_folder)
