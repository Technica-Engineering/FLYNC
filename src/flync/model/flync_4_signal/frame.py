"""
Defines frames and their transmission timing for FLYNC.

Provides the :class:`Frame` base class with the bus specific :class:`CANFrame`, :class:`CANFDFrame` and
:class:`LINFrame`, as well as the timing models :class:`FrameEventTiming`, :class:`FrameCyclicTiming` and
:class:`FrameTransmissionTiming`. Validates CAN identifiers, the valid CAN FD payload lengths and the bit
positions of the contained PDU instances.
"""

from typing import Annotated, FrozenSet, List, Literal, Optional, Self

from pydantic import Field, model_validator

from flync.core.base_models import FLYNCBaseModel
from flync.core.utils.exceptions import Category, err_major, err_minor
from flync.model.flync_4_signal.pdu import (
    PDUInstance,
)


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
        Must be greater than 0.
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


class Frame(FLYNCBaseModel):
    """
    Protocol-agnostic frame base class.

    Parameters
    ----------
    name : str
        Unique name of the frame.
    length : int
        Length of the frame payload in bytes.
    frame_usage : Literal[str], optional
        Tag identifying special usage of the frame. One of:

        - ``"application"`` marks the frame as carrying regular application traffic.
        - ``"bap"`` marks the frame as carrying BAP (FIBEX compatibility).
        - ``"diag_request"`` marks the frame as diagnostics request.
        - ``"diag_response"`` marks the frame as diagnostics response.
        - ``"diag_state"`` marks the frame as diagnostics state.
        - ``"network_management"`` marks the frame as carrying Network Management traffic.
        - ``"other"`` marks the frame as other usage.
        - ``"service"`` marks the frame as service.
        - ``"tpl"`` marks the frame as carrying a transport protocol.
        - ``"xcp_pre_configured"`` marks the frame as static XCP.
        - ``"xcp_runtime_configured"`` marks the frame as dynamic XCP.

    description : str, optional
        Optional human-readable description.

    packed_pdus : list of :class:`PDUInstance`
        PDU instances placed at fixed bit offsets within this frame.
    """

    name: str = Field(min_length=1)
    length: int = Field(ge=0)
    frame_usage: Optional[
        Literal[
            "application",
            "bap",
            "diag_request",
            "diag_response",
            "diag_state",
            "network_management",
            "other",
            "service",
            "tpl",
            "xcp_pre_configured",
            "xcp_runtime_configured",
        ]
    ] = Field(default=None)
    description: Optional[str] = Field(default=None)
    packed_pdus: List[PDUInstance] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_pdu_placements(self) -> Self:
        _check_pdu_bit_positions(self.name, self.packed_pdus)
        return self


