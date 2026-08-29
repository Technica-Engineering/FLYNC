"""Tests for flync_converter.converters.dbc."""

import logging
from unittest.mock import MagicMock, patch

import pytest

from flync.model.flync_4_signal.pdu import ContainerPDU, MultiplexedPDU, StandardPDU
from flync_converter.base import ConverterConfig
from flync_converter.converters.dbc import DbcConverter, DbcConverterConfig
from flync_converter.converters.dbc.decoder import (
    _build_pdu_for_message,
    _to_flync_frame,
    decode_dbc_files,
    map_data_type,
)
from flync_converter.converters.dbc.encoder import (
    _build_can_messages,
    _collect_frame_participants,
    _decode_multiplexed_pdu,
    _decode_standard_pdu,
    decode_pdu,
    decode_signal,
    decode_signal_instance,
    write_dbc_files,
)
from flync_converter.converters.dbc.loading import (
    _attribute_value,
    _fd_baud_rate,
    _nominal_baud_rate,
    load_dbc_files,
)

_BUS_A_DBC = """\
VERSION "1.0"

NS_ :

BS_:

BU_: NODE1 NODE2 NODE3

BO_ 256 SpeedMsg: 8 NODE1
 SG_ Speed : 0|16@1+ (0.01,0) [0|300] "km/h" NODE2,NODE3
 SG_ Mode : 16|4@1+ (1,0) [0|15] "" NODE2
 SG_ Sel : 20|4@1+ (1,0) [0|15] "" NODE2
 SG_ Data1 M : 24|8@1+ (1,0) [0|255] "" NODE2
 SG_ Data2 m0 : 32|8@1+ (1,0) [0|255] "" NODE2
 SG_ Data2 m1 : 32|8@1+ (1,0) [0|255] "" NODE2

VAL_ 256 Speed 0 "Off" 1 "On" 3 "Auto" ;
"""

_BUS_B_DBC = """\
VERSION ""

NS_ :

BS_:

BU_: NODE3 NODE4

BO_ 512 TempMsg: 8 NODE3
 SG_ Temp : 0|16@1- (0.1,0) [-40|120] "degC" NODE4
"""


