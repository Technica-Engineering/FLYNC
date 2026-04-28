"""
Common Validators are validation methods that are used throughout \
the whole FLYNC model.
The Validators either raise minor, major or fatal errors as
pydantic usage proposes.
"""

from ipaddress import IPv4Address, IPv6Address
from typing import Any, Iterable, Optional

from pydantic import TypeAdapter, ValidationError, ValidationInfo

import flync.core.utils.base_utils as utils
from flync.core.utils.exceptions import (
    _validation_warnings,
    err_major,
    err_minor,
)

_LOCATION_SYSTEM = "in system"


def _resolve_location(info: ValidationInfo) -> str:
    """Return a human-readable location string from validation context."""
    data = info.data if hasattr(info, "data") and info.data else {}
    parent_name = data.get("name")
    if parent_name:
        return f"in {parent_name}"
    if "vlan_id" in data:
        return f"for VLAN Id {data['vlan_id']}"
    return _LOCATION_SYSTEM


def validate_or_remove(label: str, field_type: Any, severity: str = "minor"):
    """Factory that returns a BeforeValidator for sub-model fields.

    Use inside ``Annotated`` to pre-validate a field before Pydantic processes
    it.  If the raw data fails validation all sub-errors are packed into a
    single error.

    - ``"minor"`` severity: the field is removed and the parent model still
      loads without it.  The message says "Removing {label}…".
    - ``"major"`` severity: the parent model will fail regardless (the field
      is required).  The message reports the validation failure without
      implying graceful removal.

    The parent object's ``name`` field is included in the error message when
    available via ``info.data``.

    Parameters
    ----------
    label : str
        Human-readable field label used in the error message.
    field_type : Any
        Pydantic-compatible type to validate the data against.
    severity : str, optional
        Error severity — ``"minor"`` (default) or ``"major"``.

    Returns
    -------
    Callable
        A two-argument validator ``(data, info)`` ready for use with
        ``BeforeValidator``.
    """

    err_fn = err_major if severity == "major" else err_minor

    def _validator(data, info: ValidationInfo):
        """Validate ``data`` against ``field_type`` and raise on failure.

        Returns ``None`` unchanged.  On validation failure, packs all
        sub-errors into a single ``err_fn`` error whose message includes
        the parent object's name (read from ``info.data``) when available.
        """
        if data is None:
            return None
        try:
            TypeAdapter(field_type).validate_python(data)
        except ValidationError as ve:
            parent_name = (
                info.data.get("name")
                if hasattr(info, "data") and info.data
                else None
            )
            location = f"in {parent_name}" if parent_name else _LOCATION_SYSTEM
            sub_errors = "\n".join(
                "{loc}: {msg}".format(
                    loc=".".join(str(x) for x in e.get("loc", ())),
                    msg=e.get("msg", ""),
                )
                for e in ve.errors()
            )
            if severity == "major":
                raise err_fn(
                    f"Validation failed for {label} {location}.",
                    sub_errors=sub_errors,
                )
            raise err_fn(
                f"1 or more errors found while validating {label}. "
                f"Removing {label} {location}.",
                sub_errors=sub_errors,
            )
        return data

    return _validator


def validate_list_items_and_remove(
    label: str, item_type: Any, severity: str = "minor"
):
    """Validate each item in a list individually,
    removing only invalid entries.

    Unlike :func:`validate_or_remove`, which discards the entire list when any
    item fails, this validator keeps valid items and removes only those that
    fail validation.  Per-item errors are forwarded to the
    ``_validation_warnings`` channel so they appear in the final error report
    even though the model continues building with the remaining valid items.

    Use inside ``Annotated`` as a ``BeforeValidator``.

    Parameters
    ----------
    label : str
        Human-readable field label used in error messages.
    item_type : Any
        Pydantic-compatible type for each individual list item.
    severity : str, optional
        Error severity for removed items — ``"minor"`` (default) or
        ``"major"``.

    Returns
    -------
    Callable
        A two-argument validator ``(data, info)`` ready for use with
        ``BeforeValidator``.
    """

    def _validator(data, info: ValidationInfo):
        """Validate each item in ``data`` individually, dropping invalid ones.

        Non-list values are returned unchanged.  For each item that fails
        validation an error is raised via ``err_fn``; valid items are
        collected and returned so the parent model loads with a partial list.
        The parent object's name or VLAN ID is included in the message when
        available via ``info.data``.
        """
        if not isinstance(data, list):
            return data
        location = _resolve_location(info)
        field_name = getattr(info, "field_name", None) or label
        adapter = TypeAdapter(item_type)
        valid_items = []
        for idx, item in enumerate(data):
            try:
                adapter.validate_python(item)
                valid_items.append(item)
            except ValidationError as ve:
                sub_errors = "\n".join(
                    "{loc}: {msg}".format(
                        loc=".".join(str(x) for x in e.get("loc", ())),
                        msg=e.get("msg", ""),
                    )
                    for e in ve.errors()
                )
                accumulated = _validation_warnings.get()
                if accumulated is not None:
                    accumulated.append(
                        {
                            "type": severity,
                            "msg": (
                                f"1 or more errors found while validating"
                                f" {label}. Removing {label} {location}."
                            ),
                            "loc": (field_name, idx),
                            "input": item,
                            "ctx": {"sub_errors": sub_errors},
                            "url": "",
                        }
                    )
        return valid_items

    return _validator


