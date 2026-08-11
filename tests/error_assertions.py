"""Shared assertions for negative tests that pin the exact error a fixture is expected to produce."""

from typing import Optional

import pytest
from pydantic import ValidationError


def assert_single_error(exc_info: "pytest.ExceptionInfo[ValidationError]", expected_error_id: Optional[str], message_fragment: str) -> None:
    """Assert the fixture failed with exactly one error, raised by the expected validator call site.

    Pinning the FLYNC error id keeps a negative test tied to the rule it is named for: a fixture that grows a
    second defect, a validator ordering change that lets an unrelated pass fire first, or a message reworded
    into a different rule all fail loudly instead of silently asserting something else.

    Parameters
    ----------
    exc_info : pytest.ExceptionInfo
        The ``pytest.raises(ValidationError)`` result of the construction under test.

    expected_error_id : str, optional
        Expected ``FLYNC-<MODULE>-<SEVERITY>-<CATEGORY>-<NUMBER>`` id. Pass ``None`` for the few errors raised
        by plain Pydantic (union, literal, or a bare ``ValueError`` inside a validator), which carry no id; the
        single-error and message checks still apply.

    message_fragment : str
        Substring the reported error must contain. Searched in ``"<location>: <message>"`` so that a fragment
        may name the offending field, which is where Pydantic reports e.g. a forbidden extra input. Unlike
        ``pytest.raises(match=...)`` this is a plain substring, not a regular expression.
    """

    errors = exc_info.value.errors()
    assert len(errors) == 1, f"expected exactly one error, got: {[error['msg'] for error in errors]}"

    reported_error_id = errors[0].get("ctx", {}).get("error_id")
    assert reported_error_id == expected_error_id, f"expected error id {expected_error_id}, got {reported_error_id}: {errors[0]['msg']}"

    location = ".".join(str(part) for part in errors[0]["loc"])
    reported = f"{location}: {errors[0]['msg']}"
    assert message_fragment in reported, f"expected message fragment {message_fragment!r} in: {reported}"
