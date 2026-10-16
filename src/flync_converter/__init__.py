"""Top-level package API for flync_converter.

Provides a simple convert() function and a Converter orchestration class
that use the registry to select and run concrete converters.

A conversion has any number of sources and outputs: every source is decoded
into a FLYNC model, the models are merged into one, and the merged model is
written to every output. convert() runs the one-source, one-output case;
convert_many() and convert_request() run the general one.
"""

import logging
from collections.abc import Mapping, Sequence
from copy import copy
from pathlib import Path
from typing import Any

from flync.model import FLYNCModel

from .base import DEFAULT_REPORTERS, BaseConverter, BaseReporter, ConverterConfig
from .base.converter_config import converter_config_file
from .conversion_request import (
    ConversionOutput,
    ConversionOutputError,
    ConversionRequest,
    ConversionResult,
    ConversionSource,
    OutputFailure,
)
from .converters import FLYNCConverter, JsonConverter, YamlConverter
from .model_merger import FLYNCModelMerger, MergeConflict, MergeResult, ModelMergeConflictError, OnConflict, PartialModel
from .registry import registry
from .reporting import ConversionReport
from .utils import get_config_model

logger = logging.getLogger(__name__)


def convert(
    source: Path | str,
    destination: Path | str,
    destination_type: str = "flync",
    source_type: str | None = "flync",
    source_config: ConverterConfig | str | Path | None = None,
    destination_config: ConverterConfig | str | Path | None = None,
    reporters: Sequence[BaseReporter] = DEFAULT_REPORTERS,
) -> None:
    """Convenience function to run a one-source, one-output conversion.

    Args:
        source: Path or identifier of the source.
        destination: Path or identifier for the destination.
        destination_type: Destination converter key/name.
        source_type: Optional source converter key/name; defaults to "flync".
        source_config: Optional configuration for the source converter: a
            configuration object, or the path of a configuration YAML file.
        destination_config: Optional configuration for the destination
            converter: a configuration object, or the path of a configuration
            YAML file.
        reporters: Reporters writing the report of the conversion.

    See :meth:`Converter.convert` for how the configurations are resolved.
    """
    Converter().convert(
        source,
        destination,
        source_type=source_type,
        destination_type=destination_type,
        source_config=source_config,
        destination_config=destination_config,
        reporters=reporters,
    )


def convert_many(
    sources: Sequence[ConversionSource],
    outputs: Sequence[ConversionOutput],
    *,
    on_conflict: OnConflict = OnConflict.FIRST,
    fail_fast: bool = False,
    reporters: Sequence[BaseReporter] = DEFAULT_REPORTERS,
) -> ConversionResult:
    """Decode every source, merge the models and write every output.

    Args:
        sources: The sources, in merge order.
        outputs: The outputs.
        on_conflict: Policy for values two sources disagree on.
        fail_fast: End the conversion on the first output that fails.
        reporters: Reporters writing the report of the conversion.

    Returns:
        What the conversion did.

    See :meth:`Converter.convert_request` for the details.
    """
    return Converter.convert_many(sources, outputs, on_conflict=on_conflict, fail_fast=fail_fast, reporters=reporters)


def convert_request(request: ConversionRequest | str | Path, reporters: Sequence[BaseReporter] = DEFAULT_REPORTERS) -> ConversionResult:
    """Run a conversion request, given as an object or as the path of a conversion manifest.

    Args:
        request: The request, or the path of a manifest (see :meth:`ConversionRequest.from_yaml_file`).
        reporters: Reporters writing the report of the conversion.

    Returns:
        What the conversion did.

    See :meth:`Converter.convert_request` for the details.
    """
    if not isinstance(request, ConversionRequest):
        request = ConversionRequest.from_yaml_file(request)
    return Converter.convert_request(request, reporters)


