"""Instrumentation overlay for a FLYNC network model.

The optional ``instrumentation/`` folder. Its ``measurement_points`` list (the ASAM CMP / TECMP
capture interfaces) is loaded from ``instrumentation/measurement_points.flync.yaml`` and its
references resolved into the loaded FLYNC object graph via FLYNC's ``Reference`` idiom.
"""

from flync.model.flync_4_instrumentation.instrumentation import Instrumentation
from flync.model.flync_4_instrumentation.measurement_point import (
    CANBusMeasurementPoint,
    EthernetBusMeasurementPoint,
    EthernetPortsMeasurementPoint,
    FLYNCIndex,
    LINBusMeasurementPoint,
    MeasurementPoint,
    MeasurementPointType,
    PayloadType,
    PortCapture,
    bind_measurement_points,
    validate_measurement_points_local,
)

# Module code for this package's error ids (``FLYNC-INS-<SEVERITY>-<CATEGORY>-<NUMBER>``).
KEY = "INS"

__all__ = [
    "KEY",
    "CANBusMeasurementPoint",
    "EthernetBusMeasurementPoint",
    "EthernetPortsMeasurementPoint",
    "FLYNCIndex",
    "Instrumentation",
    "LINBusMeasurementPoint",
    "MeasurementPoint",
    "MeasurementPointType",
    "PayloadType",
    "PortCapture",
    "bind_measurement_points",
    "validate_measurement_points_local",
]
