import logging
from typing import List

from pydantic import Field, PrivateAttr, field_serializer, model_validator
from pydantic.networks import IPvAnyAddress
from pydantic_extra_types.mac_address import MacAddress

import flync.core.utils.base_utils as utils
from flync.core.base_models.base_model import FLYNCBaseModel
from flync.core.utils.exceptions import err_minor
from flync.model.flync_4_ecu import ControllerInterface, SwitchPort


class MulticastPath(FLYNCBaseModel):
    """
    Represents a single multicast path in detail.

    Describes how multicast traffic is sent from a source interface
    to one or more destination interfaces, including VLAN tagging and
    the multicast address.

    Parameters
    ----------
    vlan : int
        VLAN ID over which the multicast traffic is sent (0-4095).

    address : :class:`IPvAnyAddress` or :class:`MacAddress`
        Multicast address for this path (IPv4, IPv6, or MAC).

    src_interface : str
        Name of the source controller interface that originates the
        multicast.

    dst_interface : list of str
        Names of destination controller interfaces that receive the
        multicast.

    Private Attributes
    ------------------
    _connected_component_list : object
        Internal reference to the connected component for this
        multicast path.
    """

    vlan: int = Field(..., ge=0, le=4095)  # Optional for untagged, or 0
    address: IPvAnyAddress | MacAddress = Field()
    src_interface: str = Field()
    dst_interface: List[str] = Field()
    _connected_component_list = PrivateAttr(default=None)

    @model_validator(mode="after")
    def validate_path(self):
        """
        Validate the multicast path in the mzlticast
        config.
        """
        all_interfaces = ControllerInterface.INSTANCES
        if self.src_interface not in all_interfaces.keys():
            raise err_minor(
                f"Error validating multicast path, Address {self.address}. "
                f"Source Interface {self.src_interface} "
                f"should exist in the system. "
            )
        src_interface = all_interfaces[self.src_interface]
        dst_interfaces = []
        for interface in self.dst_interface:
            if interface not in all_interfaces.keys():
                raise err_minor(
                    f"Error validating multicast path, Address {self.address}."
                    f" Destination Interface {interface} "
                    f"should exist in the system. "
                )
            interface = all_interfaces[interface]

        all_src_vlans = [vi.vlanid for vi in src_interface.virtual_interfaces]
        if self.vlan not in all_src_vlans:
            raise err_minor(
                f"Error validating multicast path, VLAN {self.vlan} "
                f"not present in {src_interface.name}"
            )

        for dst_interface in dst_interfaces:
            self.validate_dst_interface_has_vlan_and_multicast(
                dst_interface, self.vlan, self.address
            )
        # Try to find a path from source to destination interface

        connected_components = []
        self.find_path_src_to_dest(
            connected_components,
            src_interface,
            self.address,
            dst_interfaces,
            all_interfaces,
        )

        self._connected_component_list = connected_components
        # Build the part that lists all components
        components_str = " ---> ".join(
            comp.name for comp in connected_components
        )

        # One‑line log message
        logging.info(
            f"Multicast Path validated {self.address}  {components_str}"
        )
        return self

    def validate_dst_interface_has_vlan_and_multicast(
        self, dst_interface, vlan, address
    ):
        """Helper function to help validate multicast paths.

        Validate if the dst_interface has the VLAN ID
        and multicast address described in the path
        """
        all_dst_vlans = []
        for vint in dst_interface.virtual_interfaces:
            all_dst_vlans.append(vint.vlanid)
            if vint.vlanid == vlan and address not in vlan.multicast:

                raise err_minor(
                    f"Error validating multicast path, "
                    f"Address {address}. "
                    f"Address not configured in destination "
                    f"interface {dst_interface.name}. "
                )
        if vlan not in all_dst_vlans:
            raise err_minor(
                f"Error validating multicast path, VLAN {vlan} "
                f"not present in {dst_interface.name}"
            )

    def find_path_src_to_dest(
        self,
        connected_components,
        src_interface,
        address,
        dst_interfaces,
        all_interfaces,
    ):
        """
        Helper function: Compute a path from src interface to
        destination interface
        """
        direct_conn = src_interface.get_connected_components()

        new_connected_components = [direct_conn]
        connected_components.append(src_interface)
        while len(new_connected_components) != 0:

            new_list = []
            for comp in new_connected_components:
                if comp._type == "switch_port":
                    self.get_switch_port_connected_component(
                        comp,
                        connected_components,
                        new_connected_components,
                        new_list,
                        address,
                    )

                if comp._type == "controller_interface":
                    self.get_controller_interface_connected_component(
                        comp,
                        connected_components,
                        new_connected_components,
                        new_list,
                    )

                if comp._type == "ecu_port":
                    self.get_ecu_port_connected_component(
                        comp,
                        connected_components,
                        new_connected_components,
                        new_list,
                    )

            connected_components.extend(new_connected_components)
            new_connected_components = new_list
        for interface in dst_interfaces:
            dst_interface = all_interfaces[interface]
            if dst_interface not in connected_components:
                raise err_minor(
                    f"Error validating multicast path. "
                    f"No path exists from {src_interface.name} to "
                    f"{dst_interface.name}. "
                    f"Configure the multicast in switches and "
                    f"controllers correctly."
                )
        connected_components.pop(0)

    def get_switch_port_connected_component(
        self,
        comp,
        connected_components,
        new_connected_components,
        new_list,
        address,
    ):
        """Helper function to help validate multicast paths.

        Adds all the components connected to a switch
        port to the list of components that were
        not already there in the paths
        """
        conn = comp.connected_component
        if not utils.check_obj_in_list(
            conn, connected_components
        ) and not utils.check_obj_in_list(conn, new_connected_components):
            new_list.append(conn)
        mcast_ports = comp.get_multicast_connected_ports(address)
        for sport in mcast_ports:
            sport_obj = SwitchPort.INSTANCES[sport]
            if (
                sport_obj not in connected_components
                and sport_obj not in new_connected_components
                and sport_obj.name != comp.name
            ):
                new_list.append(sport_obj)

    def get_ecu_port_connected_component(
        self, comp, connected_components, new_connected_components, new_list
    ):
        """Helper function to help validate multicast paths.

        Adds all the components connected to a ECU
        Port to the list of components that were
        not already there in the paths
        """
        conn = comp.connected_components
        for conn1 in conn:
            if not utils.check_obj_in_list(
                conn1, connected_components
            ) and not utils.check_obj_in_list(conn1, new_connected_components):
                new_list.append(conn1)

    def get_controller_interface_connected_component(
        self, comp, connected_components, new_connected_components, new_list
    ):
        """Helper function to help validate multicast paths.

        Adds all the components connected to a controller
        interface to the list of components that were
        not already there in the paths
        """
        conn = comp.connected_component
        if not utils.check_obj_in_list(
            conn, connected_components
        ) and not utils.check_obj_in_list(conn, new_connected_components):
            new_list.append(conn)
        connected_interfaces = comp.get_other_interfaces()
        for iface in connected_interfaces:
            if (
                iface not in connected_components
                and iface.name != comp.name
                and conn not in new_connected_components
            ):
                new_list.append(iface)

    def get_components(self):
        """
        Helper function: to return all the
        components in a multicast path
        """
        return self._connected_component

    def get_switch_ports(self):
        """
        Helper function: to return all the
        switch ports in a multicast path
        """
        switch_ports_list = []
        for comp in self._connected_component:
            if comp._type == "switch_port":
                switch_ports_list.append(comp)
        return switch_ports_list

    def get_controller_interfaces(self):
        """
        Helper function: to return all the
        controller interfaces in a multicast path
        """
        controller_interfaces = []
        for comp in self._connected_component:
            if comp._type == "controller_interface":
                controller_interfaces.append(comp)
        return controller_interfaces

    def get_ecu_ports(self):
        """
        Helper function: to return all the
        ecu ports in a multicast path
        """
        ecu_port_list = []
        for comp in self._connected_component:
            if comp._type == "ecu_port":
                ecu_port_list.append(comp)
        return ecu_port_list

    @field_serializer("address")
    def serialize_address(self, address):
        if address is not None:
            return str(address).upper()


class MulticastConfig(FLYNCBaseModel):
    """
    Represents the system-wide multicast paths.

    This model aggregates all source and destination pairs that define
    each multicast route in the system.

    Parameters
    ----------
    paths : list of :class:`MulticastPath`
        Instances representing individual multicast paths in the system.
    """

    paths: list[MulticastPath] = Field()
