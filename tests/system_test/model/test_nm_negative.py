# ============================================================================
# Imports
# ============================================================================

import pytest
from pydantic import ValidationError

from flync.model.flync_4_signal.pdu import ContainedPDURef, ContainerPDU, ContainerPDUHeader

# ============================================================================
# Constants
# ============================================================================

NM_PDU_NAME = "NmPdu"

# ============================================================================
# Tests
# ============================================================================
#
# Earlier revisions also carried three "negative" tests for wrong-VLAN
# multicast isolation, an unmapped transport, and a catalog-only NM PDU. They
# were removed on review: all three actually passed on an unrelated
# "Sockets must be tied to the same address as the IPv4 endpoint" error, and
# the behaviours they claimed (VLAN isolation, ignoring an unmapped transport,
# catalog-vs-deployment binding) are not construction-time validations of the
# model. Genuine model-level NM negatives (unknown pdu_ref, duplicate NM PDU)
# live in test_nm_positive.py, next to the model builders they need.


def test_CAN_NM_headerless_container_multiple_pdus_raises():
    """A headerless ContainerPDU (header length 0) may hold only one contained PDU."""
    with pytest.raises(ValidationError, match="only one contained PDU"):
        ContainerPDU(
            name="BadHeaderless",
            length=16,
            pdu_id=0x0003,
            pdu_usage="network_management",
            header=ContainerPDUHeader(id_length_bits=0, length_field_bits=0),
            contained_pdus=[
                ContainedPDURef(pdu_id=1, pdu_ref=NM_PDU_NAME, offset=0),
                ContainedPDURef(pdu_id=2, pdu_ref=NM_PDU_NAME, offset=8),
            ],
        )


def test_Simple_Ethernet_ECU_Multicast_NM_container_too_small_raises():
    """A ContainerPDU too small to hold its per-slot header overhead is rejected."""
    # length=1 is positive (so the generic "> 0" rule is not what trips) yet below
    # the slot-header overhead, so the overhead check is what actually fires.
    with pytest.raises(ValidationError, match="too small to hold"):
        ContainerPDU(
            name="BadContainer",
            length=1,
            pdu_id=0x0002,
            pdu_usage="network_management",
            header=ContainerPDUHeader(id_length_bits=16, length_field_bits=16),
            contained_pdus=[ContainedPDURef(pdu_id=1, pdu_ref=NM_PDU_NAME, offset=0)],
        )
