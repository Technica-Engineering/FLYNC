"""Tests for flync_converter.converters.dbc_converter."""

import logging
from unittest.mock import MagicMock, patch

import pytest

from flync.model.flync_4_signal.pdu import ContainerPDU, MultiplexedPDU, StandardPDU
from flync_converter.base import ConverterConfig
from flync_converter.converters.dbc_converter import (
    DbcConverter,
    _build_can_messages,
    _collect_frame_participants,
    _decode_multiplexed_pdu,
    _decode_standard_pdu,
    decode_pdu,
    decode_signal,
    decode_signal_instance,
    load_dbc_files,
    write_dbc_files,
)


def _mock_signal(name="spd", bit_length=8, is_signed=False, factor=1.0, offset=0.0, unit="km/h", description=None):
    sig = MagicMock()
    sig.name = name
    sig.bit_length = bit_length
    sig.data_type.is_signed_integer.return_value = is_signed
    sig.data_type.is_float.return_value = False
    sig.factor = factor
    sig.offset = offset
    sig.unit = unit
    sig.description = description
    return sig


def _mock_si(signal, bit_position=0):
    si = MagicMock()
    si.signal = signal
    si.bit_position = bit_position
    return si


class TestDecodeSignal:
    def test_basic_properties(self):
        sig = _mock_signal(name="speed", bit_length=8)
        result = decode_signal(sig, bit_pos=0)
        assert result.name == "speed"
        assert result.start == 0
        assert result.length == 8
        assert result.byte_order == "little_endian"
        assert not result.is_signed

    def test_big_endian_and_signed(self):
        sig = _mock_signal(name="temp", bit_length=16, is_signed=True)
        result = decode_signal(sig, bit_pos=8, byte_order="big_endian")
        assert result.start == 8
        assert result.byte_order == "big_endian"
        assert result.is_signed

    def test_bit_position_offset(self):
        sig = _mock_signal(name="v", bit_length=8)
        result = decode_signal(sig, bit_pos=24)
        assert result.start == 24

    def test_unit_preserved(self):
        sig = _mock_signal(name="rpm", unit="1/min")
        result = decode_signal(sig, bit_pos=0)
        assert result.unit == "1/min"

    def test_null_unit_becomes_empty_string(self):
        sig = _mock_signal(name="x", unit=None)
        result = decode_signal(sig, bit_pos=0)
        assert result.unit == ""

    def test_receivers_passed_through(self):
        sig = _mock_signal()
        result = decode_signal(sig, bit_pos=0, receivers=["ECU_A", "ECU_B"])
        assert result.receivers == ["ECU_A", "ECU_B"]

    def test_multiplexer_fields(self):
        sig = _mock_signal(name="sel", bit_length=4)
        result = decode_signal(
            sig,
            bit_pos=0,
            is_multiplexer=True,
            multiplexer_signal="mux_sel",
            multiplexer_ids=[0, 1],
        )
        assert result.is_multiplexer
        assert result.multiplexer_signal == "mux_sel"
        assert result.multiplexer_ids == [0, 1]


class TestDecodeSignalInstance:
    def test_offset_applied(self):
        sig = _mock_signal(name="foo", bit_length=8)
        si = _mock_si(sig, bit_position=16)
        result = decode_signal_instance(si, bit_pos=8)
        assert result.start == 24

    def test_none_bit_position_treated_as_zero(self):
        sig = _mock_signal(name="bar", bit_length=4)
        si = _mock_si(sig, bit_position=None)
        result = decode_signal_instance(si, bit_pos=4)
        assert result.start == 4


class TestDecodeStandardPdu:
    def test_empty_pdu(self):
        pdu = MagicMock()
        pdu.signals = []
        pdu.signal_groups = []
        assert _decode_standard_pdu(pdu, 0, None) == []

    def test_two_signals(self):
        s1 = _mock_si(_mock_signal("a", 8), 0)
        s2 = _mock_si(_mock_signal("b", 8), 8)
        pdu = MagicMock()
        pdu.signals = [s1, s2]
        pdu.signal_groups = []
        result = _decode_standard_pdu(pdu, 0, ["recv"])
        assert len(result) == 2
        assert result[0].name == "a"
        assert result[1].name == "b"

    def test_signal_group_warns(self, caplog):
        pdu = MagicMock()
        pdu.signals = []
        pdu.signal_groups = [MagicMock()]
        with caplog.at_level(logging.WARNING, logger="flync_converter.converters.dbc_converter"):
            result = _decode_standard_pdu(pdu, 0, None)
        assert "Signal Group not supported" in caplog.text
        assert result == []


