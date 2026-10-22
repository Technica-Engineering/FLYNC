"""Reference to a CAN frame by CAN ID and identifier format."""

from typing import Literal

from pydantic import Field

from flync.core.base_models import FLYNCBaseModel


class CANFrameRef(FLYNCBaseModel):
    """
    Reference to a CAN frame by CAN ID and identifier format.

    The bus is not part of the reference: it is the ``bus_ref`` of the owning :class:`~flync.model.flync_4_ecu.can_interface.CANInterface`.
    The combination of ``id_format`` and ``frame_ref`` locates the frame on that bus.

    Parameters
    ----------
    frame_ref : int
        CAN ID of the :class:`~flync.model.flync_4_signal.frame.CANFrame` or
        :class:`~flync.model.flync_4_signal.frame.CANFDFrame` on the interface's bus.
    id_format : Literal["standard_11bit", "extended_29bit"]
        Identifier format of the referenced frame. A standard and an extended frame may share the same
        numeric CAN ID on one bus, so the format is needed to tell them apart.
    """

    frame_ref: int = Field()
    id_format: Literal["standard_11bit", "extended_29bit"] = Field()
