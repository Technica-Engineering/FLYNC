"""Defines the ECU model for FLYNC."""

from itertools import product
from typing import Annotated, List, Optional, TypeVar

from pydantic import BeforeValidator, Field, model_validator

import flync.core.utils.common_validators as common_validators
from flync.core.annotations import (
    External,
    Implied,
    ImpliedStrategy,
    NamingStrategy,
    OutputStrategy,
)
from flync.core.base_models import UniqueName
from flync.core.utils.base_utils import find_all
from flync.core.utils.exceptions import err_major, err_minor
from flync.model.flync_4_ecu.controller import (
    Controller,
    ControllerInterface,
    VirtualControllerInterface,
)
from flync.model.flync_4_ecu.internal_topology import InternalTopology
from flync.model.flync_4_ecu.mac_multicast_endpoint import (
    MACMulticastEndpoints,
)
from flync.model.flync_4_ecu.multicast_groups import MulticastGroupMembership
from flync.model.flync_4_ecu.port import ECUPort
from flync.model.flync_4_ecu.socket_container import SocketContainer
from flync.model.flync_4_ecu.sockets import Socket
from flync.model.flync_4_ecu.switch import Switch, SwitchPort
from flync.model.flync_4_metadata import ECUMetadata
from flync.model.flync_4_someip import (  # type: ignore  # noqa: F401
    SOMEIPServiceConsumer,
    SOMEIPServiceDeployment,
    SOMEIPServiceProvider,
)

_T_Service = TypeVar("_T_Service", bound=SOMEIPServiceDeployment)


