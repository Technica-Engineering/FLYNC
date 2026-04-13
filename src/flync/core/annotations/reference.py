from dataclasses import dataclass
from enum import IntFlag


class ReferenceStrategy(IntFlag):
    """
    The strategy on how a concrete flync object will be referenced.
    """

    AUTO = 1
    PRIVATE_ATTR = AUTO


@dataclass(frozen=True)
class Reference:
    """
    Indicates this field is a reference to an already loaded/generated field.
    """

    source: str
    reference_strategy: ReferenceStrategy = ReferenceStrategy.PRIVATE_ATTR
