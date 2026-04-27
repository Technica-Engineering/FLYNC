"""Defines the general system-wide configuration in FLYNC"""

from typing import Annotated, List, Optional

from pydantic import BeforeValidator, Field

import flync.core.utils.common_validators as common_validators
from flync.core.annotations.external import (
    External,
    NamingStrategy,
    OutputStrategy,
)
from flync.core.base_models import FLYNCBaseModel
from flync.model.flync_4_ecu import TCPOption
from flync.model.flync_4_someip import SOMEIPConfig


class FLYNCGeneralConfig(FLYNCBaseModel):
    """
    The top-level configuration object that aggregates all reusable
    FLYNC settings for the whole system.

    Parameters
    ----------
    tcp_profiles : list of \
    :class:`~flync.model.flync_4_ecu.sockets.TCPOption`
        List of TCP profiles that define the selectable
        TCP socket options.

    someip_config : :class:`~flync.model.flync_4_someip.SOMEIPConfig`
        Configuration block that holds the global SOME/IP service
        interface definition, SOME/IP timings, and SD timings profiles
        used by every ECU in the system.
    """

    tcp_profiles: Annotated[
        List[TCPOption],
        External(output_structure=OutputStrategy.SINGLE_FILE),
        BeforeValidator(
            common_validators.validate_or_remove(
                "TCP profiles", List[TCPOption]
            )
        ),
        BeforeValidator(common_validators.none_to_empty_list),
    ] = Field(default=[])
    someip_config: Annotated[
        Optional[SOMEIPConfig],
        External(
            output_structure=OutputStrategy.FOLDER,
            naming_strategy=NamingStrategy.FIXED_PATH,
            path="someip",
        ),
        BeforeValidator(
            common_validators.validate_or_remove(
                "SOME/IP config", SOMEIPConfig
            )
        ),
    ] = Field(
        default=None,
        description="contains the SOME/IP config for the entire system.",
    )
