"""Tests for the report data the built-in converters record."""

import json
from types import SimpleNamespace

import pytest
import yaml
from cantools.database.can.signal import Signal

from flync.model.flync_4_signal.signal import SignalDataType
from flync_converter.base import ConverterConfig, ConverterReport
from flync_converter.converters.dbc import DbcConverter, DbcConverterConfig, decode_dbc_files, load_dbc_files, write_dbc_files
from flync_converter.converters.dbc.decoder import _in_range_choices
from flync_converter.converters.flync_converter import log_workspace_diagnostics
from flync_converter.converters.json_converter import JsonConverter, load_json_files
from flync_converter.converters.yaml_converter import YamlConverter, load_yaml_files
from flync_converter.reporting import ConversionReport, reports_root


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# region YAML and JSON loaders


@pytest.mark.parametrize(
    "load, extension, dump",
    [(load_yaml_files, "yaml", yaml.safe_dump), (load_json_files, "json", json.dumps)],
)
def test_loader_reports_input_files_and_overridden_keys(tmp_path, load, extension, dump):
    first = tmp_path / f"a.{extension}"
    second = tmp_path / f"b.{extension}"
    _write(first, dump({"ecus": [1], "apps": []}))
    _write(second, dump({"ecus": [2]}))
    report = ConverterReport()

    combined = load(tmp_path, report)

    assert combined == {"ecus": [2], "apps": []}
    assert report.as_mapping() == {
        "skipped": [{"item": f"{first}: ecus", "reason": f"overridden by {second}"}],
        "custom": {"input_files": [first, second]},
    }


@pytest.mark.parametrize("load, extension", [(load_yaml_files, "yaml"), (load_json_files, "json")])
def test_loader_without_overrides_reports_no_skipped(tmp_path, load, extension):
    _write(tmp_path / f"a.{extension}", '{"ecus": []}')
    _write(tmp_path / f"b.{extension}", '{"apps": []}')
    report = ConverterReport()

    load(tmp_path, report)

    assert "skipped" not in report.as_mapping()


@pytest.mark.parametrize("load, extension", [(load_yaml_files, "yaml"), (load_json_files, "json")])
def test_loader_records_nothing_without_a_report(tmp_path, load, extension):
    _write(tmp_path / f"a.{extension}", '{"ecus": []}')

    assert load(tmp_path) == {"ecus": []}


# endregion
# region encoders


@pytest.mark.parametrize("converter_type, filename", [(YamlConverter, "FLYNCModel.yaml"), (JsonConverter, "FLYNCModel.json")])
def test_encode_reports_the_output_file(tmp_path, flync_object, converter_type, filename):
    destination = converter_type(ConverterConfig(config_path=str(tmp_path)))
    source = YamlConverter()
    with ConversionReport(tmp_path, source, destination):
        destination.encode(flync_object)

    written = yaml.safe_load((reports_root(tmp_path) / destination.name / "report.yaml").read_text(encoding="utf-8"))
    assert written == {"custom": {"output_file": str(tmp_path / filename)}}


# endregion
# region FLYNC workspace diagnostics


def _workspace(diags):
    return SimpleNamespace(documents_diags=diags)


def test_workspace_diagnostics_are_reported():
    ws = _workspace(
        {
            "ecus/body.yaml": [
                {"type": "warning", "loc": ("ports", 0), "msg": "unused port", "ctx": {"error_id": "FLYNC-ECU-WARN-VAL-001"}},
                {"type": "missing", "loc": ("name",), "msg": "Field required"},
            ]
        }
    )
    report = ConverterReport()

    log_workspace_diagnostics(ws, report)

    assert report.as_mapping() == {
        "custom": {
            "diagnostics": [
                {
                    "document": "ecus/body.yaml",
                    "id": "FLYNC-ECU-WARN-VAL-001",
                    "severity": "warning",
                    "location": "ports.0",
                    "message": "unused port",
                },
                {"document": "ecus/body.yaml", "id": "missing", "severity": "error", "location": "name", "message": "Field required"},
            ]
        }
    }


def test_clean_workspace_reports_no_diagnostics():
    report = ConverterReport()

    log_workspace_diagnostics(_workspace({}), report)

    assert report.is_empty()


