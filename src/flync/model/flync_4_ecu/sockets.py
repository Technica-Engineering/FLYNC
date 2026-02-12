from ipaddress import IPv4Address, IPv6Address
from typing import Any, ClassVar, Dict, List, Literal, Optional, Union

from pydantic import (
    Field,
    RootModel,
    StrictBool,
    ValidationError,
    field_serializer,
    field_validator,
    model_validator,
)

from flync.core.base_models import DictInstances, FLYNCBaseModel
from flync.core.datatypes.ipaddress import IPv4AddressEntry, IPv6AddressEntry
from flync.core.utils.exceptions import err_minor
from flync.model.flync_4_someip import (
    SOMEIPSDDeployment,
    SOMEIPServiceConsumer,
    SOMEIPServiceProvider,
)


class IPv4AddressEndpoint(IPv4AddressEntry):
    """
    Represents an IPv4 address endpoint for a network interface.

    Parameters
    ----------
    sockets : list of :class:`~flync.model.flync_4_ecu.sockets.SocketTCP` or \
    :class:`~flync.model.flync_4_ecu.sockets.SocketUDP`
        TCP and UDP sockets that are part of this IPv4 address endpoint.
    """

    sockets: Optional[List[Union["SocketTCP", "SocketUDP"]]] = Field(
        default_factory=list, exclude=True
    )

    @model_validator(mode="after")
    def check_if_sockets_have_the_same_ip(self):
        """
        Validate that every socket is bound to the same IPv4
        address as the one defined in the class.

        Raises:
            err_minor: If any socket's ``endpoint_address``
            differs from ``self.address``.
        """
        for socket in self.sockets:
            if str(socket.endpoint_address) != str(self.address):
                raise err_minor(
                    "Sockets must be tied to the same address "
                    "as the IPv4 endpoint."
                )

        return self


class IPv6AddressEndpoint(IPv6AddressEntry):
    """
    Represents an IPv6 address endpoint for a network interface.

    Parameters
    ----------
    sockets : list of :class:`~flync.model.flync_4_ecu.sockets.SocketTCP` or \
    :class:`~flync.model.flync_4_ecu.sockets.SocketUDP`
        TCP and UDP sockets that are part of this IPv6 address endpoint.
    """

    sockets: Optional[List[Union["SocketTCP", "SocketUDP"]]] = Field(
        default_factory=list, exclude=True
    )

    @model_validator(mode="after")
    def check_if_sockets_have_the_same_ip(self):
        """
        Validate that every socket is bound to the same IPv6
        address as the one defined in the class.

        Raises:
            err_minor: If any socket's ``endpoint_address``
            differs from ``self.address``.
        """
        for socket in self.sockets:
            if str(socket.endpoint_address) != str(self.address):
                raise err_minor(
                    "Sockets must be tied to the same address "
                    "as the IPv6 endpoint."
                )
        return self


class DeploymentUnion(RootModel):
    """
    Union type representing a deployment configuration for a socket.
    This model wraps a union of different deployment models and uses the
    ``deployment_type`` field as a discriminator to determine which specific
    deployment model is present.

    Possible types
    --------------
    :class:`~flync.model.flync_4_someip.SOMEIPServiceConsumer`
    or
    :class:`~flync.model.flync_4_someip.SOMEIPServiceProvider`
    or
    :class:`~flync.model.flync_4_someip.SOMEIPSDDeployment`

    """

    root: (
        SOMEIPServiceConsumer | SOMEIPServiceProvider | SOMEIPSDDeployment
    ) = Field(discriminator="deployment_type")


class Socket(FLYNCBaseModel):
    """
    Defines a virtual-interface socket that is bound to a specific IP
    address.

    Parameters
    ----------
    name : str
        A readable identifier for the socket.

    endpoint_address : :class:`IPv4Address` or :class:`IPv6Address`
        The IP address assigned to the socket.

    port_no : int
        The port number the socket uses for communication.

    deployments : list of :class:`DeploymentUnion`, optional
        Deployments of the socket.

    """

    name: str = Field()
    endpoint_address: IPv4Address | IPv6Address = Field()
    port_no: int = Field()
    deployments: Optional[List[DeploymentUnion]] = Field(default_factory=list)

    @field_validator("deployments", mode="before")
    def drop_invalid_deployment(cls, deployment):
        """
        Drop invalid deployments from the list of deployments.
        """
        valid_deployment = []
        idx = 0
        for dep in deployment:
            try:
                DeploymentUnion.model_validate(dep)
                valid_deployment.append(dep)
            except ValidationError as e:
                raise err_minor(
                    f"Validation error in deployment {idx} of socket "
                    f"Skipping to the next deployment - {e}"
                )
            idx = idx + 1
        return valid_deployment

    @field_serializer("endpoint_address")
    def serialize_endpoint_address(self, endpoint):
        if endpoint is not None:
            return str(endpoint).upper()


