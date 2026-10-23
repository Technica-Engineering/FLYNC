"""
Validators for the compatibility of interface/connection settings between two
components: MII, MACsec, gPTP, HTB, CBS/ingress streams and VLAN uniqueness.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING, Protocol

from flync.core.utils.exceptions import Category, err_major, err_minor
from flync.core.validators.generic import validate_list_items_unique
from flync.model.flync_4_ecu.mii import USGMII, USXGMII, XMIIConfig, mii_carries_mdi_speed

if TYPE_CHECKING:
    from flync.model.flync_4_ecu.controller import VirtualControllerInterface
    from flync.model.flync_4_ecu.phy import BASET, BASET1, BASET1S
    from flync.model.flync_4_ecu.port import ECUPort
    from flync.model.flync_4_ecu.switch import SwitchPort
    from flync.model.flync_4_security import MACsecConfig
    from flync.model.flync_4_tsn import HTBInstance, PTPConfig, Stream, TrafficClass

    type MIIPort = ECUPort | SwitchPort
    type MDIConfig = BASET1 | BASET1S | BASET


# The compatibility checks only read a few attributes of the components they compare (an ECU port, a switch port, an interface
# configuration...). These protocols name exactly those attributes, so the validators do not depend on the concrete model classes.
class Named(Protocol):
    """A component that can be named in an error message (an interface configuration is unnamed until its interface binds it)."""

    @property
    def name(self) -> str | None: ...


class HasMIIConfig(Named, Protocol):
    """A component that may carry an MII configuration."""

    @property
    def mii_config(self) -> XMIIConfig | None: ...


class HasMACsecConfig(Named, Protocol):
    """A component that may carry a MACsec configuration."""

    @property
    def macsec_config(self) -> MACsecConfig | None: ...


class HasPTPConfig(Named, Protocol):
    """A component that may carry a PTP configuration."""

    @property
    def ptp_config(self) -> PTPConfig | None: ...


class HasHTB(Named, Protocol):
    """A component that may carry an HTB configuration."""

    @property
    def htb(self) -> HTBInstance | None: ...


def validate_ingress_streams_fields(streams: Sequence[Stream], location: str) -> Sequence[Stream]:
    """
    Raise err_minor if any stream carries an ipv or ats value.

    ``location`` is a human-readable label such as ``"compute node"`` or ``"controller interface"`` used in the error message.
    """

    for ingress_stream in streams:
        if ingress_stream.ipv is not None:
            raise err_minor(
                f"Validation Error in Ingress Streams. "
                f"Removing config from the interface. "
                f"Ingress stream {ingress_stream.name} "
                f"at the {location} should not have an ipv value.",
                category=Category.CONSISTENCY,
                error_number="007",
            )
        if ingress_stream.ats is not None:
            raise err_minor(
                f"Validation Error in Ingress Streams. "
                f"Removing config from the interface. "
                f"Ingress stream {ingress_stream.name} at the "
                f"{location} should not have an ats value",
                category=Category.CONSISTENCY,
                error_number="008",
            )
    return streams


def validate_vlan_ids_unique(virtual_interfaces: Iterable[VirtualControllerInterface], name: str | None) -> None:
    """
    Raise err_major if any VLAN ID appears more than once.
    """

    all_vlans = [vi.vlanid for vi in virtual_interfaces]
    list_label = "VLAN IDs of virtual Controller Interface" + (f" in interface {name}" if name else "")
    validate_list_items_unique(all_vlans, list_label)


def validate_cbs_idleslopes_fit_portspeed(traffic_classes: list[TrafficClass] | None, port_speed: int | None) -> list[TrafficClass] | None:
    """
    Custom Validator for a list of Traffic Classes to check conformity to MII/MDI speed.

    Args:
        traffic_classes (list): List of element type `TrafficClass`.

        port_speed (int): MII or MDI speed of the port.

    Raises:
        err_major: The sum of idleslopes of all shapers on one port must be equal or lower than the port speed.

    Returns:
        list: Return list of traffic classes as received.
    """

    if not traffic_classes:
        return None
    if not port_speed:
        raise err_major(
            "Cannot validate Traffic Classes! No port speed defined. Make sure to configure MII or MDI.",
            category=Category.REQUIRED,
            error_number="010",
        )

    sum_idleslopes = 0

    for tr_class in traffic_classes:
        if tr_class.selection_mechanisms and tr_class.selection_mechanisms.type == "cbs":
            sum_idleslopes += tr_class.selection_mechanisms.idleslope

    if sum_idleslopes > port_speed * 1000:
        raise err_major(
            ("The sum of idleslopes of all shapers on one port" + " cannot be higher than the link speed!"),
            category=Category.CONSISTENCY,
            error_number="011",
        )
    return traffic_classes


def validate_optional_mii_config_compatibility(comp1: HasMIIConfig | None, comp2: HasMIIConfig | None, id: str) -> None:
    """
    Custom validator for optional MII configuration compatibility between two components.

    Args:
        comp1 (object): First component that may contain a ``mii_config`` attribute.

        comp2 (object): Second component that may contain a ``mii_config`` attribute.

        id (str): Identifier of the connection (used only in error messages).

    Raises:
        err_major: One component has an MII config while the other does not.

        err_major: Both components have an MII config but the *mode* values are identical. The modes must differ.

        err_major: Both components have an MII config but the *speed* values are different.

        err_major: Both components have an MII config but the *type* values are different.
    """

    if comp1 is None or comp2 is None:
        return

    mii_comp1 = comp1.mii_config
    mii_comp2 = comp2.mii_config

    # Neither side specifies MII
    if mii_comp1 is None and mii_comp2 is None:
        return

    # Look for wrong config variants: exactly one side declares an MII config
    if mii_comp1 is None or mii_comp2 is None:
        raise err_major(
            f"Invalid MII config in connection {id}: "
            f"{comp1.name} ↔ {comp2.name} "
            f"(MII mismatch for PHY type). Both or None of "
            f"the components should have a MII config",
            category=Category.COMPATIBILITY,
            error_number="012",
        )

    # Both sides use MII, so let us check it:
    _check_mii_pair_compatibility(comp1, comp2, mii_comp1, mii_comp2, id)


def _check_mii_pair_compatibility(
    comp1: Named,
    comp2: Named,
    mii_comp1: XMIIConfig,
    mii_comp2: XMIIConfig,
    id: str,
) -> None:
    """
    Compare the MII settings of two components that both carry an MII config.

    Args:
        comp1 (object): First component (used only in error messages).

        comp2 (object): Second component (used only in error messages).

        mii_comp1 (object): ``mii_config`` of ``comp1``.

        mii_comp2 (object): ``mii_config`` of ``comp2``.

        id (str): Identifier of the connection (used only in error messages).

    Raises:
        err_major: The *mode* values are identical. The modes must differ.

        err_major: The *speed* values are different.

        err_major: The *type* values are different.
    """

    if mii_comp1.mode == mii_comp2.mode:
        raise err_major(
            f"Incompatible MII Mode: {comp1.name} ({mii_comp1.mode}) ↔ {comp2.name}({mii_comp2.mode})",
            category=Category.COMPATIBILITY,
            error_number="013",
        )
    if mii_comp1.speed is not None and mii_comp2.speed is not None and mii_comp1.speed != mii_comp2.speed:
        raise err_major(
            f"Incompatible MII Speed: {comp1.name} ({mii_comp1.speed}) ↔ {comp2.name}({mii_comp2.speed})",
            category=Category.COMPATIBILITY,
            error_number="014",
        )
    if mii_comp1.type != mii_comp2.type:
        raise err_major(
            f"Incompatible MII Type: {comp1.name} ({mii_comp1.type}) ↔ {comp2.name}({mii_comp2.type})",
            category=Category.COMPATIBILITY,
            error_number="015",
        )


def validate_compulsory_mii_config_compatibility(comp1: HasMIIConfig, comp2: HasMIIConfig, id: str) -> None:
    """
    Validator that enforces a **mandatory** MII configuration on both components and then checks optional compatibility.

    Args:
        comp1 (object): First component. Must have ``mii_config``.

        comp2 (object): Second component. Must have ``mii_config``.

        id (str): Identifier of the connection (used only in error messages).

    Raises:
        err_major: Either component is missing a required MII configuration.

        err_major: Propagated from :func:`validate_optional_mii_config_compatibility` when the optional checks fail.
    """

    if not comp1.mii_config or not comp2.mii_config:
        raise err_major(
            f"Invalid MII config in connection {id}: {comp1.name} ↔ {comp2.name} (MII configuration missing).",
            category=Category.COMPATIBILITY,
            error_number="016",
        )
    validate_optional_mii_config_compatibility(comp1, comp2, id)


def validate_htb(comp: HasHTB | None, speed: int | None) -> None:
    """
    Validator that checks an HTB (Hierarchical Token Bucket) configuration against the physical link speed.

    Args:
        comp (object): Component that owns an ``htb`` attribute with ``child_classes``.

        speed (int): Link speed of the interface (same unit as the HTB rates).

    Raises:
        err_major: The sum of the ``rate`` values of all child classes exceeds the provided ``speed``.
    """

    if not comp or not speed or not comp.htb:
        return
    sum_child_rates = sum(child.rate for child in comp.htb.child_classes)
    if sum_child_rates > speed:
        raise err_major(
            f"Incompatible HTB config for {comp.name}: sum of all child class rates {sum_child_rates} should be less than link speed {speed}",
            category=Category.CONSISTENCY,
            error_number="017",
        )


def validate_macsec(comp1: HasMACsecConfig | None, comp2: HasMACsecConfig | None, id: str) -> None:
    """
    Validator for MACsec configuration compatibility between two components.

    Args:
        comp1 (object): First component: May contain a ``macsec_config``.

        comp2 (object): Second component: May contain a ``macsec_config``.

        id (str): Identifier of the connection (used only in error messages).

    Raises:
        err_major: One component has a MACsec config while the other does not.

        err_major: MKA (Key Agreement) enabled state differs between the two components.

        err_major: ``macsec_mode`` differs between the two components.
    """

    if comp1 is None or comp2 is None:
        return

    macsec1 = comp1.macsec_config
    macsec2 = comp2.macsec_config

    # Neither side uses MACsec
    if macsec1 is None and macsec2 is None:
        return

    # Look for wrong config variants: exactly one side declares a MACsec config
    if macsec1 is None or macsec2 is None:
        configured, unconfigured = (comp1, comp2) if macsec1 is not None else (comp2, comp1)
        raise err_major(
            f"Incomplete MACsec config in connection {id}: {configured.name} has a macsec config "
            f"but {unconfigured.name} does not. Both or none of the components should have one.",
            category=Category.COMPATIBILITY,
            error_number="018",
        )

    # Both sides use MACsec, so let us check it:
    _check_macsec_pair_compatibility(comp1, comp2, macsec1, macsec2, id)


def _check_macsec_pair_compatibility(comp1: Named, comp2: Named, macsec1: MACsecConfig, macsec2: MACsecConfig, id: str) -> None:
    """
    Compare the MACsec settings of two components that both carry a MACsec config.

    Args:
        comp1 (object): First component (used only in error messages).

        comp2 (object): Second component (used only in error messages).

        macsec1 (object): ``macsec_config`` of ``comp1``.

        macsec2 (object): ``macsec_config`` of ``comp2``.

        id (str): Identifier of the connection (used only in error messages).

    Raises:
        err_major: MKA (Key Agreement) enabled state differs between the two components.

        err_major: ``macsec_mode`` differs between the two components.
    """

    if (not macsec1.mka_enabled and macsec2.mka_enabled) or (macsec1.mka_enabled and not macsec2.mka_enabled):
        raise err_major(
            f"MACsec should be enabled in both - {comp1.name} and {comp2.name} in connection {id} ",
            category=Category.COMPATIBILITY,
            error_number="019",
        )

    if macsec1.macsec_mode != macsec2.macsec_mode:
        raise err_major(
            f"Both {comp1.name} and {comp2.name} should have the same macsec_mode. in connection {id} ",
            category=Category.COMPATIBILITY,
            error_number="020",
        )


def validate_gptp(comp1: HasPTPConfig | None, comp2: HasPTPConfig | None, id: str) -> None:
    """
    Validator that checks gPTP (generic Precision Time Protocol) configuration compatibility between two components.

    Args:
        comp1 (object): First component. May contain a ``ptp_config``.

        comp2 (object): Second component. May contain a ``ptp_config``.

        id (str): Identifier of the connection (used only in error messages).

    Raises:
        err_major: PTP configuration present on one side only.

        err_major: Mismatch of the ``cmlds_linkport_enabled`` flag between the two components.

        err_major: Propagated from :func:`validate_gptp_domains` when domain level checks fail.
    """

    if comp1 is None or comp2 is None:
        return

    ptp1 = comp1.ptp_config
    ptp2 = comp2.ptp_config

    if bool(ptp1) != bool(ptp2):
        raise err_major(
            f"Incompatible PTP config. PTP config not present in either {comp1.name} or  {comp2.name} in connection {id} ",
            category=Category.COMPATIBILITY,
            error_number="021",
        )

    # Neither side uses PTP, so there is nothing to compare
    if not ptp1 or not ptp2:
        return

    validate_gptp_domains(comp1, comp2, ptp1, ptp2, id)
    validate_gptp_domains(comp2, comp1, ptp2, ptp1, id)

    if ptp1.cmlds_linkport_enabled != ptp2.cmlds_linkport_enabled:
        raise err_major(
            f"CMLDS mismatch: {comp1.name} has "
            f"cmlds_linkport_enabled="
            f"{ptp1.cmlds_linkport_enabled}, but "
            f"{comp2.name} has "
            f"{ptp2.cmlds_linkport_enabled}",
            category=Category.COMPATIBILITY,
            error_number="022",
        )


def validate_gptp_domains(comp1: Named | None, comp2: Named | None, ptp1: PTPConfig | None, ptp2: PTPConfig | None, id: str) -> None:
    """
    Helper that validates matching PTP domains and sync-config types between two components.

    Args:
        comp1 (object): First component (source of ``ptp1``).

        comp2 (object): Second component (source of ``ptp2``).

        ptp1 (object): ``ptp_config`` of ``comp1``.

        ptp2 (object): ``ptp_config`` of ``comp2``.

        id (str): Identifier of the connection (used only in error messages).

    Raises:
        err_major: A domain present in ``ptp1`` is missing in ``ptp2``.

        err_major: The ``sync_config.type`` of a matching domain is identical on both sides (they must differ for a valid configuration).
    """

    if not comp1 or not comp2 or not ptp1 or not ptp2:
        return

    for ptp_port_iface in ptp1.ptp_ports:
        domain = ptp_port_iface.domain_id
        ptp_port_iface2 = next(
            (p for p in ptp2.ptp_ports if p.domain_id == domain),
            None,
        )
        if ptp_port_iface2 is None:
            raise err_major(
                f"Incompatible PTP Config: Domain {domain} not present in {comp2.name} in connection {id}",
                category=Category.COMPATIBILITY,
                error_number="023",
            )
        if ptp_port_iface.sync_config and ptp_port_iface2.sync_config and ptp_port_iface.sync_config.type == ptp_port_iface2.sync_config.type:
            raise err_major(
                f"Incompatible PTP Config: Domain ID {domain} in {comp1.name} and {comp2.name} in connection {id}",
                category=Category.COMPATIBILITY,
                error_number="024",
            )


def validate_mii_subports(ports: Sequence[MIIPort], label: str, uplink_ports: frozenset[str] = frozenset()) -> None:
    """
    Validate ``mii_subport_of``/``mii_subport_id`` references between ports sharing a multi-port xMII link
    (see :class:`~flync.model.flync_4_ecu.mii.USXGMII`/:class:`~flync.model.flync_4_ecu.mii.USGMII`).

    Args:
        ports (list): Ports to check, each exposing ``name``, ``mii_config``, ``mii_subport_of``, ``mii_subport_id``.

        label (str): Human-readable label for the owning port list (used in error messages).

        uplink_ports (frozenset[str]): Names of ports that terminate the channelized uplink of a port extender. Such a port is a
            pure lane: it carries the multi-port link but occupies none of its channels, which the extender ports claim instead.

    Raises:
        err_major: A port sets both ``mii_config`` and ``mii_subport_of``.

        err_major: ``mii_subport_of`` does not name another port in ``ports``.

        err_major: The referenced port's ``mii_config`` is not a multi-port USXGMII/USGMII link.

        err_major: ``mii_subport_id`` is not one of the referenced link's channel ``subport_id`` values.

        err_major: A port carrying a multi-port link has a ``mii_subport_id`` (default 0) that is not one of its own channels.

        err_major: Two ports claim the same channel of the same link. The port carrying the link claims the channel
            named by its own ``mii_subport_id`` (default 0); subports claim the others.

        err_major: A listed channel is claimed by no port.

        err_major: A port's ``mdi_config`` speed (the carrying port's included) is one its channel cannot carry (the rule of
            :meth:`~flync.model.flync_4_ecu.port.ECUPort.verify_mdi_and_mii_config_speeds_are_compatible`, applied per channel).
            Skipped for a port that has no ``mdi_config`` of its own yet, such as a switch port.
    """

    by_name = {port.name: port for port in ports}
    claimed: list[tuple[str, int]] = []
    subports: list[tuple[MIIPort, MIIPort]] = []

    for port in ports:
        if port.mii_subport_of is None:
            continue
        sibling = _resolve_subport_link(port, port.mii_subport_of, by_name, label)
        claimed.append((port.mii_subport_of, port.mii_subport_id or 0))
        subports.append((port, sibling))

    # The port carrying a link occupies one of its channels too: the one named by its own mii_subport_id, default 0.
    for port in ports:
        if not isinstance(port.mii_config, (USXGMII, USGMII)) or port.name in uplink_ports:
            continue
        own_channel = _own_channel(port, port.mii_config, label)
        claimed.append((port.name, own_channel))
        subports.append((port, port))

    validate_list_items_unique(claimed, f"{label} mii_subport_of/mii_subport_id")

    claimed_set = set(claimed)
    for port in ports:
        if isinstance(port.mii_config, (USXGMII, USGMII)):
            _validate_channels_claimed(port, port.mii_config, claimed_set, label)

    for port, link in subports:
        mdi_config = getattr(port, "mdi_config", None)
        if mdi_config is not None:
            validate_mdi_speed_fits_channel(label, port, link, mdi_config)


def _resolve_subport_link(port: MIIPort, subport_of: str, by_name: dict[str, MIIPort], label: str) -> MIIPort:
    """
    Resolve and validate the multi-port link a subport refers to via ``mii_subport_of``.

    Args:
        port (object): The port that sets ``mii_subport_of``.

        subport_of (str): The value of that ``mii_subport_of``.

        by_name (dict): Ports of the owning list, keyed by name.

        label (str): Human-readable label for the owning port list (used in error messages).

    Returns:
        object: The port carrying the referenced multi-port link.

    Raises:
        err_major: ``port`` also sets ``mii_config``, the reference is not another port, the referenced port carries no
            multi-port link, or ``mii_subport_id`` is not one of the link's channels.
    """

    if port.mii_config is not None:
        raise err_major(
            "{label} '{port}' sets both mii_config and mii_subport_of; a channel of a shared multi-port link does not have its own mii_config.",
            label=label,
            port=port.name,
            category=Category.CONSISTENCY,
            error_number="383",
        )

    sibling = by_name.get(subport_of)
    if sibling is None or sibling.name == port.name:
        raise err_major(
            "{label} '{port}' has mii_subport_of '{subport_of}', which is not another port in {label}.",
            label=label,
            port=port.name,
            subport_of=port.mii_subport_of,
            category=Category.REFERENCE,
            error_number="384",
        )

    if not isinstance(sibling.mii_config, (USXGMII, USGMII)):
        raise err_major(
            "{label} '{port}' has mii_subport_of '{sibling}', which does not carry a multi-port USXGMII/USGMII link.",
            label=label,
            port=port.name,
            sibling=sibling.name,
            category=Category.COMPATIBILITY,
            error_number="385",
        )

    channel_subport_ids = {channel.subport_id for channel in sibling.mii_config.channels}
    if port.mii_subport_id not in channel_subport_ids:
        raise err_major(
            "{label} '{port}' has mii_subport_id {subport_id}, which is not a channel of '{sibling}' (channels: {channels}).",
            label=label,
            port=port.name,
            subport_id=port.mii_subport_id,
            sibling=sibling.name,
            channels=sorted(channel_subport_ids),
            category=Category.REFERENCE,
            error_number="386",
        )
    return sibling


def _own_channel(port: MIIPort, lane: USXGMII | USGMII, label: str) -> int:
    """
    Return the channel a port carrying a multi-port link occupies, checking that it exists.

    Args:
        port (object): Port whose ``mii_config`` is a multi-port link.

        lane (object): That multi-port link.

        label (str): Human-readable label for the owning port list (used in error messages).

    Returns:
        int: The ``mii_subport_id`` of the port (default 0).

    Raises:
        err_major: The channel is not one of the link's own channels.
    """

    own_channel = port.mii_subport_id or 0
    own_channel_ids = sorted(channel.subport_id for channel in lane.channels)
    if own_channel not in own_channel_ids:
        raise err_major(
            "{label} '{port}' carries a multi-port link and occupies channel {channel} (mii_subport_id, default 0), "
            "which is not one of its channels ({channels}).",
            label=label,
            port=port.name,
            channel=own_channel,
            channels=own_channel_ids,
            category=Category.REFERENCE,
            error_number="389",
        )
    return own_channel


def _validate_channels_claimed(port: MIIPort, lane: USXGMII | USGMII, claimed_set: set[tuple[str, int]], label: str) -> None:
    """
    Check that every channel of a port's multi-port link is claimed by some port.

    Args:
        port (object): Port whose ``mii_config`` is a multi-port link.

        lane (object): That multi-port link.

        claimed_set (set): ``(port name, channel id)`` pairs claimed across the port list.

        label (str): Human-readable label for the owning port list (used in error messages).

    Raises:
        err_major: A channel of the link is claimed by no port.
    """

    unclaimed = sorted(c.subport_id for c in lane.channels if (port.name, c.subport_id) not in claimed_set)
    if unclaimed:
        raise err_major(
            "{label} '{port}' carries a multi-port link whose channel(s) {unclaimed} are not claimed by any port. "
            "Every channel needs exactly one port with a matching mii_subport_of/mii_subport_id.",
            label=label,
            port=port.name,
            unclaimed=unclaimed,
            category=Category.CONSISTENCY,
            error_number="387",
        )


def validate_mdi_speed_fits_channel(label: str, port: MIIPort, link: MIIPort, mdi_config: MDIConfig) -> None:
    """
    Check that the channel a port occupies on a multi-port xMII link can carry the port's MDI speed.

    This is the rule of :meth:`~flync.model.flync_4_ecu.port.ECUPort.verify_mdi_and_mii_config_speeds_are_compatible`, applied to
    one channel of the link.

    Args:
        label (str): Human-readable label for the owning port list (used in error messages).

        port (object): The port whose channel is checked; its ``mii_subport_id`` (default 0) picks the channel.

        link (object): The port whose ``mii_config`` is the multi-port link (``port`` itself when it carries the link).

        mdi_config (object): MDI configuration whose ``speed`` is compared against the channel.

    Raises:
        err_major: The channel's speed is lower than the MDI speed.
    """

    lane = link.mii_config
    if not isinstance(lane, (USXGMII, USGMII)):
        return
    channel = next(c for c in lane.channels if c.subport_id == (port.mii_subport_id or 0))
    if not mii_carries_mdi_speed(lane, mdi_config.speed, channel.speed):
        raise err_major(
            "{label} '{port}' has an MDI speed of {mdi_speed} Mbps, which channel {subport_id} of '{link}' ({channel_speed} Mbps) cannot carry.",
            label=label,
            port=port.name,
            mdi_speed=mdi_config.speed,
            subport_id=channel.subport_id,
            link=link.name,
            channel_speed=channel.speed,
            category=Category.CONSISTENCY,
            error_number="388",
        )


def validate_switch_port_mdi_speed(switch_port: SwitchPort) -> None:
    """
    Check a switch port's MDI speed against the xMII it sits on, once the MDI config has been copied in.

    ``SwitchPort.mdi_config`` is only set when the internal topology binds a connection, so
    :func:`validate_mii_subports` cannot see it; this runs after that step. It covers a port that carries a multi-port link
    (its own channel), a subport (the channel it claims on the sibling's link) and a port with a plain single-port xMII.

    Args:
        switch_port (object): The switch port, already holding its ``mdi_config``. Nothing is checked while that is ``None``.

    Raises:
        err_major: The xMII, or the channel the port occupies, cannot carry the MDI speed.
    """

    mdi_config = switch_port.mdi_config
    if mdi_config is None:
        return

    label = "Switch Ports"
    link = None
    if isinstance(switch_port.mii_config, (USXGMII, USGMII)):
        link = switch_port
    elif switch_port.mii_subport_of is not None:
        link = next((p for p in switch_port.get_switch().ports if p.name == switch_port.mii_subport_of), None)

    if link is not None and isinstance(link.mii_config, (USXGMII, USGMII)):
        validate_mdi_speed_fits_channel(label, switch_port, link, mdi_config)
        return

    mii_config = switch_port.mii_config
    if mii_config is not None and mii_config.speed is not None and not mii_carries_mdi_speed(mii_config, mdi_config.speed):
        raise err_major(
            "{label} '{port}' has an MDI speed of {mdi_speed} Mbps, which its MII config ({mii_speed} Mbps) cannot carry.",
            label=label,
            port=switch_port.name,
            mdi_speed=mdi_config.speed,
            mii_speed=mii_config.speed,
            category=Category.CONSISTENCY,
            error_number="390",
        )
