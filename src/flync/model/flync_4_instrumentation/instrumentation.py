"""The instrumentation overlay - the optional wrapper that groups a system's measurement points.

The wrapper maps to the ``instrumentation/`` workspace folder. It holds ``measurement_points``,
the captured-point registry loaded from ``instrumentation/measurement_points.flync.yaml``. The
overlay is entirely optional: a workspace that is not being measured has no ``instrumentation/``
folder and ``FLYNCModel.instrumentation`` stays ``None``.
"""

from typing import Annotated, List, Optional, Self

from pydantic import Field, model_validator

from flync.core.annotations import External, NamingStrategy, OutputStrategy
from flync.core.base_models import FLYNCBaseModel
from flync.model.flync_4_instrumentation.measurement_point import (
    MeasurementPointType,
    validate_measurement_points_local,
)


class Instrumentation(FLYNCBaseModel):
    """
    Optional workspace-level wrapper (``instrumentation/``) grouping the measurement points.

    Parameters
    ----------
    measurement_points : list of :class:`~flync.model.flync_4_instrumentation.measurement_point.MeasurementPointType`, optional
        The measurement points recording this system, one file listing them all, discriminated by
        ``type``. Absent when the workspace is not being measured.
    """

    measurement_points: Annotated[
        Optional[List[MeasurementPointType]],
        External(
            output_structure=OutputStrategy.SINGLE_FILE | OutputStrategy.OMMIT_ROOT,
            naming_strategy=NamingStrategy.FIXED_PATH,
            path="measurement_points",
        ),
    ] = Field(default=None, description="The measurement points recording this system.")

    @model_validator(mode="after")
    def validate_local(self) -> Self:
        """FLYNC-independent structural rules over the measurement point list (unique ids and names)."""
        validate_measurement_points_local(self.measurement_points)
        return self
