"""Channel-level configuration for CAN, LIN, Ethernet, and PDU definitions."""

from typing import Annotated, List, Optional, Union

from pydantic import Field, model_validator

from flync.core.annotations.external import (
    External,
    NamingStrategy,
    OutputStrategy,
)
from flync.core.base_models import FLYNCBaseModel
from flync.core.utils.exceptions import err_major
from flync.model.flync_4_bus.can_bus import CANBus
from flync.model.flync_4_bus.lin_bus import LINBus
from flync.model.flync_4_signal.pdu import (
    ContainerPDU,
    MultiplexedPDU,
    StandardPDU,
)


class FLYNCChannelConfig(FLYNCBaseModel):
    """
    Channel-level configuration grouping all buses and shared PDU definitions.

    Parameters
    ----------
    pdus : list of :class:`StandardPDU` | :class:`MultiplexedPDU`, optional
        Shared PDU definitions that may be referenced from any channel.
    can_buses : list of :class:`CANBus`, optional
        CAN and CAN FD bus configurations.
    lin_buses : list of :class:`LINBus`, optional
        LIN bus configurations.
    ethernet_pdu_containers : list of :class:`ContainerPDU`, optional
        Ethernet Container PDU definitions.
    """

    pdus: Annotated[
        Optional[
            List[
                Annotated[
                    Union[StandardPDU, MultiplexedPDU],
                    Field(discriminator="type"),
                ]
            ]
        ],
        External(
            output_structure=OutputStrategy.FOLDER,
            naming_strategy=NamingStrategy.FIXED_PATH,
            path="pdus",
        ),
    ] = Field(
        default_factory=list,
        description="Shared PDU definitions, one file per PDU.",
    )
    can_buses: Annotated[
        Optional[List[CANBus]],
        External(
            output_structure=OutputStrategy.FOLDER,
            naming_strategy=NamingStrategy.FIXED_PATH,
            path="can",
        ),
    ] = Field(
        default=None,
        description="CAN / CAN FD bus definitions, one file per bus.",
    )
    lin_buses: Annotated[
        Optional[List[LINBus]],
        External(
            output_structure=OutputStrategy.FOLDER,
            naming_strategy=NamingStrategy.FIXED_PATH,
            path="lin",
        ),
    ] = Field(
        default=None,
        description="LIN bus definitions, one file per bus.",
    )
    ethernet_pdu_containers: Annotated[
        Optional[List[ContainerPDU]],
        External(
            output_structure=OutputStrategy.FOLDER,
            naming_strategy=NamingStrategy.FIXED_PATH,
            path="ethernet_pdu_containers",
        ),
    ] = Field(
        default=None,
        description="Ethernet Container PDU definitions.",
    )

    @model_validator(mode="after")
    def validate_pdu_refs(self) -> "FLYNCChannelConfig":
        if self.can_buses:
            pdu_registry = {p.name: p for p in (self.pdus or [])}
            for bus in self.can_buses:
                unknown_refs = _collect_unknown_pdu_refs(bus, pdu_registry)
                if unknown_refs:
                    raise err_major(
                        "CANBus '{name}' references unknown PDU(s): {unknown_refs}",
                        name=bus.name,
                        unknown_refs=sorted(unknown_refs),
                    )
        return self


def _collect_unknown_pdu_refs(bus: "CANBus", pdu_registry: dict) -> "set[str]":
    """Return pdu_ref names in bus frames not present in the PDU registry."""
    unknown: set[str] = set()
    for frame in bus.frames:
        for pdu_inst in frame.packed_pdus:
            if pdu_inst.pdu_ref not in pdu_registry:
                unknown.add(pdu_inst.pdu_ref)
    return unknown
