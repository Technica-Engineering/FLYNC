import typer
from rich import box
from rich.console import Console
from rich.table import Table

from flync_cli.utils.run_validation import run_validation

app = typer.Typer()
console = Console(force_terminal=True)


def print_table(someip_list, service):
    """Print a Rich table showing all consumer/provider deployments for the given SOME/IP service."""
    table = Table(
        title=f"Service {service}",
        show_lines=True,
        box=box.SQUARE,
    )
    table.add_column("ECU Name", style="bold cyan")
    table.add_column("Controller Name", style="bold cyan")
    table.add_column("Role", style="bold white")
    table.add_column("IP Address", style="bold blue")

    table.add_column("Port No.", style="bold green")

    table.add_column("Instance ID", style="yellow")

    table.add_column("Major Version", style="bright_red")

    for ele in someip_list:
        table.add_row(*[str(x) for x in ele])

    console.print(table)


def get_ctrl_for_address(ecu, address):
    """Return the controller name whose IP list contains the given address, or 0.0 if not found."""
    for ctrl in ecu.get_all_controllers():
        addresses = ctrl.get_all_ips()
        for ip in addresses:
            if str(ip) == address:
                return ctrl.name
    return 0.0


def add_consumers_and_providers(socket, ecu, service, someip_list):
    """Append consumer and provider deployment rows for the named service from this socket to someip_list."""
    for deployment in socket.deployments:
        ctrl = get_ctrl_for_address(ecu, str(socket.endpoint_address))
        if deployment.root.deployment_type == "someip_consumer" and deployment.root.service.name == service:
            someip_list.append(
                [
                    ecu.name,
                    ctrl,
                    "Consumer",
                    str(socket.endpoint_address),
                    socket.port_no,
                    deployment.root.instance_id,
                    deployment.root.major_version,
                ]
            )
        if deployment.root.deployment_type == "someip_provider" and deployment.root.service.name == service:
            someip_list.append(
                [
                    ecu.name,
                    ctrl,
                    "Provider",
                    str(socket.endpoint_address),
                    socket.port_no,
                    deployment.root.instance_id,
                    deployment.root.major_version,
                ]
            )


@app.command(help="Display all details related to a SOME/IP service deployment")
def display_service_info(
    service: str = typer.Argument(
        help="Service for which the information needs to be displayed",
    ),
    path: str = typer.Argument(
        help="Path to flync config directory.",
    ),
):
    """Display all SOME/IP consumer and provider deployment details for a named service."""
    loaded_ws = run_validation(path)
    someip_list: list = []
    for ecu in loaded_ws.flync_model.ecus:
        for sockets in ecu.get_all_sockets().values():
            for socket in sockets:
                add_consumers_and_providers(socket, ecu, service, someip_list)
    print_table(someip_list, service)
