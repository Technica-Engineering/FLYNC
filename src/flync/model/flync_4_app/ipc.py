"""Defines ECU-internal inter-process communication (IPC) channels and the application references to them."""

from typing import Literal, Optional

from pydantic import Field

from flync.core.base_models import FLYNCBaseModel


class IPCChannel(FLYNCBaseModel):
    """
    Communication channel between applications inside a single ECU.

    The channel never leaves the ECU. Which applications take part is declared by the applications through
    :class:`IPCChannelReference`; the channel itself only carries the transport configuration.

    Parameters
    ----------
    name: str
        Name of the channel. Unique within the ECU.

    transport: Literal["shared_memory", "unix_socket", "message_queue", "pipe", "other"]
        Mechanism used to carry the data.

    description: str, optional
        Free-text description of the channel.

    max_payload_size: int, optional
        Maximum size of a single message or of the shared memory region in bytes.

    queue_depth: int, optional
        Number of messages the channel buffers. Only meaningful for queue-like transports.
    """

    name: str = Field(min_length=1, description="Name of the channel, unique within the ECU.")
    transport: Literal["shared_memory", "unix_socket", "message_queue", "pipe", "other"] = Field(description="Mechanism used to carry the data.")
    description: Optional[str] = Field(default=None, description="Free-text description of the channel.")
    max_payload_size: Optional[int] = Field(default=None, gt=0, description="Maximum message size or shared memory size in bytes.")
    queue_depth: Optional[int] = Field(default=None, gt=0, description="Number of messages the channel buffers.")


class IPCChannelReference(FLYNCBaseModel):
    """
    Participation of an application in an :class:`IPCChannel`.

    Parameters
    ----------
    channel_ref: str
        Name of an :class:`IPCChannel` of the ECU hosting the application.

    role: Literal["producer", "consumer", "bidirectional"]
        Role the application plays on the channel.
    """

    channel_ref: str = Field(min_length=1, description="Name of an IPC channel of the hosting ECU.")
    role: Literal["producer", "consumer", "bidirectional"] = Field(description="Role the application plays on the channel.")
