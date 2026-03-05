from itertools import product
from typing import Annotated, List, Optional

from pydantic import Field, model_validator

from flync.core.annotations import (
    External,
    Implied,
    ImpliedStrategy,
    NamingStrategy,
    OutputStrategy,
)
from flync.core.base_models import UniqueName
from flync.core.utils.base_utils import find_all
from flync.core.utils.exceptions import err_minor
from flync.model.flync_4_ecu.controller import (
    Controller,
    ControllerInterface,
    VirtualControllerInterface,
)
from flync.model.flync_4_ecu.internal_topology import InternalTopology
from flync.model.flync_4_ecu.port import ECUPort
from flync.model.flync_4_ecu.socket_container import SocketContainer
from flync.model.flync_4_ecu.sockets import Socket
from flync.model.flync_4_ecu.switch import Switch, SwitchPort
from flync.model.flync_4_metadata import ECUMetadata


def RESET_unique_name_cache():
    ControllerInterface.NAMES = set()
    SwitchPort.NAMES = set()


class ECU(UniqueName):
    """
    Represents an Electronic Control Unit (ECU) in the network.

    Parameters
    ----------
    name : str
        Name of the ECU.

    ports : list of :class:`~flync.model.flync_4_ecu.port.ECUPort`
        List of physical ECU ports.
        At least one port must be provided.

    controllers : list of \
    :class:`~flync.model.flync_4_ecu.controller.Controller`
        Controllers associated with this ECU.

    switches : list of \
    :class:`~flync.model.flync_4_ecu.switch.Switch`, optional
        Switches integrated within the ECU. If not provided, the ECU
        contains no internal switches.

    sockets : list of \
    :class:`~flync.model.flync_4_ecu.socket_container.SocketContainer`, \
    optional
        Socket containers within the ECU. If not provided, the ECU
        has no socket deployments configured.

    topology : \
    :class:`~flync.model.flync_4_ecu.internal_topology.InternalTopology`
        Internal topology defining the connectivity between
        ECU components.

    ecu_metadata : :class:`~flync.model.flync_4_metadata.metadata.ECUMetadata`
        Metadata information describing the ECU.
    """

    name: Annotated[
        str,
        Implied(
            strategy=ImpliedStrategy.FOLDER_NAME,
        ),
    ] = Field()
    ports: Annotated[
        List["ECUPort"],
        External(
            output_structure=OutputStrategy.SINGLE_FILE,
            naming_strategy=NamingStrategy.FIELD_NAME,
        ),
    ] = Field(min_length=1, default_factory=list)
    controllers: Annotated[
        List["Controller"],
        External(
            output_structure=OutputStrategy.FOLDER,
            naming_strategy=NamingStrategy.FIELD_NAME,
        ),
    ] = Field()
    switches: Annotated[
        Optional[List["Switch"]],
        External(
            output_structure=OutputStrategy.FOLDER,
            naming_strategy=NamingStrategy.FIELD_NAME,
        ),
    ] = Field(default_factory=list)
    topology: Annotated[
        "InternalTopology",
        External(
            output_structure=OutputStrategy.SINGLE_FILE
            | OutputStrategy.OMMIT_ROOT,
            naming_strategy=NamingStrategy.FIELD_NAME,
        ),
    ] = Field()
    ecu_metadata: Annotated[
        "ECUMetadata",
        External(
            output_structure=OutputStrategy.SINGLE_FILE
            | OutputStrategy.OMMIT_ROOT
        ),
    ] = Field()
    sockets: Annotated[
        Optional[List[SocketContainer]],
        External(
            output_structure=OutputStrategy.FOLDER,
            naming_strategy=NamingStrategy.FIELD_NAME,
        ),
    ] = Field(default_factory=list)

    @model_validator(mode="after")
    def reference_ecu_in_children(self):
        """
        allows the children attributes to access ._ecu
        """
        RESET_unique_name_cache()
        [setattr(p, "_ecu", self) for p in self.ports]  # noqa
        [setattr(c, "_ecu", self) for c in self.topology.connections]  # noqa
        return self

    @model_validator(mode="after")
    def validate_vlans_in_sockets(self):
        """
        Validate that the VLAN IDs specified in the socket containers
        are configured in at least one virtual interface of the ECU."""

        if self.sockets is not None:
            vlan_ids_in_sockets = {socket.vlan_id for socket in self.sockets}
            vlan_ids_in_interfaces = {
                vi.vlanid
                for vi in find_all(
                    self.controllers, VirtualControllerInterface
                )
            }
            missing_vlans = vlan_ids_in_sockets - vlan_ids_in_interfaces
            if missing_vlans:
                raise err_minor(
                    f"Error in socket configuration:\n"
                    f"The following VLAN IDs are specified in the socket "
                    f"containers but not configured in any virtual interface "
                    f"of the ECU {self.name}: {missing_vlans}."
                )
        return self

    @model_validator(mode="after")
    def bind_sockets_to_ip(self):
        """
        Associate the given sockets with the matching ECU IP address.

        Raises:
            err_minor: If a socket's endpoint address does not belong
                to any virtual interface in the ECU, or if the address is
                found on a virtual interface whose VLAN name differs from
                the one supplied.
        """
        controllers = self.controllers
        sockets_per_vlan = self.get_all_sockets()
        all_virtual_interfaces = [
            vi for vi in find_all(controllers, VirtualControllerInterface)
        ]
        ips = self.get_all_ips()

        for interface, (_, sockets) in product(
            all_virtual_interfaces, sockets_per_vlan.items()
        ):
            if not sockets:
                continue
            for socket in sockets:
                if socket.endpoint_address not in ips:
                    raise err_minor(
                        f"Error in socket {socket.name}:\n"
                        f"The IP {socket.endpoint_address} is not configured "
                        f"in any virtual interface of the ECU {self.name}."
                    )

                for ip in interface.addresses:
                    if ip.address == socket.endpoint_address:
                        ip.sockets.append(socket)

        return self

    def get_all_controllers(self):
        """Return a list of all controllers of the ECU."""
        return self.controllers

    def get_all_ports(self):
        """Return a list of all ports of the ECU."""
        return self.ports

    def get_all_switches(self):
        """Return a list of all switches of the ECU."""
        return self.switches

    def get_internal_topology(self):
        """Return a list of all switches of the ECU."""
        return self.topology

    def get_all_interfaces(self):
        """Return a list of all physical interfaces of the ECU."""
        interfaces = []
        for controller in self.controllers:
            for iface in controller.interfaces:
                if iface:
                    interfaces.append(iface)
        return interfaces if interfaces else None

    def get_all_switch_ports(self) -> List["SwitchPort"]:
        """Return a list of all ports of the ECU switch."""
        ports = []
        if self.switches is not None:
            for switch in self.switches:
                for port in switch.ports:
                    if port:
                        ports.append(port)
        return ports

    def get_switch_by_name(self, switch_name: str):
        """Retrieve a Switch of the ECU by name."""
        if self.switches is not None:
            for switch in self.switches:
                if switch.name == switch_name:
                    return switch
        return None  # Return None if not found

    def get_all_ips(self):
        """
        Get all IPs in a ECU
        """
        ip_lists = []
        for ctrl in self.get_all_controllers():
            ip_lists.extend(ctrl.get_all_ips())
        return ip_lists

    def get_all_sockets(self) -> dict[int, List[Socket]]:
        """
        Get all sockets in a ECU, grouped by VLAN ID.
        """
        return {
            vlan_id: [
                socket
                for socket_container in self.sockets or []
                if socket_container.vlan_id == vlan_id
                for socket in socket_container.sockets or []
            ]
            for vlan_id in set(
                socket_container.vlan_id
                for socket_container in self.sockets or []
            )
        }
