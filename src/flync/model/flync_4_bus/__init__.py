"""Top-level package for flync-4-bus."""

from flync.model.flync_4_bus.can_bus import (
    CANBus,
    CANBusNode,
)
from flync.model.flync_4_bus.lin_bus import (
    AnyLINNode,
    LINBus,
    LINMasterNode,
    LINScheduleEntry,
    LINScheduleTable,
    LINSlaveNode,
)

__all__ = [
    # CAN
    "CANBusNode",
    "CANBus",
    # LIN
    "AnyLINNode",
    "LINMasterNode",
    "LINSlaveNode",
    "LINScheduleEntry",
    "LINScheduleTable",
    "LINBus",
]
