"""Per-conversion reporting.

A conversion has any number of inputs and outputs. Each of them is an endpoint
with its own reports folder, by default ``<endpoint>/.flync/reports`` (see
:attr:`~flync_converter.ConverterConfig.report_dir`), holding one folder for
its converter::

    <reports>/<converter_name>/config.yaml  configuration the converter ran with
    <reports>/<converter_name>/logs.txt     that converter's records
    <reports>/<converter_name>/report.yaml  what the converter reported (its reporters' files)
    <reports>/<converter_name>/...          files the converter writes itself

The reports folder of every output also holds the report of the conversion as
a whole::

    <reports>/logs.txt     every captured record
    <reports>/report.yaml  inputs, outputs, merge conflicts, model counts, status (its reporters' files)

An endpoint that is a single file uses the folder the file is in. An endpoint
with ``report_enabled`` set to ``False``, or whose reports folder cannot be
written, gets no report; the conversion runs all the same. A source that does
not exist is not created for its report.

The logs use the standard :mod:`logging` hierarchy. The base library defines
the main ``flync_converter`` logger. The conversion log captures it, so it holds
every converter sub-logger (e.g. ``flync_converter.converters.flync_converter``),
plus every logger the converters list in
:attr:`~flync_converter.base.BaseConverter.report_loggers`. A converter's own
log captures only the loggers that converter lists, and only while that
converter runs when the conversion marks it with :meth:`ConversionReport.step`.

No other logger is captured or has its level changed. Loggers exist once per
process, so one conversion at a time is supported per process: a second
conversion running concurrently also writes its records into the first one's
report.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from types import TracebackType
from typing import Any, Self

import yaml

from flync.model import FLYNCModel
from flync.sdk.context.workspace_config import CONFIG_DIRNAME

from .base.base_converter import BaseConverter
from .base.converter_config import ConverterConfig
from .base.converter_report import INACTIVE_REPORT, ConverterReport, write_with
from .base.reporters import DEFAULT_REPORTERS, BaseReporter

logger = logging.getLogger(__name__)

#: Name of the main converter logger that converter sub-loggers propagate into.
MAIN_LOGGER = "flync_converter"

#: Name of the report directory inside the ``.flync`` metadata directory.
REPORTS_DIRNAME = "reports"

#: Filename of the conversion log and of every per-converter log.
LOG_FILENAME = "logs.txt"

#: Filename of the configuration record in every per-converter folder.
CONFIG_RECORD_FILENAME = "config.yaml"

#: Format of every line in a log.
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def _outermost(names: Iterable[str]) -> list[str]:
    """Drop every logger name that has an ancestor in ``names``.

    A record propagates through all its ancestors, so a handler attached to
    both ``flync`` and ``flync.sdk`` would write each ``flync.sdk`` record twice.

    Args:
        names: Dotted logger names.

    Returns:
        The names without a listed ancestor, sorted and without duplicates.
    """
    unique = sorted(set(names))
    return [name for name in unique if not any(name.startswith(f"{other}.") for other in unique)]


def reports_root(endpoint: str | Path) -> Path:
    """Return the default reports folder of an endpoint folder.

    Args:
        endpoint: Folder a conversion reads from or writes to.

    Returns:
        ``<endpoint>/.flync/reports``.
    """
    return Path(endpoint) / CONFIG_DIRNAME / REPORTS_DIRNAME


def report_dir(endpoint: str | Path, converter_name: str) -> Path:
    """Return the default report folder of one converter in an endpoint folder.

    Args:
        endpoint: Folder a conversion reads from or writes to.
        converter_name: Name of the converter.

    Returns:
        ``<endpoint>/.flync/reports/<converter_name>``.
    """
    return reports_root(endpoint) / converter_name


def config_reports_root(config: ConverterConfig) -> Path:
    """Return the reports folder of the endpoint a configuration belongs to.

    Args:
        config: The resolved configuration of the endpoint's converter.

    Returns:
        ``report_dir`` when it is set, resolved against the endpoint folder
        when relative; otherwise ``<endpoint>/.flync/reports``. The endpoint
        folder is ``config_path``, or the folder holding it when it is a file.
    """
    path = Path(config.config_path)
    folder = path.parent if path.is_file() else path
    if config.report_dir is None:
        return reports_root(folder)
    return folder / config.report_dir


def _write_config_record(path: Path, config: ConverterConfig) -> None:
    """Write every value of a converter configuration, defaults and ``config_path`` included.

    Unlike :meth:`~flync_converter.ConverterConfig.to_yaml_file`, which stores
    the starting point of the next conversion, this records what one
    conversion ran with.

    Args:
        path: File to write, replacing an existing one.
        config: The resolved configuration.
    """
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(config.model_dump(mode="json"), f, sort_keys=False)


def model_counts(model: FLYNCModel) -> dict[str, int]:
    """Count the main elements of a model, for the conversion report.

    Args:
        model: The model the conversion handled.

    Returns:
        The number of ECUs, applications, CAN and LIN buses, shared PDUs and
        Ethernet PDU containers.
    """
    channels = model.communication.channels if model.communication is not None else None
    return {
        "ecus": len(model.ecus or []),
        "apps": len(model.apps or []),
        "can_buses": len(channels.can_buses or []) if channels is not None else 0,
        "lin_buses": len(channels.lin_buses or []) if channels is not None else 0,
        "shared_pdus": len(channels.pdus or []) if channels is not None else 0,
        "ethernet_pdus": len(channels.ethernet_pdu_containers or []) if channels is not None else 0,
    }


@dataclass
class _Endpoint:
    """One input or output of the conversion and where its report goes."""

    converter: BaseConverter
    root: Path | None
    level: int
    entry: dict[str, Any] = field(default_factory=dict)

    @property
    def folder(self) -> Path | None:
        """The converter's report folder, or ``None`` without a report."""
        return None if self.root is None else self.root / self.converter.name


