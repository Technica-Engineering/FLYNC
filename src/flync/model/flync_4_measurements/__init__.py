"""Measurement and logging overlay for a FLYNC network model.

Declares measurement points, and resolves their references into the loaded FLYNC object graph via
FLYNC's ``Reference``/``PrivateAttr`` idiom.
"""

from flync.model.flync_4_measurements.measurement_point import MeasurementPoint, PayloadType
from flync.model.flync_4_measurements.measurement_system import MeasurementSystem

# Module code for this package's error ids (``FLYNC-MEA-<SEVERITY>-<CATEGORY>-<NUMBER>``).
KEY = "MEA"

__all__ = [
    "KEY",
    "MeasurementPoint",
    "MeasurementSystem",
    "PayloadType",
]
