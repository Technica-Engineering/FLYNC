"""Integration test for plugin discovery via CLI."""

import subprocess
import sys
import tempfile
from pathlib import Path


def _get_registered_converters(flync_converter_exe: Path) -> list[str]:
    """Get list of registered converters by running flync-converter list-converters.

    Args:
        flync_converter_exe: Path to the flync-converter executable.

    Returns:
        List of converter names found in the output.

    Raises:
        AssertionError: If the CLI command fails.
    """
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

    return result.stdout


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
        subprocess.run(
            [str(pip_exe), "install", "-e", "."],
            cwd=Path(__file__).parent.parent.parent,
            check=True,
            capture_output=True,
            text=True,
        )

        # Verify we can list converters and there are some available
        converters_before = _get_registered_converters(flync_converter_exe)
        assert len(converters_before) > 0, "Expected at least some converters to be registered"

        # Verify dummy plugin is NOT in the list before installation
        assert "dummy" not in converters_before, (
            f"Expected 'dummy' converter NOT in output before plugin install, got:\n{converters_before}"
        )

        # Install the dummy plugin in the venv
        subprocess.run(
            [str(pip_exe), "install", "-e", str(plugin_path), "--no-deps"],
            check=True,
            capture_output=True,
            text=True,
        )

        # Verify the dummy plugin is now in the list after installation
        converters_after = _get_registered_converters(flync_converter_exe)
        assert "dummy" in converters_after, (
            f"Expected 'dummy' converter in output after plugin install, got:\n{converters_after}"
        )
