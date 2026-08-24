"""
Define and validate ECU connections
within the system.
"""

from typing import Annotated, List, Literal, Optional

from pydantic import Field, model_serializer, model_validator

from flync.core.annotations.external import External, OutputStrategy
from flync.core.annotations.reference import Reference
from flync.core.base_models import FLYNCBaseModel
from flync.core.utils.exceptions import Category, err_major, warn
from flync.core.utils.validators_connection_compatibility import validate_gptp, validate_macsec
from flync.model.flync_4_ecu.port import ECUPort
from flync.model.flync_4_topology.bus_topology import CANBusTopology, LINBusTopology


class ExternalConnection(FLYNCBaseModel):
    """
    Represents a connection between two ECU (Electronic Control Unit)
    ports.

    This model captures a directed or undirected link between two
    named ports on separate ECUs.

    Parameters
    ----------
    type : Literal["ecu_port_to_ecu_port"]
        The type of the connection.
        Defaults to "ecu_port_to_ecu_port" for schema identification.

    id : str
        A unique identifier for the external connection.

    ecu1_port_name : str
        The name of the first ECU port (alias: "ecu1_port").

    ecu2_port_name : str
        The name of the second ECU port (alias: "ecu2_port").

    Private Attributes
    ------------------
    _ecu1_port : :class:`~flync.model.flync_4_ecu.port.ECUPort`
        Runtime reference to the first ECUPort object.

    _ecu2_port : :class:`~flync.model.flync_4_ecu.port.ECUPort`
        Runtime reference to the second ECUPort object.
    """

    type: Literal["ecu_port_to_ecu_port"] = Field(default="ecu_port_to_ecu_port")
    id: str = Field()
    ecu1_port_name: Annotated[str, Reference(source="_ecu1_port")] = Field(alias="ecu1_port")
    ecu2_port_name: Annotated[str, Reference(source="_ecu2_port")] = Field(alias="ecu2_port")

    _ecu1_port: Optional[ECUPort] = None
    _ecu2_port: Optional[ECUPort] = None

    @property
    def ecu1_port(self) -> Optional[ECUPort]:
        return self._ecu1_port

    @property
    def ecu2_port(self) -> Optional[ECUPort]:
        return self._ecu2_port

    @model_serializer
    def serialize(self):
        return {
            "type": self.type,
            "id": self.id,
            "ecu1_port": self.ecu1_port_name,
            "ecu2_port": self.ecu2_port_name,
        }

    def bind(self, ports_by_name: dict) -> None:
        """Resolve port references and run all MDI/MACsec/gPTP compatibility checks."""
        port1 = ports_by_name.get(self.ecu1_port_name)
        if port1 is None:
            raise err_major(
                f"ECU port name {self.ecu1_port_name} in connection {self.id} of system topology does not exist",
                category=Category.REFERENCE,
                error_number="142",
            )
        port2 = ports_by_name.get(self.ecu2_port_name)
        if port2 is None:
            raise err_major(
                f"ECU port name {self.ecu2_port_name} in connection {self.id} of system topology does not exist",
                category=Category.REFERENCE,
                error_number="143",
            )

        self._ecu1_port = port1
        self._ecu2_port = port2

        # Add connected component to each other
        port1._connected_components.append(port2)
        port2._connected_components.append(port1)

        mdi_ecu1_port = port1.mdi_config
        mdi_ecu2_port = port2.mdi_config

        if not mdi_ecu1_port or not mdi_ecu2_port:
            raise err_major(
                f"One or both ports missing MDI config: {port1.ecu.name}:{self.ecu1_port_name}, {port2.ecu.name}:{self.ecu2_port_name}",
                category=Category.COMPATIBILITY,
                error_number="144",
            )
        if mdi_ecu1_port.mode != mdi_ecu2_port.mode:
            raise err_major(
                f"Incompatible MDI Mode: "
                f"{port1.ecu.name}:{self.ecu1_port_name} "
                f"({mdi_ecu1_port.mode}) ↔ {port2.ecu.name}:"
                f"{self.ecu2_port_name} ({mdi_ecu2_port.mode})",
                category=Category.COMPATIBILITY,
                error_number="145",
            )
        if mdi_ecu1_port.speed != mdi_ecu2_port.speed:
            raise err_major(
                f"Incompatible MDI Speed: "
                f"{port1.ecu.name}:{self.ecu1_port_name} "
                f"({mdi_ecu1_port.speed}) ↔ {port2.ecu.name}:"
                f"{self.ecu2_port_name} ({mdi_ecu2_port.speed})",
                category=Category.COMPATIBILITY,
                error_number="146",
            )
        if mdi_ecu1_port.duplex != mdi_ecu2_port.duplex:
            raise err_major(
                f"Incompatible MDI Duplex Mode: "
                f"{port1.ecu.name}:{self.ecu1_port_name} "
                f"({mdi_ecu1_port.duplex}) ↔ {port2.ecu.name}:"
                f"{self.ecu2_port_name} ({mdi_ecu2_port.duplex})",
                category=Category.COMPATIBILITY,
                error_number="147",
            )
        if mdi_ecu1_port.role == mdi_ecu2_port.role:
            raise err_major(
                f"Incompatible MDI Roles: "
                f"{port1.ecu.name}:{self.ecu1_port_name} "
                f"({mdi_ecu1_port.role}) ↔ {port2.ecu.name}:"
                f"{self.ecu2_port_name} ({mdi_ecu2_port.role})",
                category=Category.COMPATIBILITY,
                error_number="148",
            )
        if mdi_ecu1_port.autonegotiation != mdi_ecu2_port.autonegotiation:
            raise err_major(
                f"Incompatible MDI Autonegotiation: "
                f"{port1.ecu.name}:{self.ecu1_port_name} "
                f"({mdi_ecu1_port.autonegotiation}) ↔ "
                f"{port2.ecu.name}:{self.ecu2_port_name} "
                f"({mdi_ecu2_port.autonegotiation})",
                category=Category.COMPATIBILITY,
                error_number="149",
            )
        comp1 = port1.get_internal_connected_component([port1.ecu])
        comp2 = port2.get_internal_connected_component([port2.ecu])
        validate_macsec(comp1, comp2, self.id)
        validate_gptp(comp1, comp2, self.id)


