from dataclasses import dataclass
from enum import IntFlag


class ImpliedStrategy(IntFlag):
    """
    The strategy on how an implied field will be calculated.
    """

    FOLDER_NAME = 0b1
    FILE_NAME = 0b10
    OPTIONAL = 0b100
    AUTO = FOLDER_NAME


@dataclass(frozen=True)
class Implied(object):
    """
    Indicates this field is implied instead of loaded/generated.
    """

    strategy: ImpliedStrategy = ImpliedStrategy.AUTO