def validate_mac_unicast(input: str) -> str:
    """Custom Validator for Unicast MAC addresses.

    Args:
        input (str): MAC address to validate.

    Raises:
        err_minor: Input is not a Unicast address based
        on the expected format.

    Returns:
        Any: Input is handed over.
    """
    is_unicast, msg = utils.is_mac_unicast(input)
    if not is_unicast:
        raise err_minor(msg)
    return input


def validate_mac_multicast(input: str) -> Any:
    """Custom Validator for Multicast MAC addresses.

    Args:
        input (str): MAC address to validate.

    Raises:
        err_minor: Input is not a Multicast address based on the expected
        format.

    Returns:
        Any: Input is handed over.
    """
    is_multicast, msg = utils.is_mac_multicast(input)
    if not is_multicast:
        raise err_minor(msg)
    return input


def validate_ip_multicast(input: IPv4Address | IPv6Address | str) -> Any:
    """Custom Validator for Multicast IP addresses.

    Args:
        input (:class:`IPv4Address` | :class:`IPv6Address`): IP address
        to validate.

    Raises:
        err_minor: Input is not a Multicast address based on the
        expected format.

    Returns:
        Any: Input is handed over.
    """
    is_multicast, msg = utils.is_ip_multicast(input)
    if not is_multicast:
        raise err_minor(msg)
    return input


def validate_any_multicast_address(
    input: IPv4Address | IPv6Address | str,
) -> Any:
    """Custom Validator for Multicast MAC or IP addresses.

    Args:
        input (:class:`IPv4Address` | :class:`IPv6Address` | str):
        IP address or MAC Address to validate.

    Raises:
        err_minor: The address is not a multicast address.

    Returns:
        Any: Input is handed over.
    """
    is_ip, _ = utils.is_ip_address(input)
    if is_ip:
        validate_ip_multicast(input)
    if isinstance(input, str):
        is_mac, _ = utils.is_mac_address(input)
        if is_mac and isinstance(input, str):
            validate_mac_multicast(input)
    return input


def validate_multicast_list_only_ip(input_list: list):
    """Custom Validator for a list of Multicast IP addresses.

    Args:
        input_list (list): List of only Multicast IPs.

    Raises:
        err_minor: Any of the addresses in the list is not an
        IP multicast address.
    """
    for value in input_list:
        validate_ip_multicast(value)
    return input_list


def validate_multicast_list(input_list: list):
    """Custom Validator for a list of Multicast MAC or IP addresses.

    Args:
        input_list (list): List of Multicast IPs and MACs.

    Raises:
        err_minor: Any of the addresses in the list is not a
        multicast address.
    """
    for value in input_list:
        validate_any_multicast_address(value)
    return input_list


def validate_ingress_streams_fields(streams, location: str):
    """Raise err_minor if any stream carries an ipv or ats value.

    ``location`` is a human-readable label such as ``"compute node"`` or
    ``"controller interface"`` used in the error message.
    """
    for ingress_stream in streams:
        if ingress_stream.ipv is not None:
            raise err_minor(
                f"Validation Error in Ingress Streams. "
                f"Removing config from the interface. "
                f"Ingress stream {ingress_stream.name} "
                f"at the {location} should not have an ipv value."
            )
        if ingress_stream.ats is not None:
            raise err_minor(
                f"Validation Error in Ingress Streams. "
                f"Removing config from the interface. "
                f"Ingress stream {ingress_stream.name} at the "
                f"{location} should not have an ats value"
            )
    return streams


