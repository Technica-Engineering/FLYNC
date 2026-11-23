"""Workspace-level validators for bus interface frame references (CAN / CAN FD and LIN).

Complements :mod:`flync.core.validators.forwarder`, which resolves *forwarder* references only.
The passes here cover the plain ``sender_frames`` / ``receiver_frames`` declarations of the bus
interfaces, plus the interface's own ``bus_ref``, so that a dangling id or a CAN interface pointing at
a LIN bus (or vice versa) is reported instead of silently ignored.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Iterator, Tuple, Union

from pydantic_core import PydanticCustomError

from flync.core.utils.exceptions import Category, err_major
from flync.model.flync_4_ecu.can_interface import CANFrameRef, CANInterface
from flync.model.flync_4_ecu.lin_interface import LINFrameRef, LINMasterInterface, LINSlaveInterface
from flync.model.flync_4_signal.frame import CANFDFrame, CANFrame, J1939Frame, LINFrame
from flync.model.flync_4_signal.j1939_frame_ref import J1939FrameRef

if TYPE_CHECKING:
    from flync.model.flync_4_communication.flync_channels import FLYNCChannelConfig
    from flync.model.flync_4_ecu.controller import Controller
    from flync.model.flync_model import FLYNCModel


CANAnyFrame = Union[CANFrame, CANFDFrame]
AnyFrame = Union[CANFrame, CANFDFrame, LINFrame]
AnyFrameRef = Union[CANFrameRef, LINFrameRef]
FrameKey = Union[int, Tuple[str, int]]
AnyBusInterface = Union[CANInterface, LINMasterInterface, LINSlaveInterface]

_CAN_BUSES_CATALOG = "communication.channels.can_buses"
_LIN_BUSES_CATALOG = "communication.channels.lin_buses"


# ---------------------------------------------------------------------------
# Error source attribution
#
# These checks run as a FLYNCModel-level ``model_validator``, so their errors attach to the
# workspace-root document and the validate CLI would show an empty Source column. We stamp each
# finding with a structural ``yaml_path`` locator, exactly as the forwarder passes do.
# ---------------------------------------------------------------------------


def _with_source(err: PydanticCustomError, locator: str) -> PydanticCustomError:
    """Return *err* re-created with ``yaml_path=locator`` added to its context."""

    ctx = dict(err.context or {})
    if "yaml_path" in ctx:
        return err
    ctx["yaml_path"] = locator
    # err.type / err.message_template are typed as ``str`` but were originally constructed
    # from ``LiteralString``, so re-forwarding them through PydanticCustomError is safe.
    return PydanticCustomError(err.type, err.message_template, ctx)


def _interface_locator(controller: Controller, iface: AnyBusInterface, kind: str) -> str:
    """Path-style Source locator for a bus interface (bracket-free: the CLI renders this through Rich)."""

    return f"controllers/{controller.name}/{kind}_interfaces/{iface.name}"


# ---------------------------------------------------------------------------
# Catalogs
# ---------------------------------------------------------------------------


def _channels(model: FLYNCModel) -> FLYNCChannelConfig | None:
    """Return ``communication.channels`` or ``None`` when the model declares no communication."""

    return getattr(model.communication, "channels", None) if model.communication else None


def _frame_key(ref: AnyFrameRef) -> FrameKey:
    """Return the key locating *ref*'s frame on its interface's bus: ``(id_format, can_id)`` for CAN, the LIN id for LIN."""

    if isinstance(ref, CANFrameRef):
        return (ref.id_format, ref.frame_ref)
    return ref.frame_ref


def _build_can_frames_by_bus(model: FLYNCModel) -> Dict[str, Dict[FrameKey, CANAnyFrame]]:
    """Return ``{bus_name: {(id_format, can_id): frame}}`` for every CAN / CAN FD bus under ``communication.channels``."""

    out: Dict[str, Dict[FrameKey, CANAnyFrame]] = {}
    channels = _channels(model)
    if channels is None or channels.can_buses is None:
        return out
    for bus in channels.can_buses:
        out[bus.name] = {(frame.id_format, frame.can_id): frame for frame in bus.frames or [] if not isinstance(frame, J1939Frame)}
    return out


def _build_lin_frames_by_bus(model: FLYNCModel) -> Dict[str, Dict[int, LINFrame]]:
    """Return ``{bus_name: {lin_id: frame}}`` for every LIN bus under ``communication.channels``."""

    out: Dict[str, Dict[int, LINFrame]] = {}
    channels = _channels(model)
    if channels is None or channels.lin_buses is None:
        return out
    for bus in channels.lin_buses:
        out[bus.name] = {frame.lin_id: frame for frame in bus.frames or []}
    return out


def _build_j1939_frames_by_bus(model: FLYNCModel) -> Dict[str, Dict[str, J1939Frame]]:
    """Return ``{bus_name: {frame_name: frame}}`` for every J1939 frame under ``communication.channels``.

    The catalog is keyed by frame ``name`` because J1939 references resolve by name or CAN identifier, not by
    PGN — a bus may carry several frames sharing a Parameter Group Number. Names are unique per bus
    (``CANBus.validate_unique_frame_ids``), so no frame is shadowed here.
    """

    out: Dict[str, Dict[str, J1939Frame]] = {}
    channels = _channels(model)
    if channels is None or channels.can_buses is None:
        return out
    for bus in channels.can_buses:
        out[bus.name] = {frame.name: frame for frame in bus.frames or [] if isinstance(frame, J1939Frame)}
    return out


# ---------------------------------------------------------------------------
# Tree walking
# ---------------------------------------------------------------------------


def _iter_bus_interfaces(model: FLYNCModel) -> Iterator[Tuple[Controller, AnyBusInterface, str]]:
    """Yield ``(controller, interface, kind)`` for every CAN and LIN interface in the model."""

    for ecu in model.ecus or []:
        for controller in ecu.controllers or []:
            for can_iface in controller.can_interfaces or []:
                yield controller, can_iface, "can"
            for lin_iface in controller.lin_interfaces or []:
                yield controller, lin_iface, "lin"


def _iter_frame_refs(iface: AnyBusInterface) -> Iterator[Tuple[str, AnyFrameRef]]:
    """Yield ``(field_name, frame_ref)`` for the sender / receiver declarations present on *iface*."""

    for field_name in ("sender_frames", "receiver_frames"):
        for ref in getattr(iface, field_name, None) or []:
            yield field_name, ref


# ---------------------------------------------------------------------------
# Validation pass
# ---------------------------------------------------------------------------


def _bus_kind_label(kind: str) -> str:
    """Return the catalog wording used in the error messages for *kind*."""

    return _CAN_BUSES_CATALOG if kind == "can" else _LIN_BUSES_CATALOG


def _validate_interface(iface: AnyBusInterface, kind: str, frames_by_bus: Dict[str, Dict[FrameKey, AnyFrame]]) -> None:
    """Resolve one interface's own ``bus_ref`` plus every sender / receiver frame reference it declares.

    *frames_by_bus* is the catalog of the interface's own bus kind, so an unresolvable name is reported against
    that kind - see :func:`validate_interface_frame_refs` for why the catalog is picked that way.
    """

    owner = f"{type(iface).__name__}(name={iface.name})"
    catalog = _bus_kind_label(kind)

    if iface.bus_ref not in frames_by_bus:
        raise err_major(
            "{owner}: bus_ref '{bus}' does not name any bus declared under {catalog}.",
            owner=owner,
            bus=iface.bus_ref,
            catalog=catalog,
            category=Category.REFERENCE,
            error_number="215",
        )

    bus_frames = frames_by_bus[iface.bus_ref]
    for field_name, ref in _iter_frame_refs(iface):
        if _frame_key(ref) not in bus_frames:
            raise err_major(
                "{owner}: {field}: frame_ref id={ref} does not name any frame declared on bus '{bus}' under {catalog}.",
                owner=owner,
                field=field_name,
                ref=ref.frame_ref,
                bus=iface.bus_ref,
                catalog=catalog,
                category=Category.REFERENCE,
                error_number="217",
            )


def _resolve_j1939_frame_ref(
    ref: J1939FrameRef,
    frames_on_bus: dict[str, J1939Frame],
) -> list[J1939Frame]:
    """Resolve *ref* against *frames_on_bus* and return every matching frame.

    A reference may address its frame three ways:

    * by ``frame_ref`` (name) — the named frame must exist on the bus (at most one match);
    * by ``can_id`` — the full on-bus identifier has its Source Address bits stripped and the remainder
      (priority + PGN base, ``can_id & ~0xFF``) is matched against each frame's derived ``can_id``. Several
      frames on a bus may share the same derived identifier (same PGN / priority), so the caller must treat
      more than one match as ambiguous rather than pick one;
    * by both — the two must agree on the same frame (double verification); the caller checks the *named*
      frame's derived ``can_id`` against the reference's base.
    """

    if ref.can_id is not None:
        base = ref.can_id & ~0xFF
        return [frame for frame in frames_on_bus.values() if frame.can_id == base]
    if ref.frame_ref is not None:
        frame = frames_on_bus.get(ref.frame_ref)
        return [frame] if frame is not None else []
    return []


def _render_j1939_ref(ref: J1939FrameRef) -> str:
    """Return a human-readable rendering of *ref* for error messages (its name, CAN id or ``<none>``)."""

    if ref.frame_ref is not None:
        return ref.frame_ref
    if ref.can_id is not None:
        return f"0x{ref.can_id:x}"
    return "<none>"


def _validate_j1939_ref(owner: str, field_name: str, ref: J1939FrameRef, bus_frames: Dict[str, J1939Frame], bus_ref: str) -> None:
    """Resolve one J1939 sender / receiver reference against its bus, raising on any inconsistency."""

    if ref.frame_ref is not None and ref.can_id is not None:
        frame_by_name = bus_frames.get(ref.frame_ref)
        if frame_by_name is None:
            raise err_major(
                "{owner}: {field}: frame reference '{frame}' does not resolve to any J1939 frame declared on bus '{bus}' under {catalog}.",
                owner=owner,
                field=field_name,
                frame=ref.frame_ref,
                bus=bus_ref,
                catalog=_CAN_BUSES_CATALOG,
                category=Category.REFERENCE,
                error_number="372",
            )
        # A frame name and a CAN identifier are consistent only if the named frame's derived
        # identifier (SA stripped) equals the reference's identifier (SA stripped). Several frames
        # on a bus may share the same derived identifier (same PGN / priority), so the id check
        # must be made against the *named* frame, never by picking an arbitrary frame with a
        # matching id and comparing names.
        base = ref.can_id & ~0xFF
        if frame_by_name.can_id != base:
            raise err_major(
                "{owner}: {field}: name '{frame}' and CAN identifier {can_id} do not agree "
                "— the frame named has derived identifier {derived} on bus '{bus}'.",
                owner=owner,
                field=field_name,
                frame=ref.frame_ref,
                can_id=f"0x{ref.can_id:x}",
                derived=f"0x{frame_by_name.can_id:x}",
                bus=bus_ref,
                category=Category.CONSISTENCY,
                error_number="423",
            )
        return

    matches = _resolve_j1939_frame_ref(ref, bus_frames)
    if not matches:
        raise err_major(
            "{owner}: {field}: frame reference {frame} does not resolve to any J1939 frame declared on bus '{bus}' under {catalog}.",
            owner=owner,
            field=field_name,
            frame=_render_j1939_ref(ref),
            bus=bus_ref,
            catalog=_CAN_BUSES_CATALOG,
            category=Category.REFERENCE,
            error_number="424",
        )
    if len(matches) > 1:
        other = ", ".join(sorted(frame.name for frame in matches[1:]))
        raise err_major(
            "{owner}: {field}: CAN identifier {can_id} is ambiguous on bus '{bus}': it matches more than "
            "one J1939 frame ({first}, {other}). Name the frame with frame_ref to disambiguate.",
            owner=owner,
            field=field_name,
            can_id=f"0x{ref.can_id:x}",
            bus=bus_ref,
            first=matches[0].name,
            other=other,
            catalog=_CAN_BUSES_CATALOG,
            category=Category.CONSISTENCY,
            error_number="425",
        )


def _validate_j1939_interface(iface: CANInterface, j1939_frames_by_bus: Dict[str, Dict[str, J1939Frame]]) -> None:
    """Resolve every J1939 sender / receiver frame reference on *iface* against its own bus.

    ``J1939Frame`` may be addressed by name (a string), by its full on-bus CAN identifier (an integer), or by
    both. The catalog here is keyed by frame name. A ``can_id`` reference carries the emitter's Source Address
    in its low byte; the referenced frame is recovered by stripping those bits (``can_id & ~0xFF``) and
    matching the remainder against the frame's derived ``can_id``. A ``frame_ref`` reference is matched against
    the frame name directly. When both are given they must resolve to the *same* frame (double verification);
    a name/id mismatch is a consistency error. The bus is the interface's own ``bus_ref``, which is checked
    against the declared J1939 buses; a J1939 bus must exist for the node to attach to.
    """

    owner = f"CANInterface(name={iface.name})"

    if iface.bus_ref not in j1939_frames_by_bus:
        raise err_major(
            "{owner}: bus_ref '{bus}' does not name any J1939 bus declared under {catalog}.",
            owner=owner,
            bus=iface.bus_ref,
            catalog=_CAN_BUSES_CATALOG,
            category=Category.REFERENCE,
            error_number="374",
        )
    bus_frames = j1939_frames_by_bus[iface.bus_ref]
    for field_name in ("j1939_sender_frames", "j1939_receiver_frames"):
        for ref in getattr(iface, field_name) or []:
            _validate_j1939_ref(owner, field_name, ref, bus_frames, iface.bus_ref)


def _emitter_sa_for_ref(ref: J1939FrameRef, iface: CANInterface, frames_on_bus: Dict[str, J1939Frame]) -> Tuple[str, int] | None:
    """Return ``(frame_name, source_address)`` an emitter *ref* would place on the wire, or ``None``.

    A ``can_id`` emitter carries its own SA in the low byte; a ``frame_ref`` emitter uses the interface's
    ``source_address``. Either way the frame must resolve uniquely on the bus.
    """

    emitter: Tuple[str, int] | None = None
    if ref.can_id is not None:
        base = ref.can_id & ~0xFF
        matches = [f for f in frames_on_bus.values() if f.can_id == base]
        if len(matches) == 1:
            emitter = matches[0].name, ref.can_id & 0xFF
        # otherwise the can_id sender is ambiguous (384) or resolves to nothing (383), reported elsewhere
    elif ref.frame_ref is not None and iface.source_address is not None:
        frame = frames_on_bus.get(ref.frame_ref)
        if frame is not None:
            emitter = frame.name, iface.source_address
    return emitter


def _build_j1939_emitter_sas(model: FLYNCModel, j1939_frames_by_bus: Dict[str, Dict[str, J1939Frame]]) -> Dict[Tuple[str, str], list[int]]:
    """Map ``(bus_ref, frame_name)`` to the source_addresses of every modelled J1939 emitter of that frame.

    A reference that resolves to a frame by name needs a Source Address to form the full on-bus identifier.
    A sender supplies its own ``source_address``; a receiver observes a message sent by *another* node, so its
    SA must come from whoever is modelled as transmitting that frame on the bus. This pass collects, for every
    J1939 sender reference across the whole model, the SA each transmission would place on the wire and buckets
    them by ``(bus_ref, frame_name)`` so a receiver can look up the emitter's SA.

    A sender reference contributes an SA when it carries an explicit ``can_id`` (whose SA byte is its own) or
    when it declares a ``source_address``. A sender that names a frame but declares no SA contributes nothing,
    so a receiver of that frame gets no SA and drops out of uniqueness (it is undecidable, not an error).
    """

    emitter_sas: Dict[Tuple[str, str], list[int]] = {}
    for controller, iface, kind in _iter_bus_interfaces(model):
        if not (isinstance(iface, CANInterface) and iface.is_j1939()):
            continue
        frames_on_bus = j1939_frames_by_bus.get(iface.bus_ref)
        if not frames_on_bus:
            continue  # dangling bus_ref is reported elsewhere as 374
        for ref in iface.j1939_sender_frames or []:
            emitter = _emitter_sa_for_ref(ref, iface, frames_on_bus)
            if emitter is not None:
                emitter_sas.setdefault((iface.bus_ref, emitter[0]), []).append(emitter[1])
    return emitter_sas


def _full_id_for_frame(iface: CANInterface, field_name: str, frame: J1939Frame, emitter_sas: Dict[Tuple[str, str], list[int]]) -> int | None:
    """Return the full on-bus identifier *frame* gets under *field_name*, or ``None`` when it cannot be fixed.

    A sender uses its own ``source_address``; a receiver has none of its own, so it borrows the SA of whoever
    is modelled as emitting the frame on the bus (from *emitter_sas*). No usable SA means ``None``.
    """

    if field_name == "j1939_sender_frames":
        # a sender without a declared SA is undecidable
        full_id = None if iface.source_address is None else frame.can_id | iface.source_address
    else:
        # a receiver borrows its emitter's SA; no known SA is undecidable
        sas = sorted(set(emitter_sas.get((iface.bus_ref, frame.name), ())))
        full_id = frame.can_id | sas[0] if sas else None
    return full_id


def _resolve_j1939_full_id(
    iface: CANInterface,
    field_name: str,
    ref: J1939FrameRef,
    frames_on_bus: Dict[str, J1939Frame],
    emitter_sas: Dict[Tuple[str, str], list[int]],
) -> Tuple[J1939Frame | None, int | None]:
    """Resolve *ref* and form its full on-bus J1939 identifier, or ``(None, None)`` when it cannot be fixed.

    Returns ``(frame, full_id)``. ``full_id`` is the complete 29-bit identifier the reference places on (or
    observes on) the wire, Source Address included:

    * a reference with an explicit ``can_id`` — sender or receiver — fixes the full id to ``ref.can_id``, whose
      SA byte is already set;
    * a sender named only by ``frame_ref`` derives the full id from the frame's own ``can_id`` OR the
      interface's ``source_address`` (the node transmits, so it uses its own SA);
    * a receiver named only by ``frame_ref`` has no SA of its own (it does not transmit): its SA is that of
      whoever is modelled as sending the frame on the bus, looked up in *emitter_sas*. When no emitter with a
      known SA exists, no full id can be fixed and ``(None, None)`` is returned — the reference is undecidable,
      not an error.

    Returns ``(None, None)`` when the reference is unresolvable (reported elsewhere as 372/383/384) or when no
    full id can be determined.
    """

    frame: J1939Frame | None = None
    full: int | None = None
    if ref.can_id is not None:
        base = ref.can_id & ~0xFF
        matches = [f for f in frames_on_bus.values() if f.can_id == base]
        if len(matches) == 1:
            frame = matches[0]
            full = ref.can_id
    elif ref.frame_ref is not None:
        frame = frames_on_bus.get(ref.frame_ref)
        if frame is not None:
            full = _full_id_for_frame(iface, field_name, frame, emitter_sas)
    return (frame, full) if frame is not None and full is not None else (None, None)


def _register_j1939_full_id(
    controller: Controller,
    iface: CANInterface,
    field_name: str,
    ref: J1939FrameRef,
    j1939_frames_by_bus: Dict[str, Dict[str, J1939Frame]],
    emitter_sas: Dict[Tuple[str, str], list[int]],
    bus_full_ids: Dict[str, Dict[int, Tuple[str, str]]],
) -> None:
    """Resolve *ref* and flag a collision when its full on-bus id was already used by a different frame."""

    owner = f"CANInterface(name={iface.name})"
    frames_on_bus = j1939_frames_by_bus.get(iface.bus_ref)
    if not frames_on_bus:
        return  # a dangling bus_ref is already reported as 374
    frame, full = _resolve_j1939_full_id(iface, field_name, ref, frames_on_bus, emitter_sas)
    if frame is None or full is None:
        return  # unresolvable or no fixed id, reported elsewhere
    seen = bus_full_ids.setdefault(iface.bus_ref, {})
    prior = seen.get(full)
    if prior is not None and prior[0] != frame.name:
        err = err_major(
            "{owner}: {field} reference to frame '{frame}' yields CAN identifier {can_id} on bus "
            "'{bus}', already used by {prior}. A J1939 identifier is the frame's derived id OR'd "
            "with the node's source address and must be unique per bus.",
            owner=owner,
            field=field_name,
            frame=_render_j1939_ref(ref),
            can_id=hex(full),
            bus=iface.bus_ref,
            prior=prior[1],
            category=Category.UNIQUENESS,
            error_number="427",
        )
        raise _with_source(err, _interface_locator(controller, iface, "can")) from None
    seen[full] = (frame.name, f"{owner}: {field_name} '{_render_j1939_ref(ref)}'")


def _validate_j1939_unique_can_ids_on_bus(model: FLYNCModel, j1939_frames_by_bus: Dict[str, Dict[str, J1939Frame]]) -> None:
    """Require a unique full on-bus J1939 identifier per bus across all node references.

    The identifier that actually appears on the wire is not a J1939 frame's bare ``can_id``: its low byte is
    the *source address* of the node transmitting (or observing) it. The bus-level ``054`` rule compares raw
    frames in isolation and so cannot see the SA; this workspace-level pass therefore gathers every J1939
    sender / receiver reference across all nodes sharing a bus, forms the full on-bus identifier for each
    (see :func:`_resolve_j1939_full_id`), and flags any full identifier that two references would put on the
    wire under *different* frames.

    Two references that resolve to the *same* frame on the same bus are allowed to share a full id — that is
    the normal emitter + its receivers pattern, and the multi-node case where several nodes each emit the
    same Parameter Group (each with its own distinct SA, so distinct full ids). Only two *distinct* frames
    collapsing to the same on-bus id are a true collision.
    """

    bus_full_ids: Dict[str, Dict[int, Tuple[str, str]]] = {}
    emitter_sas = _build_j1939_emitter_sas(model, j1939_frames_by_bus)
    for controller, iface, kind in _iter_bus_interfaces(model):
        if not (isinstance(iface, CANInterface) and iface.is_j1939()):
            continue
        for field_name in ("j1939_sender_frames", "j1939_receiver_frames"):
            for ref in getattr(iface, field_name) or []:
                _register_j1939_full_id(controller, iface, field_name, ref, j1939_frames_by_bus, emitter_sas, bus_full_ids)


def _validate_lin_single_publisher(model: FLYNCModel) -> None:
    """Require at most one publisher per LIN frame: a frame is in the ``sender_frames`` of one interface only.

    The master issues the header of every frame in the schedule tables; the node that lists the frame in its
    ``sender_frames``, the master or a slave, fills in the response.
    """

    publishers: Dict[Tuple[str, int], str] = {}
    for controller, iface, kind in _iter_bus_interfaces(model):
        if not isinstance(iface, (LINMasterInterface, LINSlaveInterface)):
            continue
        owner = f"{type(iface).__name__}(name={iface.name})"
        for ref in iface.sender_frames or []:
            prior = publishers.setdefault((ref.bus_ref, ref.frame_ref), owner)
            if prior != owner:
                err = err_major(
                    "{owner}: sender_frames: LIN frame id={frame} on bus '{bus}' is already published by {prior}. "
                    "A LIN frame has exactly one publisher.",
                    owner=owner,
                    frame=ref.frame_ref,
                    bus=ref.bus_ref,
                    prior=prior,
                    category=Category.UNIQUENESS,
                    error_number="489",
                )
                raise _with_source(err, _interface_locator(controller, iface, kind)) from None


def validate_interface_frame_refs(model: FLYNCModel) -> None:
    """Workspace pass: every CAN / LIN interface must name a declared bus of its own kind and resolve its frame refs.

    The check is a plain lookup - is this frame id declared on this bus - performed against the catalog of the
    interface's own bus kind. Both aspects are load-bearing:

    *Scoped by bus*, because a CAN id is only unique within a bus: id ``0x100`` on ``CAN1`` and on ``CAN2`` are
    two different frames. The bus is the interface's own ``bus_ref``; a
    :class:`~flync.model.flync_4_ecu.can_interface.CANFrameRef` carries the ``frame_ref`` plus its ``id_format``
    (a standard and an extended frame may share a numeric id). Asking only whether an id exists *somewhere*
    would accept an interface on ``CAN1`` declaring a frame that only exists on ``CAN2``.

    *Scoped by bus kind*, because ``bus_ref`` is a plain string and ``frame_ref`` a plain int - the type system
    stops a ``LINFrameRef`` from landing in a ``CANInterface``, but nothing stops a CAN interface from naming a
    LIN bus. Resolving a CAN interface against ``can_buses`` only is what catches that, so no separate cross-kind
    rule is needed: the LIN bus name simply is not in the CAN catalog. A single catalog merged over both
    kinds would instead accept LIN ids on a CAN interface, and would be ambiguous anyway - bus names are unique
    per kind but not across kinds, so a workspace may hold a CAN bus and a LIN bus of the same name.

    A bus kind whose catalog is empty is skipped: FLYNC supports partial models (an ECU or controller may be
    modeled without the bus catalog it will later be wired into), and there is nothing to resolve against.
    Once a workspace declares buses of a kind, every interface of that kind must resolve.

    A LIN frame has at most one sender: only one interface lists it in its ``sender_frames``.
    """

    can_frames_by_bus = _build_can_frames_by_bus(model)
    lin_frames_by_bus = _build_lin_frames_by_bus(model)
    j1939_frames_by_bus = _build_j1939_frames_by_bus(model)

    for controller, iface, kind in _iter_bus_interfaces(model):
        frames_by_bus: Dict[str, Dict[FrameKey, AnyFrame]] = can_frames_by_bus if kind == "can" else lin_frames_by_bus  # type: ignore[assignment]
        if not frames_by_bus:
            continue
        try:
            _validate_interface(iface, kind, frames_by_bus)
        except PydanticCustomError as err:
            raise _with_source(err, _interface_locator(controller, iface, kind)) from None
        if isinstance(iface, CANInterface) and iface.is_j1939():
            try:
                _validate_j1939_interface(iface, j1939_frames_by_bus)
            except PydanticCustomError as err:
                raise _with_source(err, _interface_locator(controller, iface, "can")) from None

    _validate_j1939_unique_can_ids_on_bus(model, j1939_frames_by_bus)
    _validate_lin_single_publisher(model)