def _write_dbc(tmp_path, name, content):
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


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
    sig.lower_limit = None
    sig.upper_limit = None
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

    def test_small_raw_bounds_are_integers(self):
        sig = _mock_signal(name="byte", bit_length=8)
        result = decode_signal(sig, bit_pos=0)
        assert result.minimum == 0
        assert result.maximum == 255
        assert isinstance(result.maximum, int)

    def test_large_raw_bounds_use_scientific_notation(self):
        sig = _mock_signal(name="blob", bit_length=64)
        result = decode_signal(sig, bit_pos=0)
        assert result.maximum == float(2**64 - 1)
        assert isinstance(result.maximum, float)
        assert str(result.maximum) == "1.8446744073709552e+19"

        wide = decode_signal(_mock_signal(name="wide", bit_length=512), bit_pos=0)
        assert isinstance(wide.maximum, float)
        assert str(wide.maximum).startswith("1.3407807929942597e+154")

    def test_integral_float_limits_render_as_integers(self):
        sig = _mock_signal(name="f", bit_length=16)
        sig.lower_limit = -40.0
        sig.upper_limit = 120.0
        result = decode_signal(sig, bit_pos=0)
        assert result.minimum == -40
        assert result.maximum == 120
        assert isinstance(result.minimum, int)
        assert isinstance(result.maximum, int)

    def test_large_float_limit_stays_scientific(self):
        sig = _mock_signal(name="f", bit_length=64)
        sig.lower_limit = 0.0
        sig.upper_limit = float("1.8446744074e+19")
        result = decode_signal(sig, bit_pos=0)
        assert result.minimum == 0
        assert isinstance(result.maximum, float)
        assert str(result.maximum) == "1.8446744074e+19"

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
        with caplog.at_level(logging.WARNING, logger="flync_converter.converters.dbc.encoder"):
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
        result = _decode_multiplexed_pdu(MagicMock(), pdu, 0, None, pdus={})
        assert len(result) == 1
        assert result[0].name == "sel"

    def test_with_mux_group(self):
        sel_inst = _mock_si(_mock_signal("sel", 4), 0)
        data_inst = _mock_si(_mock_signal("data", 8), 8)
        data_pdu = StandardPDU.model_construct(name="data_pdu", length=8, signals=[data_inst], signal_groups=[])
        grp = MagicMock()
        grp.pdu = MagicMock(pdu_ref="data_pdu", bit_position=0)
        grp.selector_value = 1
        pdu = MagicMock()
        pdu.selector_signal = sel_inst
        pdu.static_group = None
        pdu.mux_groups = [grp]
        result = _decode_multiplexed_pdu(MagicMock(), pdu, 0, None, pdus={"data_pdu": data_pdu})
        assert len(result) == 2
        assert result[0].name == "sel"
        assert result[1].name == "data"

    def test_mux_group_missing_reference_warns(self, caplog):
        sel_inst = _mock_si(_mock_signal("sel", 4), 0)
        grp = MagicMock()
        grp.pdu = MagicMock(pdu_ref="missing_pdu", bit_position=0)
        grp.selector_value = 0
        pdu = MagicMock()
        pdu.selector_signal = sel_inst
        pdu.static_group = None
        pdu.mux_groups = [grp]
        with caplog.at_level(logging.WARNING, logger="flync_converter.converters.dbc.encoder"):
            result = _decode_multiplexed_pdu(MagicMock(), pdu, 0, None, pdus={})
        assert len(result) == 1  # only the selector
        assert "Referenced mux PDU 'missing_pdu' not found" in caplog.text

    def test_mux_group_signal_group_warns(self, caplog):
        sel_inst = _mock_si(_mock_signal("sel", 4), 0)
        grp_pdu = StandardPDU.model_construct(name="grp_pdu", length=8, signals=[], signal_groups=[MagicMock()])
        grp = MagicMock()
        grp.pdu = MagicMock(pdu_ref="grp_pdu", bit_position=0)
        grp.selector_value = 0
        pdu = MagicMock()
        pdu.selector_signal = sel_inst
        pdu.static_group = None
        pdu.mux_groups = [grp]
        with caplog.at_level(logging.WARNING, logger="flync_converter.converters.dbc.encoder"):
            _decode_multiplexed_pdu(MagicMock(), pdu, 0, None, pdus={"grp_pdu": grp_pdu})
        assert "Signal Group inside MuxGroup not supported" in caplog.text

    def test_with_static_group(self):
        sel_inst = _mock_si(_mock_signal("sel", 4), 0)
        static_si = _mock_si(_mock_signal("static_sig", 8), 4)
        static_pdu = StandardPDU.model_construct(name="static_pdu", length=8, signals=[static_si], signal_groups=[])
        pdu = MagicMock()
        pdu.selector_signal = sel_inst
        pdu.static_group = [MagicMock(pdu_ref="static_pdu", bit_position=0)]
        pdu.mux_groups = []
        result = _decode_multiplexed_pdu(MagicMock(), pdu, 0, None, pdus={"static_pdu": static_pdu})
        assert len(result) == 2
        assert result[0].name == "sel"
        assert result[1].name == "static_sig"

    def test_with_multiple_static_groups(self):
        sel_inst = _mock_si(_mock_signal("sel", 4), 0)
        static_1 = StandardPDU.model_construct(name="static_1", length=8, signals=[_mock_si(_mock_signal("static_sig_1", 8), 4)], signal_groups=[])
        static_2 = StandardPDU.model_construct(name="static_2", length=8, signals=[_mock_si(_mock_signal("static_sig_2", 8), 0)], signal_groups=[])
        pdu = MagicMock()
        pdu.selector_signal = sel_inst
        pdu.static_group = [MagicMock(pdu_ref="static_1", bit_position=0), MagicMock(pdu_ref="static_2", bit_position=16)]
        pdu.mux_groups = []
        result = _decode_multiplexed_pdu(MagicMock(), pdu, 0, None, pdus={"static_1": static_1, "static_2": static_2})
        assert len(result) == 3
        assert result[0].name == "sel"
        assert [s.name for s in result[1:]] == ["static_sig_1", "static_sig_2"]
        assert [s.start for s in result[1:]] == [4, 16]


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
        with caplog.at_level(logging.WARNING, logger="flync_converter.converters.dbc.encoder"):
            result = decode_pdu(MagicMock(), container, 0)
        assert "ContainerPDU not implemented" in caplog.text
        assert result == []

    def test_unknown_type_warns_and_returns_empty(self, caplog):
        with caplog.at_level(logging.WARNING, logger="flync_converter.converters.dbc.encoder"):
            result = decode_pdu(MagicMock(), MagicMock(spec_set=[]), 0)
        assert result == []


