"""CLI, TUI, and GUI entry points for flync_converter.

Provides three modes:
- quick CLI commands for scripted conversions (`convert`, `list-converters`)
- interactive Textual TUI (`tui` subcommand, `-i`/`--interactive` flag, or
  the `flync-converter-interactive` entry point)
- PySide6 desktop GUI (`gui` subcommand, `--gui` flag, or the
  `flync-converter-gui` entry point)

The module exposes `main`, `main_interactive`, and `main_gui` entry points
used by packaging.
"""

from . import commands  # noqa: F401 — registers subcommands on cli
from .group import cli


def main():
    """Entry point for the non-interactive CLI."""
    from flync_converter.registry import registry

    registry.load_plugins()
    cli()


def main_interactive():
    """Entry point for the interactive TUI CLI."""
    from flync_converter.cli.tui import run_tui

    run_tui()


def main_gui():
    """Entry point for the PySide6 GUI."""
    from flync_converter.cli.gui import run_gui

    run_gui()


if __name__ == "__main__":
    main()
