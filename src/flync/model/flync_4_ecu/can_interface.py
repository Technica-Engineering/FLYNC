"""CAN interface configuration for ECU controllers."""

from typing import List

from pydantic import Field

from flync.core.base_models import FLYNCBaseModel


class CANFrameRef(FLYNCBaseModel):
    """
    Reference to a CAN frame by name.

    Parameters
    ----------
    frame_ref : str
        Name of the :class:`~flync.model.flync_4_signal.frame.CANFrame` or
        :class:`~flync.model.flync_4_signal.frame.CANFDFrame` defined in the referenced CAN bus.
    """

    frame_ref: str = Field()


class CANInterfaceConfig(FLYNCBaseModel):
    """
    CAN interface of a controller, declaring which frames the controller sends and receives on a CAN bus.

    Parameters
    ----------
    bus_ref : str
        Name of the :class:`~flync.model.flync_4_bus.can_bus.CANBus` this interface connects to.
    sender_frames : list of :class:`CANFrameRef`
        Frames transmitted by this controller on the bus.
    receiver_frames : list of :class:`CANFrameRef`
        Frames received by this controller from the bus.
    """

    bus_ref: str = Field()
    sender_frames: List[CANFrameRef] = Field(default_factory=list)
    receiver_frames: List[CANFrameRef] = Field(default_factory=list)