def _endpoint(converter: BaseConverter, is_input: bool) -> _Endpoint:
    """Describe a converter taking part in a conversion, from its configuration."""
    config = converter.config
    if not isinstance(config, ConverterConfig):
        return _Endpoint(converter, None, logging.INFO, {"converter": converter.name, "path": None})
    root = config_reports_root(config) if config.report_enabled else None
    # A missing source is not created for the sake of its report.
    if is_input and config.report_dir is None and not Path(config.config_path).exists():
        root = None
    return _Endpoint(converter, root, config.report_level, {"converter": converter.name, "path": config.config_path})


class ConversionReport:
    """Context manager writing the report of one conversion.

    Every converter passed in must already hold the configuration it runs
    with: its ``report_enabled``, ``report_min_log_level`` and ``report_dir``
    decide whether, how and where its part of the report is written. A
    converter without a configuration gets no report.

    On entry:

    * the conversion log ``logs.txt`` is created in the reports folder of every
      output, with a :class:`logging.FileHandler` attached to the
      ``flync_converter`` logger and to the ``report_loggers`` of all
      converters;
    * each converter gets its folder ``<reports>/<name>/``, exposed to it as
      :attr:`~flync_converter.base.BaseConverter.report_dir`, holding
      ``config.yaml`` (every value of the configuration the converter runs
      with, defaults included) and, when it lists ``report_loggers``, its own
      ``logs.txt`` capturing only those loggers;
    * each converter gets an active
      :class:`~flync_converter.base.ConverterReport` as
      :attr:`~flync_converter.base.BaseConverter.report`;
    * every captured logger has its level lowered to the lowest level a log
      asks for when it would otherwise drop those records.

    A reports folder that cannot be created is logged as a warning and left
    out.

    On exit, while the logs are still open:

    * when the block raised, the exception and its traceback are written to the
      conversion log as an ``ERROR`` record. The record goes to the conversion
      log only, not to other handlers, and the exception propagates unchanged;
    * the conversion's ``report.yaml`` is written into the reports folder of
      every output: the inputs and outputs with their report folders, the
      merge record when :meth:`record_merge` was called, the model counts when
      :meth:`record_model` was called, and the status (``succeeded``, or
      ``failed`` with the error);
    * each converter's report is written by its
      :attr:`~flync_converter.base.BaseConverter.reporters`. A reporter that
      fails is logged and skipped.

    Then the log handlers are detached and closed, every logger's previous
    level is restored, and each converter's ``report_dir`` and ``report`` are
    reset. Every file replaces the one of a previous conversion.

    Example:
        >>> with ConversionReport([source_converter], [destination_converter]) as report:
        ...     with report.step(source_converter):
        ...         model = source_converter.decode()
        ...     report.record_model(model)
        ...     with report.step(destination_converter):
        ...         destination_converter.encode(model)
    """

    def __init__(
        self,
        inputs: Sequence[BaseConverter],
        outputs: Sequence[BaseConverter],
        reporters: Sequence[BaseReporter] = DEFAULT_REPORTERS,
    ) -> None:
        """Prepare the report without touching the file system or logging.

        Args:
            inputs: The converters reading the sources, configured.
            outputs: The converters writing the destinations, configured.
            reporters: Reporters writing the conversion's report into the
                reports folder of every output, one file each.

        Raises:
            ValueError: If two converters of one name share a reports folder.
        """
        self.reporters = tuple(reporters)
        self._inputs = [_endpoint(converter, is_input=True) for converter in inputs]
        self._outputs = [_endpoint(converter, is_input=False) for converter in outputs]
        self._endpoints = [*self._inputs, *self._outputs]
        self._reject_shared_folders()
        # Reports folder of every output and the lowest level any output sharing it asks for.
        self._roots: dict[Path, int] = {}
        for endpoint in self._outputs:
            if endpoint.root is not None:
                self._roots[endpoint.root] = min(endpoint.level, self._roots.get(endpoint.root, endpoint.level))
        self._shared: dict[str, Any] = {}
        self._failed_outputs = False
        self._current: BaseConverter | None = None
        self._shared_handlers: list[logging.FileHandler] = []
        self._handlers: list[tuple[logging.Handler, list[logging.Logger]]] = []
        self._previous_levels: dict[logging.Logger, int] = {}

    def _reject_shared_folders(self) -> None:
        """Refuse two converters writing their report into the same folder."""
        seen: set[Path] = set()
        for endpoint in self._endpoints:
            folder = endpoint.folder
            if folder is None:
                continue
            resolved = folder.resolve()
            if resolved in seen:
                raise ValueError(
                    f"Two '{endpoint.converter.name}' converters would write their report to {folder}. Give one of them its own report_dir."
                )
            seen.add(resolved)

    @property
    def roots(self) -> tuple[Path, ...]:
        """The reports folders holding the report of the conversion as a whole."""
        return tuple(self._roots)

    def record_model(self, model: FLYNCModel) -> None:
        """Record the counts of the model the conversion handled.

        Args:
            model: The decoded, merged model.
        """
        self._shared["model"] = model_counts(model)

    def record_merge(self, policy: str, conflicts: Iterable[dict[str, Any]]) -> None:
        """Record how the models of several inputs were merged.

        Args:
            policy: The conflict policy the merge ran with.
            conflicts: The conflicts the merge resolved, as plain data.
        """
        self._shared["merge"] = {"policy": policy, "conflicts": list(conflicts)}

    def record_failure(self, converter: BaseConverter, error: BaseException) -> None:
        """Record that one output failed while the conversion carried on.

        Args:
            converter: The converter of the output that failed.
            error: What it raised.
        """
        self._failed_outputs = True
        for endpoint in self._outputs:
            if endpoint.converter is converter:
                endpoint.entry["error"] = f"{type(error).__name__}: {error}"

    @contextmanager
    def step(self, converter: BaseConverter) -> Iterator[None]:
        """Mark ``converter`` as the one running, so only its own log captures its loggers.

        Without it, two converters listing the same logger both capture every
        record of that logger.

        Args:
            converter: The converter decoding or encoding inside the block.
        """
        previous, self._current = self._current, converter
        try:
            yield
        finally:
            self._current = previous

    def __enter__(self) -> Self:
        """Create the report files and folders and start capturing records."""
        all_converter_loggers = [name for endpoint in self._endpoints for name in endpoint.converter.report_loggers]
        unwritable = []
        for root, level in self._roots.items():
            try:
                root.mkdir(parents=True, exist_ok=True)
                self._shared_handlers.append(self._attach(root / LOG_FILENAME, [MAIN_LOGGER, *all_converter_loggers], level))
            except OSError as error:
                logger.warning("Conversion report skipped, cannot write to %s: %s", root, error)
                unwritable.append(root)
        for root in unwritable:
            del self._roots[root]

        for endpoint in self._endpoints:
            folder = endpoint.folder
            if folder is None:
                continue
            converter = endpoint.converter
            try:
                folder.mkdir(parents=True, exist_ok=True)
                if isinstance(converter.config, ConverterConfig):
                    _write_config_record(folder / CONFIG_RECORD_FILENAME, converter.config)
                if converter.report_loggers:
                    handler = self._attach(folder / LOG_FILENAME, converter.report_loggers, endpoint.level)
                    handler.addFilter(self._while_running(converter))
            except OSError as error:
                logger.warning("Report of converter %s skipped, cannot write to %s: %s", converter.name, folder, error)
                endpoint.root = None
                continue
            endpoint.entry["report"] = str(folder)
            converter.report_dir = folder
            converter.report = ConverterReport()
        return self

    def _while_running(self, converter: BaseConverter) -> Callable[[logging.LogRecord], bool]:
        """Return a log filter passing records only while ``converter`` runs, or while no converter is marked."""

        def accept(_record: logging.LogRecord) -> bool:
            """Return whether the record is logged while ``converter`` or no marked converter runs."""
            return self._current is None or self._current is converter

        return accept

    def _attach(self, path: Path, logger_names: Iterable[str], level: int) -> logging.FileHandler:
        """Open a log file and attach its handler to the given loggers.

        Args:
            path: Log file to create, replacing an existing one.
            logger_names: Names of the loggers the file captures.
            level: Lowest severity the file captures.

        Returns:
            The handler writing the file.
        """
        handler = logging.FileHandler(path, mode="w", encoding="utf-8")
        handler.setLevel(level)
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        loggers = [logging.getLogger(name) for name in _outermost(logger_names)]
        for log in loggers:
            self._previous_levels.setdefault(log, log.level)
            # A logger at NOTSET takes its effective level from its ancestors, which may drop
            # records below WARNING, so it is set explicitly. An existing more permissive level is kept.
            if log.level == logging.NOTSET or log.level > level:
                log.setLevel(level)
            log.addHandler(handler)
        self._handlers.append((handler, loggers))
        return handler

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Record the outcome, write the reports, then close the logs and restore the loggers."""
        if exc is not None:
            record = logging.getLogger(MAIN_LOGGER).makeRecord(
                MAIN_LOGGER, logging.ERROR, __file__, 0, "Conversion failed: %s", (exc,), (type(exc), exc, traceback)
            )
            for shared_handler in self._shared_handlers:
                shared_handler.handle(record)
        self._write_reports(exc)
        for handler, loggers in self._handlers:
            for log in loggers:
                log.removeHandler(handler)
            handler.close()
        for log, level in self._previous_levels.items():
            log.setLevel(level)
        self._handlers.clear()
        self._shared_handlers.clear()
        self._previous_levels.clear()
        for endpoint in self._endpoints:
            endpoint.converter.report_dir = None
            endpoint.converter.report = INACTIVE_REPORT

    def _write_reports(self, exc: BaseException | None) -> None:
        """Write the conversion report and each converter's report while the logs are still open."""
        shared: dict[str, Any] = {
            "inputs": [endpoint.entry for endpoint in self._inputs],
            "outputs": [endpoint.entry for endpoint in self._outputs],
            **self._shared,
            "status": "failed" if exc is not None or self._failed_outputs else "succeeded",
        }
        if exc is not None:
            shared["error"] = f"{type(exc).__name__}: {exc}"
        for root in self._roots:
            write_with(self.reporters, shared, root)
        for endpoint in self._endpoints:
            if endpoint.folder is not None:
                endpoint.converter.report.write(endpoint.converter.reporters, endpoint.folder)
