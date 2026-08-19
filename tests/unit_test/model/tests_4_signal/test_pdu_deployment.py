import pytest
from pydantic import ValidationError

from flync.model.flync_4_signal.pdu_deployment import PDUReceiver, PDUSender


def test_positive_pdu_sender_basic():
    sender = PDUSender(pdu_ref="my_container_pdu")
    assert sender.deployment_type == "pdu_sender"
    assert sender.pdu_ref == "my_container_pdu"


def test_positive_pdu_sender_model_validate():
    data = {"deployment_type": "pdu_sender", "pdu_ref": "container_pdu_1"}
    sender = PDUSender.model_validate(data)
    assert isinstance(sender, PDUSender)


def test_positive_pdu_sender_default_type():
    sender = PDUSender(pdu_ref="pdu_x")
    assert sender.deployment_type == "pdu_sender"


def test_negative_pdu_sender_missing_pdu_ref():
    with pytest.raises(ValidationError):
        PDUSender.model_validate({"deployment_type": "pdu_sender"})


def test_positive_pdu_receiver_basic():
    receiver = PDUReceiver(pdu_ref="my_container_pdu")
    assert receiver.deployment_type == "pdu_receiver"
    assert receiver.pdu_ref == "my_container_pdu"


def test_positive_pdu_receiver_model_validate():
    data = {"deployment_type": "pdu_receiver", "pdu_ref": "container_pdu_1"}
    receiver = PDUReceiver.model_validate(data)
    assert isinstance(receiver, PDUReceiver)


def test_positive_pdu_receiver_default_type():
    receiver = PDUReceiver(pdu_ref="pdu_x")
    assert receiver.deployment_type == "pdu_receiver"


def test_negative_pdu_receiver_missing_pdu_ref():
    with pytest.raises(ValidationError):
        PDUReceiver.model_validate({"deployment_type": "pdu_receiver"})
