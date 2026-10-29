"""Click subcommands for the flync_converter CLI."""

import logging
from typing import NamedTuple, cast

import click
from click.core import ParameterSource
from pydantic import ValidationError
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from ruamel.yaml.error import YAMLError

from flync_converter import Converter
from flync_converter.base import ConverterConfig
from flync_converter.conversion_request import ConversionOutput, ConversionRequest, ConversionSource
from flync_converter.model_merger import OnConflict
from flync_converter.registry import registry
from flync_converter.utils import get_config_model

from .dynamic import DST_PREFIX, NO_PREFIX, SRC_PREFIX, ConvertGroup, DynamicConverterCommand, EndpointCommand
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


@cli.group(cls=ConvertGroup, chain=True, invoke_without_command=True, subcommand_metavar="source ... destination ...")
@click.option("-s", "--source", help="[deprecated] Source location of the flat one-to-one form.")
@click.option("-o", "--output", help="[deprecated] Output location of the flat one-to-one form.")
@click.option("-sf", "--source-format", help="[deprecated] Source format of the flat one-to-one form.", default="flync")
@click.option("-of", "--output-format", help="[deprecated] Output format of the flat one-to-one form.", default="flync")
@click.option(
    "--src-config",
    "source_config_file",
    type=click.Path(exists=True, dir_okay=False),
    help="[deprecated] Source converter configuration YAML of the flat one-to-one form.",
)
@click.option(
    "--dst-config",
    "destination_config_file",
    type=click.Path(exists=True, dir_okay=False),
    help="[deprecated] Destination converter configuration YAML of the flat one-to-one form.",
)
@click.option(
    "--on-conflict",
    type=click.Choice([policy.value for policy in OnConflict]),
    default=OnConflict.FIRST.value,
    show_default=True,
    help="What to do when two sources disagree on the same value.",
)
@click.option("--fail-fast", is_flag=True, default=False, help="Stop at the first destination that fails.")
@click.option("--dry-run", is_flag=True, default=False, help="Check the conversion and print its preview, without converting.")
@_no_preview_option
@click.pass_context
def convert(ctx, **kwargs):
    """Convert one or many sources to one or many destinations.

    \b
    flync-converter convert \\
      source -p first/ -f flync \\
      source -p buses/ -f dbc --baud-rate-default 500000 \\
      destination -p merged/ -f json

    Every source is decoded to a FLYNC model, the models are merged in the
    order given, and the merged model is encoded to every destination. Run
    ``convert source -f <format> --help`` to list that format's own options.

    The flat ``-s/-o/-sf/-of`` form with ``--src-<field>`` / ``--dst-<field>``
    options is deprecated and runs a one-to-one conversion.

    \f
    The group itself does nothing: it also runs ahead of a subcommand's
    ``--help``. The conversion runs in :func:`_run_convert`.
    """


def _registered_format(ctx: click.Context, param: click.Parameter, value: str) -> str:
    """Reject a ``-f`` value that names no registered converter.

    Without this check an unknown format only fails once the conversion starts,
    and ``--dry-run`` would accept it.
    """
    if value not in registry:
        known = ", ".join(sorted(registry.keys())) or "none"
        raise click.BadParameter(f"{value!r} is not a registered converter. Registered: {known}.", ctx, param)
    return value


@convert.command("source", cls=EndpointCommand, side_prefix=SRC_PREFIX)
@click.option("-p", "--path", required=True, help="Location to read from.")
@click.option("-f", "--format", "converter_type", required=True, callback=_registered_format, help="Source format, as listed by list-converters.")
@click.option(
    "--config",
    "config_file",
    type=click.Path(exists=True, dir_okay=False),
    help="Converter configuration YAML, used instead of the one stored in the source.",
)
@click.pass_context
def convert_source(ctx, path, converter_type, config_file, **_fields):
    """Add one source to the conversion. Repeatable; sources merge in order."""
    return _parsed_endpoint(ctx, "source", path, converter_type, config_file)


@convert.command("destination", cls=EndpointCommand, side_prefix=DST_PREFIX)
@click.option("-p", "--path", required=True, help="Location to write to.")
@click.option(
    "-f", "--format", "converter_type", required=True, callback=_registered_format, help="Destination format, as listed by list-converters."
)
@click.option(
    "--config",
    "config_file",
    type=click.Path(exists=True, dir_okay=False),
    help="Converter configuration YAML, used instead of the one stored in the destination.",
)
@click.pass_context
def convert_destination(ctx, path, converter_type, config_file, **_fields):
    """Add one destination to the conversion. Repeatable."""
    return _parsed_endpoint(ctx, "destination", path, converter_type, config_file)


