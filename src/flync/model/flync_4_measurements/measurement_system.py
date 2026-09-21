"""
Measurement System - root model of the measurement and logging overlay.
"""

from typing import TYPE_CHECKING, Annotated, List, Optional, Self, Set

from pydantic import Field, model_validator

from flync.core.annotations import External, NamingStrategy, OutputStrategy
from flync.core.base_models import FLYNCBaseModel
from flync.core.utils.exceptions import Category, err_major
from flync.model.flync_4_measurements.flync_model_index import (
    collect_buses_by_name,
    collect_ethernet_interfaces_by_name,
    collect_virtual_interfaces,
)
from flync.model.flync_4_measurements.measurement_point import MeasurementPoint

if TYPE_CHECKING:  # `flync_model` imports this package, so the root is a type-only reference here.
    from flync.model.flync_model import FLYNCModel


class MeasurementSystem(FLYNCBaseModel):
    """
    Root of a measurement/logging configuration overlaid on a FLYNC network topology.

    Parameters
    ----------
    measurement_points : list of :class:`~flync.model.flync_4_measurements.measurement_point.MeasurementPoint`, optional
        The measurement points declared in this measurement system.
    """

    measurement_points: Annotated[
        Optional[List[MeasurementPoint]],
        External(
            output_structure=OutputStrategy.SINGLE_FILE,
            naming_strategy=NamingStrategy.FIELD_NAME,
        ),
    ] = Field(default_factory=list, description="The measurement points declared in this measurement system.")

    @model_validator(mode="after")
    def validate_local(self) -> Self:
        """FLYNC-independent structural validation and reference resolution."""
        self._validate_unique_interface_ids()
        self._validate_unique_interface_names()
        return self

    # --- Uniqueness rules -------------------------------------------------------------------------

    def _validate_unique_interface_ids(self) -> None:
        """``interface_id`` unique across every measurement point in the measurement system."""
        seen: Set[int] = set()
        for interface in self.measurement_points or []:
            if interface.interface_id in seen:
                raise err_major(
                    "Duplicate MeasurementPoint interface_id {interface_id}",
                    interface_id=interface.interface_id,
                    category=Category.UNIQUENESS,
                    error_number="348",
                )
            seen.add(interface.interface_id)

    def _validate_unique_interface_names(self) -> None:
        """``name`` unique across every measurement point in the measurement system - it is the key a
        later measurement setup uses to refer to one."""
        seen: Set[str] = set()
        for interface in self.measurement_points or []:
            if interface.name in seen:
                raise err_major(
                    "Duplicate MeasurementPoint name '{name}'",
                    name=interface.name,
                    category=Category.UNIQUENESS,
                    error_number="349",
                )
            seen.add(interface.name)

    # --- FLYNC binding ----------------------------------------------------------------------------

    def bind(self, flync_model: "FLYNCModel") -> None:
        """
        Resolve every FLYNC-dependent reference against an already-loaded FLYNC model.

        Resolves each :class:`~flync.model.flync_4_measurements.measurement_point.MeasurementPoint`'s ``observes``
        entries against the bound model. Raises on the first failure.

        Parameters
        ----------
        flync_model : flync.model.flync_model.FLYNCModel
            An already-loaded and already-validated FLYNC model, e.g.
            ``FLYNCWorkspace.load_workspace(...).flync_model``.
        """
        buses_by_name = collect_buses_by_name(flync_model)
        ethernet_interfaces_by_name = collect_ethernet_interfaces_by_name(flync_model)
        (
            virtual_interfaces_by_name,
            ambiguous_virtual_interface_names,
        ) = collect_virtual_interfaces(flync_model)
        for interface in self.measurement_points or []:
            interface.bind(
                buses_by_name,
                ethernet_interfaces_by_name,
                virtual_interfaces_by_name,
                ambiguous_virtual_interface_names=ambiguous_virtual_interface_names,
            )
