from typing import List, Optional

from pydantic import Field

from flync.core.base_models import FLYNCBaseModel

from .sockets import SocketTCP, SocketUDP


class SocketContainer(FLYNCBaseModel):
    """
    Represents a socket container for the ecu.

    Parameters
    ----------
    vlan_id : int
        ID of the virtual interface.

    sockets : list of \
    :class:`~flync.model.flync_4_ecu.sockets.SocketTCP` or \
    :class:`~flync.model.flync_4_ecu.sockets.SocketUDP`
        Assigned TCP and UDP socket endpoints.
    """

    vlan_id: int = Field(ge=0, le=4095, default=0)
    sockets: Optional[List[SocketTCP | SocketUDP]] = Field(
        default_factory=list
    )
