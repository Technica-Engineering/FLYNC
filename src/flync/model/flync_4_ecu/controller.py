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
    Represents a virtual interface on a controller.

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


class ControllerInterface(NamedDictInstances):
    """
    Represents a physical controller interface including virtual
    interfaces and optional PTP configuration.

    Parameters
    ----------
    name : str
        Interface name.

    mac_address : :class:`MacAddress`
        MAC address in standard notation.

    mii_config : :class:`~flync.model.flync_4_ecu.phy.MII` or \
    :class:`~flync.model.flync_4_ecu.phy.RMII` or \
    :class:`~flync.model.flync_4_ecu.phy.SGMII` or \
    :class:`~flync.model.flync_4_ecu.phy.RGMII`, optional
        Media-independent interface configuration.

    virtual_interfaces : list of :class:`VirtualControllerInterface`
        Virtual interfaces configured on top of the physical controller
        interface.

    ptp_config : :class:`~flync.model.flync_4_tsn.PTPConfig`, \
    optional
        Precision Time Protocol configuration.

    macsec_config : \
    :class:`~flync.model.flync_4_security.MACsecConfig`, optional
        MACsec configuration.

    firewall : :class:`~flync.model.flync_4_security.Firewall`, \
    optional
        Firewall configuration for the interface.

    htb : :class:`~flync.model.flync_4_tsn.HTBInstance`, optional
        Hierarchical Token Bucket (HTB) configuration.

    ingress_streams : list of :class:`~flync.model.flync_4_tsn.Stream`, \
    optional
        Stream-based IEEE 802.1Qci configuration.

    traffic_classes : list of \
    :class:`~flync.model.flync_4_tsn.TrafficClass`, optional
        Traffic class definitions and traffic shaping configuration
        applied to egress queues.

    Private Attributes
    ------------------

    _connected_component:
        The switch port, controller interface or ecu port connected
        to the controller interface. This attribute
        is managed internally and is not part of the public API.
    _type:
        The type of the object generated. Set to controller_interface.
    """

    INSTANCES: ClassVar[Dict[str, "ControllerInterface"]] = {}
    name: str = Field()
    mac_address: MacAddress = Field()
    mii_config: Optional[MII | RMII | SGMII | RGMII | XFI] = Field(
        default=None, discriminator="type"
    )
    virtual_interfaces: List[VirtualControllerInterface] = Field(
        ..., min_length=1
    )
    ptp_config: Optional[PTPConfig] = Field(default=None)
    macsec_config: Optional[MACsecConfig] = Field(default=None)
    firewall: Optional[Firewall] = Field(default=None)
    htb: Optional[HTBInstance] = Field(default=None)
    ingress_streams: Annotated[
        Optional[List[Stream]],
        BeforeValidator(common_validators.none_to_empty_list),
    ] = Field(default=[])
    traffic_classes: Annotated[
        Optional[List[TrafficClass]],
        AfterValidator(common_validators.validate_traffic_classes),
        BeforeValidator(common_validators.none_to_empty_list),
    ] = Field(default_factory=list)
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
            "Fatal Error: " "The interface is not a part of any controller"
        )

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


    Private Attributes
    ------------------
    _type:
        The type of the object generated. Set to Controller.
    """

    INSTANCES: ClassVar[List["Controller"]] = []
    meta: EmbeddedMetadata = Field()
    name: str = Field()
    interfaces: List[ControllerInterface] = Field()
    _type: Literal["controller"] = PrivateAttr(default="controller")

    def get_all_ips(self):
        """Helper function.
        Return all the IPs in the Controller
        """
        all_ips = []
        for i in self.interfaces:
            for vi in i.virtual_interfaces:
                for address in vi.addresses:
                    all_ips.append(address.address)
        return all_ips
