"""Structured report data a converter records during a conversion.

Every converter has a :class:`ConverterReport` as
:attr:`~flync_converter.base.BaseConverter.report`. During a conversion it is
active and its content is written into the converter's report folder by the
converter's :attr:`~flync_converter.base.BaseConverter.reporters`; outside a
conversion, or with reporting disabled, it is inactive and records nothing.

The report holds well-known groups with a fixed structure, filled through
dedicated methods, and a free-form ``custom`` group::

    skipped:
      - {item: ecus.body_ecu, reason: no CAN interface}
    unsupported:
      - {item: pdus.diag_container, reason: Ethernet PDUs have no DBC equivalent}
    custom:
      dbc_files: [CAN1.dbc, CAN2.dbc]
"""

import logging
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .reporters import BaseReporter

logger = logging.getLogger(__name__)


class ConverterReport:
    """Structured report data of one converter for one conversion.

    Groups that received nothing are left out of the written report, and a
    report that received nothing at all is not written.
    """

    def __init__(self, active: bool = True) -> None:
        """Create an empty report.

        Args:
            active: When ``False`` every method records nothing.
        """
        self.active = active
        self._skipped: list[dict[str, str]] = []
        self._unsupported: list[dict[str, str]] = []
        self._custom: dict[str, Any] = {}

    def skipped(self, item: str, reason: str) -> None:
        """Record model content the converter did not use or write.

        Args:
            item: The skipped content, e.g. ``"ecus.body_ecu"``.
            reason: Why it was skipped.
        """
        if self.active:
            self._skipped.append({"item": item, "reason": reason})

    def unsupported(self, item: str, reason: str) -> None:
        """Record content that cannot be represented in the converter's format.

        Args:
            item: The unsupported content, e.g. ``"pdus.diag_container"``.
            reason: Why the format cannot represent it.
        """
        if self.active:
            self._unsupported.append({"item": item, "reason": reason})

    def add(self, key: str, value: Any) -> None:
        """Record any other data under the ``custom`` group.

        Args:
            key: Name of the datum. Adding the same key again replaces the value.
            value: The datum. Values a reporter cannot serialize are written in
                their string form.
        """
        if self.active:
            self._custom[key] = value

    def as_mapping(self) -> dict[str, Any]:
        """Return the recorded groups, leaving out the empty ones."""
        groups: dict[str, Any] = {"skipped": list(self._skipped), "unsupported": list(self._unsupported), "custom": dict(self._custom)}
        return {name: content for name, content in groups.items() if content}

    def is_empty(self) -> bool:
        """Return whether nothing has been recorded."""
        return not (self._skipped or self._unsupported or self._custom)

    def write(self, reporters: Iterable[BaseReporter], folder: Path) -> list[Path]:
        """Write the report with each reporter into ``folder``.

        An empty report writes nothing. A reporter that fails is logged and
        skipped, so a report never replaces the outcome of the conversion it
        describes.

        Args:
            reporters: The reporters to write with.
            folder: The converter's report folder.

        Returns:
            The paths of the files written.
        """
        if self.is_empty():
            return []
        return write_with(reporters, self.as_mapping(), folder)


def write_with(reporters: Iterable[BaseReporter], data: dict[str, Any], folder: Path) -> list[Path]:
    """Write ``data`` with each reporter into ``folder``, logging and skipping a reporter that fails.

    Args:
        reporters: The reporters to write with.
        data: The report data.
        folder: The folder the reporters write into.

    Returns:
        The paths of the files written.
    """
    folder.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for reporter in reporters:
        try:
            written.append(reporter.write(data, folder))
        except Exception:
            logger.exception("Report writer %s failed in %s", type(reporter).__name__, folder)
    return written


#: The report every converter holds outside a conversion; it records nothing.
INACTIVE_REPORT = ConverterReport(active=False)
