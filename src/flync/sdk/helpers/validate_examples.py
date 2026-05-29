"""
Example validation script for the FLYNC SDK.

Iterates over every subdirectory in the ``examples/`` folder at the project root and validates each one as a FLYNC workspace by invoking
:mod:`flync.sdk.helpers.validate_workspace` as a subprocess.
"""

import subprocess
from pathlib import Path

PROJECT_BASE = Path(__file__).resolve().parents[4]
EXAMPLES_DIR = PROJECT_BASE / "examples"
WORKSPACE_EXAMPLE = EXAMPLES_DIR / "flync_example"
ECU_VARIANTS = EXAMPLES_DIR / "ecu_variants"

print("----- Validate Workspace Example -----")
subprocess.run(
    [
        "flync",
        "validate",
        WORKSPACE_EXAMPLE,
        "--config",
        WORKSPACE_EXAMPLE.name,
    ]
)

print("----- Validate ECU Variants -----")
for example_dir in list(ECU_VARIANTS.iterdir()):
    subprocess.run(
        [
            "flync",
            "validate",
            example_dir,
            "--config",
            example_dir.name,
            "--node",
            "ECU",
        ]
    )
