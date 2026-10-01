"""Negative and positive cases for the HTB (Hierarchical Token Bucket) egress shaping rules.

Every rule of :meth:`HTBInstance.validate_htb_config` gets one minimal fixture that trips exactly it, plus the
accepted counterparts (no default class, a legal nested hierarchy) so an inverted condition cannot pass.
"""

from typing import Any, Optional

import pytest
from pydantic import ValidationError

from flync.model.flync_4_tsn.qos import HTBInstance
from tests.error_assertions import assert_single_error


def child_class(classid: int, priority: int, rate: int = 5, ceil: int = 10, child_classes: Optional[list] = None) -> dict:
    """One HTB child class, named for the classid and priority the rule under test cares about."""

    return dict(classid=classid, priority=priority, rate=rate, ceil=ceil, child_classes=child_classes or [])


def htb_data(default_class: Optional[int] = 12, child_classes: Optional[list] = None, root_id: str = "1:") -> dict:
    """A valid two-leaf HTB configuration, overridable field by field by a negative case."""

    return dict(
        root_id=root_id,
        default_class=default_class,
        child_classes=child_classes if child_classes is not None else [child_class(11, 1), child_class(12, 2)],
    )


@pytest.mark.parametrize(
    "data, expected_error_id, message_fragment",
    [
        pytest.param(
            htb_data(default_class=99),
            "FLYNC-TSN-MIN-REF-155",
            "Default class 99 should exist",
            id="default_class_missing",
        ),
        pytest.param(
            htb_data(child_classes=[child_class(11, 1), child_class(12, 2, child_classes=[child_class(13, 3, rate=2, ceil=8)])]),
            "FLYNC-TSN-MIN-STRUCT-156",
            "Default class 12 must be a leaf class",
            id="default_class_not_a_leaf",
        ),
        pytest.param(
            htb_data(child_classes=[child_class(11, 1, rate=5, ceil=1), child_class(12, 2)]),
            "FLYNC-TSN-MIN-CONS-157",
            "Ceil cannot be less than  rate. Class 11.",
            id="ceil_below_rate",
        ),
        pytest.param(
            htb_data(child_classes=[child_class(11, 1), child_class(12, 1)]),
            "FLYNC-TSN-MIN-UNIQ-158",
            "All priorities must be unique, prio 1",
            id="duplicate_priority",
        ),
        pytest.param(
            htb_data(default_class=11, child_classes=[child_class(11, 1), child_class(11, 2)]),
            "FLYNC-TSN-MIN-UNIQ-159",
            "All classids must be unique, classid 11",
            id="duplicate_classid",
        ),
        pytest.param(
            htb_data(
                default_class=11,
                child_classes=[
                    child_class(11, 1),
                    child_class(12, 2, child_classes=[child_class(13, 3, rate=4, ceil=5), child_class(14, 4, rate=4, ceil=5)]),
                ],
            ),
            "FLYNC-TSN-MIN-CONS-160",
            "Sum of rate of child classes is greater than the rate of parent class. Class 12.",
            id="child_rate_sum_exceeds_parent",
        ),
        pytest.param(
            htb_data(
                default_class=11,
                child_classes=[child_class(11, 1), child_class(12, 2, child_classes=[child_class(13, 3, rate=2, ceil=20)])],
            ),
            "FLYNC-TSN-MIN-CONS-161",
            "Ceil of child class should be less than parent's class. Class 12.",
            id="child_ceil_exceeds_parent",
        ),
        pytest.param(
            htb_data(root_id="1"),
            None,
            "root_id: String should match pattern",
            id="root_id_without_colon",
        ),
        pytest.param(
            {**htb_data(), "default_class": "12a"},
            None,
            "default_class: Input should be a valid integer",
            id="default_class_not_an_integer",
        ),
    ],
)
def test_htb_rejects(data: dict, expected_error_id: Optional[str], message_fragment: str) -> None:
    """Each broken HTB configuration fails with exactly the rule it was built to trip."""

    with pytest.raises(ValidationError) as exc_info:
        HTBInstance(**data)

    assert_single_error(exc_info, expected_error_id, message_fragment)


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(htb_data(), id="two_leaf_classes"),
        pytest.param(htb_data(default_class=None), id="no_default_class"),
        pytest.param(
            htb_data(
                default_class=13,
                child_classes=[child_class(11, 1), child_class(12, 2, child_classes=[child_class(13, 3, rate=5, ceil=10)])],
            ),
            id="default_class_is_a_nested_leaf",
        ),
    ],
)
def test_htb_accepts(data: dict) -> None:
    """The rules leave legal configurations - including a nested hierarchy - alone."""

    htb: Any = HTBInstance(**data)
    assert htb.root_id == data["root_id"]
    assert htb.default_class == data["default_class"]
