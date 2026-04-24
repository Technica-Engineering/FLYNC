"""Defines the Controller and ControllerInterface models for FLYNC."""

from typing import Annotated, ClassVar, Dict, List, Literal, Optional

from pydantic import (
    AfterValidator,
    BeforeValidator,
    Field,
    PrivateAttr,
    field_serializer,
    field_validator,
    model_validator,
)
from pydantic.networks import IPvAnyAddress
from pydantic_extra_types.mac_address import MacAddress

import flync.core.utils.common_validators as common_validators
from flync.core.base_models import (
    FLYNCBaseModel,
    NamedDictInstances,
    NamedListInstances,
)
from flync.core.utils.exceptions import err_fatal, err_minor
from flync.model.flync_4_ecu.phy import MII, RGMII, RMII, SGMII, XFI
from flync.model.flync_4_ecu.sockets import (
    IPv4AddressEndpoint,
    IPv6AddressEndpoint,
)
from flync.model.flync_4_ecu.vlan_entry import VLANEntry
from flync.model.flync_4_metadata.metadata import EmbeddedMetadata
from flync.model.flync_4_security import Firewall, MACsecConfig
from flync.model.flync_4_tsn import (
    HTBInstance,
    PTPConfig,
    Stream,
    TrafficClass,
)


class VirtualControllerInterface(FLYNCBaseModel):
    """
    A VLAN-tagged virtual interface stacked on top of a physical controller
    interface or a compute node.

    Each virtual interface represents one logical network endpoint, identified
    by a VLAN ID and assigned one or more IP addresses. Multiple virtual
    interfaces can be defined on the same physical interface or compute node to
    separate traffic across different VLANs.

    Parameters
    ----------
    name : str
        Name of the virtual interface.

    vlanid : int
        VLAN identifier in the range 0-4095.

    addresses : list of \
    :class:`~flync.model.flync_4_ecu.sockets.IPv4AddressEndpoint` or \
    :class:`~flync.model.flync_4_ecu.sockets.IPv6AddressEndpoint`
        Assigned IPv4 and IPv6 address endpoints.

    multicast : list of :class:`IPv4Address` or :class:`IPv6Address` \
    or str, optional
        Allowed multicast addresses.
    """

    name: str = Field()
    vlanid: int = Field(..., ge=0, le=4095)
    addresses: List[IPv6AddressEndpoint | IPv4AddressEndpoint] = Field()
    multicast: Annotated[
        Optional[List[IPvAnyAddress | MacAddress]],
        AfterValidator(common_validators.validate_multicast_list),
        BeforeValidator(common_validators.none_to_empty_list),
    ] = Field(default=[])

    @field_serializer("addresses", "multicast")
    def serialize_addresses(self, value):
        if value is not None:
            return [
                (
                    v.model_dump()
                    if isinstance(v, FLYNCBaseModel)
                    else str(v).upper()
                )
                for v in value
            ]


