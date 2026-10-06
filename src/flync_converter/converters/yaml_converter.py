"""Converter that loads and writes FLYNC models as YAML."""

import logging
from pathlib import Path

import yaml

from flync.model import FLYNCModel

from ..base.base_converter import BaseConverter
from ..base.converter_report import INACTIVE_REPORT, ConverterReport
from ..registry import hookimpl
from .helpers import content_files, merge_tracking_overrides, pydantic_dump

"""classe for converter between :class:`FLYNCModel` a YAML file."""

logger = logging.getLogger(__name__)


def load_yaml_files(root_folder, report: ConverterReport = INACTIVE_REPORT):
    """Recursively load all YAML files and merge into a single dict.

    Files inside a ``.flync`` metadata folder are skipped. Files are merged in
    path order; a top-level key defined by several files takes the value of
    the last one.

    The files read are recorded in ``report`` as ``input_files``, and every
    overridden top-level key as ``skipped``.

    Args:
        root_folder: Root folder path to search for YAML files.
        report: The converter's report.

    Returns:
        Merged dictionary from all YAML files found.

    Raises:
        ValueError: If a YAML file does not contain a YAML object.
    """
    combined: dict = {}
    origins: dict[str, Path] = {}
    root = Path(root_folder)
    logger.debug("Scanning for YAML files under: %s", root_folder)

    if root.is_file():
        if root.suffix.casefold() not in {".yaml", ".yml"}:
            raise ValueError(f"Expected a YAML file, got: {root}")
        candidates = [root]
    else:
        candidates = sorted(path for pattern in ("*.yaml", "*.yml") for path in content_files(root, pattern))

    report.add("input_files", candidates)
    for yaml_file in candidates:
        logger.debug("Loading YAML file: %s", yaml_file)
        with yaml_file.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            if isinstance(data, dict):
                logger.debug("Merging %d keys from %s", len(data), yaml_file.name)
                merge_tracking_overrides(combined, data, yaml_file, origins, report)
            else:
                raise ValueError(f"File {yaml_file} is not a YAML object")

    logger.debug("Finished loading YAML files: %d total keys merged", len(combined))
    return combined


class YamlConverter(BaseConverter):
    """Converter between FLYNCModel and YAML format.

    Reads/writes FLYNCModel instances to/from YAML files in a folder.
    """

    name = "yaml"
    report_loggers = (__name__,)
    source_extensions = ("yaml", "yml")

    def can_decode(self):
        """Return True — the YAML converter supports decoding."""
        return True

    def encode(self, source: FLYNCModel):
        """Encode a FLYNCModel into target representation.

        Args:
            source (FLYNCModel): The model to encode.

        Returns:
            Any: The encoded representation.
        """
        if self.config is None:
            raise ValueError("config must be set before encoding")
        configured_path = Path(self.config.config_path)
        output_path = (
            configured_path if configured_path.suffix.casefold() in {".yaml", ".yml"} else configured_path / f"{source.__class__.__name__}.yaml"
        )
        logger.debug("Encoding FLYNCModel to YAML at: %s", output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as output:
            yaml.safe_dump(pydantic_dump(source), output, indent=2, sort_keys=False)
        self.report.add("output_file", output_path)
        logger.info("YAML encode complete: %s", output_path)

    def decode(self) -> FLYNCModel:
        """Decode data into a FLYNCModel.

        Returns:
            FLYNCModel: The decoded model.
        """
        if self.config is None:
            raise ValueError("config must be set before decoding")
        logger.debug(
            "Decoding FLYNCModel from YAML path: %s",
            self.config.config_path,
        )
        dict_content = load_yaml_files(self.config.config_path, self.report)
        logger.debug("Validating FLYNCModel from %d keys", len(dict_content))
        model = FLYNCModel.model_validate(dict_content)
        logger.debug("YAML decode complete")
        return model


@hookimpl
def register_converters():
    """Register the YamlConverter with the pluggy plugin manager."""
    return [YamlConverter()]
