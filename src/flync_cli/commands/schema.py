"""``flync schema`` command: exports the FLYNC model as JSON Schema files, one per Pydantic model class."""

from enum import Enum
from pathlib import Path
from typing import Optional

import typer
from typing_extensions import Annotated

from flync.model import FLYNCModel
from flync.sdk.utils.model_schema import DEFAULT_SCHEMA_SUFFIX, dump_model_schemas
from flync_cli.utils.console import console

app = typer.Typer()


class SchemaMode(str, Enum):
    """Which side of the model the exported schemas describe."""

    VALIDATION = "validation"
    SERIALIZATION = "serialization"


@app.command(help="Export the FLYNC model as JSON Schema files, one per Pydantic model class, linked with $ref.")
def schema(
    output_dir: Annotated[Path, typer.Argument(help="Directory the schema files are written to.")] = Path("schemas"),
    mode: Annotated[
        SchemaMode,
        typer.Option("--mode", help="Describe the input accepted by validation or the output produced by serialization."),
    ] = SchemaMode.VALIDATION,
    base_uri: Annotated[
        Optional[str],
        typer.Option("--base-uri", help="URI the schema files are published under. Sets an absolute $id on every file."),
    ] = None,
    suffix: Annotated[str, typer.Option("--suffix", help="File name suffix of every schema file.")] = DEFAULT_SCHEMA_SUFFIX,
):
    """Write one JSON Schema file per Pydantic model class reachable from ``FLYNCModel`` into ``output_dir``."""
    paths = dump_model_schemas(FLYNCModel, output_dir, suffix=suffix, mode=mode.value, base_uri=base_uri)
    console.print(f"Exported {len(paths)} schema files to {output_dir}, root schema: {paths[0].name}")