def validate_vlan_ids_unique(virtual_interfaces, name: str):
    """Raise err_major if any VLAN ID appears more than once."""
    all_vlans = [vi.vlanid for vi in virtual_interfaces]
    list_label = (
        f"VLAN IDs of virtual Controller Interface in interface {name}"
    )
    validate_list_items_unique(all_vlans, list_label)


def validate_list_items_unique(
    input_list: list, list_label: Optional[str] = None
) -> list:
    """Custom Validator for a list of items where every item should be unique.

    Args:
        input_list (list): List of items.

        list_label(str): Add an optional label to the error message.

    Raises:
        err_major: List contains duplicates.

    Returns:
        list: Input is handed over.
    """
    dupes = []
    if list_label:
        msg = f"Duplicates found in {list_label}:"
    else:
        msg = "Duplicates found:"

    if len(set(input_list)) != len(input_list):
        dupes = utils.get_duplicates_in_list(input_list)
        raise err_major(msg + str(dupes))
    return input_list


def validate_cbs_idleslopes_fit_portspeed(
    traffic_classes: list, port_speed: int
):
    """Custom Validator for a list of Traffic Classes to check conformity \
        to MII/MDI speed.

    Args:
        traffic_classes (list): List of element type `TrafficClass`.

        port_speed (int): MII or MDI speed of the port.

    Raises:
        err_major: The sum of idleslopes of all shapers on one port
                    must be equal or lower than the port speed.

    Returns:
        list: Return list of traffic classes as received.
    """
    if not traffic_classes:
        return
    if not port_speed:
        raise err_major(
            "Cannot validate Traffic Classes! "
            "No port speed defined. Make sure to configure MII or MDI."
        )

    sum_idleslopes = 0

    for tr_class in traffic_classes:
        if (
            tr_class.selection_mechanisms
            and tr_class.selection_mechanisms.type == "cbs"
        ):
            sum_idleslopes += tr_class.selection_mechanisms.idleslope

    if sum_idleslopes > port_speed * 1000:
        raise err_major(
            (
                "The sum of idleslopes of all shapers on one port"
                + " cannot be higher than the link speed!"
            )
        )
    return traffic_classes


def validate_optional_mii_config_compatibility(comp1, comp2, id):
    """Custom validator for optional MII configuration
    compatibility between two components.

    Args:
        comp1 (object): First component that may contain a ``mii_config``
        attribute.

        comp2 (object): Second component that may contain a ``mii_config``
        attribute.

        id (Any): Identifier of the connection (used only in error messages).

    Raises:
        err_major: One component has an MII config while the other does not.

        err_major: Both components have an MII config but the *mode*
        values are identical. The modes must differ.

        err_major: Both components have an MII config but the *speed*
        values are different.

        err_major: Both components have an MII config but the *type*
        values are different.
    """
    if not comp1 or not comp2 or not comp1.mii_config or not comp2.mii_config:
        return
    mii_comp1 = comp1.mii_config
    mii_comp2 = comp2.mii_config
    # Look for wrong config variants: neither external nor internal PHYs
    # used
    if (mii_comp1 is None and mii_comp2 is not None) or (
        mii_comp1 is not None and mii_comp2 is None
    ):
        raise err_major(
            f"Invalid MII config in connection {id}: "
            f"{comp1.name} ↔ {comp2.name} "
            f"(MII mismatch for PHY type). Both or None of "
            f"the components should have a MII config"
        )

    # External PHY is used for this connection
    if (mii_comp1 and mii_comp1 is not None) and (
        mii_comp2 and mii_comp2 is not None
    ):
        if mii_comp1.mode == mii_comp2.mode:
            raise err_major(
                f"Incompatible MII Mode: {comp1.name} "
                f"({mii_comp1.mode}) ↔ {comp2.name}"
                f"({mii_comp2.mode})"
            )
        if mii_comp1.speed != mii_comp2.speed:
            raise err_major(
                f"Incompatible MII Speed: {comp1.name} "
                f"({mii_comp1.speed}) ↔ {comp2.name}"
                f"({mii_comp2.speed})"
            )
        if mii_comp1.type != mii_comp2.type:
            raise err_major(
                f"Incompatible MII Type: {comp1.name} "
                f"({mii_comp1.type}) ↔ {comp2.name}"
                f"({mii_comp2.type})"
            )


