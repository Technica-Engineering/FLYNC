"""Measurement points - the capture locations an instrumentation setup reads.

A measurement point taps exactly one medium and carries the ASAM CMP / TECMP interface id(s) that
capture it: the one or two ports of a point-to-point Ethernet link, an Ethernet shared-medium
segment, a CAN bus, or a LIN bus. The medium is not declared - it is whatever the point references.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated, Dict, FrozenSet, List, Literal, Self, Set

from pydantic import Field, model_validator

from flync.core.annotations.reference import Reference
from flync.core.base_models import FLYNCBaseModel
from flync.core.utils.exceptions import Category, err_major
from flync.model.flync_4_bus import CANBus, LINBus
from flync.model.flync_4_ecu import ECUPort
from flync.model.flync_4_topology.ethernet_multidrop import EthernetMultidropConnection
from flync.model.flync_4_topology.ethernet_topology import EthernetPointToPointConnection

if TYPE_CHECKING:  # `flync_model` imports this package, so the root is a type-only reference here.
    from flync.model.flync_model import FLYNCModel

PayloadType = Literal["can", "can_fd", "lin", "ethernet"]
"""The kind of traffic a measurement point captures."""

INTERFACE_ID_MAX = 0xFFFFFFFF

INTERFACE_ID_DESCRIPTION = "Interface identifier of this capture, unique across the measurement system."


@dataclass(frozen=True)
class FLYNCIndex:
    """
    The bound FLYNC model reduced to the lookup tables a measurement point resolves its references against.

    Parameters
    ----------
    ports_by_name : dict of str to :class:`~flync.model.flync_4_ecu.port.ECUPort`
        Every ECU port, keyed by name - port names are globally unique in FLYNC.
    can_buses_by_name : dict of str to :class:`~flync.model.flync_4_bus.can_bus.CANBus`
        Every CAN bus, keyed by name.
    lin_buses_by_name : dict of str to :class:`~flync.model.flync_4_bus.lin_bus.LINBus`
        Every LIN bus, keyed by name.
    segments_by_id : dict of str to :class:`~flync.model.flync_4_topology.ethernet_multidrop.EthernetMultidropConnection`
        Every Ethernet shared-medium segment, keyed by connection id.
    point_to_point_pairs : frozenset of frozensets of str
        One frozenset of the two port names per resolved point-to-point Ethernet connection.
    """

    ports_by_name: Dict[str, ECUPort]
    can_buses_by_name: Dict[str, CANBus]
    lin_buses_by_name: Dict[str, LINBus]
    segments_by_id: Dict[str, EthernetMultidropConnection]
    point_to_point_pairs: FrozenSet[FrozenSet[str]]

    @classmethod
    def from_model(cls, flync_model: "FLYNCModel") -> Self:
        """Build the lookup tables from an already-loaded, already-bound FLYNC model."""
        channels = flync_model.communication.channels if flync_model.communication is not None else None
        can_buses = channels.can_buses if channels is not None else None
        lin_buses = channels.lin_buses if channels is not None else None

        connections = flync_model.topology.ethernet_topology.connections if flync_model.topology.ethernet_topology is not None else []
        segments = {conn.id: conn for conn in connections if isinstance(conn, EthernetMultidropConnection)}
        pairs = frozenset(
            frozenset({conn.ecu1_port.name, conn.ecu2_port.name})
            for conn in connections
            if isinstance(conn, EthernetPointToPointConnection) and conn.ecu1_port is not None and conn.ecu2_port is not None
        )

        return cls(
            ports_by_name=flync_model.get_all_ecu_ports_by_name(),
            can_buses_by_name={bus.name: bus for bus in (can_buses or [])},
            lin_buses_by_name={bus.name: bus for bus in (lin_buses or [])},
            segments_by_id=segments,
            point_to_point_pairs=pairs,
        )


class MeasurementPoint(FLYNCBaseModel):
    """
    Base of every measurement point - the name a later measurement setup uses to refer to it.

    Parameters
    ----------
    name : str
        Unique name of this measurement point, unique across the measurement system.
    description : str, optional
        Human-readable purpose of this measurement point.
    type : str
        The discriminator: which kind of medium this point taps.
    """

    name: str = Field(min_length=1, description="Unique name of this measurement point, unique across the measurement system.")
    description: str | None = Field(default=None, description="Human-readable purpose of this measurement point.")
    type: str = Field()

    def interface_ids(self) -> List[int]:
        """Every CMP interface id this point carries - one per captured medium or link direction."""
        raise NotImplementedError

    def captured_payload_types(self) -> List[PayloadType]:
        """The payload types this point captures, as dictated by its medium."""
        raise NotImplementedError

    def bind(self, index: FLYNCIndex) -> None:
        """Resolve this point's references against the bound FLYNC model. Called by the root model's instrumentation pass."""
        raise NotImplementedError


class CANBusMeasurementPoint(MeasurementPoint):
    """
    A measurement point tapping one CAN bus.

    Parameters
    ----------
    type : Literal["can_bus"]
        The discriminator. Defaults to ``"can_bus"``.
    bus : str
        Name of the CAN bus this point taps.
    interface_id : int
        Interface identifier (32-bit) of this capture, unique across the measurement system.
    payload_types : list of "can" | "can_fd"
        Every payload type captured on the bus - at least one, no duplicates. A bus with
        ``fd_enabled=True`` must include ``can_fd``; a bus without it must not.
    """

    type: Literal["can_bus"] = Field("can_bus")
    bus: Annotated[str, Reference(source="_bus")] = Field(description="Name of the CAN bus this point taps.")
    interface_id: int = Field(ge=0, le=INTERFACE_ID_MAX, description=INTERFACE_ID_DESCRIPTION)
    payload_types: List[PayloadType] = Field(min_length=1, description="Every payload type captured on the bus; at least one.")

    _bus: CANBus | None = None

    @property
    def observed_bus(self) -> CANBus | None:
        """The resolved CAN bus; ``None`` until :meth:`bind` has run."""
        return self._bus

    @model_validator(mode="after")
    def validate_payload_types_distinct(self) -> Self:
        """``payload_types`` must contain no duplicates."""
        seen: Set[str] = set()
        for payload_type in self.payload_types:
            if payload_type in seen:
                raise err_major(
                    "MeasurementPoint '{name}' declares payload_type '{payload_type}' more than once",
                    name=self.name,
                    payload_type=payload_type,
                    category=Category.UNIQUENESS,
                    error_number="352",
                )
            seen.add(payload_type)
        return self

    def interface_ids(self) -> List[int]:
        """The point's single interface id."""
        return [self.interface_id]

    def captured_payload_types(self) -> List[PayloadType]:
        """The declared payload types."""
        return list(self.payload_types)

    def bind(self, index: FLYNCIndex) -> None:
        """Resolve the bus and check the declared payload types against it."""
        self._bus = index.can_buses_by_name.get(self.bus)
        if self._bus is None:
            raise err_major(
                "MeasurementPoint '{name}' taps unknown CAN bus '{bus}'",
                name=self.name,
                bus=self.bus,
                category=Category.REFERENCE,
                error_number="353",
            )
        bus_is_fd = self._bus.fd_enabled
        declares_fd = "can_fd" in self.payload_types
        if declares_fd and not bus_is_fd:
            raise err_major(
                "MeasurementPoint '{name}' declares payload_type 'can_fd' but CAN bus '{bus}' does not have fd_enabled=True",
                name=self.name,
                bus=self.bus,
                category=Category.COMPATIBILITY,
                error_number="357",
            )
        if bus_is_fd and not declares_fd:
            raise err_major(
                "MeasurementPoint '{name}' taps CAN bus '{bus}', which has fd_enabled=True, but does not declare payload_type 'can_fd'",
                name=self.name,
                bus=self.bus,
                category=Category.COMPATIBILITY,
                error_number="358",
            )


