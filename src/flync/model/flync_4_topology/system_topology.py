from typing import Annotated, List, Literal, Optional

from pydantic import Field, PrivateAttr, model_serializer, model_validator

import flync.core.utils.common_validators as common_validators
from flync.core.annotations.external import External, OutputStrategy
from flync.core.base_models.base_model import FLYNCBaseModel
from flync.core.utils.exceptions import err_major
from flync.model.flync_4_ecu.port import ECUPort
from flync.model.flync_4_topology.multicast_paths import MulticastConfig


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

    type: Literal["ecu_port_to_ecu_port"] = Field(
        default="ecu_port_to_ecu_port"
    )
    id: str = Field()
    ecu1_port_name: str = Field(alias="ecu1_port")
    ecu2_port_name: str = Field(alias="ecu2_port")

    _ecu1_port: Optional[ECUPort] = PrivateAttr(default=None)
    _ecu2_port: Optional[ECUPort] = PrivateAttr(default=None)

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

    @model_validator(mode="after")
    def validate_external_connection(self):
        """
        Verify that the two ECU ports connected by this object are compatible.

        The check includes compatibility of MDI, MACSec and gPTP.

        err_major: If any of the MDI parameters are missing or do not match
                    between the two ports, or if the port roles are not
                    complementary.
        """
        if self.ecu1_port_name not in ECUPort.INSTANCES.keys():
            raise err_major(
                f"ECU port name {self.ecu1_port_name} in connection"
                f" {self.id} does not exist"
            )
        self._ecu1_port = ECUPort.INSTANCES[self.ecu1_port_name]

        if self.ecu2_port_name not in ECUPort.INSTANCES.keys():
            raise err_major(
                f"ECU port name {self.ecu2_port_name} in connection"
                f" {self.id} does not exist"
            )
        self._ecu2_port = ECUPort.INSTANCES[self.ecu2_port_name]

        # Add connected component to each other
        self.ecu1_port._connected_components.append(self.ecu2_port)
        self.ecu2_port._connected_components.append(self.ecu1_port)

        mdi_ecu1_port = self.ecu1_port.mdi_config
        mdi_ecu2_port = self.ecu2_port.mdi_config

        # If no MDI config exists, error
        if not mdi_ecu1_port or not mdi_ecu2_port:
            raise err_major(
                f"One or both ports missing MDI config: "
                f"{self.ecu1_port.ecu.name}:{self.ecu1_port_name}, "
                f"{self.ecu2_port.ecu.name}:{self.ecu2_port_name}"
            )
        # Check mdi mode
        if mdi_ecu1_port.mode != mdi_ecu2_port.mode:
            raise err_major(
                f"Incompatible MDI Mode: "
                f"{self.ecu1_port.ecu.name}:{self.ecu1_port_name} "
                f"({mdi_ecu1_port.mode}) ↔ {self.ecu2_port.ecu.name}:"
                f"{self.ecu2_port_name} ({mdi_ecu2_port.mode})"
            )
        # Check mdi speed
        if mdi_ecu1_port.speed != mdi_ecu2_port.speed:
            raise err_major(
                f"Incompatible MDI Speed: "
                f"{self.ecu1_port.ecu.name}:{self.ecu1_port_name} "
                f"({mdi_ecu1_port.speed}) ↔ {self.ecu2_port.ecu.name}:"
                f"{self.ecu2_port_name} ({mdi_ecu2_port.speed})"
            )

        # Check mdi duplex mode
        if mdi_ecu1_port.duplex != mdi_ecu2_port.duplex:
            raise err_major(
                f"Incompatible MDI Duplex Mode: "
                f"{self.ecu1_port.ecu.name}:{self.ecu1_port_name} "
                f"({mdi_ecu1_port.duplex}) ↔ {self.ecu2_port.ecu.name}:"
                f"{self.ecu2_port_name} ({mdi_ecu2_port.duplex})"
            )

        # Check mdi role (should be complementary, e.g., MASTER ↔ SLAVE)
        if mdi_ecu1_port.role == mdi_ecu2_port.role:
            raise err_major(
                f"Incompatible MDI Roles: "
                f"{self.ecu1_port.ecu.name}:{self.ecu1_port_name} "
                f"({mdi_ecu1_port.role}) ↔ {self.ecu2_port.ecu.name}:"
                f"{self.ecu2_port_name} ({mdi_ecu2_port.role})"
            )

        # Check mdi autonegotiation
        if mdi_ecu1_port.autonegotiation != mdi_ecu2_port.autonegotiation:
            raise err_major(
                f"Incompatible MDI Autonegotiation: "
                f"{self.ecu1_port.ecu.name}:{self.ecu1_port_name} "
                f"({mdi_ecu1_port.autonegotiation}) ↔ "
                f"{self.ecu2_port.ecu.name}:{self.ecu2_port_name} "
                f"({mdi_ecu2_port.autonegotiation})"
            )
        # Check mdi speed
        comp1 = self.ecu1_port.get_internal_connected_component(
            [self.ecu1_port.ecu]
        )
        comp2 = self.ecu2_port.get_internal_connected_component(
            [self.ecu2_port.ecu]
        )
        # Check timesync validity
        common_validators.validate_macsec(comp1, comp2, self.id)
        common_validators.validate_gptp(comp1, comp2, self.id)
        return self


class SystemTopology(FLYNCBaseModel):
    """
    Represents the system-wide topology consisting of external connections
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

    connections: List[ExternalConnection] = Field()


class FLYNCTopology(FLYNCBaseModel):
    """
    Represents the complete FLYNC system topology, including ECU connections
    and multicast routing configuration.

    Parameters
    ----------
    system_topology : :class:`SystemTopology`
        The system-wide external connection topology between ECUs.

    multicast_paths : \
    :class:`~flync.model.flync_4_topology.multicast_paths.MulticastConfig`, \
    optional
        Optional collection of system-wide multicast paths, defining source
        and destination host pairs for each multicast route.
    """

    system_topology: Annotated[
        SystemTopology,
        External(
            output_structure=OutputStrategy.SINGLE_FILE
            | OutputStrategy.OMMIT_ROOT
        ),
    ]
    multicast_paths: Annotated[
        Optional[MulticastConfig],
        External(
            output_structure=OutputStrategy.SINGLE_FILE
            | OutputStrategy.OMMIT_ROOT
        ),
    ] = Field(default=None)
