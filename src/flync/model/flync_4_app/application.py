"""Defines the Application model for FLYNC including its service provider and consumer references."""

from typing import Annotated, List, Literal, Optional

from pydantic import Field

from flync.core.annotations import (
    Implied,
    ImpliedStrategy,
)
from flync.core.base_models import FLYNCBaseModel


class ServiceConsumerReference(FLYNCBaseModel):
    """
    Reference to resolve a SOME/IP Consumer Instance.

    Parameters
    ----------
    type: Literal["consumer"]
        Type of the service reference.

    service_name: str
        Name of the referenced service instance.

    instance_id: int
        Instance ID of the referenced service instance.

    major_version: int
        Major version of the referenced service instance.
    """

    type: Literal["consumer"] = Field(default="consumer", description="Type of the service reference.")
    service_name: str = Field(default="consumer", description="Name of the referenced service instance.")
    instance_id: int = Field(description="Instance ID of the referenced service instance.")
    major_version: int = Field(description="Major version of the referenced service instance.")


class ServiceProviderReference(FLYNCBaseModel):
    """
    Reference to resolve a SOME/IP Provider Instance.

    Parameters
    ----------
    type: Literal["provider"]
        Type of the service reference.

    service_name: str
        Name of the referenced service instance.

    instance_id: int
        Instance ID of the referenced service instance.

    major_version: int
        Major version of the referenced service instance.

    minor_version: int
        Minor version of the referenced service instance.
    """

    type: Literal["provider"] = Field(default="provider", description="Type of the service reference.")
    service_name: str = Field(default="consumer", description="Name of the referenced service instance.")
    instance_id: int = Field(description="Instance ID of the referenced service instance.")
    major_version: int = Field(description="Major version of the referenced service instance.")


class App(FLYNCBaseModel):
    """
    Definition of an application in the system.

    Parameters
    ----------
    name: str
        Name of this application. Implied from filename.

    service_consumer_refs: list of :class:`~ServiceConsumerReference`
        Reference of all Consumer Instances of this application.

    service_provider_refs: list of :class:`~ServiceProviderReference`
        Reference of all Provider Instances of this application.
    """

    name: Annotated[str, Implied(strategy=ImpliedStrategy.FILE_NAME)] = Field(description="Name of this application.")
    service_consumer_refs: Optional[List[ServiceConsumerReference]] = Field(
        description="Reference of all Consumer Instances of this application.", default_factory=list
    )
    service_provider_refs: Optional[List[ServiceProviderReference]] = Field(
        description="Reference of all Provider Instances of this application.", default_factory=list
    )
