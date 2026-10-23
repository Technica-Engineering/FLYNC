"""Defines the SwitchConfig for automotive Ethernet Switches"""

from __future__ import annotations

from typing import Annotated, List, Optional

from pydantic import BeforeValidator, Field, StrictInt

from flync.core.base_models.base_model import FLYNCBaseModel
from flync.core.validators.generic import none_to_empty_list
from flync.model.flync_4_ecu.port_extender import PortExtender
from flync.model.flync_4_ecu.switch_port import SwitchPort
from flync.model.flync_4_ecu.switch_tcam import TCAMRule
from flync.model.flync_4_ecu.vlan_entry import VLANEntry
from flync.model.flync_4_metadata import EmbeddedMetadata


class SwitchConfig(FLYNCBaseModel):
    """
    Core switch configuration data stored in ``switch.flync.yaml``.

    This model holds the switch metadata, ports, VLANs, and TCAM rules.
    It is loaded from the ``switch.flync.yaml`` file inside each switch folder.

    Parameters
    ----------
    meta : :class:`~flync.model.flync_4_metadata.metadata.EmbeddedMetadata`
        Metadata associated with the switch.

    ports : list of :class:`SwitchPort`
        List of switch ports, including those that sit on port extenders.

    vlans : list of :class:`~flync.model.flync_4_ecu.vlan_entry.VLANEntry`
        List of VLAN entries configured on the switch.

    tcam_rules : list of :class:`TCAMRule`, optional
        List of TCAM rules configured on the switch.
    dynamic_address_aging_time : int, optional
        Aging time, in seconds, for dynamically learned address entries in the switch's Filtering Database (FDB).
        A learned MAC address is removed if no matching frame is seen within this interval.
        Must be a positive value.

    port_extenders : list of :class:`~flync.model.flync_4_ecu.port_extender.PortExtender`, optional
        Port extenders controlled by this switch. Each lists the names of its ports from ``ports``.
    """

    meta: EmbeddedMetadata = Field()
    tcam_rules: Annotated[
        Optional[List[TCAMRule]],
        BeforeValidator(none_to_empty_list),
    ] = Field(default=[])
    ports: List[SwitchPort] = Field()
    vlans: List[VLANEntry] = Field()
    dynamic_address_aging_time: Optional[StrictInt] = Field(default=None, gt=0)
    port_extenders: Annotated[
        Optional[List[PortExtender]],
        BeforeValidator(none_to_empty_list),
    ] = Field(default_factory=list)
