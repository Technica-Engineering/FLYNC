"""Defines firewall configuration models for FLYNC."""

from typing import Annotated, List, Literal, Optional

from pydantic import BeforeValidator, Field, field_validator, model_validator

import flync.core.utils.common_validators as common_validators
from flync.core.base_models.base_model import FLYNCBaseModel
from flync.core.utils.exceptions import err_minor
from flync.model.flync_4_tsn.qos import FrameFilter


class FirewallRule(FLYNCBaseModel):
    """
    Defines a single firewall rule for matching and handling frames.

    Parameters
    ----------
    name : str
        A unique name identifying the rule.

    action : Literal['reject', 'accept', 'drop']
        The action to take when the pattern matches. Can be one of
        ``'reject'``, ``'accept'``, or ``'drop'``.

    pattern : :class:`~flync.model.flync_4_tsn.qos.FrameFilter`
        The filter pattern used to match frames for this rule.
    """

    name: str = Field()
    action: Literal["reject", "accept", "drop"] = Field()
    pattern: FrameFilter = Field()

    @model_validator(mode="after")
    def validate_pattern(self):
        pattern = self.pattern
        if all(field is None for field in vars(pattern).values()):
            raise err_minor(
                "At least one of the fields in pattern of firewall rule "
                "should be present"
            )
        if pattern.dst_ipv4 is not None and pattern.dst_ipv6 is not None:
            raise err_minor(
                "Firewall rule cannot have both dst ipv4 and dst ipv6 set"
            )
        if pattern.src_ipv4 is not None and pattern.src_ipv6 is not None:
            raise err_minor(
                "Firewall rule cannot have both src ipv4 and src ipv6 set"
            )
        if pattern.src_ipv4 is not None and pattern.dst_ipv6 is not None:
            raise err_minor(
                "Firewall rule cannot have both src ipv4 and dst ipv6 set"
            )
        if pattern.src_ipv6 is not None and pattern.dst_ipv4 is not None:
            raise err_minor(
                "Firewall rule cannot have both src ipv6 and dst ipv4 set"
            )
        return self


class Firewall(FLYNCBaseModel):
    """
    Represents a set of firewall rules with a default action.

    Parameters
    ----------
    default_action : Literal['reject', 'accept', 'drop']
        The action to apply to packets that do not match any rule.
        Can be one of ``'reject'``, ``'accept'``, or ``'drop'``.

    rules : list of :class:`FirewallRule`
        A list of ``FirewallRule`` objects that define matching
        conditions and actions.
    """

    default_action: Optional[Literal["reject", "accept", "drop"]] = Field(
        default="reject"
    )
    input_rules: Annotated[
        Optional[List[FirewallRule]],
        BeforeValidator(common_validators.none_to_empty_list),
    ] = Field(default=[])
    output_rules: Annotated[
        Optional[List[FirewallRule]],
        BeforeValidator(common_validators.none_to_empty_list),
    ] = Field(default=[])
    forward_rules: Annotated[
        Optional[List[FirewallRule]],
        BeforeValidator(common_validators.none_to_empty_list),
    ] = Field(default=[])

    @field_validator("input_rules", "output_rules", "forward_rules")
    @classmethod
    def check_duplicate_rules(
        cls, rules: List[FirewallRule]
    ) -> List[FirewallRule]:
        filter_list = []
        for rule in rules:
            if rule.pattern in filter_list:
                raise err_minor("Two or more rules cannot be the same")
            filter_list.append(rule.pattern)
        return rules
