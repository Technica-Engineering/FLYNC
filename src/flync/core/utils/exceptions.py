"""Defines custom pydantic errors."""

from contextvars import ContextVar
from typing import List, Optional

from pydantic_core import ErrorDetails, PydanticCustomError

# Accumulates informational warnings during a validate_with_policy call.
# Validators append to this list via warn() instead of raising, so the
# validated field is kept while the message still surfaces as a warning.
_validation_warnings: ContextVar[Optional[List[ErrorDetails]]] = ContextVar(
    "_validation_warnings", default=None
)


def warn(msg: str) -> None:
    """Record a validation warning without raising a validation error.

    The message is appended to the active warning list (set up by
    ``validate_with_policy``) and will be returned alongside
    ``load_errors`` so that it appears in the warnings table.  If called
    outside a ``validate_with_policy`` context the call is silently ignored.

    Parameters
    ----------
    msg : str
        Human-readable warning message.
    """
    warnings_list = _validation_warnings.get()
    if warnings_list is not None:
        warnings_list.append(
            {
                "type": "warning",
                "msg": msg,
                "loc": (),
                "ctx": {},
                "input": None,
                "url": "",
            }
        )


def err_minor(msg: str, **ctx) -> PydanticCustomError:
    """
    Factory that returns PydanticCustomError with type **minor**.

    Parameters
    ----------
    msg : str
        Error message that may contain placeholders

    ctx : dict
        Context arguments that define key-value
        pairs to fill the placeholders in `msg`

    Returns
    -------
    PydanticCustomError
    """
    return PydanticCustomError("minor", msg, ctx)


def err_major(msg: str, **ctx) -> PydanticCustomError:
    """
    Factory that returns PydanticCustomError with type **major**.

    Parameters
    ----------
    msg : str
        Error message that may contain placeholders

    ctx : dict
        Context arguments that define key-value
        pairs to fill the placeholders in `msg`

    Returns
    -------
    PydanticCustomError
    """
    return PydanticCustomError("major", msg, ctx)


def err_fatal(msg: str, **ctx) -> PydanticCustomError:
    """
    Factory that returns PydanticCustomError with type **fatal**.

    Parameters
    ----------
    msg : str
        Error message that may contain placeholders

    ctx : dict
        Context arguments that define key-value
        pairs to fill the placeholders in `msg`

    Returns
    -------
    PydanticCustomError
    """
    return PydanticCustomError("fatal", msg, ctx)