class TestDecodeMultiplexedPdu:
    def test_selector_only(self):
        sel_inst = _mock_si(_mock_signal("sel", 4), 0)
        pdu = MagicMock()
        pdu.selector_signal = sel_inst
        pdu.static_group = None
        pdu.mux_groups = []
        result = _decode_multiplexed_pdu(MagicMock(), pdu, 0, None)
        assert len(result) == 1
        assert result[0].name == "sel"

    def test_with_mux_group(self):
        sel_inst = _mock_si(_mock_signal("sel", 4), 0)
        data_inst = _mock_si(_mock_signal("data", 8), 8)
        grp_pdu = MagicMock()
        grp_pdu.signals = [data_inst]
        grp_pdu.signal_groups = []
        grp = MagicMock()
        grp.pdu = grp_pdu
        grp.selector_value = 1
        pdu = MagicMock()
        pdu.selector_signal = sel_inst
        pdu.static_group = None
        pdu.mux_groups = [grp]
        result = _decode_multiplexed_pdu(MagicMock(), pdu, 0, None)
        assert len(result) == 2
        assert result[0].name == "sel"
        assert result[1].name == "data"

    def test_mux_group_signal_group_warns(self, caplog):
        sel_inst = _mock_si(_mock_signal("sel", 4), 0)
        grp_pdu = MagicMock()
        grp_pdu.signals = []
        grp_pdu.signal_groups = [MagicMock()]
        grp = MagicMock()
        grp.pdu = grp_pdu
        grp.selector_value = 0
        pdu = MagicMock()
        pdu.selector_signal = sel_inst
        pdu.static_group = None
        pdu.mux_groups = [grp]
        with caplog.at_level(logging.WARNING, logger="flync_converter.converters.dbc_converter"):
            _decode_multiplexed_pdu(MagicMock(), pdu, 0, None)
        assert "Signal Group inside MuxGroup not supported" in caplog.text

    def test_with_static_group(self):
        sel_inst = _mock_si(_mock_signal("sel", 4), 0)
        static_si = _mock_si(_mock_signal("static_sig", 8), 4)
        static_pdu = StandardPDU.model_construct(name="sp", length=8, signals=[static_si], signal_groups=[])
        pdu = MagicMock()
        pdu.selector_signal = sel_inst
        pdu.static_group = static_pdu
        pdu.mux_groups = []
        result = _decode_multiplexed_pdu(MagicMock(), pdu, 0, None)
        assert len(result) == 2
        assert result[0].name == "sel"
        assert result[1].name == "static_sig"


class TestDecodePdu:
    def test_none_returns_empty(self):
        assert decode_pdu(MagicMock(), None, 0) == []

    def test_standard_pdu_dispatches(self):
        std = StandardPDU.model_construct(name="p", length=8, signals=[], signal_groups=[])
        assert decode_pdu(MagicMock(), std, 0) == []

    def test_multiplexed_pdu_dispatches(self):
        sel_inst = _mock_si(_mock_signal("sel", 4), 0)
        mux = MultiplexedPDU.model_construct(name="mux", length=8, type="multiplexed", selector_signal=sel_inst, static_group=None, mux_groups=[])
        result = decode_pdu(MagicMock(), mux, 0)
        assert len(result) == 1
        assert result[0].name == "sel"

    def test_container_pdu_warns_and_returns_empty(self, caplog):
        from flync.model.flync_4_signal.pdu import ContainerPDUHeader

        hdr = ContainerPDUHeader.model_construct(id_length_bits=16, length_field_bits=16)
        container = ContainerPDU.model_construct(name="c", length=8, pdu_id=0, header=hdr, contained_pdus=[], type="container")
        with caplog.at_level(logging.WARNING, logger="flync_converter.converters.dbc_converter"):
            result = decode_pdu(MagicMock(), container, 0)
        assert "ContainerPDU not implemented" in caplog.text
        assert result == []

    def test_unknown_type_warns_and_returns_empty(self, caplog):
        with caplog.at_level(logging.WARNING, logger="flync_converter.converters.dbc_converter"):
            result = decode_pdu(MagicMock(), MagicMock(spec_set=[]), 0)
        assert result == []


