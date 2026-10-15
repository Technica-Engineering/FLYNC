"""Click subcommands for the flync_converter CLI."""

import logging
from typing import cast

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from flync_converter import Converter
from flync_converter.base import ConverterConfig
from flync_converter.registry import registry
from flync_converter.utils import get_config_model

from .dynamic import DST_PREFIX, SRC_PREFIX, DynamicConverterCommand
from .group import cli
from .interactive import interactive_configure_converter, select_converter
from .preview import ConversionEndpoint, config_endpoint, conversion_summary, render_preview

logger = logging.getLogger(__name__)
console = Console()

_no_preview_option = click.option(
    "--no-preview",
    is_flag=True,
    default=False,
    help="Hide the conversion preview.",
)


def _show_preview(ctx: click.Context, no_preview: bool) -> bool:
    """Return whether the conversion preview is shown.

    Args:
        ctx: Click context of the subcommand.
        no_preview: The subcommand's own ``--no-preview`` flag.

    Returns:
        ``False`` when ``--no-preview`` is given on the subcommand or on the main command.
    """
    return not (no_preview or (ctx.obj or {}).get("no_preview", False))


@cli.command()
def list_converters():
    """List all registered converters with descriptions."""
    available_converters = list(registry.keys())

    if not available_converters:
        console.print("[bold yellow]No converters registered.[/bold yellow]")
        return

    table = Table(title="[bold cyan]Registered Converters[/bold cyan]")
    table.add_column("Converter Type", style="magenta", width=20)
    table.add_column("Description", style="green")

    for converter_type in available_converters:
        try:
            converter_class = registry[converter_type]
            description = (converter_class.__doc__ or "No description available").strip().split("\n")[0]
        except Exception as e:
            logger.warning(f"Failed to get description for {converter_type}: {e}")
            description = "No description available"

        table.add_row(converter_type, description)

    console.print(Panel(table, expand=False))


@cli.command()
@_no_preview_option
@click.pass_context
def convert_interactive(ctx, no_preview):
    """Run the interactive session to configure and execute a conversion.

    This command:
        1. Lets the user select and configure a source converter.
        2. Lets the user select and configure a destination converter.
        3. Executes the conversion and reports status.
    """
    console.print(
        Panel(
            "[bold cyan]FLYNC Converter Interactive Session[/bold cyan]",
            expand=True,
        )
    )

    console.print("\n[bold]Step 1: Configure Source[/bold]")
    source_type = select_converter("source")
    source_config = interactive_configure_converter(source_type, "source")

    console.print("\n[bold]Step 2: Configure Destination[/bold]")
    destination_type = select_converter("destination")
    destination_config = interactive_configure_converter(destination_type, "destination")

    sources = [config_endpoint(source_type, source_config, SRC_PREFIX)]
    destinations = [config_endpoint(destination_type, destination_config, DST_PREFIX)]
    if _show_preview(ctx, no_preview):
        console.print(render_preview(sources, destinations), markup=False, highlight=False)
    console.print(conversion_summary(sources, destinations), markup=False, highlight=False, style="bold")

    console.print("\n[bold]Step 3: Starting Conversion[/bold]")
    try:
        converter = Converter()
        with console.status("[bold green]Converting..."):
            converter.convert(
                source=source_config.config_path,
                destination=destination_config.config_path,
                source_type=source_type,
                destination_type=destination_type,
                source_config=source_config,
                destination_config=destination_config,
            )
        console.print("[bold green]✓ Conversion completed successfully![/bold green]")
    except Exception as e:
        logger.exception("Conversion failed: %s", e)
        console.print(f"[bold red]✗ Conversion failed: {e}[/bold red]")


