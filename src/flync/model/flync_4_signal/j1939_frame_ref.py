"""Reference to a J1939 frame by name and/or CAN identifier."""

from typing import Self

from pydantic import Field, field_validator, model_validator

from flync.core.base_models import FLYNCBaseModel
from flync.core.utils.exceptions import Category, err_major


class J1939FrameRef(FLYNCBaseModel):
    """
    Reference to a J1939 frame by frame name and/or on-bus CAN identifier.

    ``J1939Frame`` may be addressed by its ``name`` (a string), by its full on-bus CAN identifier
    ``can_id`` (an integer that carries the emitter's Source Address in its low 8 bits), or by both. The
    identifier follows the J1939 CAN identifier layout
    ``(priority << 26) | (extended_data_page << 25) | (data_page << 24) | (pdu_format << 16) | (pdu_specific << 8) | sa``;
    at reference-resolution time the frame it names is recovered by stripping the Source Address bits.
    Because references resolve by name or CAN id (not by PGN), a bus may carry several frames that share a
    Parameter Group Number while staying distinguishable.

    The bus is not part of the reference: it is the ``bus_ref`` of the owning
    :class:`~flync.model.flync_4_ecu.can_interface.CANInterface`.

    Parameters
    ----------
    frame_ref : str, optional
        Name of the :class:`~flync.model.flync_4_signal.frame.J1939Frame` on the interface's bus. At least one
        of ``frame_ref`` or ``can_id`` must be given.
    can_id : int, optional
        Full 29-bit CAN identifier of the frame as it appears on the bus (Source Address included in its low
        byte). At least one of ``frame_ref`` or ``can_id`` must be given.
    """

    frame_ref: str | None = Field(default=None)
    can_id: int | None = Field(default=None, ge=0, le=0x1FFFFFFF)

    @field_validator("frame_ref")
    @classmethod
    def _frame_ref_not_empty_string(cls, value: str | None) -> str | None:
        """Reject a blank string used as the frame-name form of ``frame_ref``."""
        if isinstance(value, str) and not value:
            raise ValueError("frame_ref must not be empty")
        return value

    @model_validator(mode="after")
    def _require_name_or_can_id(self) -> Self:
        """A J1939 frame reference must name the frame or give its on-bus CAN identifier."""

        if self.frame_ref is None and self.can_id is None:
            raise err_major(
                "J1939FrameRef: a J1939 reference must set frame_ref and/or can_id.",
                category=Category.REQUIRED,
                error_number="422",
            )
        return self
