"""Shared Rich console instance for all flync_cli commands."""

import shutil

from rich.console import Console

# Rich falls back to a bare 80 columns when it cannot detect a real terminal (redirected output, CI logs,
# the test runner) - too narrow for the wider info reports (sockets, ip). Widen that fallback; a real
# terminal's actual size still wins.
_WIDTH, _ = shutil.get_terminal_size(fallback=(200, 50))
console = Console(force_terminal=True, width=_WIDTH)


def print_error(message: str, hint: str | None = None) -> None:
    """
    Print why a command cannot go on: a red ``Error:`` label and the message, then an optional dimmed hint below it.

    Both texts may contain Rich markup, so escape anything that comes from the user or the workspace with
    :func:`rich.markup.escape`.

    Args:
        message (str): What went wrong, as one sentence.
        hint (str | None): What the user can do about it, or what the valid choices are.
    """

    console.print(f"[bold red]Error:[/bold red] {message}", highlight=False)
    if hint:
        console.print(f"       [dim]{hint}[/dim]", highlight=False)
