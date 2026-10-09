"""Reporters writing a converter's structured report data.

A reporter serialises report data into one file of a report folder: a
converter's report (see :class:`~flync_converter.base.ConverterReport`) into
the converter's folder, and the shared report of a conversion into the reports
folder::

    <destination>/.flync/reports/<reporter.filename>
    <destination>/.flync/reports/<converter_name>/<reporter.filename>

Converters list the reporters they use in
:attr:`~flync_converter.base.BaseConverter.reporters`; the reporters of the
shared report are passed to :func:`~flync_converter.convert`. A new format is
added by subclassing :class:`BaseReporter`.
"""

import json
from abc import ABC, abstractmethod
from collections.abc import Mapping
from pathlib import Path
from typing import IO, Any, ClassVar

import yaml


def _plain(data: Mapping[str, Any]) -> Any:
    """Return ``data`` with every value a reporter cannot serialise turned into its string form.

    Converters record values such as paths, enums or addresses; reporters only
    need to handle plain mappings, lists, strings, numbers, booleans and ``None``.
    """
    return json.loads(json.dumps(data, default=str))


class BaseReporter(ABC):
    """Writes report data into a report folder.

    Attributes:
        filename (str): Name of the file written into the report folder.
    """

    filename: ClassVar[str]

    def write(self, data: Mapping[str, Any], folder: Path) -> Path:
        """Write ``data`` to ``folder / filename``, replacing an existing file.

        Args:
            data: The report data, as ``{group: content}``.
            folder: The report folder.

        Returns:
            The path of the written file.
        """
        path = folder / self.filename
        with open(path, "w", encoding="utf-8") as stream:
            self.dump(_plain(data), stream)
        return path

    @abstractmethod
    def dump(self, data: Any, stream: IO[str]) -> None:
        """Serialise plain report data to an open text stream.

        Args:
            data: The report data, holding only plain values.
            stream: The file to write to.
        """


class YamlReporter(BaseReporter):
    """Writes the report data as ``report.yaml``."""

    filename = "report.yaml"

    def dump(self, data: Any, stream: IO[str]) -> None:
        """Serialise the report data as YAML, keeping the recording order."""
        yaml.safe_dump(data, stream, sort_keys=False, allow_unicode=True)


class JsonReporter(BaseReporter):
    """Writes the report data as ``report.json``."""

    filename = "report.json"

    def dump(self, data: Any, stream: IO[str]) -> None:
        """Serialise the report data as indented JSON."""
        json.dump(data, stream, indent=2, ensure_ascii=False)


#: Reporters used when none are given: a single ``report.yaml``.
DEFAULT_REPORTERS: tuple[BaseReporter, ...] = (YamlReporter(),)
