import sys
from enum import Enum

import typer
from rich.console import Console
from rich.table import Table
from typing_extensions import Annotated

from flync_cli.utils.run_validation import run_validation

app = typer.Typer()
console = Console(force_terminal=True)

_COL_ECU_NAME = "ECU Name"
_COL_CONTROLLER_NAME = "Controller Name"
_COL_SWITCH_NAME = "Switch Name"
_COL_PORT_NAME = "Port Name"
_COL_IP_ADDRESS = "IP Address"


class InfoLevel(Enum):
    """Component types available for the info command."""

    ECUS = "list-ecus"
    CONTROLLERS = "list-controllers"
    SWITCHES = "list-switches"
    PORTS = "list-ports"
    SOCKETS = "list-sockets"
    SERVICES = "list-services"
    IPS = "list-ips"


def print_list_ecu(ele_list, tag):
    """Print a two-column Rich table listing elements with their index under the given column tag."""
    table = Table(show_lines=True)
    table.add_column("Num.", justify="right")
    table.add_column(tag, style="cyan")

    for idx, ele in enumerate(ele_list, 1):
        table.add_row(str(idx), ele)

    console.print(table)


def print_list_ecu_wise(ele_list, tag):  # NOSONAR
    """Print a Rich table showing each ECU alongside its controllers, switches, or ports."""
    table = Table(show_lines=True)
    table.add_column("Num.", justify="right")
    table.add_column(_COL_ECU_NAME, style="bold blue")
    table.add_column(tag, style="cyan")

    for idx, ele in enumerate(ele_list, 1):
        if tag == _COL_CONTROLLER_NAME:
            items = [c.name for c in ele.get_all_controllers()]
        elif tag == _COL_SWITCH_NAME:
            items = [s.name for s in ele.get_all_switches()]
        elif tag == _COL_PORT_NAME:
            items = [p.name for p in ele.get_all_ports()]
        else:
            items = []
        for mem in items:
            table.add_row(str(idx), ele.name, mem)

    console.print(table)


def print_list_per_ecu(model, tag, ecu_name):  # NOSONAR
    """Print a Rich table of a specific component type (controllers/switches/ports/IPs) for one ECU."""
    ecu = model.get_ecu_by_name(ecu_name)
    if ecu is None:
        console.print("⚠️ [bold red] ECU must exist in the FLYNC model![/bold red]")
        sys.exit()
    if tag == _COL_CONTROLLER_NAME:
        items = [c.name for c in ecu.get_all_controllers()]
    elif tag == _COL_SWITCH_NAME:
        items = [s.name for s in ecu.get_all_switches()]
    elif tag == _COL_PORT_NAME:
        items = [p.name for p in ecu.get_all_ports()]
    elif tag == _COL_IP_ADDRESS:
        items = ecu.get_all_ips()
    else:
        items = []

    table = Table(show_lines=True)
    table.add_column(_COL_ECU_NAME, justify="right")
    table.add_column(tag, style="cyan")

    for ele in items:
        table.add_row(ecu_name, ele)
    console.print(table)


def print_ips(model, ecu_name):
    """Print a Rich table of all IP addresses per controller, optionally filtered to one ECU."""
    if ecu_name is not None:
        ecu_list = [model.get_ecu_by_name(ecu_name)]
    else:
        ecu_list = [model.get_ecu_by_name(e) for e in model.get_all_ecus()]

    table = Table(show_lines=True)
    table.add_column(_COL_ECU_NAME, style="bold blue")
    table.add_column(_COL_CONTROLLER_NAME, style="bold red")
    table.add_column("IPs", style="cyan")

    for e in ecu_list:
        ctrl_list = e.get_all_controllers()
        for c in ctrl_list:
            ips = c.get_all_ips()
            for ip in ips:
                table.add_row(e.name, c.name, str(ip))
    console.print(table)


@app.command(help="Display model information in a structured and user-friendly format.")
def info(  # NOSONAR
    component: Annotated[
        InfoLevel,
        typer.Argument(
            case_sensitive=False,
            help="Specify the component type for which you want to display information.",
        ),
    ],
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
    """Display FLYNC model information for the requested component type."""
    loaded_ws = run_validation(path)
    ecu_list = [loaded_ws.flync_model.get_ecu_by_name(e) for e in loaded_ws.flync_model.get_all_ecus()]

    if component == InfoLevel.ECUS:
        print_list_ecu(loaded_ws.flync_model.get_all_ecus(), _COL_ECU_NAME)

    elif component == InfoLevel.CONTROLLERS:
        if ecu_name is not None:
            print_list_per_ecu(loaded_ws.flync_model, _COL_CONTROLLER_NAME, ecu_name)
        else:
            print_list_ecu_wise(ecu_list, _COL_CONTROLLER_NAME)
    elif component == InfoLevel.SWITCHES:
        if ecu_name is not None:
            print_list_per_ecu(loaded_ws.flync_model, _COL_SWITCH_NAME, ecu_name)
        else:
            print_list_ecu_wise(ecu_list, _COL_SWITCH_NAME)
    elif component == InfoLevel.PORTS:
        if ecu_name is not None:
            print_list_per_ecu(loaded_ws.flync_model, _COL_PORT_NAME, ecu_name)
        else:
            print_list_ecu_wise(ecu_list, _COL_PORT_NAME)
    elif component == InfoLevel.IPS:
        print_ips(loaded_ws.flync_model, ecu_name)
    elif component == InfoLevel.SERVICES:
        services = [s.name for s in loaded_ws.flync_model.general.someip_config.services]
        print_list_ecu(services, " Service Interface")
