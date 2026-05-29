import typer
from rich import box
from rich.console import Console
from rich.table import Table
from typing_extensions import Annotated

from flync_cli.utils.run_validation import run_validation

app = typer.Typer()
console = Console(force_terminal=True)


def _stack(items: list[str]) -> str:
    """Join items with newlines for multi-line Rich table cell display, or return empty string."""
    return "\n".join(items) if items else ""


def get_ips_per_interface(interface, vlan_id):
    """Return a list of IP address strings assigned to the interface for the given VLAN ID."""
    all_ips = []
    for vi in interface.virtual_interfaces:
        if vi.vlanid == vlan_id:
            for address in vi.addresses:
                all_ips.append(str(address.address))
    return all_ips


def get_interfaces_for_vlan(interfaces, vlan_tag):
    """Return the subset of interfaces that have a virtual interface matching vlan_tag."""
    all_interfaces = []
    for iface in interfaces:
        for vi in iface.virtual_interfaces:
            if vi.vlanid == vlan_tag:
                all_interfaces.append(iface)
    return all_interfaces


def get_switch_ports_per_vlan(ecu, vlan_id):
    """Return the list of switch port names belonging to vlan_id on any switch in the ECU."""
    for switch in ecu.get_all_switches():
        for vlan in switch.vlans:
            if vlan.id == vlan_id:
                return vlan.ports
    return []


def check_switch_host_controller(ecu, vlan_tag):
    """Return (name, ips) for the host controller of any switch in the ECU that has IPs on vlan_tag."""
    ips = []
    name = None
    for sw in ecu.get_all_switches():
        if sw.host_controller:
            ips = get_ips_per_interface(sw.host_controller, vlan_tag)
            name = sw.host_controller.name
    if len(ips) == 0:
        name = None
    return name, ips


def print_vlan_tables(ecu_names: list[str], vlan_tag: int, flync_model):
    """Print a Rich table per ECU showing interfaces, switch ports, and IPs for the given VLAN."""
    for ecu_name in ecu_names:
        ecu = flync_model.get_ecu_by_name(ecu_name)
        interfaces = ecu.get_all_interfaces()
        interfaces_per_vlan = get_interfaces_for_vlan(interfaces, vlan_tag)

        table = Table(
            title=f"ECU = {ecu_name}    VLAN {vlan_tag}",
            show_lines=True,
            box=box.SQUARE,
        )
        table.add_column("Component", style="bold cyan")
        table.add_column("Type", style="bold yellow")
        table.add_column("IPs", style="bold green")

        for iface in interfaces_per_vlan:
            iface_name = iface.name
            ips = get_ips_per_interface(iface, vlan_tag)

            table.add_row(
                iface_name,
                "Controller Interface",
                _stack(ips),
            )
        switch_ports = get_switch_ports_per_vlan(ecu, vlan_tag)
        for port in switch_ports:
            table.add_row(
                port,
                "Switch Port",
                "Not required",
            )
        name, ips = check_switch_host_controller(ecu, vlan_tag)
        if name:
            table.add_row(
                name,
                "Switch Host Controller",
                _stack(ips),
            )

        console.print(table)


@app.command(help="Display the controllers, switch ports and IPs that are part of one VLAN for the system or an ECU.")
def display_vlan_info(
    vlan_id: int = typer.Argument(
        help="VLAN ID for which the information needs to be displayed",
    ),
    path: str = typer.Argument(
        help="Path to FLYNC config directory.",
    ),
    ecu_name: Annotated[
        str | None,
        typer.Option(
            "--ecu-name",
            "-e",
            help="Optional: filter info for a specific ECU name.",
        ),
    ] = None,
):
    """Display controllers, switch ports, and IPs for a VLAN across the system or a specific ECU."""
    loaded_ws = run_validation(path)
    if ecu_name is not None:
        ecu_names = [ecu_name]
    else:
        ecu_names = loaded_ws.flync_model.get_all_ecus()
    print_vlan_tables(ecu_names, vlan_id, loaded_ws.flync_model)
