"""Reference to a J1939 frame by Parameter Group Number."""

from pydantic import Field

from flync.core.base_models import FLYNCBaseModel


class J1939FrameRef(FLYNCBaseModel):
    """
    Reference to a J1939 frame by Parameter Group Number.

    ``J1939Frame`` objects carry no CAN ID; their identity on a bus is the Parameter Group Number (``pgn``),
    which the model enforces as unique per bus (``FLYNC-GEN-MAJ-UNIQ-346``).

    The bus is not part of the reference: it is the ``bus_ref`` of the owning
    :class:`~flync.model.flync_4_ecu.can_interface.CANInterface`.

    Parameters
    ----------
    pgn : int
        18-bit J1939 Parameter Group Number of the :class:`~flync.model.flync_4_signal.frame.J1939Frame`
        on the interface's bus.
    """

    pgn: int = Field(ge=0, le=0x3FFFF)
