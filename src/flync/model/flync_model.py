"""
Top-level system model aggregating ECUs, topology,
metadata, and general configuration in FLYNC.
"""

from typing import Annotated, Dict, List, Optional, Tuple

from pydantic import Field, model_validator
from pydantic_core import PydanticCustomError

from flync.core.annotations import External, NamingStrategy, OutputStrategy
from flync.core.base_models.base_model import FLYNCBaseModel
from flync.core.utils.base_utils import check_obj_in_list
from flync.core.utils.exceptions import err_major, warn
from flync.core.utils.multicast import (
    collect_ipv6_solicited_node_rx,
    collect_ipv6_solicited_node_tx,
    compute_path,
    serialize_components,
)
from flync.model.flync_4_ecu import (
    ECU,
    ECUPort,
    MulticastGroup,
    VirtualControllerInterface,
    VLANEntry,
)
from flync.model.flync_4_general_configuration import FLYNCGeneralConfig
from flync.model.flync_4_metadata import SystemMetadata
from flync.model.flync_4_topology import FLYNCTopology


class FLYNCModel(FLYNCBaseModel):
    """
    Represents the top-level FLYNC configuration model for a system.

    This model aggregates all ECUs, system topology, metadata, and
    general configuration settings for the entire system.

    Parameters
    ----------
    ecus : list of :class:`~flync.model.flync_4_ecu.ecu.ECU`
        List of ECU definitions included in the system.

    topology : :class:`~flync.model.flync_4_topology.FLYNCTopology`
        The system-wide topology including external ECU connections
        and optional multicast paths.

    metadata : :class:`~flync.model.flync_4_metadata.SystemMetadata`
        System-level metadata including OEM, platform, and hardware/software
        information.

    general : \
        :class:`~flync.model.flync_4_general_configuration.FLYNCGeneralConfig`
        , optional
        Optional general configuration settings applicable system-wide.
    """

    general: Annotated[
        Optional[FLYNCGeneralConfig],
        External(
            output_structure=OutputStrategy.FOLDER,
            naming_strategy=NamingStrategy.FIELD_NAME,
        ),
    ] = Field(default=None)
    ecus: Annotated[
        List[ECU],
        External(
            output_structure=OutputStrategy.FOLDER,
            naming_strategy=NamingStrategy.FIELD_NAME,
        ),
    ]
    topology: Annotated[
        FLYNCTopology,
        External(
            output_structure=OutputStrategy.FOLDER,
            naming_strategy=NamingStrategy.FIELD_NAME,
        ),
    ]
    metadata: Annotated[
        SystemMetadata,
        External(
            output_structure=OutputStrategy.SINGLE_FILE
            | OutputStrategy.OMMIT_ROOT,
            naming_strategy=NamingStrategy.FIXED_PATH,
            path="system_metadata",
        ),
    ]

    _EXCLUDED_NAME_CHECK_CLASSES: Tuple[type, ...] = (
        VirtualControllerInterface,
        VLANEntry,
    )

    @model_validator(mode="before")
    @classmethod
    def skip_broken_ecus(cls, data):
        """Remove None ECUs from the list before validation.

        When an ECU file fails to load the workspace inserts None into the
        ecus list.  Errors are already reported at the ECU level, so the
        None entries are silently dropped here to prevent a cascade of
        FLYNCModel-level errors for the same root cause.
        """
        if isinstance(data, dict):
            ecus = data.get("ecus") or []
            if isinstance(ecus, list) and any(e is None for e in ecus):
                data["ecus"] = [e for e in ecus if e is not None]
        return data

    def model_post_init(self, context):
        """
        Perform post-initialization processing after the model is created.

        Following steps are performed:

        1. Populate the solicited-node RX multicast group memberships for each
           IPv6 address configured in any ECU.

        2. Populate the solicited-node TX multicast group memberships for each
           ECU based on the RX entries for the same multicast group and VLAN.
        """
        self.__populate_ipv6_solicited_node_multicasts_rx()
        self.__populate_ipv6_solicited_node_multicasts_tx()

    @model_validator(mode="after")
    def validate_unique_ips(self):
        """
        Validate all IPs are unique system wide
        """
        try:
            all_ips = []
            for ecu in self.ecus:
                new_ips = ecu.get_all_ips()
                for ip in new_ips:
                    if ip not in all_ips:
                        all_ips.append(ip)
                    else:
                        warn(f"The IP {ip} is repeated in ECU {ecu.name}")
        except PydanticCustomError as e:
            warn(str(e))
        return self

    @model_validator(mode="after")
    def check_tx_rx_multicast_group(self):
        try:
            tx_list = []
            rx_list = []
            separ = "/VLAN"
            for ecu in self.ecus:
                for mcast in ecu.multicast_groups:
                    key = str(mcast.group) + separ + str(mcast.vlan)
                    if mcast.mode == "tx" or mcast.mode == "bidir":
                        tx_list.append(key)
                    if mcast.mode == "rx" or mcast.mode == "bidir":
                        rx_list.append(key)

            for rx in rx_list:
                if rx not in tx_list:
                    warn(
                        "Invalid Multicast Configuration. There "
                        "is a multicast rx configured for the address "
                        f"{rx} but no tx."
                    )
        except PydanticCustomError as e:
            warn(str(e))
        return self

    @model_validator(mode="after")
    def validate_multicast_paths(self):
        try:
            paths = dict()
            vlans_dict = dict()
            separ = "/VLAN"
            for ecu in self.ecus:
                for mcast in ecu.multicast_groups:
                    key = str(mcast.group) + separ + str(mcast.vlan)
                    vlans_dict[key] = mcast.vlan
                    if (
                        mcast.mode == "tx" or mcast.mode == "bidir"
                    ) and key not in paths:

                        paths[key] = compute_path(mcast.vlan, mcast._interface)
                    if (
                        (mcast.mode == "tx" or mcast.mode == "bidir")
                        and key in paths
                        and not check_obj_in_list(mcast._interface, paths[key])
                    ):
                        warn(
                            "Invalid Multicast Address Configuration. There"
                            " are several RX that the TX or BiDir Endpoint at "
                            f"{mcast._interface.name} cannot reach."
                            f"{serialize_components(paths[key])}"
                        )
            self.check_rx_are_reached(separ, paths, vlans_dict)
        except PydanticCustomError as e:
            warn(str(e))
        return self

    @model_validator(mode="after")
    def validate_unique_macs(self):
        """
        Validate all MACs are unique system wide
        """
        all_macs = []
        for ecu in self.ecus:
            new_macs = ecu.get_all_macs()
            for mac in new_macs:
                if mac not in all_macs:
                    all_macs.append(mac)
                else:
                    raise err_major(
                        f"The MAC {mac} is repeated in ECU {ecu.name}"
                    )
        return self

    def check_rx_are_reached(self, separ, paths, vlans_dict):
        for ecu in self.ecus:
            for mcast in ecu.multicast_groups:
                key = str(mcast.group) + separ + str(mcast.vlan)
                if (
                    mcast.mode == "rx" or mcast.mode == "bidir"
                ) and key not in paths:

                    warn(
                        "Invalid Multicast Address Configuration. There"
                        " are no TX endpoints for this address "
                        f"{key} "
                    )
                if (
                    (mcast.mode == "rx" or mcast.mode == "bidir")
                    and key in paths
                    and not check_obj_in_list(mcast._interface, paths[key])
                ):
                    warn(
                        "Invalid Multicast Address Configuration."
                        f"The RX interface for address {key} "
                        f"- {mcast._interface.name} cannot be reached "
                        f"by the TX ports."
                    )

        self.load_switch_multicast(vlans_dict, paths)

        return self

    def __populate_ipv6_solicited_node_multicasts_rx(self):
        """
        Populate the solicited-node multicast group memberships for each
        IPv6 address configured in any ECU.
        """
        for ecu in self.ecus:
            update_ecu_multicast = collect_ipv6_solicited_node_rx(ecu)
            if ecu.name in update_ecu_multicast:
                ecu.multicast_groups.append(update_ecu_multicast[ecu.name])
        return self

    def __populate_ipv6_solicited_node_multicasts_tx(self):
        """
        Populate the solicited-node multicast group memberships for each
        IPv6 address configured in any ECU as TX if there is a RX for the
        same multicast group and VLAN.
        """
        multicasts = [
            mc
            for ecu in self.ecus
            for mc in ecu.multicast_groups
            if mc.solicited_node_multicast
        ]

        for ecu in self.ecus:
            update_ecu_multicast = collect_ipv6_solicited_node_tx(
                ecu, multicasts
            )
            if ecu.name in update_ecu_multicast:
                ecu.multicast_groups.append(update_ecu_multicast[ecu.name])
        return self

    def append_mcast(self, vlan, comp, mcast_addr):
        for v_entry in comp.get_switch().vlans:
            if v_entry.id == vlan:
                found_mcast = False
                for addr in v_entry.multicast:
                    if str(addr.address) == mcast_addr:
                        found_mcast = True
                        addr.ports.append(comp.name)
                if not found_mcast:
                    new_mcast_group = MulticastGroup(
                        address=mcast_addr, ports=[comp.name]
                    )
                    v_entry.multicast.append(new_mcast_group)

    def load_switch_multicast(self, vlans_dict, paths):
        for key, value in paths.items():
            for comp in value:
                if comp.type == "switch_port":
                    ip = key.split("/")[0]
                    self.append_mcast(vlans_dict[key], comp, ip)

    def get_all_ecus(self):
        """Return a list of all ECU names."""
        return [ecu.name for ecu in self.ecus]

    def get_ecu_by_name(self, ecu_name: str):
        """Retrieve an ECU by name."""
        for ecu in self.ecus:
            if ecu.name == ecu_name:
                return ecu
        return None

    def get_all_controllers(self):
        """Return a list of all controllers in all ECUs."""
        controllers = []
        for ecu in self.ecus:
            controllers.extend(ecu.controllers)
        return controllers

    def get_all_ecu_ports(self) -> List["ECUPort"]:
        """Return a list of all ECU ports"""
        ecu_ports = []
        for ecu in self.ecus:
            ecu_ports.extend(ecu.get_all_ports())
        return ecu_ports

    def get_all_ecu_ports_by_name(self) -> Dict[str, "ECUPort"]:
        return {e.name: e for e in self.get_all_ecu_ports()}

    def get_interface_by_name(self, name):
        return next(
            (
                interface
                for interface in self.get_all_interfaces()
                if interface.name == name
            ),
            None,
        )

    def get_all_interfaces(self):
        return [
            iface
            for controller in self.get_all_controllers()
            for iface in controller.interfaces
        ]

    def get_all_interfaces_names(self):
        """Return all the controller interface names"""
        all_interfaces = []
        for ecu in self.get_all_ecus():
            all_interfaces.extend(self.get_interfaces_for_ecu(ecu))
        return all_interfaces

    def get_interfaces_for_ecu(self, ecu_name: str):
        """Return a list of all interfaces for a given ECU."""
        ecu = self.get_ecu_by_name(ecu_name)
        if ecu:
            return [
                iface.name
                for controller in ecu.controllers
                for iface in controller.interfaces
            ]
        return []

    def get_system_topology_info(self):
        """Return system topology details."""
        return self.topology.system_topology.model_dump()
