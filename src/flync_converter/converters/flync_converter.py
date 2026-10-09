"""Converter for native FLYNC workspace files."""

import logging

from pydantic import ValidationError

from flync.core.utils.exceptions_handling import errors_to_init_errors
from flync.model import FLYNCModel
from flync.sdk.workspace.flync_workspace import (  # noqa # type: ignore[import-untyped]
    FLYNCWorkspace,
)

from ..base.base_converter import BaseConverter
from ..base.converter_report import INACTIVE_REPORT, ConverterReport
from ..registry import hookimpl

"""classe for converter between :class:`FLYNCModel` a FLYNC workspace."""

logger = logging.getLogger(__name__)


def log_workspace_diagnostics(ws: FLYNCWorkspace, report: ConverterReport = INACTIVE_REPORT) -> None:
    """Log and report the validation findings collected while loading a workspace.

    Each finding is logged on its own line with its document, error id (or
    Pydantic error type), location and message: warnings at ``WARNING``, every
    other finding at ``ERROR``. A summary line is logged at ``INFO``.

    The findings are also recorded in ``report`` as ``diagnostics``, one entry
    per finding with its document, id, severity, location and message.

    Args:
        ws: The loaded workspace.
        report: The converter's report.
    """
    findings = []
    for document, errors in ws.documents_diags.items():
        for error in errors:
            is_warning = error.get("type") == "warning"
            error_id = (error.get("ctx") or {}).get("error_id", error.get("type"))
            location = ".".join(str(part) for part in error.get("loc", ())) or "<root>"
            logger.log(logging.WARNING if is_warning else logging.ERROR, "%s: %s at %s: %s", document, error_id, location, error.get("msg"))
            findings.append(
                {
                    "document": document,
                    "id": error_id,
                    "severity": "warning" if is_warning else "error",
                    "location": location,
                    "message": error.get("msg"),
                }
            )
    logger.info("Workspace diagnostics: %d finding(s)", len(findings))
    if findings:
        report.add("diagnostics", findings)


class FLYNCConverter(BaseConverter):
    """Converter between FLYNCModel and FLYNC workspace format.

    Reads/writes FLYNCModel instances to/from FLYNC workspaces. The FLYNC SDK
    log records and the workspace diagnostics are part of the conversion log.
    """

    name = "flync"
    uses_directory = True
    report_loggers = (__name__, "flync.sdk")

    def can_decode(self):
        """Return True — the FLYNC workspace converter supports decoding."""
        return True

    def encode(self, source: FLYNCModel):
        """Encode a FLYNCModel into target representation.

        Args:
            source (FLYNCModel): The model to encode.

        Returns:
            Any: The encoded representation.
        """
        if self.config is None:
            raise ValueError("config must be set before encoding")
        logger.info(
            "Encoding FLYNCModel to FLYNC workspace at: %s",
            self.config.config_path,
        )
        ws = FLYNCWorkspace.load_model(source, "converted workspace", self.config.config_path)
        ws.generate_configs()
        logger.info("FLYNC workspace written to: %s", self.config.config_path)
        self.report.add("workspace", self.config.config_path)
        log_workspace_diagnostics(ws, self.report)

    def decode(self) -> FLYNCModel:
        """Decode data into a FLYNCBaseModel.

        The workspace diagnostics are logged before the model is checked, so
        they reach the conversion log even when loading fails.

        Returns:
            FLYNCBaseModel: The decoded model.

        Raises:
            ValidationError: If the workspace does not produce a model.
        """
        if self.config is None:
            raise ValueError("config must be set before decoding")
        logger.info("Loading FLYNC workspace from: %s", self.config.config_path)
        ws = FLYNCWorkspace.safe_load_workspace("converted_workspace", self.config.config_path)
        self.report.add("workspace", self.config.config_path)
        log_workspace_diagnostics(ws, self.report)
        if not isinstance(ws.flync_model, FLYNCModel):
            raise ValidationError.from_exception_data(
                title="Model (converted_workspace) Creation Error",
                line_errors=errors_to_init_errors(ws.load_errors),
            )
        logger.info("FLYNC workspace loaded, extracting FLYNCModel")
        return ws.flync_model


@hookimpl
def register_converters():
    """Register the FLYNCConverter with the pluggy plugin manager."""
    return [FLYNCConverter()]
