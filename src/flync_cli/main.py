import logging
from importlib import metadata

import typer
from rich import print as rprint

from flync_cli.commands.generate_system_uml import app as generate_uml
from flync_cli.commands.info import app as display_info
from flync_cli.commands.service_info import app as service_info
from flync_cli.commands.validate import app as validate_app
from flync_cli.commands.vlan_info import app as display_vlan_info

app = typer.Typer(
    help="FLYNC CLI tool for validating the model, visually displaying the relevant information and generating system UML diagrams",
    context_settings={"allow_extra_args": True},
    add_completion=True,
    no_args_is_help=True,
)
logger = logging.getLogger(__name__)

app.add_typer(validate_app)
app.add_typer(display_info)
app.add_typer(display_vlan_info)
app.add_typer(generate_uml)
app.add_typer(service_info)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        help="Show the installed version of FLYNC.",
    ),
):
    """Handle global options like --version."""
    if version and ctx.invoked_subcommand is None:
        version_str = metadata.version("flync")
        rprint(f"[green]Version: {version_str}[/green]")
        raise typer.Exit(code=0)


if __name__ == "__main__":
    app()
