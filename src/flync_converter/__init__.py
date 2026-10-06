"""Top-level package API for flync_converter.

Provides a simple convert() function and a Converter orchestration class
that use the registry to select and run concrete converters.
"""

import logging
from pathlib import Path

from .base import BaseConverter, ConverterConfig
from .base.converter_config import converter_config_file
from .converters import FLYNCConverter, JsonConverter, YamlConverter
from .registry import registry
from .reporting import ConversionLogReport
from .utils import get_config_model

logger = logging.getLogger(__name__)


def convert(
    source: Path | str,
    destination: Path | str,
    destination_type: str = "flync",
    source_type: str | None = "flync",
    source_config: ConverterConfig | str | Path | None = None,
    destination_config: ConverterConfig | str | Path | None = None,
):
    """Convenience function to run a conversion.

    Args:
        source: Path or identifier of the source.
        destination: Path or identifier for the destination.
        destination_type: Destination converter key/name.
        source_type: Optional source converter key/name.
        source_config: Optional configuration for the source converter: a
            configuration object, or the path of a configuration YAML file.
        destination_config: Optional configuration for the destination
            converter: a configuration object, or the path of a configuration
            YAML file.

    See :meth:`Converter.convert` for how the configurations are resolved.
    """
    Converter().convert(
        source,
        destination,
        source_type=source_type,
        destination_type=destination_type,
        source_config=source_config,
        destination_config=destination_config,
    )


class Converter(object):
    """High-level converter orchestration.

    Uses the registry to obtain converter implementations, wires configurations
    and executes decode/encode steps.
    """

    @staticmethod
    def convert(
        source: Path | str,
        destination: Path | str,
        source_type: str | None = None,
        destination_type: str = "flync",
        source_config: ConverterConfig | str | Path | None = None,
        destination_config: ConverterConfig | str | Path | None = None,
    ):
        """Run conversion from source to destination types.

        Args:
            source: Source path or identifier.
            destination: Destination path or identifier.
            source_type: Optional source converter name; if None the
                registry will try to pick.
            destination_type: Destination converter name.
            source_config: Optional source converter configuration: a
                configuration object, or the path of a configuration YAML file.
            destination_config: Optional destination converter
                configuration: a configuration object, or the path of a
                configuration YAML file.

        Returns:
            None

        Notes:
            This method sets converter.config on registry converter
            instances as a convenience; individual converters are expected
            to use their config when decoding/encoding.

            Each side's configuration is resolved from what is passed for it:

            * ``None``: the configuration stored in that side's workspace,
              ``<path>/.flync/converters/<converter_name>.yaml``, or the field
              defaults when there is none. A source that is a single file has
              no stored configuration.
            * a path: that YAML file, instead of the stored configuration.
              ``config_path`` is the source or destination path.
            * a configuration object: the fields set on it (see
              ``model_fields_set``) override the stored configuration, which
              in turn overrides the field defaults.

            Unless ``persist_config`` is ``False``, the resolved destination
            configuration is written to
            ``<destination>/.flync/converters/<converter_name>.yaml`` before
            the conversion starts. Unless ``report_enabled`` is ``False``, the
            conversion log is written to ``<destination>/.flync/reports/logs.txt``
            and each converter gets its own folder
            ``<destination>/.flync/reports/<converter_name>/``, holding the
            configuration it ran with (``config.yaml``), the records of its
            ``report_loggers`` and any files it writes to its ``report_dir``.
        """
        if source_type is None:
            logger.info("No source type provided. Attempting to auto-detect source type.")
            source_type = registry.pick(source).name
            logger.debug("Auto-detected source type: %s", source_type)
        if source_type == destination_type:
            logger.info("Source and destination types are the same. No conversion needed.")
            return
        logger.info(
            "Converting from %s to %s (source_type=%s, destination_type=%s)",
            source,
            destination,
            source_type,
            destination_type,
        )

        source_converter = registry[source_type]
        logger.debug("Source converter: %s", type(source_converter).__name__)
        source_converter.config = _resolve_config(source, source_type, source_converter.name, source_config)
        logger.debug("Source config: %s", source_converter.config)

        destination_converter = registry[destination_type]
        logger.debug("Destination converter: %s", type(destination_converter).__name__)
        destination_config = _resolve_config(destination, destination_type, destination_converter.name, destination_config)
        destination_converter.config = destination_config
        logger.debug("Destination config: %s", destination_converter.config)

        if destination_config.persist_config:
            destination_config.to_yaml_file(converter_config_file(destination_config.config_path, destination_converter.name))

        with ConversionLogReport(
            destination_config.config_path,
            [source_converter, destination_converter],
            enabled=destination_config.report_enabled,
            min_level=destination_config.report_level,
        ):
            logger.debug("Starting decode from source")
            source_model = source_converter.decode()
            logger.debug("Decode complete, model type: %s", type(source_model).__name__)

            logger.debug("Starting encode to destination")
            destination_converter.encode(source_model)
            logger.debug("Encode complete")


def _resolve_config(
    root: Path | str,
    converter_type: str,
    converter_name: str,
    config: ConverterConfig | str | Path | None,
) -> ConverterConfig:
    """Resolve the configuration of one side of a conversion.

    Args:
        root: Source or destination path, used as ``config_path`` unless ``config`` is an object.
        converter_type: Converter key, used to pick the config class unless ``config`` is an object.
        converter_name: Name the stored configuration file is keyed by.
        config: What the caller passed: nothing, a configuration file, or a configuration object.

    Returns:
        For ``None``, the stored configuration or the defaults. For a path, the configuration
        in that file. For an object, the stored configuration (or the defaults) with every
        field set on the object applied on top.
    """
    if isinstance(config, (str, Path)):
        return get_config_model(converter_type).from_yaml_file(config, root)
    if config is None:
        return get_config_model(converter_type).from_workspace(root, converter_name)
    model = type(config)
    stored = model.from_workspace(config.config_path, converter_name)
    return model.create_from_config(stored, **{name: getattr(config, name) for name in config.model_fields_set})


__all__ = [
    "BaseConverter",
    "YamlConverter",
    "JsonConverter",
    "FLYNCConverter",
    "ConverterConfig",
    "Converter",
    "convert",
]
