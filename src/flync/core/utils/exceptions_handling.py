from typing import Any, List, Optional, Set, Tuple, Type

from pydantic import BaseModel, TypeAdapter, ValidationError
from pydantic_core import ErrorDetails, InitErrorDetails, PydanticCustomError

from flync.core.base_models.base_model import FLYNCBaseModel

FATAL_ERROR_TYPES = {"extra_forbid", "extra_forbidden", "fatal", "missing"}


def resolve_alias(model: type[BaseModel], field_name: str) -> str:
    """
    Return the YAML key used for a Pydantic field, considering alias.
    """
    if not model or not hasattr(model, "model_fields"):
        return field_name
    field = model.model_fields.get(field_name)
    return field.alias or field_name if field else field_name


def safe_yaml_position(
    node: Any, loc: tuple, model: type[BaseModel] | None = None
) -> Tuple[int | None, int | None]:  # noqa
    """
    Given a ruamel.yaml node and a Pydantic `loc` tuple, return
    (line, column). Falls back gracefully if key/item is missing.
    """
    current = node
    current_model = model
    parent = None
    last_key = None

    for part in loc:
        parent = current
        last_key = part

        # Handle list indices
        if isinstance(part, int):
            try:
                current = current[part]
            except (IndexError, TypeError):
                return _fallback_position(parent)
            current_model = None
        else:
            # Map field name to YAML key if alias exists
            yaml_key = (
                resolve_alias(current_model, part) if current_model else part
            )

            try:
                current = current[yaml_key]
            except (KeyError, TypeError):
                return _fallback_position(parent)

            # Descend model if available
            if current_model:
                field = current_model.model_fields.get(part)
                if field:
                    annotation = field.annotation
                    # For List[Model], extract inner type
                    origin = getattr(annotation, "__origin__", None)
                    if origin in (list, tuple):
                        current_model = getattr(
                            annotation, "__args__", [None]
                        )[0]
                    else:
                        current_model = annotation
                else:
                    current_model = None

    # Get line/column for final key or index
    return _extract_position(parent, last_key)


def _extract_position(parent: Any, key: Any) -> Tuple[int | None, int | None]:
    """
    Safely extract line/col from ruamel.yaml node.
    Returns (line, column) or (None, None)
    """
    try:
        line = parent.lc.line
        col = parent.lc.col
        if isinstance(key, int):
            line, col = getattr(parent.lc, "item", lambda k: None)(key)
        else:
            line, col = getattr(parent.lc, "value", lambda k: None)(key)
    except AttributeError:
        return None, None

    return (
        line + 1 if line is not None else None,
        col + 1 if col is not None else None,
    )


def _fallback_position(node: Any) -> Tuple[int | None, int | None]:
    """
    Return the best-effort parent position if key/item is missing.
    """
    try:
        line = getattr(node.lc, "line", None)
        col = getattr(node.lc, "col", None)
    except AttributeError:
        return None, None

    return (
        line + 1 if line is not None else None,
        col + 1 if col is not None else None,
    )


def errors_to_init_errors(
    errors: List[ErrorDetails],
    model: Optional[BaseModel] = None,
    yaml_data: Optional[object] = None,
    yaml_path: Optional[str] = None,
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
    enriched = []
    for e in errors:
        ctx = e.get("ctx", {})
        if yaml_path and "yaml_path" not in ctx:
            ctx["yaml_path"] = str(yaml_path)
        if model is not None and yaml_data and "yaml_location" not in ctx:
            line, col = safe_yaml_position(yaml_data, e["loc"], model=model)
            if line:
                ctx["line"] = line
            if col:
                ctx["col"] = col
        error_detail = InitErrorDetails(
            type=PydanticCustomError(e.get("type", ""), e.get("msg", ""), ctx),
            loc=e.get("loc", tuple()),
            input=e.get("input"),
            ctx=ctx,
        )
        error_detail["metadata"] = ctx
        enriched.append(error_detail)
    return enriched


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
    model: Type[FLYNCBaseModel], data: Any, path
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
        # enrich errors
        try:
            errs2 = errors_to_init_errors(
                get_unique_errors(errs2),
                model=model,
                yaml_data=working,
                yaml_path=path,
            )
            raise ValidationError.from_exception_data(
                title=ve2.title,
                line_errors=errs2,
            )
        except ValidationError as ve3:
            errs2 = ve3.errors()
            if any(e.get("type") in FATAL_ERROR_TYPES for e in errs2):
                # CASE: Fatal
                # Re-raise original ValidationError
                raise ve3
        collected_errors.extend(errs2)
        # return caught errors for logging
        return None, get_unique_errors(collected_errors)
    except Exception as e:
        # caught a random excpetion
        # should be added to the list of caught errors and reraised as fatal.
        fatal_ctx = {"ex": e.with_traceback(None)}
        raise ValidationError.from_exception_data(
            title="Unhandled exception",
            line_errors=errors_to_init_errors(
                get_unique_errors(collected_errors),
                model=model,
                yaml_data=working,
                yaml_path=path,
            )
            + [
                InitErrorDetails(
                    type=PydanticCustomError(
                        "fatal",
                        "unhandled exception caught: {ex}",
                        fatal_ctx,
                    ),
                    ctx=fatal_ctx,
                    input=model,
                )
            ],
        )
