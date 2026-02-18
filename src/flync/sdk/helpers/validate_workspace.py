import argparse
import re
import sys
from pathlib import Path

from pydantic import ValidationError
from pydantic_core import ErrorDetails
from rich.console import Console
from rich.table import Table

from flync.sdk.workspace.flync_workspace import FLYNCWorkspace

PROJECT_BASE = Path(__file__).resolve().parent.parent
VALIDATION_ERRORS: dict = {}
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")
console = Console(force_terminal=True)


def sanitize_error_message(error_msg: str) -> str:
    return ANSI_ESCAPE_RE.sub("", error_msg)


def __add_pydantic_errors_to_report(
    pydantic_validation_errors: list[ErrorDetails],
    error_list: list,
):
    for err in pydantic_validation_errors:
        location = ".".join(str(p) for p in err.get("loc", []))
        err_type = err.get("type", "")
        msg = err.get("msg", "")
        ctx = ", ".join(f"{k}={v}" for k, v in err.get("ctx", {}).items())
        error_list.append([err_type, msg, location, ctx])


def add_errors_to_report(
    errors_report,
    config_name: str,
    exc: Exception,
):
    errs: list = []

    if isinstance(exc, ValidationError):
        pydantic_validation_errors = exc.errors()
        __add_pydantic_errors_to_report(pydantic_validation_errors, errs)
    else:
        # Generic exception handling
        location = ""
        err_type = type(exc).__name__
        msg = sanitize_error_message(str(exc))
        ctx = ""
        errs.append([err_type, msg, location, ctx])

    errors_report[config_name] = errs
    return errors_report


def render_validation_errors() -> None:
    """
    Display FLYNC project validation errors as a table.
    """

    for _, errs in VALIDATION_ERRORS.items():
        table = Table(
            show_lines=True,
        )
        table.add_column("Num.", justify="right")
        table.add_column("Error Type", style="red")
        table.add_column("Message", style="yellow")
        table.add_column("Location", style="cyan")
        table.add_column("Context", style="green")

        for idx, error_row in enumerate(errs, 1):
            table.add_row(str(idx), *error_row)

        console.print(table)


parser = argparse.ArgumentParser(
    description="Script to validate a FLYNC workspace."
)
parser.add_argument("path", help="Absolute path to FLYNC configuration.")
parser.add_argument(
    "-n",
    "--name",
    default="flync_config",
    help="Name of FLYNC configuration.",
)
args = parser.parse_args()

path = Path(args.path)
flync_name = args.name

if not path.exists():
    print(f"Error: Path does not exist: {path}", file=sys.stderr)
    sys.exit(1)


console.print(f"Validating {flync_name} ...")
loaded_ws = None
try:
    loaded_ws = FLYNCWorkspace.load_workspace(flync_name, path.resolve())
except Exception as e:
    console.print(
        f"⚠️ [bold red] Validation of {flync_name} failed![/bold red]"
    )
    VALIDATION_ERRORS = add_errors_to_report(VALIDATION_ERRORS, flync_name, e)
if loaded_ws and loaded_ws.load_errors:
    if flync_name not in VALIDATION_ERRORS:
        VALIDATION_ERRORS[flync_name] = []
    __add_pydantic_errors_to_report(
        loaded_ws.load_errors, VALIDATION_ERRORS[flync_name]
    )
render_validation_errors()

if len(VALIDATION_ERRORS) == 0:
    console.print(
        f"✅ [bold green]{flync_name} is properly configured! [bold green]"
    )
    sys.exit(0)
else:
    sys.exit(1)
