"""Per-conversion reporting.

Writes the report of a conversion into the destination workspace's ``.flync``
metadata directory: a shared part for the whole conversion, and one folder per
converter taking part in it, source and destination::

    <destination>/.flync/reports/logs.txt                      whole conversion: every captured record
    <destination>/.flync/reports/report.yaml                   whole conversion: converters, status, model counts (its reporters' files)
    <destination>/.flync/reports/<converter_name>/config.yaml  configuration the converter ran with
    <destination>/.flync/reports/<converter_name>/logs.txt     that converter's records
    <destination>/.flync/reports/<converter_name>/report.yaml  what the converter reported (its reporters' files)
    <destination>/.flync/reports/<converter_name>/...          files the converter writes itself

The logs use the standard :mod:`logging` hierarchy. The base library defines
the main ``flync_converter`` logger. The shared log captures it, so it holds
every converter sub-logger (e.g. ``flync_converter.converters.flync_converter``),
plus every logger the converters list in
:attr:`~flync_converter.base.BaseConverter.report_loggers`. A converter's own
log captures only the loggers that converter lists, so it is a subset of the
shared log. A converter that lists no loggers gets a folder but no log file.

No other logger is captured or has its level changed. Loggers exist once per
process, so one conversion at a time is supported per process: a second
conversion running concurrently also writes its records into the first one's
report, and a logger listed by both converters writes into both their logs.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
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

#: Name of the main converter logger that converter sub-loggers propagate into.
MAIN_LOGGER = "flync_converter"

#: Name of the report directory inside the ``.flync`` metadata directory.
REPORTS_DIRNAME = "reports"

#: Filename of the shared log and of every per-converter log.
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


def reports_root(destination: str | Path) -> Path:
    """Return the report directory of a destination workspace.

    Args:
        destination: Destination path of the conversion.

    Returns:
        ``<destination>/.flync/reports``.
    """
    return Path(destination) / CONFIG_DIRNAME / REPORTS_DIRNAME


def report_dir(destination: str | Path, converter_name: str) -> Path:
    """Return the report folder of one converter.

    Args:
        destination: Destination path of the conversion.
        converter_name: Name of the converter, source or destination.

    Returns:
        ``<destination>/.flync/reports/<converter_name>``.
    """
    return reports_root(destination) / converter_name


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
    """Count the main elements of a model, for the shared report.

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


def _side(converter: BaseConverter, path: str | Path | None = None) -> dict[str, Any]:
    """Describe one side of the conversion for the shared report."""
    if path is None and isinstance(converter.config, ConverterConfig):
        path = converter.config.config_path
    return {"converter": converter.name, "path": None if path is None else str(path)}


