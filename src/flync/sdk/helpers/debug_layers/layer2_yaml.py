"""Layer 2: YAML syntax validation.

Parses every .flync.yaml file under the target directory with the workspace's YAML loader.  Reports any file that cannot be
parsed as valid YAML before the schema loader even tries to read it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from flync.core.utils import yaml_io

FLYNC_EXT = ".flync.yaml"


@dataclass
class YAMLIssue(object):
    """A single YAML parsing/structure issue found in Layer 2 checks."""

    message: str
    path: str
    line: int | None = None
    col: int | None = None


def check_yaml_syntax(dir_path: Path) -> list[YAMLIssue]:
    """
    Parse every *.flync.yaml file under dir_path and return one YAMLIssue
    for each file that contains a syntax error.
    """
    issues: list[YAMLIssue] = []

    _check_yaml_files(dir_path, issues)

    return issues


def _check_yaml_files(dir_path: Path, issues: list[YAMLIssue]) -> None:
    """Parse every .flync.yaml file under dir_path collecting syntax issues."""
    for yaml_file in sorted(dir_path.rglob(f"*{FLYNC_EXT}")):
        try:
            with open(yaml_file, encoding="utf-8") as fh:
                yaml_io.safe_load(fh)
        except yaml_io.YAMLError as exc:
            mark = getattr(exc, "problem_mark", None)
            issues.append(
                YAMLIssue(
                    message=getattr(exc, "problem", str(exc)) or str(exc),
                    path=str(yaml_file.relative_to(dir_path)),
                    line=mark.line + 1 if mark else None,
                    col=mark.column + 1 if mark else None,
                )
            )
        except Exception as exc:
            issues.append(
                YAMLIssue(
                    message=str(exc),
                    path=str(yaml_file.relative_to(dir_path)),
                )
            )
