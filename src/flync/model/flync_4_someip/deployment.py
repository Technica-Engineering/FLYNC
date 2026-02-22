"""
this module contains the neccessary datastructures
to model a SOME/IP deployment.
"""

import abc
from typing import Annotated, List, Literal, Optional

from pydantic import Field, IPvAnyAddress, field_serializer, field_validator

from flync.core.base_models import FLYNCBaseModel
from flync.core.utils.base_utils import is_ip_multicast
from flync.model.flync_4_someip.service_interface import (
    SDTimings,
    SOMEIPServiceInterface,
)

DeploymentTypes = Literal["someip", "someip_provider", "someip_consumer"]


class Layer4Endpoint(FLYNCBaseModel):
    """Layer4Endpoint Class method for Layer4 endpoint .

    Parameters
    ----------

    protocol : Literal["UDP", "TCP"]
        Protocol of the Layer4Endpoint.
        Defaults to UDP.

    port : int
        Layer4 Port.
        Must be greater than 0 and less or equal to 65535.
    """

    protocol: Literal["UDP", "TCP"] = "UDP"
    port: Annotated[int, Field(gt=0, le=65535)] = Field(
        description="the l4-port"
    )


class BaseUDPDeployment(Layer4Endpoint):
    """Base class for deploying a SOME/IP service onto a UDP-endpoint."""

    protocol: Literal["UDP"] = "UDP"


class MulticastEndpoint(BaseUDPDeployment):
    """
    MulticastEndpoint for UDP Deployments.

    Parameters
    ----------

    ip_address : IPvAnyAddress
        IP-Address of the Multicast Endpoint.
    """

    ip_address: Annotated[IPvAnyAddress, is_ip_multicast] = Field()

    @field_serializer("ip_address")
    def serialize_addresses(self, ip_address):
        if ip_address is not None:
            return str(ip_address).upper()


class MulticastSDEndpoint(MulticastEndpoint):
    """MulticastSDEndpoint

    Parameters
    ----------

    ip_ttl : int
        IP Time-to-Live.
        Must be greater or equal to 0 and less or equal to 255.
    """

    ip_ttl: Annotated[int, Field(ge=0, le=255)] = Field(
        description="IP Time-to-Live"
    )


class UDPDeployment(BaseUDPDeployment):
    """Allows deploying a SOME/IP service onto
    a UDP-endpoint (including multicast).

    Parameters
    ----------

    multicast : :class:`~MulticastEndpoint`, optional
        Multicast configuration for this endpoint.
    """

    multicast: Optional["MulticastEndpoint"] = Field(
        description="multicast configuration for this endpoint", default=None
    )


class TCPDeployment(Layer4Endpoint):
    """Base class for deploying a SOME/IP service onto a TCP-endpoint"""

    protocol: Literal["TCP"] = "TCP"


class SOMEIPSDDeployment(FLYNCBaseModel):
    """Defines the Service Discovery endpoint of SOME/IP.

    Parameters
    ----------

    deployment_type: Literal["someip_sd"]

    multicast : Optional[:class:`~MulticastSDEndpoint`]
        Multicast configuration for an SD endpoint.
    """

    deployment_type: Literal["someip_sd"] = Field(default="someip_sd")
    multicast: Optional["MulticastSDEndpoint"] = Field(
        description="multicast configuration for SD endpoint", default=None
    )


class SOMEIPServiceDeployment(abc.ABC, FLYNCBaseModel):
    """SOMEIPServiceDeployment Create a service deployment
    that will be used for provided service.

    Parameters
    ----------

    deployment_type : Literal["someip"]

    service : int
        Identifies the service.
        Must be greater than 0 and less than 0xFFFF.

    instance_id: int
        Id of the Service Instance.
        Must be greater than 0 and less than 0xFFFF.

    find_service_multicast: :class:`~MulticastEndpoint`, optional
        A multicast endpoint.

    someip_sd_timings_profile: str
        The SOME/IP timings profile_id used for the deployment.
    """

    deployment_type: DeploymentTypes
    service: int = Field(
        description="identifies the service", gt=0, lt=0xFFFF, strict=True
    )
    instance_id: Annotated[int, Field(gt=0, lt=0xFFFF)] = Field(
        description="The id of the service instance"
    )
    find_service_multicast: Optional[MulticastEndpoint] = Field(
        description="a multicast endpoint", default=None
    )
    someip_sd_timings_profile: str = Field(
        description="The SOME/IP timings profile ussed for the deployment."
    )

    @abc.abstractmethod
    def model_post_init(self, __context):
        return super().model_post_init(__context)

    @field_validator("service", mode="after")
    @classmethod
    def _lookup_service_from_id(cls, value):

        id = value

        service = SOMEIPServiceInterface.INSTANCES.get((id))
        assert service, "did not find a service definition matching"
        f"the provided key {value}"
        return service

    @field_validator("someip_sd_timings_profile", mode="after")
    @classmethod
    def _lookup_some_ip_sd_timing_profile_from_id(cls, value):

        profile_id = value
        profile_found = SDTimings.INSTANCES.get((profile_id))
        assert profile_found, f'did not find a SOME/IP SD timings profile \
            with the provided key "{value}"'
        return value

    @field_serializer("service")
    def _serialize_field_as_service(self, service: "SOMEIPServiceInterface"):
        return service.id


class SOMEIPServiceConsumer(SOMEIPServiceDeployment):
    """Defines the consumer of a SOME/IP service instance
    (like subscribing & calling methods).

    Parameters
    ----------

    deployment_type : Literal["someip_consumer"]

    major_version : int
        The major version of this service interface.
        Must be greater than 0 and less or equal 255.

    consumed_eventgroups : List[str], optional
    """

    deployment_type: Literal["someip_consumer"] = Field(
        default="someip_consumer"
    )

    major_version: Annotated[int, Field(gt=0, le=255, strict=True)] = Field(
        description="the major version of this service interface", default=0
    )

    consumed_eventgroups: Optional[List[str]] = Field(default=None)

    def model_post_init(self, __context):
        return super().model_post_init(__context)

    @field_validator("consumed_eventgroups", mode="after")
    @classmethod
    def _check_consumed_eventgroups_are_provided(cls, value, values):

        consumed_eventgroups = value
        if "service" not in values.data:
            return
        service = values.data["service"]

        if consumed_eventgroups is not None:
            consumed = set(consumed_eventgroups)
            provided = set(eg.name for eg in service.eventgroups)
            found = consumed.intersection(provided)
            assert (
                found == consumed
            ), f"Did not find eventgroups with names {consumed - found}"

        return value


class SOMEIPServiceProvider(SOMEIPServiceDeployment):
    """Defines the provider of a SOME/IP service instance
    (like offering & sending responses, events).

    Parameters
    ----------

    deployment_type : Literal["someip_provider"]

    major_version : int
        The major version of this service interface.
        Must be greater than 0 and less than 255.

    minor_version : int
        The minor version of this service interface.
        Must be greater than 0 and less than 0xFFFFFFFF.
    """

    deployment_type: Literal["someip_provider"] = Field(
        default="someip_provider"
    )

    major_version: Annotated[int, Field(gt=0, lt=255, strict=True)] = Field(
        description="the major version of this service interface"
    )

    minor_version: Annotated[int, Field(ge=0, lt=0xFFFFFFFF, strict=True)] = (
        Field(
            description="the major version of this service interface",
            default=0,
        )
    )

    def model_post_init(self, __context):
        return super().model_post_init(__context)
