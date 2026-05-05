from typing import Annotated, FrozenSet, List, Literal, Optional

from pydantic import Field, model_validator

from flync.core.base_models import FLYNCBaseModel, UniqueName
from flync.core.utils.exceptions import err_minor
from flync.model.flync_4_signal.pdu import (
    PDUInstance,
)

# ---------------------------------------------------------------------------
# PDU sender deployment
# ---------------------------------------------------------------------------


class PDUSender(FLYNCBaseModel):
    """
    Deployment that publishes a Container PDU onto a socket.

    Transport (TCP/UDP, IP address, port) is owned by the enclosing socket; this model only binds a PDU to that socket.
    The publishing ECU is the owner of the socket carrying this deployment.

    Parameters
    ----------
    deployment_type : Literal["pdu_sender"]
        Discriminator value for :class:`~flync.model.flync_4_ecu.sockets.DeploymentUnion`.
    pdu_ref : str
        Name of a :class:`~flync.model.flync_4_signal.pdu.ContainerPDU` in the PDU catalog.
    """

    deployment_type: Literal["pdu_sender"] = Field(default="pdu_sender")
    pdu_ref: str = Field()


class PDUReceiver(FLYNCBaseModel):
    """
    Deployment that subscribes to a Container PDU on a socket.

    Transport (TCP/UDP, IP address, port) is owned by the enclosing socket; this model only binds a PDU to that socket.
    The receiving ECU is the owner of the socket carrying this deployment.

    Parameters
    ----------
    deployment_type : Literal["pdu_receiver"]
        Discriminator value for :class:`~flync.model.flync_4_ecu.sockets.DeploymentUnion`.
    pdu_ref : str
        Name of a :class:`~flync.model.flync_4_signal.pdu.ContainerPDU` in the PDU catalog.
    """

    deployment_type: Literal["pdu_receiver"] = Field(default="pdu_receiver")
    pdu_ref: str = Field()


# ---------------------------------------------------------------------------
# Frame transmission timing
# ---------------------------------------------------------------------------


class FrameEventTiming(FLYNCBaseModel):
    """
    Event-based transmission timing.

    Parameters
    ----------
    final_repetitions : int
        Number of repetitions after an event is triggered.  Defaults to ``0``.
    repeating_time_range : float
        Time interval in seconds between repetitions.  Defaults to ``0.0``.
    """

    final_repetitions: int = Field(default=0, ge=0)
    repeating_time_range: float = Field(default=0.0, ge=0.0)


class FrameCyclicTiming(FLYNCBaseModel):
    """
    Cyclic transmission timing.

    Parameters
    ----------
    cycle : float
        Cycle time in seconds.
    """

    cycle: float = Field(gt=0)


class FrameTransmissionTiming(FLYNCBaseModel):
    """
    Frame transmission timing configuration.

    Parameters
    ----------
    debounce_time : float, optional
        Debounce delay in seconds before transmission occurs.
    cyclic_timings : list of :class:`FrameCyclicTiming`
        Cyclic timing configurations.
    event_timings : list of :class:`FrameEventTiming`
        Event-driven timing configurations.
    """

    debounce_time: Optional[float] = Field(default=None)
    cyclic_timings: List[FrameCyclicTiming] = Field(default_factory=list)
    event_timings: List[FrameEventTiming] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Base frame
# ---------------------------------------------------------------------------


class Frame(UniqueName):
    """
    Protocol-agnostic frame base class.

    Parameters
    ----------
    name : str
        Unique name of the frame.
    description : str, optional
        Optional human-readable description.
    length : int
        Length of the frame payload in bytes.
    """

    name: str = Field()
    description: Optional[str] = Field(default=None)
    length: int = Field()


# ---------------------------------------------------------------------------
# CAN base
# ---------------------------------------------------------------------------


class CANFrameBase(Frame):
    """
    Shared fields for CAN 2.0 and CAN FD frames.

    Parameters
    ----------
    can_id : int
        CAN message identifier.
    id_format : Literal["standard_11bit", "extended_29bit"]
        Identifier format.
    packed_pdus : list of :class:`PDUInstance`
        PDU instances placed at fixed bit offsets within this frame.
    timing : :class:`FrameTransmissionTiming`, optional
        Transmission timing for this frame.
    """

    can_id: int = Field()
    id_format: Literal["standard_11bit", "extended_29bit"] = Field()
    packed_pdus: List[PDUInstance] = Field(default_factory=list)
    timing: Optional[FrameTransmissionTiming] = Field(default=None)

    @model_validator(mode="after")
    def _validate_pdu_placements(self) -> "CANFrameBase":
        _check_pdu_bit_positions(self.name, self.packed_pdus)
        return self


# ---------------------------------------------------------------------------
# CAN frames
# ---------------------------------------------------------------------------


