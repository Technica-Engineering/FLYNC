"""LIN interface configuration for ECU controllers."""

from typing import Annotated, List, Literal, Optional, Self, Union

from pydantic import Field, model_validator

from flync.core.annotations import Implied, ImpliedStrategy
from flync.core.base_models import FLYNCBaseModel
from flync.core.utils.exceptions import Category, err_major
from flync.model.flync_4_ecu.controller_interface import ControllerInterface

_LINProtocol = Literal["1.3", "2.0", "2.1", "2.2A"]


class LINFrameRef(FLYNCBaseModel):
    """
    Reference to a LIN frame by bus and LIN ID.

    Parameters
    ----------
    bus_ref : str
        Name of the :class:`~flync.model.flync_4_bus.lin_bus.LINBus` that owns the frame.
    frame_ref : int
        LIN ID of the :class:`~flync.model.flync_4_signal.frame.LINFrame` on the referenced bus.
    """

    bus_ref: str = Field(min_length=1)
    frame_ref: int = Field()


def _validate_unique_lin_frames(interface: ControllerInterface, field_name: str, frames: List[LINFrameRef]) -> None:
    """Raise ``err_major`` if the same ``(bus_ref, frame_ref)`` appears twice in ``frames``."""
    seen: set[tuple[str, int]] = set()
    duplicates: set[tuple[str, int]] = set()
    for ref in frames:
        key = (ref.bus_ref, ref.frame_ref)
        if key in seen:
            duplicates.add(key)
        seen.add(key)
    if duplicates:
        raise err_major(
            "LIN interface '{name}': duplicate frame_ref(s) in {field}: {dups}",
            name=interface.name,
            field=field_name,
            dups=[f"{bus}:{fid}" for bus, fid in sorted(duplicates)],
            category=Category.UNIQUENESS,
            error_number="435",
        )


class LINMasterInterface(ControllerInterface):
    """
    LIN interface for a controller acting as LIN master on a bus.

    The master issues the header of every frame in the bus schedule tables
    (:attr:`~flync.model.flync_4_bus.lin_bus.LINBus.schedule_tables`).  Like every LIN interface, it
    publishes the response of the frames listed in ``sender_frames`` and receives the frames listed in
    ``receiver_frames``.

    Parameters
    ----------
    name : str
        Name of the LIN interface, implied from the file name on disk.

    node_type : Literal["master"]
        Discriminator field.  Always ``"master"``.
    bus_ref : str
        Name of the :class:`~flync.model.flync_4_bus.lin_bus.LINBus` this interface connects to.
    lin_protocol : Literal["1.3", "2.0", "2.1", "2.2A"]
        LIN protocol version supported by this node.
    p2_min : float
        Minimum time (ms) between the end of a slave response and the start of the next frame header.
    st_min : float
        Minimum separation time (ms) between consecutive frame headers transmitted by the master.
    sender_frames : list of :class:`LINFrameRef`
        Frames whose response this master controller publishes.
    receiver_frames : list of :class:`LINFrameRef`
        Frames whose response, published by a slave, this master controller receives.
    """

    name: Annotated[str, Implied(strategy=ImpliedStrategy.FILE_NAME)] = Field()
    node_type: Literal["master"] = Field(default="master")
    bus_ref: str = Field(min_length=1)
    lin_protocol: _LINProtocol = Field()
    p2_min: float = Field()
    st_min: float = Field()
    sender_frames: List[LINFrameRef] = Field(default_factory=list)
    receiver_frames: List[LINFrameRef] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_sender_frames_unique(self) -> Self:
        """Reject duplicate frame references in ``sender_frames``."""
        _validate_unique_lin_frames(self, "sender_frames", self.sender_frames)
        return self


class LINSlaveInterface(ControllerInterface):
    """
    LIN interface for a controller acting as LIN slave on a bus.

    The slave responds to frame headers issued by the master.  It publishes the response of the frames
    listed in ``sender_frames`` and receives the frames listed in ``receiver_frames``.

    Parameters
    ----------
    name : str
        Name of the LIN interface, implied from the file name on disk.

    node_type : Literal["slave"]
        Discriminator field.  Always ``"slave"``.
    bus_ref : str
        Name of the :class:`~flync.model.flync_4_bus.lin_bus.LINBus` this interface connects to.
    lin_protocol : Literal["1.3", "2.0", "2.1", "2.2A"]
        LIN protocol version supported by this node.
    configured_nad : int
        Configured Node Address (0x00 – 0xFF).
        Written as ``configured_NAD`` in the LDF ``Node_attributes`` block.
    initial_nad : int
        Initial Node Address (0x00 – 0xFF).
        Written as ``initial_NAD`` in the LDF ``Node_attributes`` block.
    product_id : str, optional
        Product identification string.
        Written as ``product_id`` in the LDF ``Node_attributes`` block.
    response_error : str, optional
        Name of the signal used to report response errors.
        Written as ``response_error`` in the LDF ``Node_attributes`` block.
    sender_frames : list of :class:`LINFrameRef`
        Frames whose response this slave controller publishes when the master issues their header.
    receiver_frames : list of :class:`LINFrameRef`
        Frames received by this slave controller from the bus.
    """

    name: Annotated[str, Implied(strategy=ImpliedStrategy.FILE_NAME)] = Field()
    node_type: Literal["slave"] = Field(default="slave")
    bus_ref: str = Field(min_length=1)
    lin_protocol: _LINProtocol = Field()
    configured_nad: Annotated[int, Field(ge=0, le=0xFF)] = Field()
    initial_nad: Annotated[int, Field(ge=0, le=0xFF)] = Field()
    product_id: Optional[str] = Field(default=None)
    response_error: Optional[str] = Field(default=None)
    sender_frames: List[LINFrameRef] = Field(default_factory=list)
    receiver_frames: List[LINFrameRef] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_receiver_frames_unique(self) -> Self:
        """Reject duplicate frame references in ``receiver_frames``."""
        _validate_unique_lin_frames(self, "receiver_frames", self.receiver_frames)
        return self


AnyLINInterface = Annotated[
    Union[LINMasterInterface, LINSlaveInterface],
    Field(discriminator="node_type"),
]
"""Discriminated union of LIN master and slave interface configs, keyed on ``node_type``."""