class TestCollectFrameParticipants:
    def test_empty_model(self):
        model = MagicMock()
        model.ecus = []
        senders, receivers = _collect_frame_participants(model)
        assert senders == {} and receivers == {}

    def test_single_ecu(self):
        sf = MagicMock()
        sf.frame_ref = "FX"
        rf = MagicMock()
        rf.frame_ref = "FY"
        iface = MagicMock()
        iface.sender_frames = [sf]
        iface.receiver_frames = [rf]
        ctrl = MagicMock()
        ctrl.can_interfaces = [iface]
        ecu = MagicMock()
        ecu.name = "ECU_A"
        ecu.controllers = [ctrl]
        model = MagicMock()
        model.ecus = [ecu]
        senders, receivers = _collect_frame_participants(model)
        assert senders == {"FX": ["ECU_A"]}
        assert receivers == {"FY": ["ECU_A"]}

    def test_no_can_interfaces(self):
        ctrl = MagicMock()
        ctrl.can_interfaces = None
        ecu = MagicMock()
        ecu.name = "ECU_B"
        ecu.controllers = [ctrl]
        model = MagicMock()
        model.ecus = [ecu]
        senders, receivers = _collect_frame_participants(model)
        assert senders == {} and receivers == {}

    def test_multiple_ecus_same_frame(self):
        def _ecu(name, frame_ref):
            sf = MagicMock()
            sf.frame_ref = frame_ref
            iface = MagicMock()
            iface.sender_frames = [sf]
            iface.receiver_frames = []
            ctrl = MagicMock()
            ctrl.can_interfaces = [iface]
            e = MagicMock()
            e.name = name
            e.controllers = [ctrl]
            return e

        model = MagicMock()
        model.ecus = [_ecu("E1", "F1"), _ecu("E2", "F1")]
        senders, _ = _collect_frame_participants(model)
        assert senders == {"F1": ["E1", "E2"]}


class TestBuildCanMessages:
    def test_empty_bus(self):
        bus = MagicMock()
        bus.frames = []
        assert _build_can_messages(MagicMock(), bus, {}, {}, {}) == []

    def test_frame_no_pdus(self):
        frame = MagicMock()
        frame.packed_pdus = []
        frame.can_id = 0x100
        frame.name = "F1"
        frame.length = 8
        frame.description = None
        frame.id_format = "standard_11bit"
        frame.type = "can"
        bus = MagicMock()
        bus.frames = [frame]
        result = _build_can_messages(MagicMock(), bus, {}, {}, {})
        assert len(result) == 1
        assert result[0].name == "F1"
        assert result[0].frame_id == 0x100

    def test_frame_extended_fd(self):
        frame = MagicMock()
        frame.packed_pdus = []
        frame.can_id = 0x200
        frame.name = "F2"
        frame.length = 64
        frame.description = "FD frame"
        frame.id_format = "extended_29bit"
        frame.type = "can_fd"
        bus = MagicMock()
        bus.frames = [frame]
        result = _build_can_messages(MagicMock(), bus, {}, {}, {})
        assert result[0].is_extended_frame is True
        assert result[0].is_fd is True

    def test_frame_with_known_pdu(self):
        pdu_inst = MagicMock()
        pdu_inst.pdu_ref = "P1"
        pdu_inst.bit_position = 0
        frame = MagicMock()
        frame.packed_pdus = [pdu_inst]
        frame.can_id = 0x300
        frame.name = "F3"
        frame.length = 8
        frame.description = None
        frame.id_format = "standard_11bit"
        frame.type = "can"
        std = StandardPDU.model_construct(name="P1", length=8, signals=[], signal_groups=[])
        bus = MagicMock()
        bus.frames = [frame]
        result = _build_can_messages(MagicMock(), bus, {"P1": std}, {}, {})
        assert len(result) == 1

    def test_frame_with_unknown_pdu_ref(self):
        pdu_inst = MagicMock()
        pdu_inst.pdu_ref = "MISSING"
        pdu_inst.bit_position = 0
        frame = MagicMock()
        frame.packed_pdus = [pdu_inst]
        frame.can_id = 0x400
        frame.name = "F4"
        frame.length = 8
        frame.description = None
        frame.id_format = "standard_11bit"
        frame.type = "can"
        bus = MagicMock()
        bus.frames = [frame]
        result = _build_can_messages(MagicMock(), bus, {}, {}, {})
        assert len(result) == 1


