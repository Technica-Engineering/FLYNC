"""CAN interface configuration for ECU controllers."""

from typing import Annotated, List, Optional, Self

from pydantic import Field, model_validator

from flync.core.annotations import Implied, ImpliedStrategy
from flync.core.base_models import FLYNCBaseModel
from flync.core.utils.exceptions import Category, err_major
from flync.model.flync_4_ecu.controller_interface import ControllerInterface
from flync.model.flync_4_signal.forwarder import CANFrameForwarder


class CANFrameRef(FLYNCBaseModel):
    """
    Reference to a CAN frame by bus and CAN ID.

    Parameters
    ----------
    bus_ref : str
        Name of the :class:`~flync.model.flync_4_bus.can_bus.CANBus` that owns the frame.
    frame_ref : int
        CAN ID of the :class:`~flync.model.flync_4_signal.frame.CANFrame` or
        :class:`~flync.model.flync_4_signal.frame.CANFDFrame` on the referenced bus.
    """

    bus_ref: str = Field(min_length=1)
    frame_ref: int = Field()


class J1939FrameRef(FLYNCBaseModel):
    """
    Reference to a J1939 frame by bus and PGN.

    ``J1939Frame`` objects carry no CAN ID; their identity on a bus is the Parameter Group Number (``pgn``),
    which the model enforces as unique per bus (``FLYNC-GEN-MAJ-UNIQ-346``).

    Parameters
    ----------
    bus_ref : str
        Name of the :class:`~flync.model.flync_4_bus.can_bus.CANBus` that owns the frame.
    pgn : int
        18-bit J1939 Parameter Group Number of the :class:`~flync.model.flync_4_signal.frame.J1939Frame`
        on the referenced bus.
    """

    bus_ref: str = Field()
    pgn: int = Field(ge=0, le=0x3FFFF)


class CANInterface(ControllerInterface):
    """
    CAN interface of a controller, declaring which frames the controller sends, receives, and forwards on a CAN bus.

    Parameters
    ----------
    name : str
        Name of the CAN interface, implied from the file name on disk.

    bus_ref : str
        Name of the :class:`~flync.model.flync_4_bus.can_bus.CANBus` this interface connects to.
    sender_frames : list of :class:`CANFrameRef`
        Frames transmitted by this controller on the bus.
    receiver_frames : list of :class:`CANFrameRef`
        Frames received by this controller from the bus.
    forwarder_frames : list of \
:class:`~flync.model.flync_4_signal.frame.CANFrameForwarder`
        Frames received by this controller and re-emitted on one or more
        egresses.
    j1939_sender_frames : list of :class:`J1939FrameRef`, optional
        J1939 frames (by PGN) transmitted by this node on the bus. Declaring any J1939 reference marks
        this interface as a J1939 node, so together with ``j1939_name``.
    j1939_receiver_frames : list of :class:`J1939FrameRef`, optional
        J1939 frames (by PGN) received by this node from the bus.
    j1939_name : int, optional
        64-bit J1939 NAME of the node this interface exposes; a node may be modeled by its NAME alone.
        Setting it marks the interface as a J1939 participant on ``bus_ref``, which must then only carry
        ``J1939Frame`` frames.
    source_address : int, optional
        Preferred J1939 Source Address (SA) of the node, in the range [0, 253]. The SA is claimed at
        runtime through address claiming and may be left unset; when provided it is the address the node
        requests, not a hard assignment. Addresses 254 (NULL) and 255 (GLOBAL) are reserved by J1939.
    """

    name: Annotated[str, Implied(strategy=ImpliedStrategy.FILE_NAME)] = Field()
    bus_ref: str = Field(min_length=1)
    sender_frames: List[CANFrameRef] = Field(default_factory=list)
    receiver_frames: List[CANFrameRef] = Field(default_factory=list)
    forwarder_frames: List[CANFrameForwarder] = Field(default_factory=list)
    j1939_sender_frames: List[J1939FrameRef] = Field(default_factory=list)
    j1939_receiver_frames: List[J1939FrameRef] = Field(default_factory=list)
    j1939_name: Optional[int] = Field(default=None, ge=0, le=18446744073709551615)
    source_address: Optional[int] = Field(default=None, ge=0, le=253)

    def is_j1939(self) -> bool:
        """Whether this CAN interface participates in J1939 on its bus.

        An interface is a J1939 participant when it declares a 64-bit ``j1939_name`` (with its ``source_address``)
        or any J1939 frame reference. The bus it attaches to must then carry only ``J1939Frame`` frames.
        """
        return self.j1939_name is not None or self.source_address is not None or bool(self.j1939_sender_frames or self.j1939_receiver_frames)

    @model_validator(mode="after")
    def validate_j1939_consistency(self) -> Self:
        """A J1939 node's ``j1939_name`` is mandatory; ``source_address`` is optional.

        The 64-bit NAME identifies the node. The SA is claimed at runtime through address claiming
        (J1939-81), so a node may model only its NAME and leave ``source_address`` unset. An SA only makes
        sense as part of a named node, so ``source_address`` without ``j1939_name`` is rejected. Declaring
        J1939 frame references also requires the node NAME.
        """

        if self.source_address is not None and self.j1939_name is None:
            raise err_major(
                "CANInterface(bus_ref={bus}): source_address is set but j1939_name is missing; a J1939 "
                "node requires a NAME (source_address is optional).",
                bus=self.bus_ref,
                category=Category.REQUIRED,
                error_number="375",
            )
        if self.j1939_sender_frames or self.j1939_receiver_frames:
            if self.j1939_name is None:
                raise err_major(
                    "CANInterface(bus_ref={bus}): declares J1939 frame references but is missing j1939_name; a J1939 node requires a NAME.",
                    bus=self.bus_ref,
                    category=Category.REQUIRED,
                    error_number="376",
                )
        return self

    @model_validator(mode="after")
    def validate_forwarder_frame_uniqueness(self) -> Self:
        """Raise ``err_major`` if the same ``frame_ref`` appears twice in ``forwarder_frames``."""

        seen: set = set()
        duplicates: set = set()
        for fwd in self.forwarder_frames:
            if fwd.frame_ref in seen:
                duplicates.add(fwd.frame_ref)
            seen.add(fwd.frame_ref)
        if duplicates:
            raise err_major(
                "CANInterface(bus_ref={bus}): duplicate frame_ref(s) in forwarder_frames: {dups}",
                bus=self.bus_ref,
                dups=sorted(duplicates),
                category=Category.UNIQUENESS,
                error_number="058",
            )
        return self
