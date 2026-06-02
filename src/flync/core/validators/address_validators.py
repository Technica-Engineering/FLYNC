"""Validators for network address types."""

import re
from typing import Any

_MAC_NO_SEPARATOR_PATTERN = re.compile(r"^[0-9A-Fa-f]{12}$")


def before_validate_mac_address(value: Any) -> Any:
    """Pre-validation for MAC address fields with user-friendly error messages.

    Catches two common mistakes before pydantic_extra_types processes the value:
    - Integer input (e.g. YAML parses 001122334455 as an int)
    - String without separators (e.g. "aabbccddeeff")
    """
    if isinstance(value, int):
        raise ValueError("MAC address must be a string in the format 'xx:xx:xx:xx:xx:xx' or 'xx-xx-xx-xx-xx-xx'. ")
    if isinstance(value, str) and _MAC_NO_SEPARATOR_PATTERN.match(value):
        formatted = ":".join(value[i : i + 2] for i in range(0, 12, 2))  # noqa: E203 - black & flake8 formats colliding
        raise ValueError(f"MAC address '{value}' is missing separators. Use the format 'xx:xx:xx:xx:xx:xx' (e.g., '{formatted}').")
    return value
