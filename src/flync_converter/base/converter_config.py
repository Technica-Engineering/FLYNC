"""Configuration object passed to FLYNC converters.

A destination workspace can store a converter's configuration on disk, one file
per converter, inside the same ``.flync`` directory that holds the workspace
configuration::

    <destination>/.flync/converters/<converter_name>.yaml

The file is written after every conversion (unless ``persist_config`` is
``False``) and by :meth:`ConverterConfig.to_yaml_file`, and is read back by
:meth:`ConverterConfig.from_workspace` as the base that explicitly supplied
values override.
"""

import logging
from pathlib import Path
from typing import Any, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from flync.model.flync_4_metadata.metadata import BaseVersion
from flync.sdk.context.workspace_config import CONFIG_DIRNAME, _get_current_flync_version

logger = logging.getLogger(__name__)

#: Sub-directory of :data:`~flync.sdk.context.workspace_config.CONFIG_DIRNAME`
#: holding one configuration file per converter.
CONVERTERS_DIRNAME = "converters"

#: Extension of a persisted converter configuration file.
CONFIG_SUFFIX = ".yaml"

#: Fields that are never read from, nor written to, a converter configuration
#: file. ``config_path`` is the location the file belongs to, usually an
#: absolute path on one machine, so it is always supplied by the caller.
NON_PERSISTED_FIELDS = frozenset({"config_path"})

#: Fields that only apply to the destination side of a conversion. Front ends
#: do not offer them for the source converter.
DESTINATION_ONLY_FIELDS = frozenset({"report_enabled", "report_min_log_level", "persist_config"})


def parse_log_level(value: str | int) -> int:
    """Convert a logging level name or number into a logging level integer.

    Args:
        value: A level name (``"DEBUG"``, case-insensitive), a number, or a
            string of digits (``"10"``).

    Returns:
        The logging level integer.

    Raises:
        ValueError: If ``value`` is neither a known level name nor a number.
    """
    if isinstance(value, bool):
        raise ValueError(f"Unknown log level {value!r}")
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if text.isdigit():
        return int(text)
    try:
        return logging.getLevelNamesMapping()[text.upper()]
    except KeyError:
        raise ValueError(f"Unknown log level {value!r}; expected one of {', '.join(logging.getLevelNamesMapping())} or a number") from None


def converter_config_file(workspace_path: str | Path, converter_name: str) -> Path:
    """Return the configuration file path of a converter inside a workspace.

    Args:
        workspace_path: Root of the workspace the converter writes into.
        converter_name: Registered name of the converter.

    Returns:
        ``<workspace_path>/.flync/converters/<converter_name>.yaml``.
    """
    return Path(workspace_path) / CONFIG_DIRNAME / CONVERTERS_DIRNAME / f"{converter_name}{CONFIG_SUFFIX}"


class ConverterConfig(BaseModel):
    """Configuration model for converters.

    Converter-specific configuration classes subclass this model and add their
    own fields. Every field except those in :data:`NON_PERSISTED_FIELDS` can be
    stored in the destination workspace (see :func:`converter_config_file`).

    Attributes:
        config_path (str): Location the converter reads from or writes to.
        report_enabled (bool): When ``True`` (the default), the conversion log is written to
        ``<destination>/.flync/reports/<converter_name>/logs.txt``.
        report_min_log_level (str): Lowest severity captured in the conversion log, as a level name
        (``"DEBUG"``, ``"INFO"``, ...) or number. Stored as the canonical name. Defaults to ``"INFO"``.
        persist_config (bool): When ``True`` (the default), every conversion writes this configuration
        to the destination workspace. :meth:`to_yaml_file` writes regardless of this setting.
        version (BaseVersion): FLYNC release that last wrote this configuration. Moved forward (never
        backwards) when a newer FLYNC rewrites the file.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    config_path: str
    report_enabled: bool = True
    report_min_log_level: str = "INFO"
    persist_config: bool = True
    version: BaseVersion = Field(default_factory=_get_current_flync_version)

    @field_validator("report_min_log_level", mode="before")
    @classmethod
    def validate_report_min_log_level(cls, value: Any) -> str:
        """Reject unknown levels and store known numeric levels by name."""
        level = parse_log_level(value)
        name = logging.getLevelName(level)
        return name if name in logging.getLevelNamesMapping() else str(level)

    @property
    def report_level(self) -> int:
        """The :attr:`report_min_log_level` as a logging level integer."""
        return parse_log_level(self.report_min_log_level)

    @classmethod
    def from_yaml_file(cls, path: str | Path, config_path: str | Path) -> Self:
        """Load a configuration from a YAML file.

        Args:
            path: Path of the YAML file.
            config_path: Value for :attr:`config_path`, which the file never carries.

        Returns:
            A configuration with the values from the file.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the file is not a mapping, contains an unknown key, or
                sets a field from :data:`NON_PERSISTED_FIELDS`.
        """
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        if not isinstance(data, dict):
            raise ValueError(f"YAML file must contain a mapping, got {type(data).__name__}")

        rejected = sorted(NON_PERSISTED_FIELDS.intersection(data))
        if rejected:
            raise ValueError(f"{file_path}: {', '.join(rejected)} cannot be set from a configuration file; it is supplied by the caller.")

        # Unknown keys are rejected (extra="forbid") so typos in a hand-edited file are not silently ignored.
        return cls(config_path=str(config_path), **data)

    @classmethod
    def from_workspace(cls, workspace_path: str | Path, converter_name: str) -> Self:
        """Resolve the base configuration of a converter for a workspace.

        Loads :func:`converter_config_file` if it exists, otherwise returns
        defaults. :attr:`config_path` is set to ``workspace_path`` in both cases.

        Args:
            workspace_path: Root of the workspace the converter writes into.
            converter_name: Registered name of the converter.

        Returns:
            The stored configuration, or a default one.
        """
        file_path = converter_config_file(workspace_path, converter_name)
        if file_path.exists():
            return cls.from_yaml_file(file_path, workspace_path)
        return cls(config_path=str(workspace_path))

    def _version_to_persist(self) -> BaseVersion:
        """Return the newer of the running FLYNC release and :attr:`version`.

        Versions recorded under a different ``version_schema`` are not
        comparable and are returned unchanged.
        """
        current = _get_current_flync_version()
        if self.version.version_schema != current.version_schema:
            return self.version
        return current if current.version > self.version.version else self.version

    def to_yaml_file(self, path: str | Path) -> None:
        """Save the configuration to a YAML file.

        Only non-default values are written. ``version`` is always written, and
        fields from :data:`NON_PERSISTED_FIELDS` never are.

        Args:
            path: Path of the YAML file, usually from :func:`converter_config_file`.
        """
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        data: dict[str, Any] = self.model_dump(mode="json", exclude_defaults=True, exclude={"version", *NON_PERSISTED_FIELDS})

        version = self._version_to_persist()
        data["version"] = {
            "version_schema": version.version_schema,
            "version": str(version.version),
        }

        with open(file_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    @classmethod
    def create_from_config(cls, existing_config: "ConverterConfig", **configs: Any) -> Self:
        """Create a new configuration by overriding fields on an existing one.

        Args:
            existing_config: The base configuration to copy from.
            configs: Field names and new values to override.

        Returns:
            A new instance with the overrides applied.
        """
        existing_config_values = existing_config.model_dump()
        existing_config_values.update(**configs)
        return cls(**existing_config_values)