class ComputeNodes(FLYNCBaseModel):
    """
    A virtual machine (VM) attached to a controller interface.

    Compute nodes are VMs that run on the same SoC as the controller. Each
    compute node has its own MAC address and one or more virtual interfaces
    (VLANs). Traffic between a compute node and the physical network is
    forwarded through the :class:`L2Bridge` defined on the parent
    :class:`Controller` — the L2 bridge acts as a software MAC bridge that
    connects compute nodes to the controller interface and to each other.

    Network features such as PTP, MACsec, ingress stream policing, and traffic
    shaping can be configured either on the parent :class:`ControllerInterface`
    or offloaded to individual compute nodes, but not on both simultaneously.

    Parameters
    ----------
    name : str
        Name of the compute node / VM.

    mac_address : :class:`MacAddress`
        MAC address of the compute node in standard notation.

    virtual_interfaces : list of :class:`VirtualControllerInterface`
        One or more VLAN-tagged virtual interfaces exposed by this compute
        node.

    ptp_config : :class:`~flync.model.flync_4_tsn.PTPConfig`, optional
        Precision Time Protocol configuration (offloaded from the interface).

    macsec_config : \
    :class:`~flync.model.flync_4_security.MACsecConfig`, optional
        MACsec configuration (offloaded from the interface).

    firewall : :class:`~flync.model.flync_4_security.Firewall`, optional
        Firewall configuration for this compute node.

    htb : :class:`~flync.model.flync_4_tsn.HTBInstance`, optional
        Hierarchical Token Bucket (HTB) egress shaping configuration.

    ingress_streams : list of :class:`~flync.model.flync_4_tsn.Stream`, \
    optional
        IEEE 802.1Qci ingress stream policing configuration.

    traffic_classes : list of \
    :class:`~flync.model.flync_4_tsn.TrafficClass`, optional
        Traffic class definitions and egress queue shaping configuration.
    """

    name: str = Field()
    mac_address: MacAddress = Field()
    virtual_interfaces: List[VirtualControllerInterface] = Field(
        ..., min_length=1
    )
    firewall: Optional[Firewall] = Field(default=None)
    htb: Optional[HTBInstance] = Field(default=None)
    ptp_config: Optional[PTPConfig] = Field(default=None)
    macsec_config: Optional[MACsecConfig] = Field(default=None)
    ingress_streams: Annotated[
        Optional[List[Stream]],
        BeforeValidator(common_validators.none_to_empty_list),
    ] = Field(default=[])
    traffic_classes: Annotated[
        Optional[List[TrafficClass]],
        AfterValidator(common_validators.validate_traffic_classes),
        BeforeValidator(common_validators.none_to_empty_list),
    ] = Field(default_factory=list)

    @field_validator("ingress_streams", mode="after")
    def validate_ingress_streams(cls, value):
        """
        Validate the ``ingress_streams`` field of a Compute Node.

        Ensures that no IPv or ATS values are present, as these are
        not valid at the compute node level.
        """
        for ingress_stream in value:
            if ingress_stream.ipv is not None:
                raise err_minor(
                    f"Validation Error in Ingress Streams. "
                    f"Removing config from the interface. "
                    f"Ingress stream {ingress_stream.name} "
                    f"at the compute node "
                    f"should not have "
                    f"an ipv value."
                )
            if ingress_stream.ats is not None:
                raise err_minor(
                    f"Validation Error in Ingress Streams. "
                    f"Removing config from the interface. "
                    f"Ingress stream {ingress_stream.name} at the "
                    f"compute node "
                    f"should not have an ats value"
                )
        return value

    @model_validator(mode="after")
    def validate_vlans(self):
        """Validate the VLAN configuration of Compute Node

        Raises:
            Validation error if the VLAN ID is repeated.
        """
        all_vlans = [vi.vlanid for vi in self.virtual_interfaces]
        list_label = (
            f"VLAN IDs of virtual Controller Interface in"
            f"interface {self.name}"
        )
        common_validators.validate_list_items_unique(all_vlans, list_label)
        return self


class L2BridgePort(FLYNCBaseModel):
    """
    A port on the :class:`L2Bridge`, referencing a connected node by name.

    Each port is bound to either a :class:`ControllerInterface` or a
    :class:`ComputeNodes` instance. The ``node_connected`` name must match
    the ``name`` field of one of those objects within the same controller.

    Parameters
    ----------
    name : str
        Name of the bridge port.

    node_connected : str
        Name of the connected :class:`ControllerInterface` or
        :class:`ComputeNodes`.
    """

    name: str = Field()
    node_connected: str = Field()