class TestCollectFrameParticipants:
    def test_empty_model(self):
        model = MagicMock()
        model.ecus = []
        senders, receivers = _collect_frame_participants(model)
        assert senders == {}
        assert receivers == {}

    def test_single_ecu(self):
        sf = MagicMock()
        sf.frame_ref = 0x100
        sf.bus_ref = "BUS_A"
        rf = MagicMock()
        rf.frame_ref = 0x200
        rf.bus_ref = "BUS_A"
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
        assert senders == {("BUS_A", 0x100): ["ECU_A"]}
        assert receivers == {("BUS_A", 0x200): ["ECU_A"]}

    def test_no_can_interfaces(self):
        ctrl = MagicMock()
        ctrl.can_interfaces = None
        ecu = MagicMock()
        ecu.name = "ECU_B"
        ecu.controllers = [ctrl]
        model = MagicMock()
        model.ecus = [ecu]
        senders, receivers = _collect_frame_participants(model)
        assert senders == {}
        assert receivers == {}

    def test_multiple_ecus_same_frame(self):
        def _ecu(name, frame_ref, bus_ref="BUS_X"):
            sf = MagicMock()
            sf.frame_ref = frame_ref
            sf.bus_ref = bus_ref
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
        model.ecus = [_ecu("E1", 0x100), _ecu("E2", 0x100)]
        senders, _ = _collect_frame_participants(model)
        assert senders == {("BUS_X", 0x100): ["E1", "E2"]}


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
    def test_no_communication_warns(self, caplog):
        model = MagicMock()
        model.communication = None
        with caplog.at_level(logging.WARNING, logger="flync_converter.converters.dbc.encoder"):
            write_dbc_files(model, "/tmp")
        assert "Could not find communication/channels" in caplog.text

    def test_no_channels_warns(self, caplog):
        model = MagicMock()
        model.communication.channels = None
        with caplog.at_level(logging.WARNING, logger="flync_converter.converters.dbc.encoder"):
            write_dbc_files(model, "/tmp")
        assert "Could not find communication/channels" in caplog.text

    def test_no_can_buses_no_output(self, tmp_path):
        model = MagicMock()
        model.communicationcation.channels.pdus = []
        model.communication.channels.can_buses = []
        model.ecus = []
        write_dbc_files(model, str(tmp_path))
        assert list(tmp_path.glob("*.dbc")) == []

    def test_writes_one_dbc_per_bus(self, tmp_path):
        bus = MagicMock()
        bus.name = "CAN1"
        bus.frames = []
        model = MagicMock()
        model.communication.channels.pdus = []
        model.communication.channels.can_buses = [bus]
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
        assert len(result) == 1
        db, path = result[0]
        assert db is mock_db
        assert path.name == "bus.dbc"

    def test_loads_multiple_dbc_files(self, tmp_path):
        (tmp_path / "a.dbc").write_text("")
        (tmp_path / "b.dbc").write_text("")
        mock_db = MagicMock()
        with patch("cantools.database.load_file", return_value=mock_db):
            result = load_dbc_files(str(tmp_path))
        assert len(result) == 2
        assert {path.name for _, path in result} == {"a.dbc", "b.dbc"}

    def test_ignores_non_dbc_files(self, tmp_path):
        (tmp_path / "file.yaml").write_text("")
        (tmp_path / "file.json").write_text("")
        assert load_dbc_files(str(tmp_path)) == []

    def test_loads_single_dbc_file_path(self, tmp_path):
        # Passing a single *.dbc file (not a directory) must still be loaded, so
        # the converter works when pointed directly at a file (as the round-trip
        # example scripts do).
        dbc_file = tmp_path / "bus.dbc"
        dbc_file.write_text("")
        mock_db = MagicMock()
        with patch("cantools.database.load_file", return_value=mock_db):
            result = load_dbc_files(str(dbc_file))
        assert len(result) == 1
        db, path = result[0]
        assert db is mock_db
        assert path == dbc_file


