"""Dynamic Click command: injects converter config options at parse time."""

import enum
from typing import Any

import click

from flync_converter.base.converter_config import DESTINATION_ONLY_FIELDS
from flync_converter.utils import get_config_model

from .types import _annotation_to_click_type

#: Config fields never exposed as options: ``config_path`` comes from
#: ``--source`` / ``--output`` and ``version`` is managed by the stored file.
_SKIPPED_FIELDS = frozenset({"config_path", "version"})

#: Parameter prefix of the source converter options.
SRC_PREFIX = "src_"

#: Parameter prefix of the destination converter options.
DST_PREFIX = "dst_"


def is_config_option(name: str, prefix: str) -> bool:
    """Return whether a config field is exposed as a ``--src-*`` / ``--dst-*`` option.

    Args:
        name: Config field name.
        prefix: Prefix for option names ('src_' or 'dst_').

    Returns:
        ``False`` for fields in ``_SKIPPED_FIELDS`` and for destination-only
        fields on the source side.
    """
    if name in _SKIPPED_FIELDS:
        return False
    return not (prefix == SRC_PREFIX and name in DESTINATION_ONLY_FIELDS)


def config_option_flag(prefix: str, name: str) -> str:
    """Return the command-line flag of a config field, e.g. ``--dst-output-type``.

    Args:
        prefix: Prefix for option names ('src_' or 'dst_').
        name: Config field name.

    Returns:
        The option flag.
    """
    side = prefix.rstrip("_")
    return f"--{side.replace('_', '-')}-{name.replace('_', '-')}"


def serialize_option_value(value: Any) -> str:
    """Serialize a config value back to the form its option accepts.

    Enum members are given by name (see ``_EnumNameType``); everything else
    by its string form.

    Args:
        value: Parsed option or config field value.

    Returns:
        The command-line form of ``value``.
    """
    if isinstance(value, enum.Enum):
        return value.name
    return str(value)


class DynamicConverterCommand(click.Command):
    """Click Command that injects per-field config options for converters.

    Before Click's normal argument parsing, this command pre-scans the raw
    argument list for ``-sf``/``--source-format`` and
    ``-of``/``--output-format``,
    looks up each converter's pydantic config model, and injects
    ``--src-<field>`` / ``--dst-<field>`` options so they are available as
    regular Click options (and appear in ``--help``).
    """

    _SRC_PREFIX = SRC_PREFIX
    _DST_PREFIX = DST_PREFIX

    def _prescan_value(self, args: list, *flags: str):
        """Pre-scan argument list for flag values before Click parses.

        Args:
            args: Raw argument list.
            *flags: Flag strings to search for (e.g., '-sf', '--source-format').

        Returns:
            The value following a flag, or None if not found.
        """
        for i, arg in enumerate(args):
            for flag in flags:
                if arg == flag and i + 1 < len(args):
                    return args[i + 1]
                if arg.startswith(flag + "="):
                    return arg.split("=", 1)[1]
        return None

    def _inject_config_params(self, converter_type: str, prefix: str) -> None:
        """Inject converter-specific config options into Click command params.

        Looks up the converter's pydantic config model and creates a Click
        Option for each field (excluding config_path, and the destination-only
        fields on the source side). Options default to ``None`` so that only
        values given on the command line override the configuration stored in
        the destination workspace; the field default is shown in ``--help``.
        Silently skips if the model has no fields or lookup fails.

        Args:
            converter_type: Converter key/name as registered.
            prefix: Prefix for option names ('src_' or 'dst_').
        """
        try:
            model = get_config_model(converter_type)
            if not hasattr(model, "model_fields"):
                return
            for name, fld in model.model_fields.items():
                if self._is_offered(name, prefix):
                    self.params.append(self._make_option(converter_type, prefix, name, fld))
        except Exception:
            pass

    def _is_offered(self, name: str, prefix: str) -> bool:
        """Return whether a config field becomes an option for the given side.

        Args:
            name: Config field name.
            prefix: Prefix for option names ('src_' or 'dst_').

        Returns:
            ``False`` for fields rejected by :func:`is_config_option` and for
            fields whose option already exists.
        """
        if not is_config_option(name, prefix):
            return False
        param_name = f"{prefix}{name}"
        return not any(p.name == param_name for p in self.params)

    @staticmethod
    def _make_option(converter_type: str, prefix: str, name: str, fld) -> click.Option:
        """Build the Click option for one config field.

        The option defaults to ``None`` so that only values given on the command
        line are passed on; the field default is shown in ``--help``.

        Args:
            converter_type: Converter key/name as registered.
            prefix: Prefix for option names ('src_' or 'dst_').
            name: Config field name.
            fld: Pydantic field info of the config field.

        Returns:
            The Click option.
        """
        required = fld.is_required()
        default = None if required else fld.get_default()
        side = prefix.rstrip("_")
        return click.Option(
            [config_option_flag(prefix, name)],
            type=_annotation_to_click_type(fld.annotation),
            default=None,
            required=False,
            help=f"{'[required] ' if required else ''}{name} for {converter_type} ({side} config)",
            show_default=str(default) if default is not None else False,
        )

    def build_config_arguments(self, ctx, prefix: str) -> list[str]:
        """Build converter CLI arguments from the options injected into this command.

        Reading the actual Click options keeps preview generation aligned with
        dynamically generated converter parameters, including converter-specific
        option names, defaults, types, and ordering.

        Args:
            ctx: Parsed Click context for the conversion command.
            prefix: Parameter prefix (``src_`` or ``dst_``).

        Returns:
            A flat list of command-line arguments accepted by this command.
        """
        arguments: list[str] = []
        for parameter in self.params:
            if not isinstance(parameter, click.Option) or not parameter.name.startswith(prefix):
                continue
            value = ctx.params.get(parameter.name)
            if value is None:
                continue
            option = parameter.opts[0]
            if parameter.multiple:
                for item in value:
                    arguments.extend([option, serialize_option_value(item)])
            else:
                arguments.extend([option, serialize_option_value(value)])
        return arguments

    def parse_args(self, ctx, args):
        """Pre-scan format flags and inject per-converter config options before Click parses args.

        Args:
            ctx: Click context.
            args: Raw argument list.

        Returns:
            Result of parent parse_args.
        """
        source_format = self._prescan_value(args, "-sf", "--source-format")
        output_format = self._prescan_value(args, "-of", "--output-format") or "flync"
        if source_format:
            self._inject_config_params(source_format, self._SRC_PREFIX)
        self._inject_config_params(output_format, self._DST_PREFIX)
        return super().parse_args(ctx, args)