class L2Bridge(FLYNCBaseModel):
    """
    A software MAC bridge (Linux bridge) inside a controller.

    The L2 bridge is the connectivity fabric that ties together the
    controller's physical interfaces and their compute nodes. It must be
    defined on the :class:`Controller` whenever compute nodes are present or
    when multiple interfaces need to exchange traffic at Layer 2.

    Each :class:`L2BridgePort` references either a
    :class:`ControllerInterface` or a :class:`ComputeNodes` by name.
    VLANs defined on the bridge control which ports share broadcast domains,
    mirroring the role of VLANs on a hardware switch.

    Parameters
    ----------
    name : str
        Name of the L2 bridge instance.

    ports : list of :class:`L2BridgePort`
        Bridge ports, each referencing a controller interface or compute node.

    vlans : list of :class:`~flync.model.flync_4_ecu.vlan_entry.VLANEntry`
        VLAN membership table: defines which ports belong to each VLAN and
        therefore which nodes can communicate at Layer 2.
    """

    name: str = Field()
    ports: List[L2BridgePort] = Field()
    vlans: List[VLANEntry] = Field()


class ControllerInterface(NamedDictInstances):
    """
    A physical Ethernet interface on a controller.

    A controller interface is the hardware-level network endpoint of the
    controller. It can be used in two ways:

    * **Direct mode** — virtual interfaces (VLANs) are stacked directly on
      the physical interface. No compute nodes or L2 bridge are needed.

    * **Bridge mode** — one or more :class:`ComputeNodes` (VMs) are attached
      to the interface. In this case the :class:`L2Bridge` defined on the
      parent :class:`Controller` acts as a software MAC bridge: it connects
      the physical interface and each compute node together, and can also
      bridge multiple physical interfaces at Layer 2.

    Network features (PTP, MACsec, ingress stream policing, traffic shaping)
    can be configured at the interface level or offloaded to individual
    compute nodes, but not on both simultaneously.

    Parameters
    ----------
    name : str
        Interface name.

    mac_address : :class:`MacAddress`
        MAC address of the physical interface in standard notation.

    mii_config : :class:`~flync.model.flync_4_ecu.phy.MII` or \
    :class:`~flync.model.flync_4_ecu.phy.RMII` or \
    :class:`~flync.model.flync_4_ecu.phy.SGMII` or \
    :class:`~flync.model.flync_4_ecu.phy.RGMII`, optional
        Media-independent interface configuration.

    compute_nodes : list of :class:`ComputeNodes`, optional
        VMs attached to this interface. When present, an :class:`L2Bridge`
        must be defined on the parent :class:`Controller` to connect them.

    virtual_interfaces : list of :class:`VirtualControllerInterface`, \
    optional
        VLAN-tagged virtual interfaces stacked directly on this physical
        interface (used in direct mode, without compute nodes).

    ptp_config : :class:`~flync.model.flync_4_tsn.PTPConfig`, optional
        Precision Time Protocol configuration.

    macsec_config : \
    :class:`~flync.model.flync_4_security.MACsecConfig`, optional
        MACsec configuration.

    firewall : :class:`~flync.model.flync_4_security.Firewall`, optional
        Firewall configuration for the interface.

    htb : :class:`~flync.model.flync_4_tsn.HTBInstance`, optional
        Hierarchical Token Bucket (HTB) egress shaping configuration.

    ingress_streams : list of :class:`~flync.model.flync_4_tsn.Stream`, \
    optional
        IEEE 802.1Qci ingress stream policing configuration.

    traffic_classes : list of \
    :class:`~flync.model.flync_4_tsn.TrafficClass`, optional
        Traffic class definitions and egress queue shaping configuration.

    Private Attributes
    ------------------
    _connected_component :
        The switch port, controller interface, or ECU port connected to this
        interface. Managed internally; not part of the public API.
    _type :
        Fixed to ``"controller_interface"``.
    """

    INSTANCES: ClassVar[Dict[str, "ControllerInterface"]] = {}
    name: str = Field()
    mac_address: MacAddress = Field()
    mii_config: Optional[MII | RMII | SGMII | RGMII | XFI] = Field(
        default=None, discriminator="type"
    )
    compute_nodes: Optional[List[ComputeNodes]] = Field(default_factory=list)
    virtual_interfaces: Optional[List[VirtualControllerInterface]] = Field(
        default_factory=list
    )
    ptp_config: Optional[PTPConfig] = Field(default=None)
    macsec_config: Optional[MACsecConfig] = Field(default=None)
    ingress_streams: Annotated[
        Optional[List[Stream]],
        BeforeValidator(common_validators.none_to_empty_list),
    ] = Field(default=[])
    traffic_classes: Annotated[
        Optional[List[TrafficClass]],
        AfterValidator(common_validators.validate_traffic_classes),
        BeforeValidator(common_validators.none_to_empty_list),
    ] = Field(default_factory=list)
    firewall: Optional[Firewall] = Field(default=None)
    htb: Optional[HTBInstance] = Field(default=None)
    _connected_component = PrivateAttr(default=None)
    _type: Literal["controller_interface"] = PrivateAttr(
        default="controller_interface"
    )

    @property
    def type(self):
        return self._type

    @property
    def connected_component(self):
        return self._connected_component

    @field_validator("ingress_streams", mode="after")
    def validate_ingress_streams(cls, value):
        """
        Validate the ``ingress_streams`` field of an Interface model.

        The validator checks each ``IngressStream`` object attached to an
        interface and ensures that no IPv or ATS values are present

        Parameters
        ----------
        cls : type
            The model class on which the validator is defined (automatically
            supplied by *pydantic*).

        value : list of class:`~flync.flync_4_ecu.IngressStream`

        Returns
        -------
        list
            A list containing the validated ``IngressStream`` objects.  If an
            invalid IPv or ATS attribute is detected the function raises a
            value error.
        """
        ingress_streams = value
        for ingress_stream in ingress_streams:
            if ingress_stream.ipv is not None:

                raise err_minor(
                    f"Validation Error in Ingress Streams. "
                    f"Removing config from the interface. "
                    f"Ingress stream {ingress_stream.name} "
                    f"at the controller interface "
                    f"should not have "
                    f"an ipv value."
                )
            if ingress_stream.ats is not None:
                raise err_minor(
                    f"Validation Error in Ingress Streams. "
                    f"Removing config from the interface. "
                    f"Ingress stream {ingress_stream.name} at the "
                    f"controller interface "
                    f"should not have an ats value"
                )
        return value

    @model_validator(mode="after")
    def validate_vlans(self):
        """Validate the VLAN configuration of Controller Interface

        Raises:
            Validation error if the VLAN ID is repeated.
        """
        all_vlans = [vi.vlanid for vi in self.virtual_interfaces]
        list_label = (
            f"VLAN IDs of virtual Controller Interface in"
            f"interface {self.name}"
        )
        common_validators.validate_list_items_unique(all_vlans, list_label)
        return self

    @model_validator(mode="after")
    def validate_offloaded_configs_not_duplicated(self):
        """Validate that offloadable configs are not set on both the
        controller interface and any of its compute nodes.

        MACsec, PTP, ingress streams, and traffic classes can be
        offloaded to compute nodes. Configuring a feature at both
        levels simultaneously is not allowed.

        Raises:
            Validation error if ptp_config, macsec_config,
            ingress_streams, or traffic_classes is set on both the
            controller interface and a compute node.
        """
        if not self.compute_nodes:
            return self

        offloadable = {
            "ptp_config": self.ptp_config is not None,
            "macsec_config": self.macsec_config is not None,
            "ingress_streams": bool(self.ingress_streams),
            "traffic_classes": bool(self.traffic_classes),
        }

        for node in self.compute_nodes:
            node_has = {
                "ptp_config": node.ptp_config is not None,
                "macsec_config": node.macsec_config is not None,
                "ingress_streams": bool(node.ingress_streams),
                "traffic_classes": bool(node.traffic_classes),
            }
            for feature, iface_set in offloadable.items():
                if iface_set and node_has[feature]:
                    raise err_minor(
                        f"{feature} is configured on both controller "
                        f"interface {self.name} and compute node "
                        f"{node.name}. It must be defined on either "
                        f"the interface or its compute nodes, not both."
                    )
        return self

    def get_controller(self):
        """
        Helper function
        Returns the controller that the interface is a part of
        """

        for ctrl in Controller.INSTANCES:
            for interface in ctrl.interfaces:
                if interface.name == self.name:
                    return ctrl
        raise err_fatal(
            "Fatal Error: The interface is not a part of any controller"
        )

    def is_part_of_vlan(self, vlan):
        for node in self.compute_nodes:
            for vint in node.virtual_interfaces:
                if vint.vlanid == vlan:
                    return True
        for vint in self.virtual_interfaces:
            if vint.vlanid == vlan:
                return True

        return False

    def get_other_interfaces(self):
        """
        Helper function. Returns all the controller interfaces
        of the controller that the interface is a part of

        """
        for controller in Controller.INSTANCES:
            for interface in controller.interfaces:
                if interface.name == self.name:
                    return controller.interfaces

    def get_connected_components(self):
        """
        Return the component connected  to the controller interface.

        """
        return self._connected_component

    def get_all_ips(self):
        ips = []
        for node in self.compute_nodes:
            for viface in node.virtual_interfaces:
                for address in viface.addresses:
                    ips.append(str(address.address))
        for viface in self.virtual_interfaces:
            for address in viface.addresses:
                ips.append(str(address.address))

        return ips

    def get_all_macs(self):
        macs = []
        macs.append(self.mac_address)
        for node in self.compute_nodes:
            macs.append(node.mac_address)

        return macs