def reset_unique_name_cache():
    """Reset cached unique names for controller interfaces and switch ports."""
    ControllerInterface.NAMES.clear()
    SwitchPort.NAMES.clear()


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

    multicast_groups : list of \
    :class:`~flync.model.flync_4_ecu.multicast_groups.\
        MulticastGroupMembership`, optional
        Multicast group memberships of the ECU. This field is populated
        automatically internally.

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
        BeforeValidator(
            common_validators.validate_or_remove(
                "internal topology", InternalTopology, severity="major"
            )
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
    ] = Field(default_factory=list, exclude=True)
    mac_multicast_endpoints: Annotated[
        Optional["MACMulticastEndpoints"],
        External(
            output_structure=OutputStrategy.SINGLE_FILE
            | OutputStrategy.OMMIT_ROOT
        ),
    ] = Field(exclude=True, default=None)
    multicast_groups: Optional[List[MulticastGroupMembership]] = Field(
        default_factory=list, exclude=True
    )

    def model_post_init(self, context):
        """
        Perform post-initialization processing after the model is created.

        Following steps are performed:
        1. Reference the ECU in child components to allow access to ECU-level
           information.

        2. Bind sockets to their corresponding IP addresses in the ECU's
           virtual interfaces, ensuring that each socket is associated with
           the correct ECU IP.

        3. Populate multicast group memberships based on socket configurations
           and virtual interface settings.
        """
        self.__reference_ecu_in_children()
        self.__bind_sockets_to_ip()
        self.__populate_multicast_tx_groups_from_socket()
        self.__populate_multicast_rx_groups_from_interfaces()
        self._populate_multicast_tx_groups_from_mac_multicast_endpoints()

    @model_validator(mode="before")
    @classmethod
    def skip_on_broken_controllers(cls, data):
        """Skip ECU validation when controllers or switches failed to load.

        When a controller or switch cannot be parsed, the workspace places
        None in the respective list.  Attempting to validate the ECU in that
        state produces a cascade of unhelpful errors.  Instead report a
        single major error so that per-component errors remain the focus.
        """
        if isinstance(data, dict):
            controllers = data.get("controllers") or []
            switches = data.get("switches") or []
            broken_controllers = isinstance(controllers, list) and any(
                c is None for c in controllers
            )
            broken_switches = isinstance(switches, list) and any(
                s is None for s in switches
            )
            if broken_controllers or broken_switches:
                raise err_major(
                    "ECU has invalid components. "
                    "Check controller and switch errors for details."
                )
        return data

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

    def __bind_sockets_to_ip(self):
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
                if socket.endpoint_type == "multicast":
                    continue
                if str(socket.endpoint_address) not in ips:
                    ip = socket.endpoint_address
                    raise err_minor(
                        f"Error in socket {socket.name}:\n"
                        f"The IP {ip} is not configured "
                        "in any virtual interface"
                        f" of the ECU {self.name}."
                    )

                for ip in interface.addresses:
                    if ip.address == socket.endpoint_address:
                        ip.sockets.append(socket)

        return self

    def __reference_ecu_in_children(self):
        """
        allows the children attributes to access ._ecu
        """
        reset_unique_name_cache()
        [setattr(p, "_ecu", self) for p in self.ports]  # noqa
        [setattr(c, "_ecu", self) for c in self.topology.connections]  # noqa
        return self

    def __populate_multicast_tx_groups_from_socket(self):
        """
        Add Multicast TX entries from sockets
        to multicast group memberships.
        """

        for socket_container in self.sockets:
            for socket in socket_container.sockets:
                if socket.endpoint_type == "multicast":
                    for multicast_addr in socket.multicast_tx:
                        group = MulticastGroupMembership(
                            group=multicast_addr,
                            description=socket.name,
                            mode="tx",
                            vlan=socket_container.vlan_id,
                            src_ip=socket.endpoint_address,
                        )
                        interface = self.get_interface_for_ip(
                            str(socket.endpoint_address)
                        )
                        group._interface = interface
                        self.multicast_groups.append(group)
        return self

    def __populate_multicast_rx_groups_from_interfaces(self):
        """
        Add Multicast RX entries from virtual interfaces
        to multicast group memberships.
        """

        for interface in find_all(self.controllers, ControllerInterface):
            for viface in interface.virtual_interfaces:
                for multicast_addr in viface.multicast:
                    group = MulticastGroupMembership(
                        group=multicast_addr,
                        description="",
                        mode="rx",
                        vlan=viface.vlanid,
                        src_ip=None,
                    )
                    group._interface = interface
                    self.multicast_groups.append(group)
            for node in interface.compute_nodes:
                for viface in node.virtual_interfaces:
                    for multicast_addr in viface.multicast:
                        group = MulticastGroupMembership(
                            group=multicast_addr,
                            description="",
                            mode="rx",
                            vlan=viface.vlanid,
                            src_ip=None,
                        )
                        group._interface = interface
                        self.multicast_groups.append(group)
        return self

    def _populate_multicast_tx_groups_from_mac_multicast_endpoints(self):
        """
        Add Multicast TX entries from MAC multicast endpoints
        to multicast group memberships.
        """

        if self.mac_multicast_endpoints is not None:
            for endpoint_union in self.mac_multicast_endpoints.endpoints:
                endpoint = endpoint_union.root
                for multicast_addr in endpoint.multicast_tx:
                    group = MulticastGroupMembership(
                        group=multicast_addr,
                        description=endpoint.name,
                        mode="tx",
                        vlan=endpoint.vlan_id or None,
                        src_ip=None,
                    )
                    interface = self.get_interface_for_mac(
                        str(endpoint.mac_address)
                    )
                    if not interface:
                        raise err_minor(
                            f"Error in MAC multicast:\n"
                            f"endpoints. Could not find an interface for "
                            f"address {endpoint.mac_address}. ECU {self.name}"
                        )
                    group._interface = interface
                    self.multicast_groups.append(group)
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
        for ctrl in self.controllers or []:
            ip_lists.extend(ctrl.get_all_ips())
        for switch in self.switches:
            if switch.host_controller:
                ip_lists.extend(switch.host_controller.get_all_ips())
        return ip_lists

    def get_all_macs(self):
        """
        Get all MAC addresses in a ECU
        """
        mac_lists = []
        for ctrl in self.controllers:
            mac_lists.extend(ctrl.get_all_macs())
        for switch in self.switches or []:
            if switch.host_controller is not None:
                mac_lists.extend(switch.host_controller.get_all_macs())
        return mac_lists

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

    def get_interface_for_ip(self, ip):
        for iface in self.get_all_interfaces():
            if ip in iface.get_all_ips():
                return iface

    def get_interface_for_mac(self, mac):
        for iface in self.get_all_interfaces():
            macs = [iface.mac_address] + [
                node.mac_address for node in iface.compute_nodes
            ]
            if mac in macs:
                return iface

    def __get_services_of_type(
        self, service_type: type[_T_Service]
    ) -> list[_T_Service]:
        """Return all SOME/IP service deployments of a given type.

        Iterates over all socket containers and their sockets, collecting
        deployments whose root matches ``service_type``.

        Parameters
        ----------
        service_type : type[SOMEIPServiceDeployment]
            The concrete deployment type to filter by (e.g.
            :class:`~flync.model.flync_4_someip.SOMEIPServiceConsumer` or
            :class:`~flync.model.flync_4_someip.SOMEIPServiceProvider`).

        Returns
        -------
        list[SOMEIPServiceDeployment]
            All matching service deployment instances found across the ECU's
            socket containers.
        """
        service_instances = []
        for ecu_sockets in self.sockets or []:
            for socket in ecu_sockets.sockets or []:
                for deployment in socket.deployments or []:
                    if isinstance(deployment.root, service_type):
                        someip_deployment = deployment.root
                        service_instances.append(someip_deployment)
        return service_instances

    def get_consumed_services(self) -> list[SOMEIPServiceConsumer]:
        """Return all SOME/IP service consumer deployments of the ECU.

        Returns
        -------
        list[SOMEIPServiceConsumer]
            All :class:`~flync.model.flync_4_someip.SOMEIPServiceConsumer`
            instances found across the ECU's socket containers.
        """
        return self.__get_services_of_type(SOMEIPServiceConsumer)

    def get_provided_services(self) -> list[SOMEIPServiceProvider]:
        """Return all SOME/IP service provider deployments of the ECU.

        Returns
        -------
        list[SOMEIPServiceProvider]
            All :class:`~flync.model.flync_4_someip.SOMEIPServiceProvider`
            instances found across the ECU's socket containers.
        """
        return self.__get_services_of_type(SOMEIPServiceProvider)
