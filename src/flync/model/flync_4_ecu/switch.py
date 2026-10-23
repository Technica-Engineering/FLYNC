"""Defines the automotive Ethernet Switch for FLYNC.

The switch components live in sibling modules and are re-exported here so that
``flync.model.flync_4_ecu.switch`` remains the public import path:

* :mod:`~flync.model.flync_4_ecu.switch_port` holds :class:`SwitchPort`.
* :mod:`~flync.model.flync_4_ecu.switch_tcam` holds the TCAM actions and rules.
* :mod:`~flync.model.flync_4_ecu.switch_config` holds :class:`SwitchConfig`.
"""

from __future__ import annotations

from typing import Annotated, List, Optional, Self

from pydantic import Field, model_validator

from flync.core.annotations import (
    External,
    Implied,
    ImpliedStrategy,
    NamingStrategy,
    OutputStrategy,
)
from flync.core.base_models.base_model import FLYNCBaseModel
from flync.core.datatypes.macaddress import FLYNCMacAddress
from flync.core.utils.exceptions import Category, err_minor
from flync.core.validators.connection_compatibility import validate_mii_subports
from flync.core.validators.generic import (
    validate_elements_in,
    validate_list_items_unique,
)
from flync.model.flync_4_ecu.controller import Controller
from flync.model.flync_4_ecu.port_extender import (
    PortExtender,
    bind_port_extenders,
    get_channelized_uplink_ports,
    get_extender_uplink_ports,
    validate_extender_names,
    validate_extender_port_channels,
    validate_extender_port_references,
    validate_extender_uplink_links,
    validate_extender_uplinks,
    validate_uplink_port_usage,
    warn_extender_without_ports,
)
from flync.model.flync_4_ecu.switch_config import SwitchConfig
from flync.model.flync_4_ecu.switch_port import SwitchPort
from flync.model.flync_4_ecu.switch_tcam import (
    Drop,
    ForceEgress,
    FrameMask,
    Mirror,
    PortScopedAction,
    RemoveVLAN,
    TCAMRule,
    VLANOverwrite,
)
from flync.model.flync_4_ecu.vlan_entry import VLANEntry
from flync.model.flync_4_metadata import EmbeddedMetadata
from flync.model.flync_4_tsn import TrafficClass

__all__ = [
    "Controller",
    "Drop",
    "ForceEgress",
    "FrameMask",
    "Mirror",
    "PortScopedAction",
    "RemoveVLAN",
    "Switch",
    "SwitchConfig",
    "SwitchPort",
    "TCAMRule",
    "TrafficClass",
    "VLANEntry",
    "VLANOverwrite",
]