@cli.command(cls=DynamicConverterCommand)
@click.option(
    "-s",
    "--source",
    prompt="source location",
    help="Source location to convert from.",
)
@click.option(
    "-o",
    "--output",
    prompt="output location",
    help="output location to convert to.",
)
@click.option("-sf", "--source-format", help="Source format type.", default="flync")
@click.option("-of", "--output-format", help="Output format type.", default="flync")
@click.option(
    "--src-config",
    "source_config_file",
    type=click.Path(exists=True, dir_okay=False),
    help="Source converter configuration YAML, used instead of the one stored in the source workspace.",
)
@click.option(
    "--dst-config",
    "destination_config_file",
    type=click.Path(exists=True, dir_okay=False),
    help="Destination converter configuration YAML, used instead of the one stored in the destination workspace.",
)
@_no_preview_option
@click.pass_context
def convert(ctx, source, output, source_format, output_format, source_config_file, destination_config_file, no_preview, **kwargs):
    """Quick command to convert a single source to a destination.

    Any config fields for the selected converter formats are exposed as
    ``--src-<field>`` and ``--dst-<field>`` options and appear in ``--help``
    once ``--source-format`` / ``--output-format`` are known.

    Args:
        source: Source folder path.
        output: Output folder path.
        source_format: Source format (default: flync).
        output_format: Destination format (default: flync).
        source_config_file: Optional source configuration YAML (``--src-config``).
            ``--src-<field>`` options override the values in it.
        destination_config_file: Optional destination configuration YAML (``--dst-config``).
            ``--dst-<field>`` options override the values in it.
        no_preview: Hide the conversion preview (``--no-preview``).
    """
    if source_format == output_format:
        click.echo("Source and output formats are the same. No conversion needed.")
        return

    src_fields = {
        k[len(DynamicConverterCommand._SRC_PREFIX) :]: v
        for k, v in ctx.params.items()
        if k.startswith(DynamicConverterCommand._SRC_PREFIX) and v is not None
    }
    dst_fields = {
        k[len(DynamicConverterCommand._DST_PREFIX) :]: v
        for k, v in ctx.params.items()
        if k.startswith(DynamicConverterCommand._DST_PREFIX) and v is not None
    }

    dynamic_command = cast(DynamicConverterCommand, ctx.command)
    sources = [_cli_endpoint(ctx, dynamic_command, SRC_PREFIX, source_format, source, source_config_file, src_fields)]
    destinations = [_cli_endpoint(ctx, dynamic_command, DST_PREFIX, output_format, output, destination_config_file, dst_fields)]
    if _show_preview(ctx, no_preview):
        click.echo(render_preview(sources, destinations))
    click.echo(conversion_summary(sources, destinations))

    source_config = _cli_config(source_format, source, source_config_file, src_fields)
    destination_config = _cli_config(output_format, output, destination_config_file, dst_fields)

    from flync_converter import convert as convert_func

    convert_func(
        source,
        output,
        output_format,
        source_format,
        source_config=source_config,
        destination_config=destination_config,
    )


def _cli_endpoint(
    ctx: click.Context,
    command: DynamicConverterCommand,
    prefix: str,
    converter_type: str,
    path: str,
    config_file: str | None,
    fields: dict,
) -> ConversionEndpoint:
    """Describe one side of a ``convert`` invocation as a conversion endpoint.

    Args:
        ctx: Parsed Click context of ``convert``.
        command: The ``convert`` command.
        prefix: Option prefix of the side (``src_`` or ``dst_``).
        converter_type: Converter key of the side.
        path: Source or destination path.
        config_file: The ``--src-config`` / ``--dst-config`` file, if any.
        fields: The per-field options given on the command line.

    Returns:
        The endpoint, with the options exactly as given on the command line.
    """
    arguments = command.build_config_arguments(ctx, prefix)
    if config_file is not None:
        arguments = [f"--{prefix.rstrip('_')}-config", config_file, *arguments]
    return ConversionEndpoint(converter_type, path, fields, arguments)


def _cli_config(converter_type: str, path: str, config_file: str | None, fields: dict) -> ConverterConfig | str:
    """Combine a ``--src-config`` / ``--dst-config`` file and the per-field options into one config argument.

    Args:
        converter_type: Converter key, used to pick the config class.
        path: Source or destination path, used as ``config_path``.
        config_file: The configuration file given on the command line, if any.
        fields: The per-field options given on the command line.

    Returns:
        The file path when only a file is given, so it replaces the stored configuration;
        the file's configuration with the options applied when both are given; otherwise a
        configuration object holding the options, layered over the stored configuration.
    """
    model = get_config_model(converter_type)
    if config_file is None:
        return model(config_path=path, **fields)
    if not fields:
        return config_file
    return model.create_from_config(model.from_yaml_file(config_file, path), **fields)


@cli.command()
def tui():
    """Launch the full interactive Textual TUI (requires flync[tui])."""
    from flync_converter.cli._optional import load_run_tui

    load_run_tui()()


@cli.command()
def gui():
    """Launch the PySide6 desktop GUI (requires flync[gui])."""
    from flync_converter.cli._optional import load_run_gui

    load_run_gui()()