class LINBusMeasurementPoint(MeasurementPoint):
    """
    A measurement point tapping one LIN bus.

    Parameters
    ----------
    type : Literal["lin_bus"]
        The discriminator. Defaults to ``"lin_bus"``.
    bus : str
        Name of the LIN bus this point taps.
    interface_id : int
        Interface identifier (32-bit) of this capture, unique across the measurement system.
    """

    type: Literal["lin_bus"] = Field("lin_bus")
    bus: Annotated[str, Reference(source="_bus")] = Field(description="Name of the LIN bus this point taps.")
    interface_id: int = Field(ge=0, le=INTERFACE_ID_MAX, description=INTERFACE_ID_DESCRIPTION)

    _bus: LINBus | None = None

    @property
    def observed_bus(self) -> LINBus | None:
        """The resolved LIN bus; ``None`` until :meth:`bind` has run."""
        return self._bus

    def interface_ids(self) -> List[int]:
        """The point's single interface id."""
        return [self.interface_id]

    def captured_payload_types(self) -> List[PayloadType]:
        """``["lin"]`` - dictated by the medium."""
        return ["lin"]

    def bind(self, index: FLYNCIndex) -> None:
        """Resolve the bus."""
        self._bus = index.lin_buses_by_name.get(self.bus)
        if self._bus is None:
            raise err_major(
                "MeasurementPoint '{name}' taps unknown LIN bus '{bus}'",
                name=self.name,
                bus=self.bus,
                category=Category.REFERENCE,
                error_number="354",
            )