class Converter:
    """High-level converter orchestration.

    Uses the registry to obtain converter implementations, wires configurations
    and executes decode/encode steps. Each converter implementation remains
    responsible for a single ``decode`` or ``encode`` operation.
    """

    @staticmethod
    def convert(
        source: Path | str,
        destination: Path | str,
        source_type: str | None = None,
        destination_type: str = "flync",
        source_config: ConverterConfig | str | Path | None = None,
        destination_config: ConverterConfig | str | Path | None = None,
        reporters: Sequence[BaseReporter] = DEFAULT_REPORTERS,
    ) -> None:
        """Run a one-source, one-output conversion.

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
            reporters: Reporters writing the report of the conversion, one
                file each. Defaults to ``report.yaml``.

        Returns:
            None

        Notes:
            Nothing happens when the source and destination types are the
            same. A configuration object decides the location of its side:
            its ``config_path`` is used, not ``source`` or ``destination``.
            An output that fails raises its own exception.

            See :meth:`convert_request` for how configurations are resolved
            and what is written.
        """
        if source_type is None:
            logger.info("No source type provided. Attempting to auto-detect source type.")
            source_type = registry.pick(source).name
            logger.debug("Auto-detected source type: %s", source_type)
        if source_type == destination_type:
            logger.info("Source and destination types are the same. No conversion needed.")
            return
        if isinstance(source_config, ConverterConfig):
            source = source_config.config_path
        if isinstance(destination_config, ConverterConfig):
            destination = destination_config.config_path
        request = ConversionRequest(
            sources=[ConversionSource(path=source, converter_type=source_type, config=source_config)],
            outputs=[ConversionOutput(path=destination, converter_type=destination_type, config=destination_config)],
            fail_fast=True,
        )
        Converter.convert_request(request, reporters)

    @staticmethod
    def convert_many(
        sources: Sequence[ConversionSource],
        outputs: Sequence[ConversionOutput],
        *,
        on_conflict: OnConflict = OnConflict.FIRST,
        fail_fast: bool = False,
        reporters: Sequence[BaseReporter] = DEFAULT_REPORTERS,
    ) -> ConversionResult:
        """Decode every source, merge the models and write every output.

        Args:
            sources: The sources, in merge order.
            outputs: The outputs.
            on_conflict: Policy for values two sources disagree on.
            fail_fast: End the conversion on the first output that fails.
            reporters: Reporters writing the report of the conversion.

        Returns:
            What the conversion did.

        See :meth:`convert_request` for the details.
        """
        request = ConversionRequest(sources=list(sources), outputs=list(outputs), on_conflict=on_conflict, fail_fast=fail_fast)
        return Converter.convert_request(request, reporters)

    @staticmethod
    def convert_request(request: ConversionRequest, reporters: Sequence[BaseReporter] = DEFAULT_REPORTERS) -> ConversionResult:
        """Run one conversion request.

        Every source is decoded once, in order. The models are merged once (a
        single model is used as it is), and the same merged model is written
        to every output. Nothing is written to an output before every source
        is decoded and merged.

        Args:
            request: The sources, the outputs and how conflicts are handled.
            reporters: Reporters writing the report of the conversion, one
                file each. Defaults to ``report.yaml``.

        Returns:
            What the conversion did.

        Raises:
            ValueError: For an unknown converter type, or two converters of
                one name sharing a reports folder.
            ModelMergeConflictError: Under ``OnConflict.ERROR``, when two
                sources disagree.
            ConversionOutputError: When outputs failed and ``fail_fast`` is
                off; it carries the result. With ``fail_fast`` the first
                failing output raises its own exception instead.
            Exception: Whatever a decoder raises, unchanged.

        Notes:
            Each converter used by a conversion is an isolated copy obtained
            from the registry, so two endpoints of one format do not share
            their configuration or report.

            Each endpoint's configuration is resolved from what is given for it:

            * ``None``: the configuration stored in the endpoint,
              ``<path>/.flync/converters/<converter_name>/config.yaml``, or
              the field defaults when there is none. An endpoint that is a
              single file has no stored configuration.
            * a path: that YAML file, instead of the stored configuration.
            * a configuration object or a mapping of fields: the fields set
              override the stored configuration, which in turn overrides the
              field defaults.

            Unless ``persist_config`` is ``False``, the resolved configuration
            of every output is written to its stored file when the output is
            written. The configuration of a source is never written.

            Unless its ``report_enabled`` is ``False``, every endpoint gets
            its converter's report in ``<report_dir>/<converter_name>/``,
            ``<path>/.flync/reports/<converter_name>/`` by default: the
            configuration it ran with (``config.yaml``), the records of its
            ``report_loggers``, what it recorded in its ``report`` and any
            files it writes to its ``report_dir``. The reports folder of every
            output also holds the conversion's ``logs.txt`` and
            ``report.yaml``: the inputs, the outputs, the merge conflicts, the
            counts of the merged model and the outcome.
        """
        logger.info("Converting %d source(s) to %d output(s)", len(request.sources), len(request.outputs))
        sources = [(source, Converter._configured(source, side="source")) for source in request.sources]
        outputs = [(output, Converter._configured(output, side="destination")) for output in request.outputs]
        report = ConversionReport([converter for _, converter in sources], [converter for _, converter in outputs], reporters)

        with report:
            partial_models: list[PartialModel] = []
            for source, converter in sources:
                logger.debug("Decoding %s", source.describe())
                with report.step(converter):
                    partial_models.append(PartialModel(source=_config_of(converter).config_path, model=converter.decode()))

            merged = FLYNCModelMerger(request.on_conflict).merge(partial_models)
            if len(partial_models) > 1:
                report.record_merge(request.on_conflict.value, (conflict.as_mapping() for conflict in merged.conflicts))
            report.record_model(merged.model)

            result = ConversionResult(model=merged.model, decoded=list(request.sources), conflicts=merged.conflicts)
            for output, converter in outputs:
                logger.debug("Encoding %s", output.describe())
                try:
                    with report.step(converter):
                        Converter._write(converter, merged.model)
                except Exception as error:
                    if request.fail_fast:
                        raise
                    logger.exception("Writing output %s failed", output.describe())
                    report.record_failure(converter, error)
                    result.failures.append(OutputFailure(output, error))
                else:
                    result.written.append(output)

            if result.failures:
                raise ConversionOutputError(result) from result.failures[0].error
        return result

    @staticmethod
    def _write(converter: BaseConverter, model: FLYNCModel) -> None:
        """Store the configuration of an output unless ``persist_config`` is off, then write the model to it."""
        config = _config_of(converter)
        if config.persist_config:
            config.to_yaml_file(converter_config_file(config.config_path, converter.name))
        converter.encode(model)

    @staticmethod
    def _configured(endpoint: ConversionSource | ConversionOutput, *, side: str) -> BaseConverter:
        """Return an isolated converter for one endpoint, holding its resolved configuration."""
        try:
            converter = copy(registry[endpoint.converter_type])
        except KeyError:
            raise ValueError(f"Unknown {side} converter type: {endpoint.converter_type!r}") from None
        converter.config = _resolve_config(endpoint.path, endpoint.converter_type, converter.name, endpoint.config)
        logger.debug("%s converter %s: %s", side.capitalize(), type(converter).__name__, converter.config)
        return converter


