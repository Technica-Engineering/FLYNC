from typing import Callable, Any
from dataclasses import dataclass
from enum import IntFlag


class HintStrategy(IntFlag):
    """
    The strategy on how an external field will be generated.
    """

    AUTO = 1
    FIXED = AUTO
    FUNCTION = 2


@dataclass(frozen=True)
class Hint:
    """
    Indicates this field is loaded from a separate location.
    """

    value: Any | None = None
    function: Callable[..., Any] | None = None
    hint_strategy: HintStrategy = HintStrategy.AUTO