class EthernetBusMeasurementPoint(MeasurementPoint):
    """
    A measurement point tapping an Ethernet shared-medium segment (an ``ethernet_multidrop`` connection).

    Parameters
    ----------
    type : Literal["ethernet_bus"]
        The discriminator. Defaults to ``"ethernet_bus"``.
    bus : str
        Id of the Ethernet multidrop connection (segment) this point taps.
    interface_id : int
        Interface identifier (32-bit) of this capture, unique across the measurement system.
    """

    type: Literal["ethernet_bus"] = Field("ethernet_bus")
    bus: Annotated[str, Reference(source="_segment")] = Field(description="Id of the Ethernet multidrop connection (segment) this point taps.")
    interface_id: int = Field(ge=0, le=INTERFACE_ID_MAX, description=INTERFACE_ID_DESCRIPTION)

    _segment: EthernetMultidropConnection | None = None

    @property
    def observed_segment(self) -> EthernetMultidropConnection | None:
        """The resolved segment; ``None`` until :meth:`bind` has run."""
        return self._segment

    def interface_ids(self) -> List[int]:
        """The point's single interface id."""
        return [self.interface_id]

    def captured_payload_types(self) -> List[PayloadType]:
        """``["ethernet"]`` - dictated by the medium."""
        return ["ethernet"]

    def bind(self, index: FLYNCIndex) -> None:
        """Resolve the segment by connection id."""
        self._segment = index.segments_by_id.get(self.bus)
        if self._segment is None:
            raise err_major(
                "MeasurementPoint '{name}' taps unknown Ethernet segment '{bus}' - no ethernet_multidrop connection carries that id",
                name=self.name,
                bus=self.bus,
                category=Category.REFERENCE,
                error_number="355",
            )


class PortCapture(FLYNCBaseModel):
    """
    One end of a point-to-point Ethernet link and the interface id capturing the frames this port transmits.

    Parameters
    ----------
    ecu_port : str
        Name of the ECU port at this end of the link. Port names are globally unique in FLYNC.
    interface_id : int
        Interface identifier (32-bit) for the frames leaving this port, unique across the measurement system.
    """

    ecu_port: Annotated[str, Reference(source="_port")] = Field(description="Name of the ECU port at this end of the link.")
    interface_id: int = Field(
        ge=0, le=INTERFACE_ID_MAX, description="Interface identifier for the frames leaving this port, unique across the measurement system."
    )

    _port: ECUPort | None = None

    @property
    def port(self) -> ECUPort | None:
        """The resolved ECU port; ``None`` until :meth:`EthernetPortsMeasurementPoint.bind` has run."""
        return self._port


