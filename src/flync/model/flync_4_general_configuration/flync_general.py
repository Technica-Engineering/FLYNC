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

from .flync_channels import FLYNCChannelConfig


class FLYNCGeneralConfig(FLYNCBaseModel):
    """
    The top-level configuration object that aggregates all reusable
    FLYNC settings for the whole system.

    Parameters
    ----------
    tcp_profiles : list of \
    :class:`~flync.model.flync_4_ecu.sockets.TCPOption`
        List of TCP profiles that define the selectable TCP socket options.

    someip_config : :class:`~flync.model.flync_4_someip.SOMEIPConfig`
        Configuration block that holds the global SOME/IP service interface definition, SOME/IP timings, and SD timings profiles
        used by every ECU in the system.

    channels : :class:`~flync.model.flync_4_general_configuration\
.flync_channels.FLYNCChannelConfig`, optional
        Channel-level configuration grouping CAN buses, LIN buses, and Ethernet Container PDU definitions.
        Loaded from the ``general/channels/`` directory.
        Each bus or container PDU is stored in its own file under the corresponding sub-folder (``can/``, ``lin/``, ``container_pdus/``).
        Absent when the ``general/channels/`` directory does not exist.
    """

    tcp_profiles: Annotated[
        List[TCPOption],
        External(output_structure=OutputStrategy.SINGLE_FILE),
        BeforeValidator(common_validators.validate_or_remove("TCP profiles", List[TCPOption])),
        BeforeValidator(common_validators.none_to_empty_list),
    ] = Field(default=[])
    someip_config: Annotated[
        Optional[SOMEIPConfig],
        External(
            output_structure=OutputStrategy.FOLDER,
            naming_strategy=NamingStrategy.FIXED_PATH,
            path="someip",
        ),
        BeforeValidator(common_validators.validate_or_remove("SOME/IP config", SOMEIPConfig)),
    ] = Field(
        default=None,
        description="contains the SOME/IP config for the entire system.",
    )
    channels: Annotated[
        Optional[FLYNCChannelConfig],
        External(
            output_structure=OutputStrategy.FOLDER,
            naming_strategy=NamingStrategy.FIXED_PATH,
            path="channels",
        ),
    ] = Field(
        default=None,
        description=("CAN buses, LIN buses and Ethernet Container PDUs, loaded from general/channels/."),
    )
