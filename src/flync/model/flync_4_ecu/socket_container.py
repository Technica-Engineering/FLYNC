"""Defines the socket container model in an ECU."""

from typing import Annotated, List, Optional

from pydantic import BeforeValidator, Field

from flync.core.annotations import Implied, ImpliedStrategy
import flync.core.utils.common_validators as common_validators
from flync.core.base_models import FLYNCBaseModel

from .sockets import SocketUnion


class SocketContainer(FLYNCBaseModel):
    """
    Represents a socket container for the ecu.

    Parameters
    ----------
    name : str
        Name of the socket container, implied from the filename on disk.

    vlan_id : int
        ID of the virtual interface.

    sockets : list of \
    :class:`~flync.model.flync_4_ecu.sockets.SocketTCP` or \
    :class:`~flync.model.flync_4_ecu.sockets.SocketUDP`
        Assigned TCP and UDP socket endpoints.
    """

    name: Annotated[str, Implied(strategy=ImpliedStrategy.FILE_NAME)] = Field()
    vlan_id: int = Field(ge=0, le=4095, default=0)
    sockets: Annotated[
        Optional[List[SocketUnion]],
        BeforeValidator(
            common_validators.validate_list_items_and_remove(
                "socket", SocketUnion, severity="minor"
            )
        ),
    ] = Field(default_factory=list)
