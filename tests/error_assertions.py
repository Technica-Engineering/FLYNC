"""Shared assertions for negative tests that pin the exact error a fixture is expected to produce."""

from typing import Any, List, Optional, Tuple

import pytest
from pydantic import ValidationError
from pydantic_core import ErrorDetails, PydanticCustomError

#: What :func:`flync.core.utils.exceptions_handling.validate_with_policy` returns: the model it managed to build
#: (``None`` if it could not) plus every collected error and warning.
ValidationResult = Tuple[Optional[Any], List[ErrorDetails]]


def _describe(error: ErrorDetails) -> str:
    """Render one error as ``"<location>: <message>"``, or just the message for a location-less warning."""

    location = ".".join(str(part) for part in error["loc"])
    return f"{location}: {error['msg']}" if location else error["msg"]


def _error_id(finding: ErrorDetails) -> Optional[str]:
    return (finding.get("ctx") or {}).get("error_id")


def _assert_single_finding(findings: List[ErrorDetails], expected_error_id: Optional[str], message_fragment: str, kind: str) -> None:
    """Assert *findings* holds exactly one entry, raised by the expected call site and naming the expected subject."""

    assert len(findings) == 1, f"expected exactly one {kind}, got: {[_describe(finding) for finding in findings]}"

    reported_error_id = _error_id(findings[0])
    assert reported_error_id == expected_error_id, f"expected error id {expected_error_id}, got {reported_error_id}: {findings[0]['msg']}"

    reported = _describe(findings[0])
    assert message_fragment in reported, f"expected message fragment {message_fragment!r} in: {reported}"


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

    _assert_single_finding(exc_info.value.errors(), expected_error_id, message_fragment, kind="error")


def assert_single_warning(validation_result: ValidationResult, expected_error_id: Optional[str], message_fragment: str) -> None:
    """Assert the fixture loaded, but recorded exactly one warning, raised by the expected validator call site.

    The warning counterpart of :func:`assert_single_error`, for rules that flag a suspicious - but legal -
    configuration: the model must still be constructed, and the warning must be the only finding, so a rule
    silently upgraded to an error (or drowned in unrelated findings) fails the test.

    Parameters
    ----------
    validation_result : tuple
        The ``(model, errors)`` return value of ``validate_with_policy``.

    expected_error_id : str, optional
        Expected ``FLYNC-<MODULE>-WARN-<CATEGORY>-<NUMBER>`` id.

    message_fragment : str
        Substring the reported warning must contain.
    """

    model, findings = validation_result
    assert model is not None, f"expected the model to still be built alongside the warning, got errors: {[_describe(f) for f in findings]}"

    _assert_single_finding(findings, expected_error_id, message_fragment, kind="warning")


def assert_warnings(validation_result: ValidationResult, *expected_error_ids: str) -> None:
    """Assert the validation produced exactly these warnings, nothing more and nothing fewer.

    The setwise counterpart of :func:`assert_single_warning` for rules that legitimately co-fire on the same
    fixture: it pins the exact list of warning ids (``FLYNC-<MODULE>-WARN-<CATEGORY>-<NUMBER>``) regardless of order,
    so a rule that starts warning where it used to stay quiet — or goes quiet where it used to warn — fails the
    test. Each id must appear exactly the number of times it is given.

    Parameters
    ----------
    validation_result : tuple
        The ``(model, findings)`` return value of ``validate_with_policy``.
    *expected_error_ids : str
        The exact set of warning ids the pass must produce.
    """

    model, findings = validation_result
    assert model is not None, f"expected the model to still be built alongside the warnings, got errors: {[_describe(f) for f in findings]}"

    actual = sorted(_error_id(finding) for finding in findings)
    assert actual == sorted(
        expected_error_ids
    ), f"expected exactly the warning ids {sorted(expected_error_ids)}, got: {[_describe(finding) for finding in findings]}"


def assert_no_findings(validation_result: ValidationResult) -> None:
    """Assert the fixture loaded cleanly: a model was built and no error or warning was recorded.

    The positive counterpart of :func:`assert_single_error` / :func:`assert_single_warning`, used to show that a
    rule is scoped to the case it targets and leaves neighbouring configurations alone.

    Parameters
    ----------
    validation_result : tuple
        The ``(model, errors)`` return value of ``validate_with_policy``.
    """

    model, findings = validation_result
    assert model is not None, f"expected the model to be built, got errors: {[_describe(finding) for finding in findings]}"
    assert not findings, f"expected no errors or warnings, got: {[_describe(finding) for finding in findings]}"


def assert_bind_error(exc_info: "pytest.ExceptionInfo[PydanticCustomError]", expected_error_id: str, message_fragment: str) -> None:
    """Assert a ``bind()`` called outside pydantic validation raised the expected single error.

    Reference resolution runs from ``bind()`` methods, which the owning model calls from a validator. When a
    test calls ``bind()`` directly there is no surrounding ``ValidationError`` to unpack, so the raised
    :class:`~pydantic_core.PydanticCustomError` is checked directly - same id and message pinning as
    :func:`assert_single_error`.

    Parameters
    ----------
    exc_info : pytest.ExceptionInfo
        The ``pytest.raises(PydanticCustomError)`` result of the ``bind()`` call under test.

    expected_error_id : str
        Expected ``FLYNC-<MODULE>-<SEVERITY>-<CATEGORY>-<NUMBER>`` id.

    message_fragment : str
        Substring the rendered message must contain.
    """

    reported_error_id = (exc_info.value.context or {}).get("error_id")
    assert reported_error_id == expected_error_id, f"expected error id {expected_error_id}, got {reported_error_id}"

    reported = exc_info.value.message()
    assert message_fragment in reported, f"expected message fragment {message_fragment!r} in: {reported}"
