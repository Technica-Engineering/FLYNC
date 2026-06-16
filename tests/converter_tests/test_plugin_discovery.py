"""Integration test for plugin discovery via CLI."""

import subprocess
import sys
import tempfile
from pathlib import Path


def test_plugin_discovery_via_cli():
    """Test that the dummy plugin is discovered via CLI in a subprocess."""
    plugin_path = Path(__file__).parent / "test_plugin"

    with tempfile.TemporaryDirectory() as tmpdir:
        venv_path = Path(tmpdir) / "venv"

        # Create virtual environment
        subprocess.run(
            [sys.executable, "-m", "venv", str(venv_path)],
            check=True,
            capture_output=True,
        )

        # Determine the pip and flync-converter executable paths
        if sys.platform == "win32":
            pip_exe = venv_path / "Scripts" / "pip"
            flync_converter_exe = venv_path / "Scripts" / "flync-converter"
        else:
            pip_exe = venv_path / "bin" / "pip"
            flync_converter_exe = venv_path / "bin" / "flync-converter"

        # Install flync in the venv
        result = subprocess.run(
            [str(pip_exe), "install", "-e", "."],
            cwd=Path(__file__).parent.parent.parent,
            check=True,
            capture_output=True,
            text=True,
        )

        # Install the dummy plugin in the venv
        result = subprocess.run(
            [str(pip_exe), "install", "-e", str(plugin_path), "--no-deps"],
            check=True,
            capture_output=True,
            text=True,
        )

        # Run flync-converter list-converters in the venv
        result = subprocess.run(
            [str(flync_converter_exe), "list-converters"],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise AssertionError(
                f"CLI command failed with exit code {result.returncode}\n"
                f"stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}"
            )

        # Verify the dummy plugin is in the output
        assert "dummy" in result.stdout, (
            f"Expected 'dummy' converter in output, got:\n{result.stdout}"
        )