class _ParsedEndpoint(NamedTuple):
    """One ``source`` or ``destination`` subcommand occurrence.

    Attributes:
        role: ``"source"`` or ``"destination"``.
        endpoint: Path, format and the options given on the command line.
        config_file: The ``--config`` file, if any.
    """

    role: str
    endpoint: ConversionEndpoint
    config_file: str | None


def _parsed_endpoint(ctx: click.Context, role: str, path: str, converter_type: str, config_file: str | None) -> _ParsedEndpoint:
    """Describe one subcommand occurrence from its parsed context."""
    command = cast(EndpointCommand, ctx.command)
    return _ParsedEndpoint(role, _cli_endpoint(ctx, command, NO_PREFIX, converter_type, path, config_file), config_file)


@convert.result_callback()
@click.pass_context
def _run_convert(ctx, parsed: list[_ParsedEndpoint], on_conflict, fail_fast, dry_run, no_preview, **kwargs):
    """Run the conversion described by the ``source`` / ``destination`` subcommands or by the flat form."""
    flat = _flat_options_given(ctx)
    if flat and parsed:
        raise click.UsageError(f"{', '.join(flat)} cannot be combined with source/destination subcommands.", ctx)
    if flat and dry_run:
        raise click.UsageError("--dry-run needs source/destination subcommands; the flat -s/-o form does not support it.", ctx)
    if flat:
        click.echo(
            "Warning: the flat -s/-o form of convert is deprecated. Use: convert source -p <path> -f <format> destination -p <path> -f <format>",
            err=True,
        )
        _convert_flat(ctx, no_preview, **kwargs)
        return
    if not parsed:
        click.echo(ctx.get_help())
        ctx.exit(2)

    roles = [item.role for item in parsed]
    if "destination" in roles and "source" in roles[roles.index("destination") :]:
        raise click.UsageError("Sources must come before destinations.", ctx)
    if "source" not in roles:
        raise click.UsageError("At least one source is required.", ctx)
    if "destination" not in roles:
        raise click.UsageError("At least one destination is required.", ctx)

    sources = [item for item in parsed if item.role == "source"]
    destinations = [item for item in parsed if item.role == "destination"]
    _convert_chained(ctx, sources, destinations, OnConflict(on_conflict), fail_fast, dry_run, no_preview)


def _flat_options_given(ctx: click.Context) -> list[str]:
    """Return the flags of the deprecated flat form given on the command line, in declaration order."""
    command = cast(ConvertGroup, ctx.command)
    flat_names = {"source", "output", "source_format", "output_format", "source_config_file", "destination_config_file"}
    return [
        param.opts[0]
        for param in command.params
        if param.name is not None
        and (param.name in flat_names or param.name.startswith((SRC_PREFIX, DST_PREFIX)))
        and ctx.get_parameter_source(param.name) not in (None, ParameterSource.DEFAULT)
    ]


def _convert_flat(
    ctx: click.Context,
    no_preview: bool,
    source=None,
    output=None,
    source_format="flync",
    output_format="flync",
    source_config_file=None,
    destination_config_file=None,
    **kwargs,
) -> None:
    """Run the deprecated flat one-to-one form.

    Args:
        ctx: Parsed Click context of ``convert``.
        no_preview: Hide the conversion preview (``--no-preview``).
        source: Source folder path, prompted when omitted.
        output: Output folder path, prompted when omitted.
        source_format: Source format (default: flync).
        output_format: Destination format (default: flync).
        source_config_file: Optional source configuration YAML (``--src-config``).
            ``--src-<field>`` options override the values in it.
        destination_config_file: Optional destination configuration YAML (``--dst-config``).
            ``--dst-<field>`` options override the values in it.
        **kwargs: The ``--src-<field>`` / ``--dst-<field>`` options.
    """
    if source is None:
        source = click.prompt("source location")
    if output is None:
        output = click.prompt("output location")
    if source_format == output_format:
        click.echo("Source and output formats are the same. No conversion needed.")
        return

    src_fields = {k[len(SRC_PREFIX) :]: v for k, v in kwargs.items() if k.startswith(SRC_PREFIX) and v is not None}
    dst_fields = {k[len(DST_PREFIX) :]: v for k, v in kwargs.items() if k.startswith(DST_PREFIX) and v is not None}

    command = cast(ConvertGroup, ctx.command)
    sources = [_cli_endpoint(ctx, command, SRC_PREFIX, source_format, source, source_config_file, src_fields)]
    destinations = [_cli_endpoint(ctx, command, DST_PREFIX, output_format, output, destination_config_file, dst_fields)]
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


