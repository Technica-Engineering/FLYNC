"""Loading of DBC files into cantools databases."""

import logging
from pathlib import Path
from typing import List, Optional, Tuple, cast

import cantools.database
from cantools.database.can.database import Database

from flync.model.flync_4_bus.can_bus import _ALLOWED_CAN_BAUD_RATES, _ALLOWED_CAN_FD_DATA_RATES

from ...base.converter_report import INACTIVE_REPORT, ConverterReport
from .dbc_config import DbcConverterConfig

logger = logging.getLogger(__name__)


def load_dbc_files(root_folder, report: ConverterReport = INACTIVE_REPORT) -> List[Tuple[Database, Path]]:
    """Recursively load all DBC files from a folder.

    The files read are recorded in ``report`` as ``input_files``.

    Args:
        root_folder: Root folder path to search for DBC files.
        report: The converter's report.

    Returns:
        List of ``(cantools Database, source Path)`` tuples, one entry per
        DBC file found.  The source path is needed because cantools does not
        expose the per-file name on the parsed database (it does expose the
        ``Baudrate`` / ``BaudrateCANFD`` attributes, which are used for the
        bus bit rates).
    """

    dbc_files: List[Tuple[Database, Path]] = []

    root = Path(root_folder)
    logger.debug("Scanning for DBC files under: %s", root_folder)

    if root.is_file():
        candidates = [root]
    else:
        candidates = sorted(root.rglob("*.dbc"))

    for dbc_file in candidates:
        logger.debug("Loading DBC file: %s", dbc_file)
        tmp = cast(Database, cantools.database.load_file(dbc_file))
        logger.info("Loaded %s: %d message(s), %d node(s)", dbc_file, len(tmp.messages), len(tmp.nodes))
        dbc_files.append((tmp, dbc_file))

    if not candidates:
        logger.warning("No DBC file found under: %s", root_folder)
    logger.debug("Finished loading DBC files: %d total files found", len(dbc_files))
    report.add("input_files", candidates)

    return dbc_files


def _attribute_value(db, name: str) -> Optional[int]:
    """Return the raw integer value of a DBC ``Baudrate*`` attribute.

    Resolves from the applied ``BA_`` value first (``db.dbc.attributes``) and falls
    back to the ``BA_DEF_DEF_`` definition default (``db.dbc.attribute_definitions``),
    which is how most Vector/ODX DBC files declare the bus bit rate.  Returns ``None``
    when the attribute is absent or not an integer.
    """
    applied = db.dbc.attributes.get(name)
    if applied is not None:
        value = getattr(applied, "value", applied)
        if isinstance(value, int):
            return value
    definition = db.dbc.attribute_definitions.get(name)
    if definition is not None and isinstance(getattr(definition, "default_value", None), int):
        return definition.default_value
    return None


def _baud_rate(db, attribute: str, allowed, default: int, bus_name: str, report: ConverterReport) -> int:
    """Return the value of a ``Baudrate*`` attribute, or ``default`` when it is absent or not allowed.

    An attribute value outside the FLYNC allow-list is logged and recorded in
    ``report`` as ``skipped``.
    """
    value = _attribute_value(db, attribute)
    if value is None:
        return default
    if value in allowed:
        return value
    logger.warning("%s %d of bus '%s' is not an allowed FLYNC rate, using %d", attribute, value, bus_name, default)
    report.skipped(f"{bus_name}.{attribute}", reason=f"{value} is not an allowed FLYNC rate, {default} used instead")
    return default


def _nominal_baud_rate(db, config: DbcConverterConfig, bus_name: str = "", report: ConverterReport = INACTIVE_REPORT) -> int:
    """Return the bus nominal bit rate, honoring the ``Baudrate`` attribute."""
    return _baud_rate(db, "Baudrate", _ALLOWED_CAN_BAUD_RATES, config.baud_rate_default, bus_name, report)


def _fd_baud_rate(db, config: DbcConverterConfig, bus_name: str = "", report: ConverterReport = INACTIVE_REPORT) -> int:
    """Return the CAN FD data-phase bit rate, honoring the ``BaudrateCANFD`` attribute."""
    return _baud_rate(db, "BaudrateCANFD", _ALLOWED_CAN_FD_DATA_RATES, config.fd_baud_rate_default, bus_name, report)
