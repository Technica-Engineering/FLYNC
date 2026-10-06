"""J1939 node identity on ``CANInterface`` (replaces the old ``J1939Application``)."""

import pytest
from pydantic import ValidationError

from flync.model.flync_4_ecu.can_interface import CANInterface
from flync.model.flync_4_ecu.controller import Controller
from tests.error_assertions import assert_single_error

_J1939_NAME_MAX = 18446744073709551615


def _j1939_iface(name="j1939_if", bus_ref="J1939BusCAN", j1939_name=1, source_address=0):
    return CANInterface(name=name, bus_ref=bus_ref, j1939_name=j1939_name, source_address=source_address)


def test_positive_j1939_interface_minimal():
    iface = _j1939_iface()
    assert iface.bus_ref == "J1939BusCAN"
    assert iface.j1939_name == 1
    assert iface.source_address == 0
    assert iface.is_j1939()


def test_positive_j1939_interface_max_name_and_address():
    iface = _j1939_iface(j1939_name=_J1939_NAME_MAX, source_address=253)
    assert iface.j1939_name == _J1939_NAME_MAX
    assert iface.source_address == 253
    assert iface.is_j1939()


def test_positive_plain_can_interface_is_not_j1939():
    iface = CANInterface(name="body_can", bus_ref="BodyCAN")
    assert not iface.is_j1939()


def test_positive_j1939_interface_with_frame_refs_is_j1939():
    from flync.model.flync_4_ecu.can_interface import J1939FrameRef

    sender = CANInterface(
        name="tx", bus_ref="J1939BusCAN", j1939_name=1, source_address=20, j1939_sender_frames=[J1939FrameRef(bus_ref="J1939BusCAN", pgn=0xEF00)]
    )
    receiver = CANInterface(
        name="rx", bus_ref="J1939BusCAN", j1939_name=2, source_address=21, j1939_receiver_frames=[J1939FrameRef(bus_ref="J1939BusCAN", pgn=0xEF00)]
    )
    assert sender.is_j1939()
    assert receiver.is_j1939()
    assert sender.j1939_sender_frames[0].pgn == 0xEF00
    assert receiver.j1939_receiver_frames[0].pgn == 0xEF00


def test_negative_j1939_frame_ref_pgn_out_of_range():
    from flync.model.flync_4_ecu.can_interface import J1939FrameRef

    for pgn in (-1, 0x40000):
        with pytest.raises(ValidationError) as exc_info:
            J1939FrameRef(bus_ref="J1939BusCAN", pgn=pgn)
        assert_single_error(exc_info, None, "pgn")


def test_positive_j1939_interface_with_name_only_is_j1939():
    iface = CANInterface(name="j1939_if2", bus_ref="J1939BusCAN", j1939_name=2)
    assert iface.is_j1939()
    assert iface.source_address is None


def test_negative_j1939_source_address_without_name():
    with pytest.raises(ValidationError) as exc_info:
        CANInterface(name="j1939_if3", bus_ref="J1939BusCAN", source_address=33)
    assert_single_error(exc_info, "FLYNC-ECU-MAJ-REQ-375", "source_address is set but j1939_name is missing; a J1939 node requires a NAME")


def test_negative_j1939_frame_refs_without_name_or_address():
    from flync.model.flync_4_ecu.can_interface import J1939FrameRef

    with pytest.raises(ValidationError) as exc_info:
        CANInterface(name="bad", bus_ref="J1939BusCAN", j1939_sender_frames=[J1939FrameRef(bus_ref="J1939BusCAN", pgn=1)])
    assert_single_error(exc_info, "FLYNC-ECU-MAJ-REQ-376", "a J1939 node requires a NAME")


@pytest.mark.parametrize(
    "field,value,msg",
    [
        pytest.param("j1939_name", -1, "greater than or equal to 0", id="name_neg"),
        pytest.param("j1939_name", _J1939_NAME_MAX + 1, "less than or equal to", id="name_hi"),
        pytest.param("source_address", -1, "greater than or equal to 0", id="addr_neg"),
        pytest.param("source_address", 254, "less than or equal to 253", id="addr_hi"),
    ],
)
def test_negative_j1939_interface_out_of_range(field, value, msg):
    kwargs = dict(name="j1939_rng", bus_ref="J1939BusCAN", j1939_name=1, source_address=0)
    kwargs[field] = value
    with pytest.raises(ValidationError) as exc_info:
        CANInterface(**kwargs)
    assert_single_error(exc_info, None, msg)


def test_positive_controller_with_j1939_interface_counts_as_interface(embedded_metadata_entry):
    ctrl = Controller.model_validate(
        {
            "controller_metadata": embedded_metadata_entry,
            "name": "j1939_controller",
            "can_interfaces": [_j1939_iface()],
        }
    )
    assert len(ctrl.can_interfaces) == 1


def test_negative_controller_without_any_interface_errors(embedded_metadata_entry):
    with pytest.raises(ValidationError) as exc_info:
        Controller.model_validate(
            {
                "controller_metadata": embedded_metadata_entry,
                "name": "empty_controller",
                "ethernet_interfaces": [],
                "can_interfaces": [],
                "lin_interfaces": [],
            }
        )
    assert_single_error(exc_info, "FLYNC-ECU-MAJ-REQ-066", "must declare at least one interface")