def validate_compulsory_mii_config_compatibility(comp1, comp2, id):
    """Validator that enforces a **mandatory** MII configuration
    on both components  and then checks optional compatibility.

    Args:
        comp1 (object): First component. Must have ``mii_config``.

        comp2 (object): Second component. Must have ``mii_config``.

        id (Any): Identifier of the connection (used only in error
        messages).

    Raises:
        err_major: Either component is missing a required MII
        configuration.

        err_major: Propagated from
        :func:`validate_optional_mii_config_compatibility`
        when the optional checks fail.
    """
    if not comp1.mii_config or not comp2.mii_config:
        raise err_major(
            f"Invalid MII config in connection {id}: "
            f"{comp1.name} ↔ {comp2.name} "
            f"(MII configuration missing)."
        )
    validate_optional_mii_config_compatibility(comp1, comp2, id)


def validate_htb(comp, speed):
    """Validator that checks an HTB (Hierarchical Token Bucket) configuration
    against the physical link speed.

    Args:
        comp (object): Component that owns an ``htb`` attribute with
        ``child_classes``.

        speed (int): Link speed of the interface (same unit as the HTB rates).

    Raises:
        err_major: The sum of the ``rate`` values of all child classes exceeds
        the provided ``speed``.
    """
    if not comp or not speed:
        return
    sum_child_rates = 0
    for nodes in comp.compute_nodes:
        if nodes.htb:
            for child in nodes.htb.child_classes:
                sum_child_rates = sum_child_rates + child.rate
    if sum_child_rates > speed:
        raise err_major(
            f"Incompatible HTB config for {comp.name}"
            f"Sum of all child classes {sum_child_rates} rates "
            f"should be less than link speed {speed}"
        )


def validate_macsec(comp1, comp2, id):
    # Check if macsec_config is compatible
    """Validator for MACsec configuration compatibility between two components.

    Args:
        comp1 (object): First component: May contain a ``macsec_config``.

        comp2 (object): Second component: May contain a ``macsec_config``.

        id (Any): Identifier of the connection (used only in error messages).

    Raises:
        err_major: One component has a MACsec config while the other does not.

        err_major: MKA (Key Agreement) enabled state differs between the two
        components.

        err_major: ``macsec_mode`` differs between the two components.
    """
    if (
        not comp1
        or not comp2
        or not comp1.macsec_config
        or not comp2.macsec_config
    ):
        return
    macsec1 = comp1.macsec_config
    macsec2 = comp2.macsec_config

    if (macsec1 and not macsec2) or (macsec2 and not macsec1):
        raise err_major(
            f"Incomplete MACsec Config. "
            f"{comp1.name} and {comp2.name} "
            f"in connection {id} should have a macsec config"
        )
    if macsec1 and macsec2:
        if (not macsec1.mka_enabled and macsec2.mka_enabled) or (
            macsec1.mka_enabled and not macsec2.mka_enabled
        ):
            raise err_major(
                f"MACsec should be enabled in both - "
                f"{comp1.name} and "
                f"{comp2.name} in connection {id} "
            )

        if macsec1.macsec_mode != macsec2.macsec_mode:
            raise err_major(
                f"Both {comp1.name} and "
                f"{comp2.name} should have the same macsec_mode. "
                f"in connection {id} "
            )


def validate_gptp(comp1, comp2, id):
    """Validator that checks gPTP (generic Precision Time Protocol)
    configuration compatibility between two components.

    Args:
        comp1 (object): First component. May contain a ``ptp_config``.

        comp2 (object): Second component. May contain a ``ptp_config``.

        id (Any): Identifier of the connection (used only in error messages).

    Raises:
        err_major: PTP configuration present on one side only.

        err_major: Mismatch of the ``cmlds_linkport_enabled`` flag between
        the two components.

        err_major: Propagated from :func:`validate_gptp_domains` when domain
        level checks fail.
    """
    if not comp1 or not comp2 or not comp1.ptp_config or not comp2.ptp_config:
        return

    ptp1 = comp1.ptp_config
    ptp2 = comp2.ptp_config

    if (ptp1 and ptp2 is None) or (ptp2 and ptp1 is None):
        raise err_major(
            f"Incompatible PTP config. PTP config not present in "
            f"either {comp1.name} or  "
            f"{comp2.name} in connection {id} "
        )

    if ptp1 and ptp2:

        validate_gptp_domains(comp1, comp2, ptp1, ptp2, id)
        validate_gptp_domains(comp2, comp1, ptp2, ptp1, id)

        if ptp1.cmlds_linkport_enabled != ptp2.cmlds_linkport_enabled:
            raise err_major(
                f"CMLDS mismatch: {comp1.name} has "
                f"cmlds_linkport_enabled="
                f"{ptp1.cmlds_linkport_enabled}, but "
                f"{comp2.name} has "
                f"{ptp2.cmlds_linkport_enabled}"
            )