class CANFrame(CANFrameBase):
    """
    Classical CAN frame (CAN 2.0A/B).

    Parameters
    ----------
    can_id : int
        CAN message identifier.  Range: [0, 0x7FF] for ``"standard_11bit"``,
        [0, 0x1FFFFFFF] for ``"extended_29bit"``.
    id_format : Literal["standard_11bit", "extended_29bit"]
        Identifier format.
    is_remote_frame : bool
        Whether this is a Remote Transmission Request (RTR) frame.
        Defaults to ``False``.
    """

    type: Literal["can"] = Field(default="can")
    is_remote_frame: bool = Field(default=False)
    length: int = Field(ge=0, le=8)

    @model_validator(mode="after")
    def validate_can_frame_constraints(self) -> "CANFrame":
        _validate_can_id(self.can_id, self.id_format)
        if self.is_remote_frame and self.length != 0:
            raise err_minor(
                "CANFrame '{name}': is_remote_frame=True requires length=0 (RTR frames carry no data payload); got length={length}",
                name=self.name,
                length=self.length,
            )
        return self


class CANFDFrame(CANFrameBase):
    """
    CAN FD frame.

    Supports payloads up to 64 bytes and an optional bit-rate switch
    for the data phase.

    Parameters
    ----------
    can_id : int
        CAN message identifier.  Same range rules as :class:`CANFrame`.
    id_format : Literal["standard_11bit", "extended_29bit"]
        Identifier format.
    bit_rate_switch : bool
        Enables a higher bit rate during the data phase.  Defaults to ``True``.
    error_state_indicator : bool
        Error State Indicator flag.  Defaults to ``False``.
    """

    type: Literal["can_fd"] = Field(default="can_fd")
    bit_rate_switch: bool = Field(default=True)
    error_state_indicator: bool = Field(default=False)
    length: int = Field(ge=0, le=64)

    @model_validator(mode="after")
    def validate_can_fd_frame_constraints(self) -> "CANFDFrame":
        _validate_can_id(self.can_id, self.id_format)
        if self.length not in _CAN_FD_VALID_LENGTHS:
            raise err_minor(
                "CANFDFrame '{name}' length {length} is not a valid CAN FD payload size; valid sizes are {valid}",
                name=self.name,
                length=self.length,
                valid=sorted(_CAN_FD_VALID_LENGTHS),
            )
        return self


# ---------------------------------------------------------------------------
# LIN frame
# ---------------------------------------------------------------------------


class LINFrame(Frame):
    """
    LIN unconditional frame.

    Parameters
    ----------
    lin_id : int
        6-bit LIN frame identifier in the range [0, 0x3F].
    checksum_type : Literal["classic", "enhanced"]
        LIN checksum model.  Defaults to ``"enhanced"``.
    packed_pdus : list of :class:`PDUInstance`
        PDU instances placed at fixed bit offsets within this frame.
    timing : :class:`FrameTransmissionTiming`, optional
        Transmission timing for this frame.
    """

    type: Literal["lin"] = Field(default="lin")
    lin_id: Annotated[int, Field(ge=0, le=0x3F)] = Field()
    checksum_type: Literal["classic", "enhanced"] = Field(default="enhanced")
    length: int = Field(ge=1, le=8)
    packed_pdus: List[PDUInstance] = Field(default_factory=list)
    timing: Optional[FrameTransmissionTiming] = Field(default=None)

    @model_validator(mode="after")
    def _validate_pdu_placements(self) -> "LINFrame":
        _check_pdu_bit_positions(self.name, self.packed_pdus)
        return self


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_CAN_FD_VALID_LENGTHS: FrozenSet[int] = frozenset({0, 1, 2, 3, 4, 5, 6, 7, 8, 12, 16, 20, 24, 32, 48, 64})


def _check_pdu_bit_positions(frame_name: str, packed_pdus: List[PDUInstance]) -> None:
    """Raise if any two PDU in the frame share the same bit_position."""
    seen: set = set()
    for pdu in packed_pdus:
        if pdu.bit_position is None:
            continue
        if pdu.bit_position in seen:
            raise err_minor(
                "Frame '{name}': multiple PDU instances share bit_position {pos}; overlapping placements are not permitted",
                name=frame_name,
                pos=pdu.bit_position,
            )
        seen.add(pdu.bit_position)


def _validate_can_id(can_id: int, id_format: str) -> None:
    """Raise if *can_id* is outside the valid range for *id_format*."""
    limit = 0x7FF if id_format == "standard_11bit" else 0x1FFFFFFF
    if not (0 <= can_id <= limit):
        raise err_minor(
            "CAN ID {can_id} is out of range for id_format '{id_format}' (allowed 0 – {limit})",
            can_id=can_id,
            id_format=id_format,
            limit=limit,
        )
