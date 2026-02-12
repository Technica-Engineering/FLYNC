from typing import Annotated, List, Optional

import pydantic
from pydantic import Field

from flync.core.annotations.implied import Implied, ImpliedStrategy
from flync.core.base_models import FLYNCBaseModel
from flync.core.utils.exceptions import err_minor

from .controller import Controller
from .sockets import SocketTCP, SocketUDP


class SocketContainer(FLYNCBaseModel):
    """
    Represents a socket container for the ecu.

    Parameters
    ----------
    vlan_name : str
        Name of the virtual interface.

    sockets : list of \
    :class:`~flync.model.flync_4_ecu.sockets.SocketTCP` or \
    :class:`~flync.model.flync_4_ecu.sockets.SocketUDP`
        Assigned TCP and UDP socket endpoints.
    """

    vlan_name: Annotated[
        str,
        Implied(
            strategy=ImpliedStrategy.FILE_NAME,
        ),
    ]
    sockets: Optional[List[SocketTCP | SocketUDP]] = Field(
        default_factory=list
    )

    @pydantic.model_validator(mode="after")
    def add_socket_to_ip(self):
        """
        Associate the given socket definitions with the match
        ing ECU IP objects.

        Raises:
            err_minor: If a socket's endpoint address does not belong to any
                virtual interface in the ECU, or if the address is found on a
                virtual interface whose VLAN name differs
                from the one supplied.
        """

        controllers = Controller.INSTANCES
        for socket in self.sockets:
            exists_ok = False
            for controller in controllers:
                for interface in controller.interfaces:
                    for v_int in interface.virtual_interfaces:
                        for ip_addr in v_int.addresses:
                            if ip_addr.address == socket.endpoint_address:
                                if v_int.name != self.vlan_name:
                                    raise err_minor(
                                        f"The endpoint address for the "
                                        f"socket is not a part of the "
                                        f"virtual_interace "
                                        f"{self.vlan_name}"
                                    )
                                ip_addr.sockets.append(socket)
                                exists_ok = True
                                break
            if not exists_ok:
                raise err_minor(
                    f"The IP {socket.endpoint_address} for socket "
                    f"{socket.name} does not exist in ecu"
                )
        return self