def validate_gptp_domains(comp1, comp2, ptp1, ptp2, id):
    """Helper that validates matching PTP domains and sync-config types between
    two components.

    Args:
        comp1 (object): First component (source of ``ptp1``).

        comp2 (object): Second component (source of ``ptp2``).

        ptp1 (object): ``ptp_config`` of ``comp1``.

        ptp2 (object): ``ptp_config`` of ``comp2``.

        id (Any): Identifier of the connection (used only in error messages).

    Raises:
        err_major: A domain present in ``ptp1`` is missing in ``ptp2``.

        err_major: The ``sync_config.type`` of a matching domain is identical
        on both sides (they must differ for a valid configuration).
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
                f"Incompatible PTP Config: Domain {domain} "
                f"not present in {comp2.name}"
                f" in connection {id}"
            )
        if ptp_port_iface.sync_config.type == ptp_port_iface2.sync_config.type:
            raise err_major(
                f"Incompatible PTP Config: Domain ID {domain} "
                f"in {comp1.name} and "
                f" {comp2.name} in connection {id}"
            )


def validate_elements_in(
    subset: Iterable[Any], superset: Iterable[Any], msg: Optional[str] = None
):
    """Custom Validator that checks if every element in `subset` \
    appears at least once in `superset`.
    E.g. Validate if port_name is in switch_port_names.

    Args:
        subset (Iterable[Any]): Subset where elements are expected \
        to be in superset.

        superset (Iterable[Any]): Reference set.

    Returns:
        Iterable[Any]: Return subset as received.
    """
    if msg:
        msg += " "
    if not all(elem in set(superset) for elem in subset):
        disallowed = set(subset) - set(superset)
        raise err_major(f"{msg}Invalid values: {sorted(disallowed)}.")


def check_prio_unique(traffic_classes):
    """
    Check if the traffic class prios are unique across
    various traffic classes in a controller interface or switch.
    """
    if not traffic_classes:
        return
    traffic_class_prios = []
    for traffic_class in traffic_classes:
        if traffic_class.priority not in traffic_class_prios:
            traffic_class_prios.append(traffic_class.priority)
        else:
            raise err_minor(
                "Traffic class priority is not unique in controller"
                " or switch."
            )


def check_pcps_different(traffic_classes):
    """
    Check if the PCPs are different across traffic classes.
    """
    if not traffic_classes:
        return
    pcp_list = []
    for traffic_class in traffic_classes:
        if traffic_class.frame_priority_values is not None:
            for pcp in traffic_class.frame_priority_values:
                if pcp in pcp_list:
                    raise err_minor(
                        f"The pcp value {pcp} is not unique for two "
                        f"different traffic classes in controller interface"
                        f"or switch port"
                    )
            pcp_list.extend(traffic_class.frame_priority_values)


def check_ipvs_unique(traffic_classes):
    """
    Check if ipvs across traffic classes are unique
    """
    if not traffic_classes:
        return
    ipv_list = []
    for traffic_class in traffic_classes:
        if traffic_class.internal_priority_values is not None:
            for ipv in traffic_class.internal_priority_values:
                if ipv in ipv_list:
                    raise err_minor(
                        f"The ipv value {ipv} is not unique for two"
                        f" different traffic classes in controller interface."
                        f" or switch port"
                    )
            ipv_list.extend(traffic_class.internal_priority_values)


def validate_traffic_classes(traffic_classes):
    """
    Validate the traffic classes in a controller
    interface and switch to find out if a pcp,
    ipv or traffic class prio is reused or not

    """
    if not traffic_classes:
        return
    # Check if priorities of traffic classes are unique
    check_prio_unique(traffic_classes)
    # Check that same pcps are not assigned to two different traffic classes
    check_pcps_different(traffic_classes)
    # Check that same ipvs are not assigned to two different traffic classes
    check_ipvs_unique(traffic_classes)
    return traffic_classes


def none_to_empty_list(v):
    """
    Make the field defined as optional [] if
    accidentally declared by the user as None
    """
    return [] if v is None else v
