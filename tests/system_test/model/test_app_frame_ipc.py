"""System-level tests for the CAN / J1939 frame and PDU references and the ECU-internal IPC channels of apps."""

import pytest
from pydantic import ValidationError

from flync.core.utils.exceptions_handling import validate_with_policy
from flync.model.flync_4_app import (
    App,
    AppBindings,
    AppCANFrameRef,
    AppCANPDURef,
    AppJ1939FrameRef,
    AppJ1939PDURef,
    IPCChannel,
    IPCChannelReference,
)
from flync.model.flync_4_bus.can_bus import CANBus
from flync.model.flync_4_communication.flync_channels import FLYNCChannelConfig
from flync.model.flync_4_communication.flync_communication import FLYNCCommunicationConfig
from flync.model.flync_4_ecu.can_interface import CANFrameRef, CANInterface
from flync.model.flync_4_ecu.controller import Controller
from flync.model.flync_4_ecu.ecu import ECU
from flync.model.flync_4_ecu.internal_topology import InternalTopology
from flync.model.flync_4_metadata.metadata import BaseVersion, ECUMetadata, EmbeddedMetadata, SystemMetadata
from flync.model.flync_4_signal import PDU, J1939Frame, StandardPDU
from flync.model.flync_4_signal.frame import CANFrame
from flync.model.flync_4_signal.j1939_frame_ref import J1939FrameRef
from flync.model.flync_4_signal.pdu import PDUInstance
from flync.model.flync_4_topology import EthernetTopology, FLYNCTopology
from flync.model.flync_model import FLYNCModel
from tests.error_assertions import ValidationResult, assert_no_findings, assert_single_error, assert_single_warning

FLYNC_VERSION = "0.15.0"
APP_NAME = "can_app"
CAN_BUS = "CAN0"
J1939_BUS = "J1939_0"
CAN_ID = 0x100
PGN = 0xFEF1
CAN_PDU = "PDU_Can"
J1939_PDU = "PDU_J1939"

UNKNOWN_BUS_ERROR_ID = "FLYNC-GEN-MAJ-REF-409"
UNRESOLVED_FRAME_ERROR_ID = "FLYNC-GEN-MAJ-REF-416"
UNRESOLVED_PGN_ERROR_ID = "FLYNC-GEN-MAJ-REF-417"
UNRESOLVED_PDU_ERROR_ID = "FLYNC-GEN-MAJ-REF-410"
UNRESOLVED_IPC_CHANNEL_ERROR_ID = "FLYNC-GEN-MAJ-REF-413"
DUPLICATE_IPC_CHANNEL_ERROR_ID = "FLYNC-CMN-MAJ-UNIQ-009"
MISSING_INTERFACE_WARNING_ID = "FLYNC-GEN-WARN-CONS-411"
SENDS_AND_RECEIVES_ERROR_ID = "FLYNC-CMN-MIN-CONS-418"
UNPAIRED_IPC_WARNING_ID = "FLYNC-GEN-WARN-CONS-414"


def _version() -> BaseVersion:
    return BaseVersion(version=FLYNC_VERSION)


def _pdu(name: str) -> PDU:
    return StandardPDU(name=name, length=8)


def _channels() -> FLYNCChannelConfig:
    """Return one CAN bus (frame 0x100 packing PDU_Can) and one J1939 bus (PGN 0xFEF1 packing PDU_J1939)."""
    can_frame = CANFrame(
        name="CAN_Frame", length=8, can_id=CAN_ID, id_format="standard_11bit", packed_pdus=[PDUInstance(pdu_ref=CAN_PDU, bit_position=0)]
    )
    j1939_frame = J1939Frame(
        name="J1939_Frame",
        priority=6,
        pdu_format=0xFE,
        pdu_specific=0xF1,
        data_page=0,
        extended_data_page=0,
        destination_type="global",
        packed_pdus=[PDUInstance(pdu_ref=J1939_PDU, bit_position=0)],
    )
    return FLYNCChannelConfig(
        pdus=[_pdu(CAN_PDU), _pdu(J1939_PDU)],
        can_buses=[
            CANBus(name=CAN_BUS, baud_rate=500000, frames=[can_frame]),
            CANBus(name=J1939_BUS, baud_rate=250000, frames=[j1939_frame]),
        ],
    )


def _controller(app_refs=(), can_interfaces=None) -> Controller:
    return Controller(
        name="CTRL1",
        controller_metadata=EmbeddedMetadata(type="embedded", author="TestTeam", target_system="Device1", compatible_flync_version=_version()),
        can_interfaces=can_interfaces if can_interfaces is not None else [],
        app_bindings=AppBindings(app_refs=list(app_refs)),
    )