class Controller(NamedListInstances["Controller"]):
    """
    Represents a controller device that contains multiple interfaces.

    Parameters
    ----------
    meta : :class:`~flync.model.flync_4_metadata.metadata.EmbeddedMetadata`
        Metadata describing the embedded controller.

    type : Literal["Controller"]
        Indicates the type of the device. Default is "Controller".

    name : str
        Name of the controller.

    interfaces : list of :class:`ControllerInterface`
        Physical interfaces of the controller.

    l2_bridge: :class:`L2Bridge` Represents a software switch
    inside a controller in case there are more than one interface
    or virtual machines/ compute nodes

    Private Attributes
    ------------------
    _type:
        The type of the object generated. Set to Controller.
    """

    INSTANCES: ClassVar[List["Controller"]] = []
    meta: EmbeddedMetadata = Field()
    name: str = Field()
    interfaces: List[ControllerInterface] = Field()
    l2_bridge: Optional[L2Bridge] = Field(default=None)
    _type: Literal["controller"] = PrivateAttr(default="controller")

    @model_validator(mode="after")
    def check_ports_l2_bridge_are_interfaces_or_compute_nodes(self):
        interface_names = []
        compute_node_names = []
        for interface in self.interfaces:
            interface_names.append(interface.name)
            if interface.compute_nodes != []:
                for compute_node in interface.compute_nodes:
                    compute_node_names.append(compute_node.name)

        if self.l2_bridge is not None:
            for port in self.l2_bridge.ports:
                if (
                    port.node_connected not in interface_names
                    and port.node_connected not in compute_node_names
                ):
                    raise err_minor(
                        f"{port.node_connected} is not a valid"
                        "controller interface or compute node"
                    )
        return self

    def get_all_ips(self):
        """Helper function.
        Return all the IPs in the Controller
        """
        all_ips = []
        for i in self.interfaces:
            all_ips.extend(i.get_all_ips())
        return all_ips

    def get_all_macs(self):
        """Helper function.
        Return all the MAC addresses in the Controller
        """
        all_macs = []
        for i in self.interfaces:
            all_macs.extend(i.get_all_macs())
        return all_macs
