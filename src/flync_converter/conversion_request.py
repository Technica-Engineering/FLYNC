"""Request and result objects of a many-source, many-output conversion.

A request keeps each path, converter type and converter configuration
together, and can be stored as a YAML file, the conversion manifest::

    on_conflict: first
    sources:
      - {path: extracts/a, converter_type: arxml}
      - {path: extracts/b, converter_type: arxml}
    outputs:
      - {path: out/powertrain, converter_type: dbc}
      - {path: out/body, converter_type: dbc, config: {baud_rate_default: 250000}}

Paths in a manifest are relative to the folder the manifest is in.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from flync.model import FLYNCModel

from .base import ConverterConfig
from .model_merger import MergeConflict, OnConflict


class _Endpoint(BaseModel):
    """One folder or file a conversion reads from or writes to.

    Attributes:
        path: Location the converter reads from or writes to.
        converter_type: Registered name of the converter.
        config: Configuration of the converter: nothing (the configuration
            stored in the endpoint, or the defaults), the path of a
            configuration YAML file used instead of the stored one, or a
            configuration object or a mapping of fields layered over the
            stored configuration.
    """

    model_config = ConfigDict(extra="forbid")

    path: Path | str
    converter_type: str
    config: ConverterConfig | Path | str | dict[str, Any] | None = None

    @model_validator(mode="after")
    def _config_object_matches_path(self) -> Self:
        """Reject a configuration object pointing somewhere else than ``path``."""
        if isinstance(self.config, ConverterConfig) and _resolved(self.config.config_path) != _resolved(self.path):
            raise ValueError(f"path {str(self.path)!r} differs from the config_path {self.config.config_path!r} of its configuration")
        return self

    def describe(self) -> str:
        """Return ``<converter_type>:<path>``, for messages."""
        return f"{self.converter_type}:{self.path}"


class ConversionSource(_Endpoint):
    """One source, decoded into a FLYNC model."""


class ConversionOutput(_Endpoint):
    """One output, written from the merged FLYNC model."""

    converter_type: str = "flync"


def _resolved(path: Path | str) -> Path:
    """Return the absolute form of an endpoint path, for comparing endpoints."""
    return Path(path).resolve()


def _rebase(endpoint: Any, base: Path) -> None:
    """Resolve the relative ``path`` and ``config`` file of one manifest endpoint against ``base``, in place."""
    if not isinstance(endpoint, dict):
        return
    for key in ("path", "config"):
        if isinstance(endpoint.get(key), str):
            endpoint[key] = str(base / endpoint[key])


def _overlap(first: Path, second: Path) -> bool:
    """Return whether two paths are the same or one contains the other."""
    return first == second or first in second.parents or second in first.parents


class ConversionRequest(BaseModel):
    """One conversion: its sources, its outputs and how conflicts are handled.

    Attributes:
        sources: The sources, in merge order. At least one.
        outputs: The outputs. At least one.
        on_conflict: Policy for values two sources disagree on.
        fail_fast: When ``True``, the first output that fails ends the
            conversion with its own exception. Otherwise the remaining outputs
            are still written and the failures are raised together at the end.
    """

    model_config = ConfigDict(extra="forbid")

    sources: list[ConversionSource] = Field(min_length=1)
    outputs: list[ConversionOutput] = Field(min_length=1)
    on_conflict: OnConflict = OnConflict.FIRST
    fail_fast: bool = False

    @model_validator(mode="after")
    def _endpoints_do_not_collide(self) -> Self:
        """Reject an endpoint used twice and a source that is also written to."""
        for endpoints in (self.sources, self.outputs):
            seen: set[tuple[Path, str]] = set()
            for endpoint in endpoints:
                key = (_resolved(endpoint.path), endpoint.converter_type)
                if key in seen:
                    raise ValueError(f"{endpoint.describe()} is listed twice")
                seen.add(key)
        for source in self.sources:
            for output in self.outputs:
                if _overlap(_resolved(source.path), _resolved(output.path)):
                    raise ValueError(f"source {source.describe()} and output {output.describe()} overlap; a conversion cannot write where it reads")
        return self

    @classmethod
    def from_yaml_file(cls, path: str | Path) -> Self:
        """Load a request from a conversion manifest.

        Relative endpoint paths and configuration file paths are resolved
        against the folder the manifest is in.

        Args:
            path: Path of the manifest.

        Returns:
            The validated request.

        Raises:
            FileNotFoundError: If the manifest does not exist.
            ValueError: If the manifest is not a mapping or does not describe a valid request.
        """
        manifest = Path(path)
        with open(manifest, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            raise ValueError(f"{manifest}: a conversion manifest must contain a mapping, got {type(data).__name__}")

        for role in ("sources", "outputs"):
            for endpoint in data.get(role) or []:
                _rebase(endpoint, manifest.parent)
        return cls.model_validate(data)


@dataclass(frozen=True)
class OutputFailure:
    """One output that could not be written."""

    output: ConversionOutput
    error: Exception


@dataclass
class ConversionResult:
    """What a conversion did.

    Attributes:
        model: The decoded, merged model every output was written from.
        decoded: The sources, in merge order.
        written: The outputs that were written.
        failures: The outputs that failed, with what they raised.
        conflicts: The conflicts the merge resolved.
    """

    model: FLYNCModel
    decoded: list[ConversionSource] = field(default_factory=list)
    written: list[ConversionOutput] = field(default_factory=list)
    failures: list[OutputFailure] = field(default_factory=list)
    conflicts: tuple[MergeConflict, ...] = ()

    @property
    def ok(self) -> bool:
        """Whether every output was written."""
        return not self.failures


class ConversionOutputError(Exception):
    """Raised at the end of a conversion in which one or more outputs failed.

    Attributes:
        result: What the conversion did, including the outputs that were written.
    """

    def __init__(self, result: ConversionResult) -> None:
        self.result = result
        failed = "; ".join(f"{failure.output.describe()}: {failure.error}" for failure in result.failures)
        super().__init__(f"{len(result.failures)} of {len(result.failures) + len(result.written)} output(s) failed: {failed}")
