"""``flync debug`` command: dumps internal FLYNC model structures for troubleshooting."""

from typing import Optional

import typer
from pydantic import BaseModel
from rich.console import Console

from flync.model import FLYNCModel
from flync.model.flync_4_communication import FLYNCChannelConfig, FLYNCCommunicationConfig
from flync.model.flync_4_ecu import ECU, Controller, EthernetInterface
from flync.model.flync_4_someip import SOMEIPConfig
from flync.model.flync_4_topology import FLYNCTopology
from flync.sdk.helpers.debug import print_field_subtree, print_flync_structure

app = typer.Typer()
console = Console(force_terminal=True)


@app.command(help="Run layered validation to debug a FLYNC model step by step")
def debug(
    dir_path: str = typer.Argument(help="Path to FLYNC config directory"),
):
    """Run the layered debug validator against the FLYNC config directory at ``dir_path``."""
    from pathlib import Path

    from flync.sdk.helpers.debug_layers import run_debug

    run_debug(Path(dir_path).resolve())


# Each value is either:
#   - a BaseModel subclass  →  passed directly to print_flync_structure
#   - a (parent_cls, field_name) tuple  →  passed to print_field_subtree
#     (used for leaf item types that have no External sub-fields of their own)
_CLASS_MAP: dict[str, type[BaseModel] | tuple[type[BaseModel], str]] = {
    # ── root ──────────────────────────────────────────────────────────
    "flync_model": FLYNCModel,
    # ── ECU tree ──────────────────────────────────────────────────────
    "ecu": ECU,
    "ports": (ECU, "ports"),
    "switches": (ECU, "switches"),
    "ecu_topology": (ECU, "topology"),
    "ecu_metadata": (ECU, "ecu_metadata"),
    "mac_multicast_endpoints": (ECU, "mac_multicast_endpoints"),
    "controller": Controller,
    "controller_metadata": (Controller, "controller_metadata"),
    "ethernet_interface": EthernetInterface,
    "interface_config": (EthernetInterface, "interface_config"),
    "sockets": (EthernetInterface, "sockets"),
    "can_interfaces": (Controller, "can_interfaces"),
    "lin_interfaces": (Controller, "lin_interfaces"),
    "virtual_switch": (Controller, "virtual_switch"),
    # ── communication tree ────────────────────────────────────────────
    "communication": FLYNCCommunicationConfig,
    "tcp_profiles": (FLYNCCommunicationConfig, "tcp_profiles"),
    "someip": SOMEIPConfig,
    "sd_config": (SOMEIPConfig, "sd_config"),
    "services": (SOMEIPConfig, "services"),
    "someip_timings": (SOMEIPConfig, "someip_timings"),
    "channels": FLYNCChannelConfig,
    "pdus": (FLYNCChannelConfig, "pdus"),
    "can": (FLYNCChannelConfig, "can_buses"),
    "lin": (FLYNCChannelConfig, "lin_buses"),
    "ethernet_pdu_containers": (FLYNCChannelConfig, "ethernet_pdu_containers"),
    # ── topology ──────────────────────────────────────────────────────
    "topology": FLYNCTopology,
    "system_topology": (FLYNCTopology, "system_topology"),
    # ── metadata ──────────────────────────────────────────────────────
    "metadata": (FLYNCModel, "metadata"),
}


@app.command(help="Display the repo structure of the current FLYNC model")
def display_repo_structure(
    cls_name: Optional[str] = typer.Option(
        None,
        "--class",
        help=("Sub-tree to visualise. " f"Choices: {', '.join(_CLASS_MAP)}. " "Defaults to the full FLYNCModel."),
    ),
):
    """Print the field structure of a FLYNC model or one of its named sub-trees.

    With no ``--class``, renders the full FLYNCModel. Otherwise looks up
    ``cls_name`` in ``_CLASS_MAP`` and renders either the mapped BaseModel
    subclass directly or, for leaf item types, the named field of the
    mapped parent class.
    """
    if cls_name is None:
        out = print_flync_structure()
    else:
        entry = _CLASS_MAP.get(cls_name)
        if entry is None:
            console.print(f"[red]Unknown class '{cls_name}'. Choose from: {', '.join(_CLASS_MAP)}[/red]")
            raise typer.Exit(code=1)

        if isinstance(entry, tuple):
            parent_cls, field_name = entry
            out = print_field_subtree(parent_cls, field_name)
        else:
            out = print_flync_structure(model_cls=entry)

    console.print("Repo structure saved at ", out)
