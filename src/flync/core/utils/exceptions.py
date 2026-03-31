"""Defines custom pydantic errors."""

from pydantic_core import PydanticCustomError


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