class EthernetTopology(FLYNCBaseModel):
    """
    Represents the system-wide ethernet topology consisting of external connections
    between ECUs.

    Parameters
    ----------
    connections : list of :class:`ExternalConnection`
        A list of ExternalConnection instances that define the links
        between ECU ports.

    Private Attributes
    ------------------
    _flync_model : :class:`~flync.model.flync_model.FLYNCModel`
        Internal reference to the FLYNC model that owns this topology.
        Managed internally and not part of the public API.
    """

    connections: List[ExternalConnection] = Field(examples=[[]])

    def validate_no_unconnected_ports(self, all_ports: List[ECUPort]) -> None:
        """Warn for every ECU port that has no counterpart in the system topology's external connections."""

        for port in all_ports:
            if not any(c.type == "ecu_port" for c in port.connected_components):
                assert port.ecu is not None
                warn(
                    f"ECU port '{port.name}' (ECU: '{port.ecu.name}') is not connected in the system topology.",
                    category=Category.STRUCTURAL,
                    error_number="214",
                )


class FLYNCTopology(FLYNCBaseModel):
    """
    Represents the complete FLYNC system topology, including ECU connections
    and multicast routing configuration.

    Parameters
    ----------
    ethernet_topology : :class:`EthernetTopology`, optional
        The system-wide ethernet topology between external ports of ECUs. Optional: a workspace with no ECU-to-ECU
        Ethernet wiring (or none yet authored) does not need one, but system-wide Ethernet features (e.g. multicast
        across multiple Ethernet ECUs) require it.

    can_bus_topology : list of :class:`~flync.model.flync_4_topology.bus_topology.CANBusTopology`
        System-wide CAN bus attachment topology. Runtime-derived from CAN bus definitions and ECU CAN interfaces;
        never authored in YAML.

    lin_bus_topology : list of :class:`~flync.model.flync_4_topology.bus_topology.LINBusTopology`
        System-wide LIN bus attachment topology. Runtime-derived from LIN bus definitions and ECU LIN interfaces;
        never authored in YAML.
    """

    ethernet_topology: Annotated[
        Optional[EthernetTopology],
        External(output_structure=OutputStrategy.SINGLE_FILE | OutputStrategy.OMMIT_ROOT),
    ] = Field(alias="system_topology", default=None)
    can_bus_topology: List[CANBusTopology] = Field(default_factory=list, exclude=True)
    lin_bus_topology: List[LINBusTopology] = Field(default_factory=list, exclude=True)

    @model_validator(mode="before")
    def warn_deprecated(cls, data):
        if isinstance(data, dict) and "system_topology" in data:
            warn(
                "The 'system_topology' attribute is deprecated and will be removed in a future release. Please use 'ethernet_topology' instead.",
                category=Category.LIFECYCLE,
                error_number="229",
            )
        return data
