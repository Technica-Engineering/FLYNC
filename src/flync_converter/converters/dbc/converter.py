"""The DBC converter class (encode/decode glue)."""

import logging
from pathlib import Path
from typing import Optional

from flync.model import FLYNCModel

from ...base.base_converter import BaseConverter
from .dbc_config import DbcConverterConfig
from .decoder import decode_dbc_files
from .encoder import write_dbc_files
from .loading import load_dbc_files

logger = logging.getLogger(__name__)


class DbcConverter(BaseConverter):
    """Converter between FLYNCModel and DBC format.

    Supports both directions: encoding (FLYNC to DBC) and decoding
    (DBC to FLYNC). The cantools log records are part of the converter's log.
    Its report lists the DBC files read or written, and the content that
    could not be converted: ``unsupported`` for content the target format
    cannot represent, ``skipped`` for content left out or replaced.
    """

    name = "dbc"
    report_loggers = ("flync_converter.converters.dbc", "cantools")
    config: Optional[DbcConverterConfig] = None

    def can_decode(self):
        """Return True — the DBC converter supports decoding."""
        return True

    def encode(self, source: FLYNCModel):
        """Encode a FLYNCModel into target representation.

        Args:
            source (FLYNCModel): The model to encode.
        """

        if self.config is None:
            raise ValueError("config must be set before encoding")

        logger.info("Encoding FLYNCModel to DBC at: %s", self.config.config_path)
        destination_path = Path(self.config.config_path)
        output_directory = destination_path.parent if destination_path.suffix.casefold() == ".dbc" else destination_path
        output_directory.mkdir(parents=True, exist_ok=True)

        written = write_dbc_files(source, self.config.config_path, self.report)

        logger.info("DBC encode complete: %d file(s) written to %s", len(written), self.config.config_path)

    def decode(self) -> FLYNCModel:
        """Decode data into a FLYNCBaseModel.

        Returns:
            FLYNCBaseModel: The decoded model.
        """

        if self.config is None:
            raise ValueError("config must be set before decoding")
        logger.info("Decoding FLYNCModel from DBC path: %s", self.config.config_path)

        dbc_files = load_dbc_files(self.config.config_path, self.report)

        model = decode_dbc_files(dbc_files, self.config, self.report)
        logger.info("DBC decode complete: %d file(s) decoded", len(dbc_files))
        return model