class TestDbcConverter:
    def test_can_decode_is_true(self):
        assert DbcConverter().can_decode() is True

    def test_encode_requires_config(self):
        converter = DbcConverter()
        model = MagicMock()

        with pytest.raises(ValueError, match="config must be set"):
            converter.encode(model)

    def test_decode_requires_config(self):
        converter = DbcConverter()

        with pytest.raises(ValueError, match="config must be set"):
            converter.decode()

    def test_encode_with_empty_model(self, tmp_path):
        conv = DbcConverter(ConverterConfig(config_path=str(tmp_path)))
        model = MagicMock()
        model.communication.channels.can_buses = []
        model.communication.channels.pdus = []
        model.ecus = []
        conv.encode(model)
        assert list(tmp_path.glob("*.dbc")) == []

    def test_decode_empty_dir_returns_empty_model(self, tmp_path):
        conv = DbcConverter(ConverterConfig(config_path=str(tmp_path)))
        result = conv.decode()
        assert result.communication.channels.can_buses == []
        assert result.communication.channels.pdus == []
        assert result.ecus == []

    def test_name_is_dbc(self):
        assert DbcConverter.name == "dbc"


class TestDbcConverterConfig:
    def test_defaults(self):
        cfg = DbcConverterConfig(config_path="/tmp")
        assert cfg.baud_rate_default == 500_000
        assert cfg.fd_baud_rate_default == 2_000_000


class TestBaudRateAttributes:
    def _db(self, applied=None, defs=None):
        db = MagicMock()
        applied = dict(applied or {})
        defs = dict(defs or {})
        db.dbc.attributes = applied
        db.dbc.attribute_definitions = defs
        return db

    def test_applied_value_wins(self):
        db = self._db()
        db.dbc.attributes["Baudrate"] = MagicMock(value=250_000)
        db.dbc.attribute_definitions["Baudrate"] = MagicMock(default_value=500_000)
        cfg = DbcConverterConfig(config_path="")
        assert _nominal_baud_rate(db, cfg) == 250_000

    def test_definition_default_used(self):
        db = self._db()
        db.dbc.attribute_definitions["Baudrate"] = MagicMock(default_value=500_000)
        cfg = DbcConverterConfig(config_path="")
        assert _nominal_baud_rate(db, cfg) == 500_000

    def test_absent_uses_default(self):
        cfg = DbcConverterConfig(config_path="")
        assert _nominal_baud_rate(self._db(), cfg) == 500_000
        assert _fd_baud_rate(self._db(), cfg) == 2_000_000

    def test_disallowed_value_falls_back(self):
        db = self._db()
        db.dbc.attribute_definitions["Baudrate"] = MagicMock(default_value=123_456)
        cfg = DbcConverterConfig(config_path="")
        assert _nominal_baud_rate(db, cfg) == 500_000

    def test_fd_baud_rate_from_attribute(self):
        db = self._db()
        db.dbc.attribute_definitions["BaudrateCANFD"] = MagicMock(default_value=2_000_000)
        cfg = DbcConverterConfig(config_path="")
        assert _fd_baud_rate(db, cfg) == 2_000_000

    def test_non_int_attribute_value_ignored(self):
        db = self._db()
        db.dbc.attributes["Baudrate"] = MagicMock(value="fast")
        cfg = DbcConverterConfig(config_path="")
        assert _nominal_baud_rate(db, cfg) == 500_000
        assert _attribute_value(db, "Baudrate") is None


class TestMapDataType:
    @pytest.mark.parametrize(
        "length,is_signed,is_float,expected",
        [
            (8, False, False, "uint8"),
            (4, False, False, "uint8"),
            (16, True, False, "int16"),
            (8, True, False, "int8"),
            (32, False, False, "uint32"),
            (32, False, True, "float32"),
            (64, False, True, "float64"),
            (64, False, False, "uint64"),
        ],
        ids=["u8", "sub_byte_unsigned", "i16", "i8", "u32", "f32", "f64", "u64"],
    )
    def test_mapping(self, length, is_signed, is_float, expected):
        assert map_data_type(length, is_signed, is_float).value == expected


