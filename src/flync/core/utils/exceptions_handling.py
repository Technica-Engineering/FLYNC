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


def get_name_by_alias(model: type[BaseModel], alias: str):
    """Return the Python field name that corresponds to the given alias.

    Parameters
    ----------
    model : type[BaseModel]
        The Pydantic model class to search.
    alias : str
        The alias to look up.

    Returns
    -------
    str
        The Python attribute name whose alias matches ``alias``.

    Raises
    ------
    KeyError
        If no field with the given alias is found.
    """
    for field_name, field in model.model_fields.items():
        if field.alias == alias:
            return field_name
    raise KeyError(alias)


def safe_yaml_position(  # noqa # nosonar
    node: Any, loc: tuple, model: type[BaseModel] | None = None
) -> Tuple[int | None, int | None]:
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
            if not current_model:
                continue

            if hasattr(current_model, "model_fields"):
                field = current_model.model_fields.get(part)
                annotation = field.annotation if field else None
            else:
                # current_model is already a container generic
                # (e.g. dict[str, Model])
                annotation = current_model

            if annotation is None:
                current_model = None
                continue

            origin = getattr(annotation, "__origin__", None)
            args = getattr(annotation, "__args__", None) or ()
            if origin in (list, tuple) and isinstance(part, int):
                current_model = args[0] if args else None
            elif origin is dict and not isinstance(part, int):
                current_model = (
                    args[1] if len(args) > 1 else None
                )  # noqa # type: ignore[misc]
            elif origin is None:
                current_model = annotation
            else:
                current_model = None
            if not hasattr(current_model, "model_fields"):
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
            line, col = getattr(  # type: ignore[misc]
                parent.lc, "item", lambda k: None
            )(key)
        else:
            line, col = getattr(  # type: ignore[misc]
                parent.lc, "value", lambda k: None
            )(key)
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
    model: Optional[type[BaseModel]] = None,
    yaml_data: Optional[object] = None,
    yaml_path: Optional[str] = None,
) -> List[InitErrorDetails]:
    """
    Convert Pydantic validation errors into ``InitErrorDetails`` for re-raising.

    Optionally enriches each error with YAML source location information when
    ``model`` and ``yaml_data`` are provided, and with the file path when
    ``yaml_path`` is provided.

    Parameters
    ----------
    errors : List[ErrorDetails]
        The list of errors to convert.
    model : type[BaseModel], optional
        The Pydantic model class used to resolve field aliases for YAML
        position look-ups.
    yaml_data : object, optional
        The parsed ruamel.yaml AST of the document, used together with
        ``model`` to locate the error position within the file.
    yaml_path : str, optional
        The workspace-relative file path to embed in each error's context
        as ``yaml_path``.

    Returns
    -------
    List[InitErrorDetails]
        The converted errors, ready to be passed to
        ``ValidationError.from_exception_data``.
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
        error_detail["metadata"] = ctx  # type: ignore[typeddict-unknown-key]
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
        errs2: List[InitErrorDetails] | List[ErrorDetails] = ve2.errors()
        # enrich errors
        try:
            errs2 = errors_to_init_errors(
                get_unique_errors(ve2.errors()),
                model=model,
                yaml_data=working,
                yaml_path=path,
            )
            raise ValidationError.from_exception_data(
                title=ve2.title,
                line_errors=errs2,  # type: ignore[arg-type]
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