class ConversionReport:
    """Context manager writing the report of one conversion.

    On entry:

    * the shared log ``reports/logs.txt`` is created, with a
      :class:`logging.FileHandler` attached to the ``flync_converter`` logger
      and to the ``report_loggers`` of both converters;
    * each converter gets its folder ``reports/<name>/``, exposed to it as
      :attr:`~flync_converter.base.BaseConverter.report_dir`, holding
      ``config.yaml`` (every value of the configuration the converter runs
      with, defaults included) and, when it lists ``report_loggers``, its own
      ``logs.txt`` capturing only those loggers;
    * each converter gets an active
      :class:`~flync_converter.base.ConverterReport` as
      :attr:`~flync_converter.base.BaseConverter.report`;
    * every captured logger has its level lowered to ``min_level`` when it would
      otherwise drop those records.

    On exit, while the logs are still open:

    * when the block raised, the exception and its traceback are written to the
      shared log as an ``ERROR`` record. The record goes to the shared log
      only, not to other handlers, and the exception propagates unchanged;
    * the shared ``reports/report.yaml`` is written: both converters, the
      status (``succeeded`` or ``failed`` with the error), and the model counts
      when :meth:`record_model` was called;
    * each converter's report is written by its
      :attr:`~flync_converter.base.BaseConverter.reporters`. A reporter that
      fails is logged and skipped.

    Then the log handlers are detached and closed, every logger's previous
    level is restored, and each converter's ``report_dir`` and ``report`` are
    reset. Every file replaces the one of a previous conversion.

    A disabled report does nothing; the converters keep an inactive report and
    ``report_dir`` stays ``None``.

    Example:
        >>> with ConversionReport("path/to/output", source_converter, destination_converter) as report:
        ...     model = source_converter.decode()
        ...     report.record_model(model)
        ...     destination_converter.encode(model)
    """

    def __init__(
        self,
        destination: str | Path,
        source_converter: BaseConverter,
        destination_converter: BaseConverter,
        enabled: bool = True,
        min_level: int = logging.INFO,
        reporters: Sequence[BaseReporter] = DEFAULT_REPORTERS,
    ) -> None:
        """Prepare the report without touching the file system or logging.

        Args:
            destination: Destination path of the conversion.
            source_converter: The converter reading the source.
            destination_converter: The converter writing the destination.
            enabled: When ``False`` the report does nothing.
            min_level: Lowest severity captured.
            reporters: Reporters writing the shared report into the reports
                folder, one file each.
        """
        self.root = reports_root(destination)
        self.path = self.root / LOG_FILENAME
        self.enabled = enabled
        self.min_level = min_level
        self.reporters = tuple(reporters)
        self._converters = [source_converter, destination_converter]
        self._shared: dict[str, Any] = {
            "source": _side(source_converter),
            "destination": _side(destination_converter, destination),
        }
        self._handlers: list[tuple[logging.FileHandler, list[logging.Logger]]] = []
        self._previous_levels: dict[logging.Logger, int] = {}

    def record_model(self, model: FLYNCModel) -> None:
        """Record the counts of the model the conversion handled in the shared report.

        Args:
            model: The decoded model.
        """
        if self.enabled:
            self._shared["model"] = model_counts(model)

    def __enter__(self) -> Self:
        """Create the report files and folders and start capturing records."""
        if not self.enabled:
            return self

        self.root.mkdir(parents=True, exist_ok=True)
        all_converter_loggers = [name for converter in self._converters for name in converter.report_loggers]
        self._attach(self.path, [MAIN_LOGGER, *all_converter_loggers])

        for converter in self._converters:
            folder = self.root / converter.name
            folder.mkdir(parents=True, exist_ok=True)
            if isinstance(converter.config, ConverterConfig):
                _write_config_record(folder / CONFIG_RECORD_FILENAME, converter.config)
            if converter.report_loggers:
                self._attach(folder / LOG_FILENAME, converter.report_loggers)
            converter.report_dir = folder
            converter.report = ConverterReport()
        return self

    def _attach(self, path: Path, logger_names: Iterable[str]) -> None:
        """Open a log file and attach its handler to the given loggers.

        Args:
            path: Log file to create, replacing an existing one.
            logger_names: Names of the loggers the file captures.
        """
        handler = logging.FileHandler(path, mode="w", encoding="utf-8")
        handler.setLevel(self.min_level)
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        loggers = [logging.getLogger(name) for name in _outermost(logger_names)]
        for log in loggers:
            if log not in self._previous_levels:
                self._previous_levels[log] = log.level
                # A logger at NOTSET takes its effective level from its ancestors, which may drop
                # records below WARNING, so it is set explicitly. An existing more permissive level is kept.
                if log.level == logging.NOTSET or log.level > self.min_level:
                    log.setLevel(self.min_level)
            log.addHandler(handler)
        self._handlers.append((handler, loggers))

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Record the outcome, write the reports, then close the logs and restore the loggers."""
        if not self.enabled:
            return
        if exc is not None:
            shared_handler = self._handlers[0][0]
            record = logging.getLogger(MAIN_LOGGER).makeRecord(
                MAIN_LOGGER, logging.ERROR, __file__, 0, "Conversion failed: %s", (exc,), (type(exc), exc, traceback)
            )
            shared_handler.handle(record)
        self._write_reports(exc)
        for handler, loggers in self._handlers:
            for log in loggers:
                log.removeHandler(handler)
            handler.close()
        for log, level in self._previous_levels.items():
            log.setLevel(level)
        self._handlers.clear()
        self._previous_levels.clear()
        for converter in self._converters:
            converter.report_dir = None
            converter.report = INACTIVE_REPORT

    def _write_reports(self, exc: BaseException | None) -> None:
        """Write the shared report and each converter's report while the logs are still open."""
        self._shared["status"] = "failed" if exc is not None else "succeeded"
        if exc is not None:
            self._shared["error"] = f"{type(exc).__name__}: {exc}"
        write_with(self.reporters, self._shared, self.root)
        for converter in self._converters:
            converter.report.write(converter.reporters, self.root / converter.name)