class TestDecodeDbcFiles:
    def test_decodes_buses_frames_pdus_and_ecus(self, tmp_path):
        _write_dbc(tmp_path, "BusA.dbc", _BUS_A_DBC)
        _write_dbc(tmp_path, "BusB.dbc", _BUS_B_DBC)

        model = decode_dbc_files(load_dbc_files(str(tmp_path)))

        buses = model.communication.channels.can_buses
        assert [b.name for b in buses] == ["BusA", "BusB"]
        assert all(b.baud_rate == 500_000 for b in buses)

        frame_names = {f.name for b in buses for f in b.frames}
        assert frame_names == {"SpeedMsg", "TempMsg"}
        speed_frame = next(f for b in buses for f in b.frames if f.name == "SpeedMsg")
        assert speed_frame.can_id == 0x100
        assert speed_frame.type == "can"
        assert speed_frame.id_format == "standard_11bit"

    def test_multiplexed_message(self, tmp_path):
        _write_dbc(tmp_path, "BusA.dbc", _BUS_A_DBC)
        model = decode_dbc_files(load_dbc_files(str(tmp_path)))

        pdu_names = {p.name for p in model.communication.channels.pdus}
        assert "BusA_SpeedMsg" in pdu_names
        mux = next(p for p in model.communication.channels.pdus if p.name == "BusA_SpeedMsg")
        assert isinstance(mux, MultiplexedPDU)
        assert mux.selector_signal.signal.name == "Data1"
        assert {g.selector_value for g in mux.mux_groups} == {0, 1}

        static = next(p for p in model.communication.channels.pdus if p.name == "BusA_SpeedMsg_static")
        speed = next(si for si in static.signals if si.signal.name == "Speed")
        assert speed.signal.factor == 0.01
        assert speed.signal.value_encoding is not None
        labels = [e.label for e in speed.signal.value_encoding.entries]
        assert labels == ["Off", "On", "Auto"]

    def test_standard_message_signed_signal(self, tmp_path):
        _write_dbc(tmp_path, "BusB.dbc", _BUS_B_DBC)
        model = decode_dbc_files(load_dbc_files(str(tmp_path)))

        pdu = next(p for p in model.communication.channels.pdus if p.name == "BusB_TempMsg")
        assert isinstance(pdu, StandardPDU)
        temp = pdu.signals[0].signal
        assert temp.bit_length == 16
        assert temp.data_type.value == "int16"
        assert temp.factor == 0.1
        assert temp.offset == 0.0
        assert temp.lower_limit == -40.0
        assert temp.upper_limit == 120.0
        assert temp.unit == "degC"

    def test_ecus_synthesized_with_sender_receiver_refs(self, tmp_path):
        _write_dbc(tmp_path, "BusA.dbc", _BUS_A_DBC)
        _write_dbc(tmp_path, "BusB.dbc", _BUS_B_DBC)
        model = decode_dbc_files(load_dbc_files(str(tmp_path)))

        ecu_by_name = {e.name: e for e in model.ecus}
        assert set(ecu_by_name) == {"NODE1", "NODE2", "NODE3", "NODE4"}

        node1 = ecu_by_name["NODE1"]
        iface = node1.controllers[0].can_interfaces[0]
        assert iface.bus_ref == "BusA"
        assert {sf.frame_ref for sf in iface.sender_frames} == {0x100}
        assert iface.receiver_frames == []

        node3 = ecu_by_name["NODE3"]
        ifaces = {i.bus_ref: i for i in node3.controllers[0].can_interfaces}
        assert set(ifaces) == {"BusA", "BusB"}
        assert {rf.frame_ref for rf in ifaces["BusA"].receiver_frames} == {0x100}
        assert {sf.frame_ref for sf in ifaces["BusB"].sender_frames} == {0x200}