def _convert_chained(
    ctx: click.Context,
    sources: list[_ParsedEndpoint],
    destinations: list[_ParsedEndpoint],
    on_conflict: OnConflict,
    fail_fast: bool,
    dry_run: bool,
    no_preview: bool,
) -> None:
    """Run the parsed ``source`` / ``destination`` subcommands through :func:`flync_converter.convert_request`.

    Args:
        ctx: Click context of ``convert``.
        sources: The ``source`` occurrences, in merge order.
        destinations: The ``destination`` occurrences.
        on_conflict: Policy for values two sources disagree on.
        fail_fast: Stop at the first destination that fails.
        dry_run: Validate the request and the ``--config`` files and print the
            preview, without converting (``--dry-run``).
        no_preview: Hide the conversion preview (``--no-preview``); ignored by a dry run.
    """
    from flync_converter import convert_request

    def _config(item: _ParsedEndpoint) -> ConverterConfig | str:
        """Return the configuration argument of one endpoint, as :func:`_cli_config` combines it."""
        endpoint = item.endpoint
        return _cli_config(endpoint.converter_type, endpoint.path, item.config_file, endpoint.options)

    try:
        request = ConversionRequest(
            sources=[ConversionSource(path=s.endpoint.path, converter_type=s.endpoint.converter_type, config=_config(s)) for s in sources],
            outputs=[ConversionOutput(path=d.endpoint.path, converter_type=d.endpoint.converter_type, config=_config(d)) for d in destinations],
            on_conflict=on_conflict,
            fail_fast=fail_fast,
        )
    except ValidationError as exc:
        raise click.UsageError("; ".join(error["msg"] for error in exc.errors()), ctx) from exc

    preview_sources = [item.endpoint for item in sources]
    preview_destinations = [item.endpoint for item in destinations]
    if dry_run:
        _check_config_files(ctx, [*sources, *destinations])
        click.echo(render_preview(preview_sources, preview_destinations))
        click.echo("Dry run: the conversion is valid. Nothing was read or written.")
        return
    if _show_preview(ctx, no_preview):
        click.echo(render_preview(preview_sources, preview_destinations))
    click.echo(conversion_summary(preview_sources, preview_destinations))
    convert_request(request)


def _check_config_files(ctx: click.Context, items: list[_ParsedEndpoint]) -> None:
    """Load every ``--config`` file as its converter's configuration, for ``--dry-run``.

    Raises:
        click.UsageError: For a file that is not a valid configuration of its converter.
    """
    for item in items:
        if item.config_file is None:
            continue
        endpoint = item.endpoint
        try:
            get_config_model(endpoint.converter_type).from_yaml_file(item.config_file, endpoint.path)
        except (ValueError, YAMLError) as exc:
            raise click.UsageError(f"--config {item.config_file} of {item.role} {endpoint.path}: {exc}", ctx) from exc


def _cli_endpoint(
    ctx: click.Context,
    command: DynamicConverterCommand,
    prefix: str,
    converter_type: str,
    path: str,
    config_file: str | None,
    fields: dict | None = None,
) -> ConversionEndpoint:
    """Describe one side of a ``convert`` invocation as a conversion endpoint.

    Args:
        ctx: Parsed Click context of ``convert`` or of its subcommand.
        command: The command holding the injected config options.
        prefix: Option prefix of the side (``src_``, ``dst_`` or ``NO_PREFIX``).
        converter_type: Converter key of the side.
        path: Source or destination path.
        config_file: The configuration file given on the command line, if any.
        fields: The per-field options given on the command line; read from
            ``ctx`` when omitted.

    Returns:
        The endpoint, with the options exactly as given on the command line.
    """
    if fields is None:
        fields = {
            option.name[len(prefix) :]: ctx.params[option.name]
            for option in command._config_options(prefix)
            if option.name is not None and ctx.params.get(option.name) is not None
        }
    arguments = command.build_config_arguments(ctx, prefix)
    if config_file is not None:
        arguments = ["--config", config_file, *arguments]
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
