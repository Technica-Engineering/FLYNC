"""Defines the Application model for FLYNC including its service, CAN / J1939 frame and PDU, and IPC references."""

from typing import Annotated, List, Literal, Optional, Self

from pydantic import Field, model_validator

from flync.core.annotations import (
    Implied,
    ImpliedStrategy,
)
from flync.core.base_models import FLYNCBaseModel
from flync.core.utils.exceptions import Category, err_minor, warn

from .ipc import IPCChannelReference
from .signal_refs import AppCANFrameRef, AppCANPDURef, AppJ1939FrameRef, AppJ1939PDURef

#: Per reference list: a label for messages and the fields that identify the target, i.e. everything but direction / role.
_REF_TARGETS: dict[str, tuple[str, tuple[str, ...]]] = {
    "can_frame_refs": ("CAN frame", ("bus_ref", "frame_ref", "id_format")),
    "j1939_frame_refs": ("J1939 PGN", ("bus_ref", "pgn")),
    "can_pdu_refs": ("CAN PDU", ("bus_ref", "pdu_ref")),
    "j1939_pdu_refs": ("J1939 PDU", ("bus_ref", "pdu_ref")),
    "ipc_refs": ("IPC channel", ("channel_ref",)),
}


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
    def check_duplicate_refs(self) -> Self:
        """
        Check every reference list for entries that point at the same target.

        The target is the reference without its direction or role, so entries differing only in those are caught too.
        An exact duplicate only warns. A frame or PDU that is both sent and received on the same bus is an error, since a
        gateway has to use different buses. Overlapping IPC roles on one channel only warn.
        """
        for field_name, (label, target_fields) in _REF_TARGETS.items():
            seen: dict[tuple[object, ...], FLYNCBaseModel] = {}
            for ref in getattr(self, field_name) or []:
                target = tuple(getattr(ref, f) for f in target_fields)
                previous = seen.setdefault(target, ref)
                if previous is ref:
                    continue
                name = "/".join(f"{v:#x}" if isinstance(v, int) else str(v) for v in target)
                if previous == ref:
                    warn(
                        f"App '{self.name}' lists the same {label} twice in {field_name}: {name}.",
                        category=Category.UNIQUENESS,
                        error_number="412",
                    )
                elif field_name == "ipc_refs":
                    warn(
                        f"App '{self.name}' lists IPC channel '{name}' with overlapping roles "
                        f"'{previous.role}' and '{ref.role}'.",  # type: ignore[attr-defined]
                        category=Category.CONSISTENCY,
                        error_number="419",
                    )
                else:
                    raise err_minor(
                        f"App '{self.name}' both sends and receives {label} {name} in {field_name}; a gateway must use different buses.",
                        category=Category.CONSISTENCY,
                        error_number="418",
                    )
        for field_name in ("service_consumer_refs", "service_provider_refs"):
            seen_services: set[tuple[int, int, int]] = set()
            for ref in getattr(self, field_name) or []:
                key = (ref.service_id, ref.instance_id, ref.major_version)
                if key in seen_services:
                    warn(
                        f"App '{self.name}' lists the same service instance twice in {field_name} "
                        f"(service_id={ref.service_id:#06x}, instance_id={ref.instance_id}, major_version={ref.major_version}).",
                        category=Category.UNIQUENESS,
                        error_number="420",
                    )
                seen_services.add(key)
        return self
