"""Measurement Point - a measurement point declared in a MeasurementSystem.

``observes`` and ``payload_types`` are lists because one interface may cover several elements on
one connector, e.g. an FD-enabled CAN bus declaring ``[can, can_fd]``, or a connector carrying
several VLANs.
"""

from typing import Annotated, Dict, List, Literal, Optional, Self, Set, Tuple, Union

from pydantic import Field, PrivateAttr, model_validator

from flync.core.annotations.reference import Reference
from flync.core.base_models import FLYNCBaseModel
from flync.core.utils.exceptions import Category, err_major
from flync.model.flync_4_bus import CANBus, LINBus
from flync.model.flync_4_ecu import EthernetInterface, VirtualControllerInterface

ObservedElement = Union[CANBus, LINBus, EthernetInterface, VirtualControllerInterface]

PayloadType = Literal["can", "can_fd", "lin", "ethernet"]
"""The kind of traffic a measurement point produces."""


def _medium_for_element(element: object) -> str:
    """The medium of a resolved FLYNC element; raises on anything not in ``ObservedElement``."""
    if isinstance(element, CANBus):
        return "can"
    if isinstance(element, LINBus):
        return "lin"
    if isinstance(element, (EthernetInterface, VirtualControllerInterface)):
        return "ethernet"
    raise AssertionError(f"unhandled ObservedElement type: {type(element).__name__}")


# Which payload_types are legal for an observed element of each medium.
_PAYLOAD_TYPES_FOR_MEDIUM: Dict[str, Tuple[str, ...]] = {
    "can": ("can", "can_fd"),
    "lin": ("lin",),
    "ethernet": ("ethernet",),
}


