"""
Example validation script for the FLYNC SDK.

Iterates over every subdirectory in the ``examples/`` folder at the project
root and validates each one as a FLYNC workspace by invoking
:mod:`flync.sdk.helpers.validate_workspace` as a subprocess.
"""

import subprocess
from pathlib import Path
from sys import executable

PROJECT_BASE = Path(__file__).resolve().parents[4]
VALIDATE_WORKSPACE_SCRIPT = Path.joinpath(
    Path(__file__).resolve().parent, Path("validate_workspace.py")
)
EXAMPLES_DIR = PROJECT_BASE / "examples"


for example_dir in list(EXAMPLES_DIR.iterdir()):
    subprocess.run(
        [
            executable,
            VALIDATE_WORKSPACE_SCRIPT,
            example_dir,
            "--name",
            example_dir.name,
        ]
    )