class TestBuildPduForMessage:
    def test_standard_message_no_aux_pdus(self):
        msg = MagicMock()
        msg.name = "Foo"
        msg.is_multiplexer = False
        sig = MagicMock()
        sig.name = "A"
        sig.length = 8
        sig.is_signed = False
        sig.is_float = False
        sig.scale = 1.0
        sig.offset = 0.0
        sig.unit = None
        sig.start = 0
        sig.byte_order = "little_endian"
        sig.minimum = None
        sig.maximum = None
        sig.comment = None
        sig.raw_initial = None
        sig.choices = None
        sig.is_multiplexer = False
        sig.multiplexer_signal = None
        sig.multiplexer_ids = None
        msg.signals = [sig]

        pdu, extra = _build_pdu_for_message(msg, "BUS")
        assert isinstance(pdu, StandardPDU)
        assert extra == []

    def test_to_flync_frame_can_and_fd(self):
        std_msg = MagicMock()
        std_msg.name = "M1"
        std_msg.length = 8
        std_msg.frame_id = 0x100
        std_msg.is_extended_frame = False
        std_msg.is_fd = False
        std_msg.comment = None
        frame = _to_flync_frame(std_msg, "BUS_M1")
        assert frame.type == "can"
        assert frame.packed_pdus[0].pdu_ref == "BUS_M1"

        fd_msg = MagicMock()
        fd_msg.name = "M2"
        fd_msg.length = 64
        fd_msg.frame_id = 0x200
        fd_msg.is_extended_frame = True
        fd_msg.is_fd = True
        fd_msg.comment = "hi"
        frame = _to_flync_frame(fd_msg, "BUS_M2")
        assert frame.type == "can_fd"
        assert frame.id_format == "extended_29bit"
        assert frame.description == "hi"


class TestRoundTrip:
    """Decode DBC -> FLYNC -> encode -> reload, checking the result is preserved."""

    def _round_trip(self, tmp_path):
        for name, content in (("BusA.dbc", _BUS_A_DBC), ("BusB.dbc", _BUS_B_DBC)):
            _write_dbc(tmp_path, name, content)
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        model = decode_dbc_files(load_dbc_files(str(tmp_path)))
        write_dbc_files(model, str(out_dir))
        import cantools.database as cdb

        return [cdb.load_file(str(out_dir / n)) for n in ("BusA.dbc", "BusB.dbc")]

    def test_buses_and_frames_preserved(self, tmp_path):
        bus_a_db, bus_b_db = self._round_trip(tmp_path)
        by_id = {m.frame_id: m for m in bus_a_db.messages}
        assert 0x100 in by_id
        assert by_id[0x100].name == "SpeedMsg"
        assert by_id[0x100].length == 8
        assert 0x200 in {m.frame_id for m in bus_b_db.messages}

    def test_standard_signal_attributes_preserved(self, tmp_path):
        _, bus_b_db = self._round_trip(tmp_path)
        (temp,) = bus_b_db.messages
        (signal,) = temp.signals
        assert signal.name == "Temp"
        assert signal.start == 0
        assert signal.length == 16
        assert signal.is_signed is True

    def test_multiplexed_round_trip(self, tmp_path):
        bus_a_db, _ = self._round_trip(tmp_path)
        msg = next(m for m in bus_a_db.messages if m.name == "SpeedMsg")

        assert [(s.name, s.start, s.length) for s in msg.signals] == [
            ("Speed", 0, 16),
            ("Mode", 16, 4),
            ("Sel", 20, 4),
            ("Data1", 24, 8),
            ("Data2", 32, 8),
            ("Data2", 32, 8),
        ]

        # Static (non-multiplexed) signals survive unchanged.
        static = [s.name for s in msg.signals if not s.is_multiplexer and s.multiplexer_signal is None]
        assert static == ["Speed", "Mode", "Sel"]

        # The selector still marks the multiplexer.
        selector = next(s for s in msg.signals if s.name == "Data1")
        assert selector.is_multiplexer is True
        assert selector.start == 24

        # Every muxed alternative is preserved with its id.
        muxed = [s for s in msg.signals if s.multiplexer_signal == "Data1"]
        assert sorted(mid for s in muxed for mid in (s.multiplexer_ids or [])) == [0, 1]
        assert all(s.start == 32 and s.length == 8 for s in muxed)

    def test_value_encoding_round_trip(self, tmp_path):
        bus_a_db, _ = self._round_trip(tmp_path)
        msg = next(m for m in bus_a_db.messages if m.name == "SpeedMsg")
        speed = next(s for s in msg.signals if s.name == "Speed")
        assert dict(speed.choices) == {0: "Off", 1: "On", 3: "Auto"}