# endregion
# region DBC

_REPORTED_DBC = """VERSION ""

NS_ :

BS_:

BU_: NODE1 NODE2 IDLE

BO_ 256 Msg: 8 NODE1
 SG_ Mode : 0|2@1+ (1,0) [0|3] "" NODE2

BA_DEF_ "Baudrate" INT 0 10000000;
BA_DEF_DEF_ "Baudrate" 123456;
VAL_ 256 Mode 0 "Off" 1 "On" 7 "Bad" ;
"""


def test_dbc_decode_reports_what_flync_cannot_represent(tmp_path):
    dbc = tmp_path / "Bus.dbc"
    _write(dbc, _REPORTED_DBC)
    report = ConverterReport()

    decode_dbc_files(load_dbc_files(tmp_path, report), report=report)

    assert report.as_mapping() == {
        "skipped": [
            {"item": "Bus.Baudrate", "reason": "123456 is not an allowed FLYNC rate, 500000 used instead"},
            {"item": "Bus.Msg.Mode.value_table", "reason": "entries [7] outside the bit range [0, 3]"},
            {"item": "nodes.IDLE", "reason": "declared in BU_ but sends and receives no message"},
        ],
        "custom": {"input_files": [dbc]},
    }


def test_dbc_value_table_of_bytearray_signal_is_unsupported():
    signal = Signal(name="Blob", start=0, length=72)
    signal.choices = {0: "zero"}
    report = ConverterReport()

    assert _in_range_choices(signal, SignalDataType.BYTEARRAY, report, "Bus.Msg.Blob") is None
    assert report.as_mapping() == {"unsupported": [{"item": "Bus.Msg.Blob.value_table", "reason": "bytearray signals have no value table in FLYNC"}]}


def test_dbc_encode_reports_non_can_content_and_output_files(tmp_path, flync_object):
    _write(tmp_path / "in" / "Bus.dbc", _REPORTED_DBC)
    decoded = decode_dbc_files(load_dbc_files(tmp_path / "in"))
    example_channels = flync_object.communication.channels
    channels = decoded.communication.channels.model_copy(
        update={"lin_buses": example_channels.lin_buses, "ethernet_pdu_containers": example_channels.ethernet_pdu_containers}
    )
    model = SimpleNamespace(communication=SimpleNamespace(channels=channels), ecus=decoded.ecus)
    report = ConverterReport()

    written = write_dbc_files(model, str(tmp_path / "out"), report)

    assert written == [tmp_path / "out" / "Bus.dbc"]
    recorded = report.as_mapping()
    assert [entry["item"] for entry in recorded["unsupported"]] == [
        *(f"lin_buses.{bus.name}" for bus in example_channels.lin_buses),
        *(f"ethernet_pdu_containers.{container.name}" for container in example_channels.ethernet_pdu_containers),
    ]
    assert recorded["custom"] == {"output_files": written}


def test_dbc_encode_without_channels_reports_skipped(tmp_path):
    model = SimpleNamespace(communication=None)
    report = ConverterReport()

    assert write_dbc_files(model, str(tmp_path), report) == []
    assert report.as_mapping() == {"skipped": [{"item": "communication", "reason": "model has no communication channels"}]}


def test_dbc_converter_writes_its_report(tmp_path):
    source_path = tmp_path / "in"
    _write(source_path / "Bus.dbc", _REPORTED_DBC)
    source = DbcConverter(DbcConverterConfig(config_path=str(source_path)))
    destination = YamlConverter(ConverterConfig(config_path=str(tmp_path / "out")))

    with ConversionReport(tmp_path / "out", source, destination):
        source.decode()

    folder = reports_root(tmp_path / "out") / "dbc"
    written = yaml.safe_load((folder / "report.yaml").read_text(encoding="utf-8"))
    assert [entry["item"] for entry in written["skipped"]] == ["Bus.Baudrate", "Bus.Msg.Mode.value_table", "nodes.IDLE"]
    assert "Value table entries for signal 'Mode'" in (folder / "logs.txt").read_text(encoding="utf-8")


def test_dbc_converter_captures_cantools_logs():
    assert "cantools" in DbcConverter.report_loggers


# endregion
