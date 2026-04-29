"""Defines the socket container model in an ECU."""

from typing import Annotated, List, Optional, Union

from pydantic import AfterValidator, BeforeValidator, Field

import flync.core.utils.common_validators as common_validators
from flync.core.annotations import Implied, ImpliedStrategy
from flync.core.base_models import FLYNCBaseModel

from .sockets import SocketTCP, SocketUDP


class SocketContainer(FLYNCBaseModel):
    """
    Represents a socket container for the ecu.

    Parameters
    ----------
    name : str
        Name of the socket container, implied from the filename on disk.

    vlan_id : int, optional
        ID of the virtual interface. Use ``None`` for an untagged
        container.

    sockets : list of \
    :class:`~flync.model.flync_4_ecu.sockets.SocketTCP` or \
    :class:`~flync.model.flync_4_ecu.sockets.SocketUDP`
        Assigned TCP and UDP socket endpoints.
    """

    name: Annotated[str, Implied(strategy=ImpliedStrategy.FILE_NAME)] = Field()
    vlan_id: Annotated[
        Optional[int], AfterValidator(common_validators.validate_vlan_id)
    ] = Field(default=0)
    sockets: Annotated[
        Optional[
            List[
                Annotated[
                    Union[SocketTCP, SocketUDP],
                    Field(discriminator="protocol"),
                ]
            ]
        ],
        BeforeValidator(
            common_validators.validate_list_items_and_remove(
                "socket",
                Annotated[
                    Union[SocketTCP, SocketUDP],
                    Field(discriminator="protocol"),
                ],
                severity="minor",
            )
        ),
    ] = Field(default_factory=list)