class Switch(FLYNCBaseModel):
    """
    Represents an automotive Ethernet network switch configuration.

    Parameters
    ----------
    name : str
        Name of the switch. Implied from the folder name.

    switch_config : :class:`SwitchConfig`
        The core switch configuration loaded from ``switch.flync.yaml``.

    host_controller : :class:`~flync.model.flync_4_ecu.controller.Controller`, optional
        The host controller managing the switch, stored in the
        ``switch_host_controller/`` sub-folder.
    """

    name: Annotated[
        str,
        Implied(strategy=ImpliedStrategy.FOLDER_NAME),
    ] = Field()
    switch_config: Annotated[
        SwitchConfig,
        External(
            output_structure=OutputStrategy.SINGLE_FILE | OutputStrategy.OMMIT_ROOT,
            naming_strategy=NamingStrategy.FIXED_PATH,
            path="switch",
        ),
    ] = Field()
    host_controller: Annotated[
        Optional[Controller],
        External(
            output_structure=OutputStrategy.FOLDER,
            naming_strategy=NamingStrategy.FIXED_PATH,
            path="switch_host_controller",
        ),
    ] = Field(default=None)

    @property
    def meta(self) -> EmbeddedMetadata:
        """Proxy to the underlying switch config metadata."""
        return self.switch_config.meta

    @property
    def tcam_rules(self) -> Optional[List[TCAMRule]]:
        """Proxy to the underlying switch config TCAM rules."""
        return self.switch_config.tcam_rules

    @property
    def ports(self) -> List[SwitchPort]:
        """Proxy to the underlying switch config ports."""
        return self.switch_config.ports

    @property
    def vlans(self) -> List[VLANEntry]:
        """Proxy to the underlying switch config VLANs."""
        return self.switch_config.vlans

    @property
    def port_extenders(self) -> List[PortExtender]:
        """Proxy to the underlying switch config port extenders."""
        return self.switch_config.port_extenders or []

    @model_validator(mode="after")
    def validate_unique_port_number(self) -> Self:
        """
        Validate if the silicon port numbers for all the different switch ports are unique

        Raises:
            Validation error if a silicon port number is repeated
        """

        silicon_port_numbers = []
        for port in self.ports:
            silicon_port_numbers.append(port.silicon_port_no)
        validate_list_items_unique(
            silicon_port_numbers,
            "Switch Ports (silicon_port_number)",
        )
        return self

    @model_validator(mode="after")
    def validate_unique_port_names(self) -> Self:
        """Validate port names are unique across this switch's ports."""
        validate_list_items_unique(
            [p.name for p in self.ports],
            "Switch Ports (name)",
        )
        return self

    @property
    def extender_uplink_ports(self) -> frozenset[str]:
        """Names of the switch ports that terminate an extender uplink."""
        return get_extender_uplink_ports(self)

    @model_validator(mode="after")
    def validate_unique_extender_names(self) -> Self:
        """
        Validate that extender names are unique within this switch.

        Raises:
            err_major: Two extenders share a name.
        """

        validate_extender_names(self)
        return self

    @model_validator(mode="after")
    def validate_extender_ports(self) -> Self:
        """
        Validate that every listed extender port is a port of this switch and is listed once.

        Raises:
            err_major: An extender lists an unknown port.

            err_major: A port is listed twice.
        """

        validate_extender_port_references(self)
        return self

    @model_validator(mode="after")
    def validate_extender_uplinks(self) -> Self:
        """
        Validate the uplink port of every extender.

        Raises:
            err_major: Two extenders share an uplink port.

            err_major: The uplink port is not a port of this switch.

            err_major: The uplink port sits on another extender (cascading is not supported).
        """

        validate_extender_uplinks(self)
        return self

    @model_validator(mode="after")
    def validate_extender_port_channels(self) -> Self:
        """
        Validate how an extender port reaches the uplink.

        On a channelized uplink a port needs ``mii_subport_of`` (the uplink port) and ``mii_subport_id``. On a tagged uplink it sets neither
        nor ``mii_config``.

        Raises:
            err_major: A channelized extender port lacks ``mii_subport_of`` or ``mii_subport_id``.

            err_major: A tagged extender port sets ``mii_config``, ``mii_subport_of`` or ``mii_subport_id``.
        """

        validate_extender_port_channels(self)
        return self

    @model_validator(mode="after")
    def validate_extender_uplink_links(self) -> Self:
        """
        Validate both ends of every uplink against the uplink type.

        The ends are checked like any xMII link (opposite modes, same type and speed). A channelized uplink also needs a multi-port lane
        with matching channels, and a tagged uplink a single-port xMII.

        Raises:
            err_major: The ends differ in mode, speed or type, or one has no xMII.

            err_major: A channelized uplink does not use a multi-port lane.

            err_major: A tagged uplink uses a multi-port lane.

            err_major: The lane channels differ between the two ends.
        """

        validate_extender_uplink_links(self)
        return self

    @model_validator(mode="after")
    def warn_extender_without_ports(self) -> Self:
        """Warn about an extender without ports."""

        warn_extender_without_ports(self)
        return self

    @model_validator(mode="after")
    def validate_uplink_port_usage(self) -> Self:
        """
        Raise err_minor on forwarding or TSN configuration on an uplink port.

        The uplink port is a lane to the extender, not a forwarding endpoint.
        """

        validate_uplink_port_usage(self)
        return self

    @model_validator(mode="after")
    def validate_mii_subports(self) -> Self:
        """Validate mii_subport_of/mii_subport_id references between this switch's ports."""
        lanes = get_channelized_uplink_ports(self)
        validate_mii_subports(self.ports, "Switch Ports", lanes)
        return self

    def _has_stream_with_ipv(self, ipv: int) -> bool:
        """
        Check whether any ingress stream on any port of this switch uses the given internal priority value.

        Args:
            ipv: The internal priority value to look for.

        Returns:
            bool: True if a matching ingress stream exists, False otherwise.
        """

        return any(stream.ipv == ipv for p in self.ports for stream in (p.ingress_streams or []))

    def _has_ats_stream(self) -> bool:
        """
        Check whether any ingress stream on any port of this switch defines an ATS instance.

        Returns:
            bool: True if an ingress stream with an ATS instance exists, False otherwise.
        """

        return any(stream.ats for p in self.ports for stream in (p.ingress_streams or []))

    @model_validator(mode="after")
    def validate_ipv_mapping(self) -> Self:
        """
        Check if internal priority value of traffic classes is defined in ingress streams
        """

        for port in self.ports:
            for tr in port.traffic_classes or []:
                for iv in tr.internal_priority_values or []:
                    if not self._has_stream_with_ipv(iv):
                        raise err_minor(
                            f"Not able to find any streams with internal priority values {iv}. Traffic class {tr.name}",
                            category=Category.REFERENCE,
                            error_number="090",
                        )
        return self

    @model_validator(mode="after")
    def validate_ats_instances(self) -> Self:
        """
        Check if the shaper is ATS, the instance is defined # on some port on ingress

        Raises:
            err_minor: No ATS Instance found for traffic class

        Returns:
            _type_: Self
        """

        for port in self.ports:
            for tr in port.traffic_classes or []:
                if tr.selection_mechanisms and tr.selection_mechanisms.type == "ats" and not self._has_ats_stream():
                    raise err_minor(f"No ATS Instance found for traffic class {tr.name}", category=Category.REFERENCE, error_number="091")

        return self

    @model_validator(mode="after")
    def validate_ports_in_tcam_exist(self) -> Self:
        """
        Validate that every port referenced in TCAM rules exists on the switch.

        Raises:
            err_minor: If a port listed in a TCAM rule (match_ports or action.ports) is not present in the switch's port list.
        """

        if not self.tcam_rules:
            return self
        switch_port_names = [port.name for port in self.ports]
        tcam_ports: list[str] = []
        for tcam_rule in self.tcam_rules:
            tcam_ports += tcam_rule.match_ports or []
            for action in tcam_rule.action or []:
                tcam_ports += action.ports or []

        validate_elements_in(
            tcam_ports,
            switch_port_names,
            "TCAM Ports must exist on the Switch.",
        )
        return self

    @model_validator(mode="after")
    def validate_ports_in_vlan_entries_exist(self) -> Self:
        """
        Validate that every port referenced in VLAN entries exists on the switch.

        Raises:
            err_minor: If a port listed in a VLAN entry (ports or multicast.ports) is not present in the switch's port list.
        """

        if not self.vlans:
            return self
        switch_port_names = [port.name for port in self.ports]
        vlan_ports = []
        for vlan_entry in self.vlans:
            vlan_ports += vlan_entry.ports
            for multicast_group in vlan_entry.multicast or []:
                vlan_ports += multicast_group.ports

        validate_elements_in(
            vlan_ports,
            switch_port_names,
            "VLAN Ports must exist on the Switch.",
        )
        return self

    @model_validator(mode="after")
    def validate_tcam_ids_unique(self) -> Self:
        """
        Validate that each TCAM rule has a unique identifier.

        Raises:
            err_minor: Duplicate ``id`` values found among the TCAM rules.
        """

        ids = [tcam.id for tcam in (self.tcam_rules or [])]
        validate_list_items_unique(ids, "tcam_rules (id)")
        return self

    @model_validator(mode="after")
    def validate_tcam_name_unique(self) -> Self:
        """
        Validate that each TCAM rule has a unique name.

        Raises:
            err_minor: Duplicate ``name`` values found among the TCAM rules.
        """

        names = [tcam.name for tcam in (self.tcam_rules or [])]
        validate_list_items_unique(names, "tcam_rules (name)")

        return self

    def get_mac(self) -> FLYNCMacAddress | None:
        """Return MAC address from the host controller's first ethernet interface."""
        host = self.host_controller
        if host is None:
            return None
        macs = host.get_all_macs()
        return macs[0] if macs else None

    def find_switch_port(self, port_name: str) -> SwitchPort:
        return next(p for p in self.ports if p.name == port_name)

    def find_port_extender(self, extender_name: str) -> Optional[PortExtender]:
        """Return the port extender with the given name, or ``None``."""
        return next((extender for extender in self.port_extenders or [] if extender.name == extender_name), None)

    def model_post_init(self, __context: object) -> None:
        for port in self.ports:
            port._switch = self

        bind_port_extenders(self)

        self._fill_empty_tcam_port_lists()
        super().model_post_init(__context)

    def _fill_empty_tcam_port_lists(self) -> None:
        """
        Fill empty or omitted port lists in TCAM rules with all available switch ports.

        The expanded list is assigned directly via ``object.__setattr__`` so it is fully
        accessible at runtime without being recorded in the model's "fields set". This keeps
        serialization faithful to the user's original input: the field serializers on
        :class:`TCAMRule` and :class:`PortScopedAction` dump an explicit empty list as ``[]``,
        while an omitted list stays omitted (under ``exclude_unset``).
        """
        if not self.tcam_rules:
            return

        # "All ports" leaves out extender uplinks: they are lanes.
        uplinks = self.extender_uplink_ports
        all_port_names = [port.name for port in self.ports if port.name not in uplinks]

        for rule in self.tcam_rules:
            if not rule.match_ports:
                object.__setattr__(rule, "match_ports", all_port_names.copy())
                object.__setattr__(rule, "_match_ports_autofilled", True)

            for action in rule.action:
                if not action.ports:
                    object.__setattr__(action, "ports", all_port_names.copy())
                    object.__setattr__(action, "_ports_autofilled", True)

            # The port-based exclusivity checks ran on the (still empty) user input, so re-run them on the expanded lists.
            rule._check_exclusive_drop_force_mirror()
            rule._check_exclusive_vlan_action()