def _full_interfaces() -> list:
    """CAN interfaces on both buses that declare every frame the apps below use."""
    return [
        CANInterface(name="CAN_IF", bus_ref=CAN_BUS, sender_frames=[CANFrameRef(frame_ref=CAN_ID, id_format="standard_11bit")]),
        CANInterface(name="J1939_IF", bus_ref=J1939_BUS, j1939_name=1, j1939_sender_frames=[J1939FrameRef(pgn=PGN)]),
    ]


def _bare_interfaces() -> list:
    """A J1939 interface declaring no frames: the J1939 bus needs one to load, and the CAN bus gets none."""
    return [CANInterface(name="J1939_IF", bus_ref=J1939_BUS, j1939_name=1)]


def _model_data(app: App, ipc_channels=(), can_interfaces=None, bind: bool = True) -> dict:
    controller = _controller(
        app_refs=[app.name] if bind else [], can_interfaces=can_interfaces if can_interfaces is not None else _full_interfaces()
    )
    ecu = ECU(
        name="ECU1",
        controllers=[controller],
        topology=InternalTopology(),
        ipc_channels=list(ipc_channels),
        ecu_metadata=ECUMetadata(type="ecu", author="TestTeam", compatible_flync_version=_version()),
    )
    return dict(
        ecus=[ecu],
        apps=[app],
        topology=FLYNCTopology(system_topology=EthernetTopology(connections=[])),
        metadata=SystemMetadata(type="system", release=_version(), author="TestTeam", compatible_flync_version=_version()),
        communication=FLYNCCommunicationConfig(channels=_channels()),
    )


def _model(app: App, ipc_channels=(), can_interfaces=None, bind: bool = True) -> FLYNCModel:
    return FLYNCModel(**_model_data(app, ipc_channels, can_interfaces, bind))


def _load(app: App, error_id: str, **kwargs) -> ValidationResult:
    """Load the model and keep only the findings carrying *error_id*; the fixture emits unrelated background warnings."""
    model, findings = validate_with_policy(FLYNCModel, _model_data(app, **kwargs), path=None)
    return model, [f for f in findings if (f.get("ctx") or {}).get("error_id") == error_id]


def test_app_with_valid_frame_and_pdu_refs_loads():
    """An app referencing existing CAN / J1939 frames and PDUs on its buses validates."""
    app = App(
        name=APP_NAME,
        can_frame_refs=[AppCANFrameRef(bus_ref=CAN_BUS, frame_ref=CAN_ID, id_format="standard_11bit", direction="sender")],
        j1939_frame_refs=[AppJ1939FrameRef(bus_ref=J1939_BUS, pgn=PGN, direction="sender")],
        can_pdu_refs=[AppCANPDURef(pdu_ref=CAN_PDU, bus_ref=CAN_BUS, direction="sender")],
        j1939_pdu_refs=[AppJ1939PDURef(pdu_ref=J1939_PDU, bus_ref=J1939_BUS, direction="sender")],
    )
    model = _model(app)
    assert model.apps[0].can_frame_refs[0].frame_ref == CAN_ID


@pytest.mark.parametrize(
    "refs, error_id, fragment",
    [
        pytest.param(
            {"can_frame_refs": [AppCANFrameRef(bus_ref="NOPE", frame_ref=CAN_ID, id_format="standard_11bit", direction="sender")]},
            UNKNOWN_BUS_ERROR_ID,
            "NOPE",
            id="unknown_bus",
        ),
        pytest.param(
            {"can_frame_refs": [AppCANFrameRef(bus_ref=CAN_BUS, frame_ref=0x7FF, id_format="standard_11bit", direction="sender")]},
            UNRESOLVED_FRAME_ERROR_ID,
            "0x7ff",
            id="unknown_can_id",
        ),
        pytest.param(
            {"can_frame_refs": [AppCANFrameRef(bus_ref=CAN_BUS, frame_ref=CAN_ID, id_format="extended_29bit", direction="sender")]},
            UNRESOLVED_FRAME_ERROR_ID,
            "extended_29bit",
            id="wrong_id_format",
        ),
        pytest.param(
            {"j1939_frame_refs": [AppJ1939FrameRef(bus_ref=J1939_BUS, pgn=0x1234, direction="receiver")]},
            UNRESOLVED_PGN_ERROR_ID,
            "0x1234",
            id="unknown_pgn",
        ),
    ],
)
def test_unresolved_frame_ref_rejected(refs, error_id, fragment):
    """A CAN / J1939 frame reference that does not resolve on its bus is rejected."""
    app = App(name=APP_NAME, **refs)
    with pytest.raises(ValidationError) as exc_info:
        _model(app)
    assert_single_error(exc_info, error_id, fragment)


