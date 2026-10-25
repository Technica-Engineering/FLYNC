"""Defines the Application model for FLYNC including its service, CAN / J1939 frame and PDU, and IPC references."""

from typing import Annotated, List, Literal, Optional, Self, Sequence

from pydantic import Field, model_validator

from flync.core.annotations import (
    Implied,
    ImpliedStrategy,
)
from flync.core.base_models import FLYNCBaseModel
from flync.core.utils.exceptions import Category, warn

from .ipc import IPCChannelReference
from .signal_refs import AppCANFrameRef, AppCANPDURef, AppJ1939FrameRef, AppJ1939PDURef


class ServiceConsumerReference(FLYNCBaseModel):
    """
    Reference to resolve a SOME/IP Consumer Instance.

    Parameters
    ----------
    type: Literal["consumer"]
        Type of the service reference.

    service_id: int
        Service ID of the referenced service instance (> 0 and < 65535).

    instance_id: int
        Instance ID of the referenced service instance.

    major_version: int
        Major version of the referenced service instance.
    """

    type: Literal["consumer"] = Field(default="consumer", description="Type of the service reference.")
    service_id: Annotated[int, Field(gt=0, lt=0xFFFF)] = Field(description="Service ID of the referenced service instance.")
    instance_id: int = Field(description="Instance ID of the referenced service instance.")
    major_version: int = Field(description="Major version of the referenced service instance.")


class ServiceProviderReference(FLYNCBaseModel):
    """
    Reference to resolve a SOME/IP Provider Instance.

    Parameters
    ----------
    type: Literal["provider"]
        Type of the service reference.

    service_id: int
        Service ID of the referenced service instance (> 0 and < 65535).

    instance_id: int
        Instance ID of the referenced service instance.

    major_version: int
        Major version of the referenced service instance.
    """

    type: Literal["provider"] = Field(default="provider", description="Type of the service reference.")
    service_id: Annotated[int, Field(gt=0, lt=0xFFFF)] = Field(description="Service ID of the referenced service instance.")
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

    can_frame_refs: list of :class:`~flync.model.flync_4_app.signal_refs.AppCANFrameRef`
        CAN / CAN FD frames this application sends or receives.

    j1939_frame_refs: list of :class:`~flync.model.flync_4_app.signal_refs.AppJ1939FrameRef`
        J1939 frames this application sends or receives.

    can_pdu_refs: list of :class:`~flync.model.flync_4_app.signal_refs.AppCANPDURef`
        PDUs this application sends or receives within CAN / CAN FD frames.

    j1939_pdu_refs: list of :class:`~flync.model.flync_4_app.signal_refs.AppJ1939PDURef`
        PDUs this application sends or receives within J1939 frames.

    ipc_refs: list of :class:`~flync.model.flync_4_app.ipc.IPCChannelReference`
        ECU-internal IPC channels this application takes part in.
    """

    name: Annotated[str, Implied(strategy=ImpliedStrategy.FILE_NAME)] = Field(description="Name of this application.")
    service_consumer_refs: Optional[List[ServiceConsumerReference]] = Field(
        description="Reference of all Consumer Instances of this application.", default_factory=list
    )
    service_provider_refs: Optional[List[ServiceProviderReference]] = Field(
        description="Reference of all Provider Instances of this application.", default_factory=list
    )
    can_frame_refs: List[AppCANFrameRef] = Field(description="CAN / CAN FD frames this application sends or receives.", default_factory=list)
    j1939_frame_refs: List[AppJ1939FrameRef] = Field(description="J1939 frames this application sends or receives.", default_factory=list)
    can_pdu_refs: List[AppCANPDURef] = Field(description="PDUs this application sends or receives within CAN frames.", default_factory=list)
    j1939_pdu_refs: List[AppJ1939PDURef] = Field(description="PDUs this application sends or receives within J1939 frames.", default_factory=list)
    ipc_refs: List[IPCChannelReference] = Field(description="ECU-internal IPC channels this application takes part in.", default_factory=list)

    @model_validator(mode="after")
    def warn_self_consumed_instances(self) -> Self:
        """Warn when a service instance is referenced in both service_consumer_refs and service_provider_refs."""
        provided = {(ref.service_id, ref.instance_id, ref.major_version) for ref in self.service_provider_refs or []}
        for ref in self.service_consumer_refs or []:
            if (ref.service_id, ref.instance_id, ref.major_version) in provided:
                warn(
                    f"App '{self.name}' both consumes and provides the same service instance "
                    f"(service_id={ref.service_id:#06x}, instance_id={ref.instance_id}, major_version={ref.major_version}).",
                    category=Category.CONSISTENCY,
                    error_number="242",
                )
        return self

    @model_validator(mode="after")
    def warn_duplicate_signal_refs(self) -> Self:
        """Warn when the same frame, PDU or IPC channel is referenced twice in the same list."""
        ref_lists: dict[str, Sequence[FLYNCBaseModel]] = {
            "can_frame_refs": self.can_frame_refs,
            "j1939_frame_refs": self.j1939_frame_refs,
            "can_pdu_refs": self.can_pdu_refs,
            "j1939_pdu_refs": self.j1939_pdu_refs,
            "ipc_refs": self.ipc_refs,
        }
        for field_name, refs in ref_lists.items():
            seen: set[str] = set()
            for ref in refs:
                key = ref.model_dump_json()
                if key in seen:
                    warn(
                        f"App '{self.name}' lists the same reference twice in {field_name}: {key}.",
                        category=Category.UNIQUENESS,
                        error_number="412",
                    )
                seen.add(key)
        return self