def _config_of(converter: BaseConverter) -> ConverterConfig:
    """Return the configuration a converter was given by :meth:`Converter._configured`."""
    assert converter.config is not None
    return converter.config


def _resolve_config(
    root: Path | str,
    converter_type: str,
    converter_name: str,
    config: ConverterConfig | str | Path | Mapping[str, Any] | None,
) -> ConverterConfig:
    """Resolve the configuration of one endpoint of a conversion.

    Args:
        root: Source or destination path, used as ``config_path`` unless ``config`` is an object.
        converter_type: Converter key, used to pick the config class unless ``config`` is an object.
        converter_name: Name the stored configuration is keyed by.
        config: What the caller passed: nothing, a configuration file, a configuration object or a mapping of fields.

    Returns:
        For ``None``, the stored configuration or the defaults. For a path, the configuration
        in that file. For an object or a mapping, the stored configuration (or the defaults)
        with every field set on it applied on top.
    """
    if isinstance(config, (str, Path)):
        return get_config_model(converter_type).from_yaml_file(config, root)
    if isinstance(config, ConverterConfig):
        model: type[ConverterConfig] = type(config)
        root = config.config_path
        fields = {name: getattr(config, name) for name in config.model_fields_set}
    else:
        model = get_config_model(converter_type)
        fields = dict(config or {})
    stored = model.from_workspace(root, converter_name)
    return stored if config is None else model.create_from_config(stored, **fields)


__all__ = [
    "BaseConverter",
    "YamlConverter",
    "JsonConverter",
    "FLYNCConverter",
    "ConverterConfig",
    "ConversionSource",
    "ConversionOutput",
    "ConversionRequest",
    "ConversionResult",
    "ConversionOutputError",
    "OutputFailure",
    "PartialModel",
    "FLYNCModelMerger",
    "MergeConflict",
    "MergeResult",
    "ModelMergeConflictError",
    "OnConflict",
    "Converter",
    "convert",
    "convert_many",
    "convert_request",
]
