"""Defines the references an application holds to CAN / J1939 frames and PDUs."""

from typing import Literal

from pydantic import Field

from flync.core.base_models import FLYNCBaseModel


class AppCANFrameRef(FLYNCBaseModel):
    """
    Reference to a CAN or CAN FD frame an application sends or receives.

    Parameters
    ----------
    bus_ref: str
        Name of the :class:`~flync.model.flync_4_bus.can_bus.CANBus` carrying the frame.

    frame_ref: int
        CAN ID of the referenced frame on that bus.

    id_format: Literal["standard_11bit", "extended_29bit"]
        Identifier format of the referenced frame.

    direction: Literal["sender", "receiver"]
        Whether the application transmits or receives the frame.
    """

    bus_ref: str = Field(min_length=1, description="Name of the CAN bus carrying the frame.")
    frame_ref: int = Field(ge=0, description="CAN ID of the referenced frame.")
    id_format: Literal["standard_11bit", "extended_29bit"] = Field(description="Identifier format of the referenced frame.")
    direction: Literal["sender", "receiver"] = Field(description="Whether the application sends or receives the frame.")


class AppJ1939FrameRef(FLYNCBaseModel):
    """
    Reference to a J1939 frame, identified by its PGN, an application sends or receives.

    Parameters
    ----------
    bus_ref: str
        Name of the :class:`~flync.model.flync_4_bus.can_bus.CANBus` carrying the frame.

    pgn: int
        18-bit Parameter Group Number of the referenced frame on that bus.

    direction: Literal["sender", "receiver"]
        Whether the application transmits or receives the frame.
    """

    bus_ref: str = Field(min_length=1, description="Name of the CAN bus carrying the frame.")
    pgn: int = Field(ge=0, le=0x3FFFF, description="Parameter Group Number of the referenced frame.")
    direction: Literal["sender", "receiver"] = Field(description="Whether the application sends or receives the frame.")


class AppCANPDURef(FLYNCBaseModel):
    """
    Reference to a PDU an application sends or receives within a CAN or CAN FD frame.

    Parameters
    ----------
    pdu_ref: str
        Name of the referenced :class:`~flync.model.flync_4_signal.pdu.PDU`.

    bus_ref: str
        Name of the CAN bus on which a CAN / CAN FD frame packs the PDU.

    direction: Literal["sender", "receiver"]
        Whether the application transmits or receives the PDU.
    """

    pdu_ref: str = Field(min_length=1, description="Name of the referenced PDU.")
    bus_ref: str = Field(min_length=1, description="Name of the CAN bus on which a CAN frame packs the PDU.")
    direction: Literal["sender", "receiver"] = Field(description="Whether the application sends or receives the PDU.")


class AppJ1939PDURef(FLYNCBaseModel):
    """
    Reference to a PDU an application sends or receives within a J1939 frame.

    Parameters
    ----------
    pdu_ref: str
        Name of the referenced :class:`~flync.model.flync_4_signal.pdu.PDU`.

    bus_ref: str
        Name of the CAN bus on which a J1939 frame packs the PDU.

    direction: Literal["sender", "receiver"]
        Whether the application transmits or receives the PDU.
    """

    pdu_ref: str = Field(min_length=1, description="Name of the referenced PDU.")
    bus_ref: str = Field(min_length=1, description="Name of the CAN bus on which a J1939 frame packs the PDU.")
    direction: Literal["sender", "receiver"] = Field(description="Whether the application sends or receives the PDU.")
