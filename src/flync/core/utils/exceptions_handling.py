from typing import Any, List, Optional, Set, Tuple, Type

from pydantic import TypeAdapter, ValidationError
from pydantic_core import ErrorDetails, InitErrorDetails, PydanticCustomError

from flync.core.base_models.base_model import FLYNCBaseModel

FATAL_ERROR_TYPES = {"extra_forbid", "fatal", "missing"}


def errors_to_init_errors(
    errors: List[ErrorDetails],
) -> List[InitErrorDetails]:
    """
    Function to convert Pydantic validation errors into init Errors to be reraised.

    Parameters
    ----------
    errors : List[ErrorDetails]
        The list of errors to be converted.

    Returns
    -------
    List[InitErrorDetails]
        The converted errors to be reraised.
    """  # noqa
    return [
        InitErrorDetails(
            type=PydanticCustomError(e.get("type", ""), e.get("msg", "")),
            loc=e.get("loc", tuple()),
            input=e.get("input"),
            ctx=e.get("ctx", dict()),
        )
        for e in errors
    ]


def delete_at_loc(data: Any, loc: Tuple):
    """
    Helper function to remove the key/item from original
    object by loc(path to an element within the object).

    Parameters
    ----------
    data : Any
        Data to remove the item from. **Will be mutated**.

    loc : Tuple
        Path to the location of item to remove.
    """
    if not loc:
        return

    cur = data

    for key in loc[:-1]:
        if isinstance(cur, dict) and key in cur:
            cur = cur[key]
        elif (
            isinstance(cur, list)
            and isinstance(key, int)
            and 0 <= key < len(cur)
        ):
            cur = cur[key]
        else:
            return

    last = loc[-1]
    if isinstance(cur, dict) and last in cur:
        del cur[last]
    elif (
        isinstance(cur, list)
        and isinstance(last, int)
        and 0 <= last < len(cur)
    ):
        cur.pop(last)


def _get_error_signature(error_details: ErrorDetails) -> Tuple:
    """
    A function to return hashable representation of ErrorDetails object or
    dict taken from ValidationError.errors() list to then use it
    for identification.

    Parameters
    ----------
    error_details: ErrorDetails
        The object with pydantic's error details

    Returns
    -------
    Tuple
    """

    loc: Tuple[int | str, ...] = error_details.get("loc", tuple())
    msg = error_details.get("msg")
    eror_type = error_details.get("type")

    return loc, str(msg), str(eror_type)


def get_unique_errors(
    errors: List[ErrorDetails],
) -> List[ErrorDetails]:
    """
    A function to get the list of unique errors.

    Parameters
    ----------
    errors: List[ErrorDetails]
        The list of pydantic's error details

    Returns
    -------
    List[ErrorDetails]
    """
    errors_seen: Set[Tuple[str, Tuple]] = set()
    unique_errors: List[ErrorDetails] = []

    for error in errors:
        error_signature = _get_error_signature(error)

        if error_signature not in errors_seen:
            errors_seen.add(error_signature)
            unique_errors.append(error)

    return unique_errors


def validate_with_policy(
    model: Type[FLYNCBaseModel], data: Any
) -> Tuple[Optional[FLYNCBaseModel], List[ErrorDetails]]:
    """
    Helper function to perform model validation from the given data,
    collect errors with different severity and perform action
    based on severity.

    Parameters
    ----------
    model : Type[FLYNCBaseModel]
        Flync model class.

    data : Any
        Data to validate and instantiate the model with.

    Returns
    -------
    Tuple[Optional[FLYNCBaseModel], List]
        Tuple with optional model instance and list of errors.

    Raises
    ------
    ValidationError
    """

    working = data
    collected_errors: List[ErrorDetails] = []
    try:
        pydantic_adapter = TypeAdapter(model)
        return pydantic_adapter.validate_python(working), get_unique_errors(
            collected_errors
        )
    except ValidationError as ve2:
        errs2 = ve2.errors()
        collected_errors.extend(errs2)

        if any(e.get("type") in FATAL_ERROR_TYPES for e in errs2):
            # CASE: Fatal
            # Re-raise original ValidationError
            raise ValidationError.from_exception_data(
                title=ve2.title,
                line_errors=errors_to_init_errors(
                    get_unique_errors(collected_errors)
                ),
            )
        # return caught errors for logging
        return None, get_unique_errors(collected_errors)
    except Exception as e:
        # caught a random excpetion
        # should be added to the list of caught errors and reraised as fatal.
        raise ValidationError.from_exception_data(
            title="Unhandled exception",
            line_errors=errors_to_init_errors(
                get_unique_errors(collected_errors)
            )
            + [
                InitErrorDetails(
                    type=PydanticCustomError(
                        "fatal",
                        "unhandled exception caught: {ex}",
                        {"ex": e.with_traceback(None)},
                    ),
                    ctx=e.__dict__,
                    input="",
                )
            ],
        )