@pytest.mark.parametrize(
    "refs, fragment",
    [
        pytest.param({"can_pdu_refs": [AppCANPDURef(pdu_ref="Ghost", bus_ref=CAN_BUS, direction="sender")]}, "Ghost", id="unknown_pdu"),
        pytest.param({"can_pdu_refs": [AppCANPDURef(pdu_ref=J1939_PDU, bus_ref=J1939_BUS, direction="sender")]}, J1939_PDU, id="j1939_pdu_as_can"),
        pytest.param({"j1939_pdu_refs": [AppJ1939PDURef(pdu_ref=CAN_PDU, bus_ref=CAN_BUS, direction="sender")]}, CAN_PDU, id="can_pdu_as_j1939"),
        pytest.param({"can_pdu_refs": [AppCANPDURef(pdu_ref=J1939_PDU, bus_ref=CAN_BUS, direction="sender")]}, J1939_PDU, id="pdu_packed_elsewhere"),
    ],
)
def test_unresolved_pdu_ref_rejected(refs, fragment):
    """A PDU reference must name a PDU packed by a frame of the matching kind on the referenced bus."""
    app = App(name=APP_NAME, **refs)
    with pytest.raises(ValidationError) as exc_info:
        _model(app)
    assert_single_error(exc_info, UNRESOLVED_PDU_ERROR_ID, fragment)


def test_ipc_channel_shared_between_roles_loads():
    """An app taking part in a channel of its ECU validates."""
    app = App(name=APP_NAME, ipc_refs=[IPCChannelReference(channel_ref="ch", role="bidirectional")])
    model = _model(app, ipc_channels=[IPCChannel(name="ch", transport="shared_memory", max_payload_size=4096)])
    assert model.ecus[0].ipc_channels[0].transport == "shared_memory"


def test_ipc_ref_to_channel_of_other_ecu_rejected():
    """An IPC reference naming a channel the hosting ECU does not define is rejected."""
    app = App(name=APP_NAME, ipc_refs=[IPCChannelReference(channel_ref="ghost", role="producer")])
    channels = [IPCChannel(name="ch", transport="pipe")]
    with pytest.raises(ValidationError) as exc_info:
        _model(app, ipc_channels=channels)
    assert_single_error(exc_info, UNRESOLVED_IPC_CHANNEL_ERROR_ID, "ghost")


def test_duplicate_ipc_channel_names_rejected():
    """Two IPC channels of one ECU must not share a name."""
    app = App(name=APP_NAME)
    channels = [IPCChannel(name="ch", transport="pipe"), IPCChannel(name="ch", transport="unix_socket")]
    with pytest.raises(ValidationError) as exc_info:
        _model(app, ipc_channels=channels)
    assert_single_error(exc_info, DUPLICATE_IPC_CHANNEL_ERROR_ID, "IPC channel names")


def test_app_duplicate_refs_warn():
    """Listing the same frame twice still validates but emits the uniqueness warning."""
    ref = AppCANFrameRef(bus_ref=CAN_BUS, frame_ref=CAN_ID, id_format="standard_11bit", direction="sender")
    app = App(name=APP_NAME, can_frame_refs=[ref, ref])
    assert len(app.can_frame_refs) == 2


def test_app_sender_and_receiver_of_same_frame_on_same_bus_rejected():
    """A frame that is both sent and received on one bus is invalid; a gateway must use different buses."""
    refs = [
        AppCANFrameRef(bus_ref=CAN_BUS, frame_ref=CAN_ID, id_format="standard_11bit", direction=direction) for direction in ("receiver", "sender")
    ]
    with pytest.raises(ValidationError) as exc_info:
        App(name=APP_NAME, can_frame_refs=refs)
    assert_single_error(exc_info, SENDS_AND_RECEIVES_ERROR_ID, "both sends and receives CAN frame")


def test_app_sender_and_receiver_of_same_frame_on_different_buses_accepted():
    """Gateway case: the same frame ID received on one bus and sent on another is fine."""
    refs = [
        AppCANFrameRef(bus_ref=bus, frame_ref=CAN_ID, id_format="standard_11bit", direction=direction)
        for bus, direction in (("CAN_A", "receiver"), ("CAN_B", "sender"))
    ]
    assert len(App(name=APP_NAME, can_frame_refs=refs).can_frame_refs) == 2


