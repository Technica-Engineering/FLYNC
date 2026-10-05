"""Per-conversion reporting.

Writes the log records of a conversion into the destination workspace's
``.flync`` metadata directory: one shared log for the whole conversion, and one
folder per converter taking part in it::

    <destination>/.flync/reports/logs.txt                   whole conversion
    <destination>/.flync/reports/<converter_name>/logs.txt  that converter's records
    <destination>/.flync/reports/<converter_name>/...       files the converter writes itself

The report uses the standard :mod:`logging` hierarchy. The base library
defines the main ``flync_converter`` logger. The shared log captures it, so it
holds every converter sub-logger (e.g. ``flync_converter.converters.flync_converter``),
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
from typing import Self

from flync.sdk.context.workspace_config import CONFIG_DIRNAME

from .base.base_converter import BaseConverter

#: Name of the main converter logger that converter sub-loggers propagate into.
MAIN_LOGGER = "flync_converter"

#: Name of the report directory inside the ``.flync`` metadata directory.
REPORTS_DIRNAME = "reports"

#: Filename of the shared log and of every per-converter log.
LOG_FILENAME = "logs.txt"

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


class ConversionLogReport:
    """Context manager writing the report of one conversion.

    On entry:

    * the shared log ``reports/logs.txt`` is created, with a
      :class:`logging.FileHandler` attached to the ``flync_converter`` logger
      and to the ``report_loggers`` of every converter;
    * each converter gets its folder ``reports/<name>/``, exposed to it as
      :attr:`~flync_converter.base.BaseConverter.report_dir`, and, when it lists
      ``report_loggers``, its own ``logs.txt`` capturing only those loggers;
    * every captured logger has its level lowered to ``min_level`` when it would
      otherwise drop those records.

    Every log replaces the file of a previous conversion. On exit the handlers
    are detached and closed, every logger's previous level is restored and each
    converter's ``report_dir`` is reset to ``None``.

    When the block raises, the exception and its traceback are written to the
    shared log as an ``ERROR`` record. The record goes to the shared log only,
    not to other handlers, and the exception propagates unchanged.

    A disabled report does nothing; ``report_dir`` stays ``None``.

    Example:
        >>> with ConversionLogReport("path/to/output", [source_converter, destination_converter]):
        ...     destination_converter.encode(source_converter.decode())
    """

    def __init__(
        self,
        destination: str | Path,
        converters: Sequence[BaseConverter],
        enabled: bool = True,
        min_level: int = logging.INFO,
    ) -> None:
        """Prepare the report without touching the file system or logging.

        Args:
            destination: Destination path of the conversion.
            converters: The converters taking part in the conversion.
            enabled: When ``False`` the report does nothing.
            min_level: Lowest severity captured.
        """
        self.root = reports_root(destination)
        self.path = self.root / LOG_FILENAME
        self.enabled = enabled
        self.min_level = min_level
        self._converters = list(converters)
        self._handlers: list[tuple[logging.FileHandler, list[logging.Logger]]] = []
        self._previous_levels: dict[logging.Logger, int] = {}

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
            if converter.report_loggers:
                self._attach(folder / LOG_FILENAME, converter.report_loggers)
            converter.report_dir = folder
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
        """Record a failure, stop capturing records, close the files and restore the logger levels."""
        if not self._handlers:
            return
        if exc is not None:
            shared_handler = self._handlers[0][0]
            record = logging.getLogger(MAIN_LOGGER).makeRecord(
                MAIN_LOGGER, logging.ERROR, __file__, 0, "Conversion failed: %s", (exc,), (type(exc), exc, traceback)
            )
            shared_handler.handle(record)
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