class MeasurementPoint(FLYNCBaseModel):
    """
    A measurement point declared in a :class:`~flync.model.flync_4_measurements.measurement_system.MeasurementSystem`,
    identified by one ``interface_id`` and observing one or more real FLYNC topology elements.

    Parameters
    ----------
    name : str
        Unique name of this measurement point, unique across the measurement system - the key later
        measurement setups (e.g. loggers) use to refer to it.
    interface_id : int
        Interface identifier (32-bit) of this measurement point, unique across the measurement system.
    description : str, optional
        Human-readable purpose of this measurement point.
    payload_types : list of "can" | "can_fd" | "lin" | "ethernet"
        Every payload type this interface produces - at least one, no duplicates.
    observes : list of str
        Names of the real FLYNC elements captured by this interface - CAN/LIN buses, physical
        Ethernet interfaces or VLAN sub-interfaces - resolved at bind time. At least one is
        required, and all must share one medium.

    Private Attributes
    ------------------
    _observed : list of CANBus | LINBus | EthernetInterface | VirtualControllerInterface
        The resolved FLYNC elements, populated by :meth:`bind`.
    """

    name: str = Field(description="Unique name of this measurement point, unique across the measurement system.")
    interface_id: int = Field(
        ge=0, le=4294967295, description="Interface identifier of this measurement point, unique across the measurement system."
    )
    description: Optional[str] = Field(default=None, description="Human-readable purpose of this measurement point.")
    payload_types: List[PayloadType] = Field(min_length=1, description="Every payload type this interface produces; at least one.")
    observes: Annotated[List[str], Reference(source="_observed")] = Field(
        min_length=1, description="Names of the real FLYNC elements captured by this interface."
    )

    _observed: List[ObservedElement] = PrivateAttr(default_factory=list)

    @property
    def observed(self) -> List[ObservedElement]:
        """The resolved FLYNC elements; empty until :meth:`bind` has run."""
        return self._observed

    @model_validator(mode="after")
    def validate_payload_types_distinct(self) -> Self:
        """``payload_types`` must contain no duplicates."""
        seen: Set[str] = set()
        for payload_type in self.payload_types:
            if payload_type in seen:
                raise err_major(
                    "MeasurementPoint (interface_id={interface_id}) declares payload_type '{payload_type}' more than once",
                    interface_id=self.interface_id,
                    payload_type=payload_type,
                    category=Category.UNIQUENESS,
                    error_number="340",
                )
            seen.add(payload_type)
        return self

    def bind(
        self,
        buses_by_name: Dict[str, Union[CANBus, LINBus]],
        ethernet_interfaces_by_name: Dict[str, EthernetInterface],
        virtual_interfaces_by_name: Dict[str, VirtualControllerInterface],
        *,
        ambiguous_virtual_interface_names: Optional[Set[str]] = None,
    ) -> None:
        """
        Resolve every ``observes`` entry against an already-loaded FLYNC model and check the
        resolved elements against ``payload_types`` and against each other.
        """
        resolved: List[ObservedElement] = []
        media: Set[str] = set()
        for ref in self.observes:
            element = self._resolve_one(
                ref,
                buses_by_name,
                ethernet_interfaces_by_name,
                virtual_interfaces_by_name,
                ambiguous_virtual_interface_names=ambiguous_virtual_interface_names,
            )
            medium = _medium_for_element(element)
            self._validate_payload_types_for_element(element, medium, ref=ref)
            resolved.append(element)
            media.add(medium)

        if len(media) > 1:
            raise err_major(
                "MeasurementPoint (interface_id={interface_id}) observes elements of more than one medium "
                "({media}) - everything one interface observes must share a medium",
                interface_id=self.interface_id,
                media=", ".join(sorted(media)),
                category=Category.CONSISTENCY,
                error_number="341",
            )

        self._observed = resolved

    def _resolve_one(
        self,
        ref: str,
        buses_by_name: Dict[str, Union[CANBus, LINBus]],
        ethernet_interfaces_by_name: Dict[str, EthernetInterface],
        virtual_interfaces_by_name: Dict[str, VirtualControllerInterface],
        *,
        ambiguous_virtual_interface_names: Optional[Set[str]],
    ) -> ObservedElement:
        """Resolve one ``observes`` entry against the combined bus / Ethernet / VLAN namespace
        ."""
        bus = buses_by_name.get(ref)
        physical = ethernet_interfaces_by_name.get(ref)
        virtual = virtual_interfaces_by_name.get(ref)
        matches = [candidate for candidate in (bus, physical, virtual) if candidate is not None]
        if len(matches) > 1:
            raise err_major(
                "MeasurementPoint (interface_id={interface_id}) observes '{ref}', which is ambiguous - it "
                "matches more than one FLYNC element (bus, physical Ethernet interface, or VLAN sub-interface)",
                interface_id=self.interface_id,
                ref=ref,
                category=Category.REFERENCE,
                error_number="342",
            )
        if matches:
            return matches[0]
        if ref in (ambiguous_virtual_interface_names or set()):
            raise err_major(
                "MeasurementPoint (interface_id={interface_id}) observes '{ref}', which is ambiguous - more "
                "than one VLAN sub-interface in the FLYNC model carries that name. Rename one of them in the "
                "FLYNC model",
                interface_id=self.interface_id,
                ref=ref,
                category=Category.REFERENCE,
                error_number="343",
            )
        raise err_major(
            "MeasurementPoint (interface_id={interface_id}) observes unknown FLYNC element '{ref}' - no "
            "CAN/LIN bus, Ethernet interface or VLAN sub-interface carries that name",
            interface_id=self.interface_id,
            ref=ref,
            category=Category.REFERENCE,
            error_number="344",
        )

    def _validate_payload_types_for_element(self, element: ObservedElement, medium: str, *, ref: str) -> None:
        """The resolved element's medium must be covered by ``payload_types``, and an
        interface must declare ``can_fd`` for an FD-enabled bus and only for one."""
        legal = _PAYLOAD_TYPES_FOR_MEDIUM[medium]
        covered = [payload_type for payload_type in self.payload_types if payload_type in legal]
        if not covered:
            raise err_major(
                "MeasurementPoint (interface_id={interface_id}) observes '{ref}' (a {kind}), but declares no "
                "payload_type able to carry it - declared: {declared}, valid for this element: {legal}",
                interface_id=self.interface_id,
                ref=ref,
                kind=type(element).__name__,
                declared=", ".join(self.payload_types),
                legal=", ".join(legal),
                category=Category.COMPATIBILITY,
                error_number="345",
            )
        if not isinstance(element, CANBus):
            return
        bus_is_fd = bool(getattr(element, "fd_enabled", False))
        declares_fd = "can_fd" in self.payload_types
        if bus_is_fd and not declares_fd:
            raise err_major(
                "MeasurementPoint (interface_id={interface_id}) observes CAN bus '{ref}', which has "
                "fd_enabled=True, but does not declare payload_type 'can_fd'",
                interface_id=self.interface_id,
                ref=ref,
                category=Category.COMPATIBILITY,
                error_number="346",
            )
        if declares_fd and not bus_is_fd:
            raise err_major(
                "MeasurementPoint (interface_id={interface_id}) declares payload_type 'can_fd' but bus '{ref}' does not have fd_enabled=True",
                interface_id=self.interface_id,
                ref=ref,
                category=Category.COMPATIBILITY,
                error_number="347",
            )