class TestWriteDbcFiles:
    def test_no_general_warns(self, caplog):
        model = MagicMock()
        model.general = None
        with caplog.at_level(logging.WARNING, logger="flync_converter.converters.dbc_converter"):
            write_dbc_files(model, "/tmp")
        assert "Could not find general/channels" in caplog.text

    def test_no_channels_warns(self, caplog):
        model = MagicMock()
        model.general.channels = None
        with caplog.at_level(logging.WARNING, logger="flync_converter.converters.dbc_converter"):
            write_dbc_files(model, "/tmp")
        assert "Could not find general/channels" in caplog.text

    def test_no_can_buses_no_output(self, tmp_path):
        model = MagicMock()
        model.general.channels.pdus = []
        model.general.channels.can_buses = []
        model.ecus = []
        write_dbc_files(model, str(tmp_path))
        assert list(tmp_path.glob("*.dbc")) == []

    def test_writes_one_dbc_per_bus(self, tmp_path):
        bus = MagicMock()
        bus.name = "CAN1"
        bus.frames = []
        model = MagicMock()
        model.general.channels.pdus = []
        model.general.channels.can_buses = [bus]
        model.ecus = []
        with patch("cantools.database.dump_file") as mock_dump:
            write_dbc_files(model, str(tmp_path))
        mock_dump.assert_called_once()
        call_path = str(mock_dump.call_args[0][1])
        assert "CAN1.dbc" in call_path


class TestLoadDbcFiles:
    def test_empty_directory(self, tmp_path):
        assert load_dbc_files(str(tmp_path)) == []

    def test_loads_dbc_files(self, tmp_path):
        (tmp_path / "bus.dbc").write_text("")
        mock_db = MagicMock()
        with patch("cantools.database.load_file", return_value=mock_db):
            result = load_dbc_files(str(tmp_path))
        assert result == [mock_db]

    def test_loads_multiple_dbc_files(self, tmp_path):
        (tmp_path / "a.dbc").write_text("")
        (tmp_path / "b.dbc").write_text("")
        mock_db = MagicMock()
        with patch("cantools.database.load_file", return_value=mock_db):
            result = load_dbc_files(str(tmp_path))
        assert len(result) == 2

    def test_ignores_non_dbc_files(self, tmp_path):
        (tmp_path / "file.yaml").write_text("")
        (tmp_path / "file.json").write_text("")
        assert load_dbc_files(str(tmp_path)) == []


class TestDbcConverter:
    def test_can_decode_is_false(self):
        assert DbcConverter().can_decode() is False

    def test_encode_requires_config(self):
        with pytest.raises(ValueError, match="config must be set"):
            DbcConverter().encode(MagicMock())

    def test_decode_requires_config(self):
        with pytest.raises(ValueError, match="config must be set"):
            DbcConverter().decode()

    def test_encode_with_empty_model(self, tmp_path):
        conv = DbcConverter(ConverterConfig(config_path=str(tmp_path)))
        model = MagicMock()
        model.general.channels.can_buses = []
        model.general.channels.pdus = []
        model.ecus = []
        conv.encode(model)
        assert list(tmp_path.glob("*.dbc")) == []

    def test_decode_returns_none_for_empty_dir(self, tmp_path):
        conv = DbcConverter(ConverterConfig(config_path=str(tmp_path)))
        result = conv.decode()
        assert result is None

    def test_name_is_dbc(self):
        assert DbcConverter.name == "dbc"
