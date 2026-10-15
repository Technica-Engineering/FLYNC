"""Preview helpers for the flync_converter CLI.

Build a human-readable description of what a conversion will do (sources,
destinations, converter options) together with the command line that runs the
same conversion. Used by the scripted ``convert`` command and the interactive
front-ends so the preview is identical everywhere.

A conversion is described by lists of :class:`ConversionEndpoint`, one per
source and destination.
"""

from __future__ import annotations

import enum
import os
import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import PurePath
from typing import Any, Sequence

from flync_converter.base import ConverterConfig

from .dynamic import config_option_flag, is_config_option, serialize_option_value

_CONVERTER_CMD = "flync-converter"

#: Width of the label column of the preview lines.
LABEL_WIDTH = 20

#: Value types an option accepts on the command line (see ``_annotation_to_click_type``).
_CLI_SCALARS = (str, int, float, bool, enum.Enum, PurePath)


@dataclass(frozen=True)
class ConversionEndpoint:
    """One source or destination of a conversion.

    Attributes:
        converter_type: Converter key/name as registered.
        path: Source or destination path.
        options: Converter options that differ from the defaults, shown in the preview.
        arguments: Command-line arguments that set those options, e.g.
            ``["--dst-output-type", "CLASSIC"]``.
    """

    converter_type: str
    path: str
    options: dict[str, Any] = field(default_factory=dict)
    arguments: list[str] = field(default_factory=list)


def config_endpoint(converter_type: str, config: ConverterConfig, prefix: str) -> ConversionEndpoint:
    """Describe a configured converter as a conversion endpoint.

    Only fields offered as command-line options and set to a value other than
    their default are included. Values an option cannot take (lists,
    mappings, nested models) are shown in the preview but left out of the
    command line.

    Args:
        converter_type: Converter key/name as registered.
        config: The converter configuration.
        prefix: Option prefix of the side the converter is on (``src_`` or ``dst_``).

    Returns:
        The endpoint.
    """
    options: dict[str, Any] = {}
    arguments: list[str] = []
    for name, fld in type(config).model_fields.items():
        if not is_config_option(name, prefix):
            continue
        value = getattr(config, name)
        if value is None or (not fld.is_required() and value == fld.get_default(call_default_factory=True)):
            continue
        options[name] = value
        if isinstance(value, _CLI_SCALARS):
            arguments += [config_option_flag(prefix, name), serialize_option_value(value)]
    return ConversionEndpoint(converter_type, str(config.config_path), options, arguments)


def join_command(parts: Sequence[str], posix: bool | None = None) -> str:
    """Quote and join command-line arguments for the current shell.

    Args:
        parts: The arguments.
        posix: ``True`` for POSIX shell quoting, ``False`` for Windows quoting;
            defaults to the quoting of the running platform.

    Returns:
        The command line.
    """
    if posix is None:
        posix = os.name != "nt"
    return shlex.join(parts) if posix else subprocess.list2cmdline(parts)


def build_command_line(
    sources: Sequence[ConversionEndpoint],
    destinations: Sequence[ConversionEndpoint],
    posix: bool | None = None,
) -> str:
    """Return the ``flync-converter convert`` command line that runs a conversion.

    Args:
        sources: Source endpoints.
        destinations: Destination endpoints.
        posix: Quoting style, see :func:`join_command`.

    Returns:
        The quoted command line.
    """
    parts = [_CONVERTER_CMD, "convert"]
    for source in sources:
        parts += ["-s", source.path, "-sf", source.converter_type]
    for destination in destinations:
        parts += ["-o", destination.path, "-of", destination.converter_type]
    for endpoint in [*sources, *destinations]:
        parts += endpoint.arguments
    return join_command(parts, posix)


def _endpoint_lines(role: str, endpoints: Sequence[ConversionEndpoint]) -> list[str]:
    """Return the preview lines of the sources or destinations, each followed by its options."""
    lines = []
    for index, endpoint in enumerate(endpoints, start=1):
        label = f"{role} {index}" if len(endpoints) > 1 else role
        lines.append(f"{'- ' + label:<{LABEL_WIDTH}}: {endpoint.converter_type} -> {endpoint.path}")
        for name, value in endpoint.options.items():
            lines.append(f"{'- ' + label + ' option':<{LABEL_WIDTH}}: {name} = {serialize_option_value(value)}")
    return lines


def conversion_summary(sources: Sequence[ConversionEndpoint], destinations: Sequence[ConversionEndpoint]) -> str:
    """Return the one-line summary printed when a conversion starts.

    Args:
        sources: Source endpoints.
        destinations: Destination endpoints.

    Returns:
        ``Converting <path> (<type>) -> <path> (<type>)``, endpoints of one side separated by commas.
    """

    def _side(endpoints: Sequence[ConversionEndpoint]) -> str:
        """Return the endpoints of one side as ``<path> (<type>)``, separated by commas."""
        return ", ".join(f"{endpoint.path} ({endpoint.converter_type})" for endpoint in endpoints)

    return f"Converting {_side(sources)} -> {_side(destinations)}"


def render_preview(
    sources: Sequence[ConversionEndpoint],
    destinations: Sequence[ConversionEndpoint],
    posix: bool | None = None,
) -> str:
    """Return the multi-line preview describing the conversion about to run.

    Shows each source and destination with its converter options and the
    command line that runs the same conversion.

    Args:
        sources: Source endpoints.
        destinations: Destination endpoints.
        posix: Quoting style of the command line, see :func:`join_command`.

    Returns:
        The preview text.
    """
    lines = [
        "Conversion preview",
        "------------------",
        *_endpoint_lines("Source", sources),
        *_endpoint_lines("Destination", destinations),
        f"{'- Command':<{LABEL_WIDTH}}: {build_command_line(sources, destinations, posix)}",
    ]
    return "\n".join(lines)