class TCPOption(DictInstances):
    """
    TCP options that can be enabled for a connection.

    Parameters
    ----------
    tcp_profile_id : int
        Unique identifier of the TCP profile.

    nagle : strict_bool
        Enable or disable Nagle algorithm.

    keepalive_enabled : bool
        Enable or disable the TCP keep-alive option.

    keepidle : int
        Seconds the connection must stay idle before the first
        keep-alive probe is sent.

    keepcount : int
        Maximum number of keep-alive probes that may be sent before the
        connection is dropped.

    keepintvl : int
        Seconds between successive keep-alive probes.

    user_timeout : int
        Maximum time in seconds that unacknowledged data may remain
        before the connection is closed.

    congestion_avoidance : str
        Congestion-avoidance algorithm to use (e.g., ``Reno``, ``cubic``,
        or ``bbr``).

    tcp_maxseg : int
        Maximum segment size for outgoing TCP packets.

    tcp_quickack : bool
        Enable or disable the “quick-ack” feature.

    tcp_syncnt : int
        Number of SYN retransmissions TCP may perform before aborting
        the connection attempt.
    """

    INSTANCES: ClassVar[Dict[Any, "TCPOption"]] = {}
    tcp_profile_id: int = Field()
    nagle: Optional[StrictBool] = Field(default=False)
    keepalive_enabled: Optional[StrictBool] = Field(default=True)
    keepidle: Optional[int] = Field(default=10)
    keepcount: Optional[int] = Field(default=10)
    keepintvl: Optional[int] = Field(default=2)
    user_timeout: Optional[int] = Field(default=28)
    congestion_avoidance: Optional[Literal["reno", "cubic", "bbr"]] = Field(
        default="reno"
    )
    tcp_maxseg: Optional[int] = Field(default=1460)
    tcp_quickack: Optional[StrictBool] = Field(default=False)
    tcp_syncnt: Optional[int] = Field(default=6)

    def get_dict_key(self):
        return self.tcp_profile_id


class UDPOption(FLYNCBaseModel):
    """
    UDP options that can be enabled for a connection.

    Parameters
    ----------
    udp_cork : bool
        Enables buffering of UDP messages before they are sent.
    """

    udp_cork: Optional[StrictBool] = Field(default=False)


class SocketTCP(Socket):
    """
    Represents a TCP socket.

    Parameters
    ----------
    protocol : Literal["tcp"]
        Transport protocol for the socket. Defaults to ``"tcp"``.
    tcp_profile : int
        The unique identifier of the TCP profile whose options
        are applied to the socket.
    """

    protocol: Literal["tcp"] = Field(default="tcp")
    tcp_profile: int = Field()

    @model_validator(mode="after")
    def check_multicast_endpoint(self):
        """
        Ensure that a socket of type *someip* does not
        specify a multicast endpoint.

        Raises:
            err_minor: If a deployment of type ``someip``
            has ``find_service_multicast``set (TCP sockets
            cannot use multicast endpoints).
        """
        for deployment in self.deployments:

            if (
                deployment.root.deployment_type == "someip_consumer"
                or deployment.root.deployment_type == "someip_provider"
            ) and deployment.root.find_service_multicast is not None:
                raise err_minor(
                    f"TCP Socket cannot have a multicast endpoint. "
                    f"Socket {self.name} "
                )
        return self

    @field_validator("tcp_profile", mode="after")
    @classmethod
    def _lookup_tcp_profile_from_id(cls, value):
        """
        Resolve the integer ``tcp_profile`` identifier to a
        registered ``TcpOption`` instance.

        Raises:
            AssertionError: If the supplied ``value`` does not
            correspond to any existing``TcpOption`` (i.e., the
            profile cannot be found in ``TcpOption.INSTANCES``).
        """
        tcp_profile_no = value

        tcp = TCPOption.INSTANCES.get((tcp_profile_no))
        assert tcp, (
            f"did not find a TCP profile matching the provided "
            f'key "{value}"'
        )
        return value


class SocketUDP(Socket):
    """
    Represents a UDP socket.

    Parameters
    ----------
    protocol : Literal["udp"]
        Transport protocol for the socket. Defaults to ``"udp"``.
    udp_options : :class:`UDPOption`, optional
        The UDP options that can be configured for this socket.
    """

    protocol: Literal["udp"] = Field(default="udp")
    udp_options: Optional[UDPOption] = Field(default=UDPOption(udp_cork=False))