class EthernetPortsMeasurementPoint(MeasurementPoint):
    """
    A measurement point tapping one or two ECU ports of a point-to-point Ethernet link.

    Two ports must be the two ends of the same ``ecu_port_to_ecu_port`` connection - the point then
    carries one interface id per direction, keyed by the transmitting port.

    Parameters
    ----------
    type : Literal["ethernet_ports"]
        The discriminator. Defaults to ``"ethernet_ports"``.
    ports : list of :class:`PortCapture`
        One or two port captures - two for a full-duplex link tapped from both sides, one for a
        single direction.
    """

    type: Literal["ethernet_ports"] = Field("ethernet_ports")
    ports: List[PortCapture] = Field(min_length=1, max_length=2, description="One or two port captures of a point-to-point Ethernet link.")

    @model_validator(mode="after")
    def validate_ports_distinct(self) -> Self:
        """A port is the end of exactly one link - it cannot appear twice in one measurement point."""
        seen: Set[str] = set()
        for capture in self.ports:
            if capture.ecu_port in seen:
                raise err_major(
                    "MeasurementPoint '{name}' captures port '{port}' more than once",
                    name=self.name,
                    port=capture.ecu_port,
                    category=Category.UNIQUENESS,
                    error_number="360",
                )
            seen.add(capture.ecu_port)
        return self

    def interface_ids(self) -> List[int]:
        """One interface id per captured port."""
        return [capture.interface_id for capture in self.ports]

    def captured_payload_types(self) -> List[PayloadType]:
        """``["ethernet"]`` - dictated by the medium."""
        return ["ethernet"]

    def bind(self, index: FLYNCIndex) -> None:
        """Resolve every port; two ports must be the ends of one point-to-point connection."""
        for capture in self.ports:
            capture._port = index.ports_by_name.get(capture.ecu_port)
            if capture._port is None:
                raise err_major(
                    "MeasurementPoint '{name}' taps unknown ECU port '{port}'",
                    name=self.name,
                    port=capture.ecu_port,
                    category=Category.REFERENCE,
                    error_number="356",
                )

        if len(self.ports) == 2:
            port_names = frozenset(capture.ecu_port for capture in self.ports)
            if port_names not in index.point_to_point_pairs:
                raise err_major(
                    "MeasurementPoint '{name}' taps ports '{port1}' and '{port2}', which are not the two ends of one "
                    "point-to-point Ethernet connection - wire them up, tap one port, or tap their segment with an ethernet_bus point",
                    name=self.name,
                    port1=self.ports[0].ecu_port,
                    port2=self.ports[1].ecu_port,
                    category=Category.CONSISTENCY,
                    error_number="359",
                )


#: The four kinds of measurement point, discriminated by ``type``.
MeasurementPointType = Annotated[
    CANBusMeasurementPoint | EthernetBusMeasurementPoint | EthernetPortsMeasurementPoint | LINBusMeasurementPoint,
    Field(discriminator="type"),
]


def validate_measurement_points_local(measurement_points: List[MeasurementPointType] | None) -> None:
    """FLYNC-independent structural rules over a workspace's instrumentation list.

    Runs at parse time, before any FLYNC model is bound: every CMP interface id (flattened across
    all points, port captures included) and every measurement point ``name`` must be unique.

    Parameters
    ----------
    measurement_points : list of :class:`MeasurementPointType`
        The measurement points collected from ``flync_model.instrumentation.measurement_points``.
    """
    validate_unique_interface_ids(measurement_points)
    validate_unique_names(measurement_points)


def validate_unique_interface_ids(measurement_points: List[MeasurementPointType] | None) -> None:
    """Raise ``err_major`` if any CMP interface id repeats across every measurement point and port capture."""
    seen: Set[int] = set()
    for point in measurement_points or []:
        for interface_id in point.interface_ids():
            if interface_id in seen:
                raise err_major(
                    "Duplicate interface_id {interface_id} in MeasurementPoint '{name}'",
                    name=point.name,
                    interface_id=interface_id,
                    category=Category.UNIQUENESS,
                    error_number="350",
                )
            seen.add(interface_id)


def validate_unique_names(measurement_points: List[MeasurementPointType] | None) -> None:
    """Raise ``err_major`` if any measurement point ``name`` repeats - it is the key a later setup uses to refer to one."""
    seen: Set[str] = set()
    for point in measurement_points or []:
        if point.name in seen:
            raise err_major(
                "Duplicate MeasurementPoint name '{name}'",
                name=point.name,
                category=Category.UNIQUENESS,
                error_number="351",
            )
        seen.add(point.name)


def bind_measurement_points(measurement_points: List[MeasurementPointType] | None, flync_model: "FLYNCModel") -> None:
    """Resolve every measurement point's references against an already-loaded FLYNC model.

    Bundled into one call so a single ``FLYNCIndex`` is built and reused across all points; the
    references a point resolves are identical to the ones :meth:`MeasurementPoint.bind` offers, only
    the lookup tables are shared.

    Parameters
    ----------
    measurement_points : list of :class:`MeasurementPointType`
        The measurement points to resolve, as collected from
        ``flync_model.instrumentation.measurement_points``.
    flync_model : flync.model.flync_model.FLYNCModel
        An already-loaded and already-validated FLYNC model, e.g.
        ``FLYNCWorkspace.load_workspace(...).flync_model``. Its buses and topology must be bound as
        well - run after the model's own binding passes.
    """
    index = FLYNCIndex.from_model(flync_model)
    for point in measurement_points or []:
        point.bind(index)