class CANFrameBase(Frame):
    """
    Shared fields for CAN 2.0 and CAN FD frames.

    Parameters
    ----------
    can_id : int
        CAN message identifier.
    id_format : Literal["standard_11bit", "extended_29bit"]
        Identifier format.
    timing : :class:`FrameTransmissionTiming`, optional
        Transmission timing for this frame.
    """

    can_id: int = Field()
    id_format: Literal["standard_11bit", "extended_29bit"] = Field()
    timing: Optional[FrameTransmissionTiming] = Field(default=None)


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
    def validate_can_frame_constraints(self) -> Self:
        _validate_can_id(self.can_id, self.id_format)
        if self.is_remote_frame and self.length != 0:
            raise err_minor(
                "CANFrame '{name}': is_remote_frame=True requires length=0 (RTR frames carry no data payload); got length={length}",
                name=self.name,
                length=self.length,
                category=Category.CONSISTENCY,
                error_number="103",
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
    def validate_can_fd_frame_constraints(self) -> Self:
        _validate_can_id(self.can_id, self.id_format)
        if self.length not in _CAN_FD_VALID_LENGTHS:
            raise err_minor(
                "CANFDFrame '{name}' length {length} is not a valid CAN FD payload size; valid sizes are {valid}",
                name=self.name,
                length=self.length,
                valid=sorted(_CAN_FD_VALID_LENGTHS),
                category=Category.VALUE_RANGE,
                error_number="104",
            )
        return self


class LINFrame(Frame):
    """
    LIN unconditional frame.

    Parameters
    ----------
    lin_id : int
        6-bit LIN frame identifier in the range [0, 0x3F].
    checksum_type : Literal["classic", "enhanced"]
        LIN checksum model.  Defaults to ``"enhanced"``.
    timing : :class:`FrameTransmissionTiming`, optional
        Transmission timing for this frame.
    """

    type: Literal["lin"] = Field(default="lin")
    lin_id: Annotated[int, Field(ge=0, le=0x3F)] = Field()
    checksum_type: Literal["classic", "enhanced"] = Field(default="enhanced")
    length: int = Field(ge=1, le=8)
    timing: Optional[FrameTransmissionTiming] = Field(default=None)


class J1939Frame(Frame):
    """
    Basic J1939 Frame.

    Parameters
    ----------
    type : Literal["j1939"]
        Discriminator tag selecting this frame kind when parsed from a CAN bus frame list.
    priority : int
        J1939 message priority.
    pdu_format : int
        PDU Format (PF) field. Values below 240 select the PDU1 format, where ``pdu_specific`` is a
        Destination Address; values 240-255 select the PDU2 format, where ``pdu_specific`` is a Group Extension.
    pdu_specific: int
        Message PDU Specific (PS) field. For PDU1 (``pdu_format`` < 240) it is a Destination Address;
        for PDU2 (``pdu_format`` >= 240) it is a Group Extension that groups related messages.
    data_page: int
        Message data page.
    extended_data_page: int
        Message extended data page.
    destination_type: Literal["global", "specific"]
        Destination type. For PDU1 (``pdu_format`` < 240) the ``pdu_specific`` field is a destination address:
        ``"specific"`` targets a single node (DA 0-254) and ``"global"`` broadcasts to every node (DA = 255).
        For PDU2 (``pdu_format`` >= 240) the message is always a group broadcast, so this must be ``"global"``.
    timing : :class:`FrameTransmissionTiming`, optional
            Transmission timing for this frame.

    Notes
    -----
    A J1939 message carries exactly one Parameter Group (one PGN) in its 8-byte data field, so ``packed_pdus``
    may contain at most one entry. This is unlike classical CAN, where a single frame may pack several PDUs.
    """

    priority: int = Field(ge=0, le=7)
    pdu_format: int = Field(ge=0, le=255)
    pdu_specific: int = Field(ge=0, le=255)
    data_page: int = Field(ge=0, le=1)
    extended_data_page: int = Field(ge=0, le=1)
    destination_type: Literal["global", "specific"]
    length: Literal[8] = Field(default=8)
    type: Literal["j1939"] = Field(default="j1939")
    timing: Optional[FrameTransmissionTiming] = Field(default=None)

    @model_validator(mode="after")
    def validate_single_packed_pdu(self) -> Self:
        if len(self.packed_pdus) > 1:
            raise err_major(
                "J1939 '{name}': a J1939 frame carries exactly one Parameter Group, got {n} packed PDUs",
                name=self.name,
                n=len(self.packed_pdus),
                category=Category.CONSISTENCY,
                error_number="370",
            )
        return self

    @model_validator(mode="after")
    def validate_pdu_format(self) -> Self:
        if self.pdu_format >= 240:
            # PDU2 (PF 240-255): pdu_specific is a Group Extension; these messages are always a group broadcast.
            if self.destination_type != "global":
                raise err_minor(
                    "J1939 '{name}': pdu_format>=240 (PDU2) is always a group broadcast, requires "
                    "destination_type=global got destination_type={destination_type}",
                    name=self.name,
                    destination_type=self.destination_type,
                    category=Category.CONSISTENCY,
                    error_number="347",
                )
        elif self.pdu_format < 240:
            # PDU1 (PF 0-239): pdu_specific is a Destination Address; a global broadcast is DA = 255.
            global_da = self.pdu_specific == 255
            if (self.destination_type == "global") != global_da:
                raise err_minor(
                    "J1939 '{name}': destination_type={destination_type} does not match pdu_specific={pdu_specific} "
                    "(PDU1: 'global' requires pdu_specific=255, 'specific' requires pdu_specific in 0-254)",
                    name=self.name,
                    destination_type=self.destination_type,
                    pdu_specific=self.pdu_specific,
                    category=Category.CONSISTENCY,
                    error_number="348",
                )
        return self


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
                category=Category.UNIQUENESS,
                error_number="105",
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
            category=Category.VALUE_RANGE,
            error_number="106",
        )
