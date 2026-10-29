"""Dynamic Click commands: inject converter config options at parse time."""

import copy
import enum
import logging
from typing import Any, Self

import click

from flync_converter.base.converter_config import DESTINATION_ONLY_FIELDS
from flync_converter.utils import get_config_model

from .types import _annotation_to_click_type

logger = logging.getLogger(__name__)

#: Config fields never exposed as options: ``config_path`` comes from
#: ``--source`` / ``--output`` and ``version`` is managed by the stored file.
_SKIPPED_FIELDS = frozenset({"config_path", "version"})

#: Parameter prefix of the source converter options.
SRC_PREFIX = "src_"

#: Parameter prefix of the destination converter options.
DST_PREFIX = "dst_"

#: Prefix of the config options of ``convert source`` and ``convert destination``,
#: whose subcommand already names the side.
NO_PREFIX = ""


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
        prefix: Prefix for option names ('src_', 'dst_' or ``NO_PREFIX``).
        name: Config field name.

    Returns:
        The option flag, ``--output-type`` without a prefix.
    """
    flag = name.replace("_", "-")
    side = prefix.rstrip("_")
    return f"--{side.replace('_', '-')}-{flag}" if side else f"--{flag}"


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
            help=f"{'[required] ' if required else ''}{name} for {converter_type}" + (f" ({side} config)" if side else ""),
            show_default=str(default) if default is not None else False,
        )

    def _config_options(self, prefix: str) -> list[click.Option]:
        """Return the injected config options of one side.

        Args:
            prefix: Parameter prefix (``src_`` or ``dst_``).

        Returns:
            The options whose name starts with ``prefix``.
        """
        return [p for p in self.params if isinstance(p, click.Option) and p.name is not None and p.name.startswith(prefix)]

    def build_config_arguments(self, ctx, prefix: str) -> list[str]:
        """Build converter CLI arguments from the options injected into this command.

        Reading the actual Click options keeps preview generation aligned with
        dynamically generated converter parameters, including defaults, types,
        and ordering. The arguments use the unprefixed flags of the ``source``
        and ``destination`` subcommands, which the preview's command line uses.

        Args:
            ctx: Parsed Click context for the conversion command.
            prefix: Parameter prefix (``src_``, ``dst_`` or ``NO_PREFIX``).

        Returns:
            A flat list of command-line arguments, e.g. ``["--output-type", "CLASSIC"]``.
        """
        arguments: list[str] = []
        for parameter in self._config_options(prefix):
            assert parameter.name is not None
            value = ctx.params.get(parameter.name)
            if value is None:
                continue
            option = config_option_flag(NO_PREFIX, parameter.name[len(prefix) :])
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


class EndpointCommand(DynamicConverterCommand):
    """The ``convert source`` / ``convert destination`` subcommand.

    The converter format is pre-scanned from ``-f`` / ``--format`` and its config
    fields are injected as plain ``--<field>`` options, since the subcommand
    already names the side. A chained group reuses one command object for every
    occurrence of a subcommand, so :class:`ConvertGroup` hands out a
    :meth:`fresh` copy per occurrence and the options of one occurrence never
    leak into the next.

    Args:
        side_prefix: ``SRC_PREFIX`` or ``DST_PREFIX``, deciding which fields are offered.
    """

    def __init__(self, *args: Any, side_prefix: str, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.side_prefix = side_prefix
        self._declared_params = list(self.params)
        self._injected: list[click.Option] = []

    def fresh(self) -> Self:
        """Return a copy holding only the declared parameters, for one occurrence."""
        command = copy.copy(self)
        command.params = list(self._declared_params)
        command._injected = []
        return command

    def _is_offered(self, name: str, prefix: str) -> bool:
        """Return whether a config field becomes an option of this subcommand.

        Fields whose flag would shadow a declared option (``--path``,
        ``--format``, ``--config``, ``--help``) are skipped with a warning.

        Args:
            name: Config field name.
            prefix: Unused; the subcommand's options are unprefixed.

        Returns:
            ``False`` for fields rejected by :func:`is_config_option` for this
            side, and for fields whose flag is already taken.
        """
        if not is_config_option(name, self.side_prefix):
            return False
        flag = config_option_flag(NO_PREFIX, name)
        taken = {"--help", *(opt for p in self.params for opt in getattr(p, "opts", []))}
        if flag in taken or any(p.name == name for p in self.params):
            logger.warning("Config field %r shadows the %s option of 'convert %s' and is not offered", name, flag, self.name)
            return False
        return True

    def _config_options(self, prefix: str) -> list[click.Option]:
        """Return the options injected for the selected format."""
        return list(self._injected)

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        """Inject the config options of the ``-f`` format, then parse normally.

        Args:
            ctx: Click context.
            args: Remaining raw arguments, including those of later subcommands.

        Returns:
            The arguments left for the following subcommands.
        """
        converter_type = self._prescan_value(args, "-f", "--format")
        if converter_type:
            declared = len(self.params)
            self._inject_config_params(converter_type, NO_PREFIX)
            self._injected = [p for p in self.params[declared:] if isinstance(p, click.Option)]
        return click.Command.parse_args(self, ctx, args)


class ConvertGroup(DynamicConverterCommand, click.Group):
    """The ``convert`` group: chained ``source`` / ``destination`` subcommands.

    Its own options are the deprecated flat one-to-one form, whose ``--src-*``
    and ``--dst-*`` options are injected as by :class:`DynamicConverterCommand`.
    """

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        """Return a fresh copy of an endpoint subcommand for each occurrence.

        Args:
            ctx: Click context.
            cmd_name: Subcommand name.

        Returns:
            The subcommand, or ``None`` when there is none of that name.
        """
        command = super().get_command(ctx, cmd_name)
        return command.fresh() if isinstance(command, EndpointCommand) else command