def test_app_overlapping_ipc_roles_still_validate():
    """Listing a channel as producer and bidirectional is redundant, not invalid."""
    refs = [IPCChannelReference(channel_ref="ch", role=role) for role in ("producer", "bidirectional")]
    assert len(App(name=APP_NAME, ipc_refs=refs).ipc_refs) == 2


@pytest.mark.parametrize(
    "refs, interfaces, fragment",
    [
        pytest.param(
            {"can_frame_refs": [AppCANFrameRef(bus_ref=CAN_BUS, frame_ref=CAN_ID, id_format="standard_11bit", direction="sender")]},
            _bare_interfaces(),
            "CAN frame 0x100",
            id="can_frame_no_interface",
        ),
        pytest.param(
            {"can_frame_refs": [AppCANFrameRef(bus_ref=CAN_BUS, frame_ref=CAN_ID, id_format="standard_11bit", direction="receiver")]},
            _full_interfaces(),
            "CAN frame 0x100",
            id="can_frame_wrong_direction",
        ),
        pytest.param(
            {"j1939_frame_refs": [AppJ1939FrameRef(bus_ref=J1939_BUS, pgn=PGN, direction="sender")]},
            _bare_interfaces(),
            "J1939 PGN 0xfef1",
            id="j1939_frame_no_interface",
        ),
        pytest.param(
            {"j1939_frame_refs": [AppJ1939FrameRef(bus_ref=J1939_BUS, pgn=PGN, direction="receiver")]},
            _full_interfaces(),
            "J1939 PGN 0xfef1",
            id="j1939_frame_wrong_direction",
        ),
        pytest.param(
            {"can_pdu_refs": [AppCANPDURef(pdu_ref=CAN_PDU, bus_ref=CAN_BUS, direction="sender")]},
            _bare_interfaces(),
            f"PDU '{CAN_PDU}'",
            id="can_pdu_no_interface",
        ),
    ],
)
def test_app_refs_without_interface_warn(refs, interfaces, fragment):
    """A bound app whose frame / PDU reference no CAN interface of its controller declares is warned about."""
    result = _load(App(name=APP_NAME, **refs), MISSING_INTERFACE_WARNING_ID, can_interfaces=interfaces)
    assert_single_warning(result, MISSING_INTERFACE_WARNING_ID, fragment)


def test_app_refs_with_interfaces_do_not_warn():
    """Interfaces declaring the referenced frames and buses silence the missing-interface warning."""
    app = App(
        name=APP_NAME,
        can_frame_refs=[AppCANFrameRef(bus_ref=CAN_BUS, frame_ref=CAN_ID, id_format="standard_11bit", direction="sender")],
        j1939_frame_refs=[AppJ1939FrameRef(bus_ref=J1939_BUS, pgn=PGN, direction="sender")],
        can_pdu_refs=[AppCANPDURef(pdu_ref=CAN_PDU, bus_ref=CAN_BUS, direction="sender")],
    )
    assert_no_findings(_load(app, MISSING_INTERFACE_WARNING_ID))


@pytest.mark.parametrize(
    "role, missing",
    [
        pytest.param("producer", "consumer", id="producer_only"),
        pytest.param("consumer", "producer", id="consumer_only"),
    ],
)
def test_unpaired_ipc_channel_warns(role, missing):
    """An IPC channel whose bound apps only produce or only consume is warned about."""
    app = App(name=APP_NAME, ipc_refs=[IPCChannelReference(channel_ref="ch", role=role)])
    result = _load(app, UNPAIRED_IPC_WARNING_ID, ipc_channels=[IPCChannel(name="ch", transport="pipe")])
    assert_single_warning(result, UNPAIRED_IPC_WARNING_ID, f"lacks a {missing}")


def test_unused_ipc_channel_warns():
    """An IPC channel no bound app references lacks a producer."""
    result = _load(App(name=APP_NAME), UNPAIRED_IPC_WARNING_ID, ipc_channels=[IPCChannel(name="ch", transport="pipe")])
    assert_single_warning(result, UNPAIRED_IPC_WARNING_ID, "lacks a producer")


def test_bidirectional_ipc_channel_does_not_warn():
    """A bidirectional participant is both producer and consumer."""
    app = App(name=APP_NAME, ipc_refs=[IPCChannelReference(channel_ref="ch", role="bidirectional")])
    assert_no_findings(_load(app, UNPAIRED_IPC_WARNING_ID, ipc_channels=[IPCChannel(name="ch", transport="pipe")]))
