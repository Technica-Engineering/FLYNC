"""Dynamic Click command: injects converter config options at parse time."""

import click

from flync_converter.base.converter_config import DESTINATION_ONLY_FIELDS
from flync_converter.utils import get_config_model

from .types import _annotation_to_click_type

#: Config fields never exposed as options: ``config_path`` comes from
#: ``--source`` / ``--output`` and ``version`` is managed by the stored file.
_SKIPPED_FIELDS = frozenset({"config_path", "version"})


class DynamicConverterCommand(click.Command):
    """Click Command that injects per-field config options for converters.

    Before Click's normal argument parsing, this command pre-scans the raw
    argument list for ``-sf``/``--source-format`` and
    ``-of``/``--output-format``,
    looks up each converter's pydantic config model, and injects
    ``--src-<field>`` / ``--dst-<field>`` options so they are available as
    regular Click options (and appear in ``--help``).
    """

    _SRC_PREFIX = "src_"
    _DST_PREFIX = "dst_"

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
            ``False`` for fields in ``_SKIPPED_FIELDS``, destination-only fields
            on the source side, and fields whose option already exists.
        """
        if name in _SKIPPED_FIELDS:
            return False
        if prefix == self._SRC_PREFIX and name in DESTINATION_ONLY_FIELDS:
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
            [f"--{side.replace('_', '-')}-{name.replace('_', '-')}"],
            type=_annotation_to_click_type(fld.annotation),
            default=None,
            required=False,
            help=f"{'[required] ' if required else ''}{name} for {converter_type} ({side} config)",
            show_default=str(default) if default is not None else False,
        )

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
