"""Tests for many-source, many-output conversions, run with the real DBC, JSON and YAML converters."""

import json
import logging
from unittest.mock import patch

import pytest
from cantools.database.errors import UnsupportedDatabaseFormatError
from pydantic import ValidationError

from flync.core.utils import yaml_io
from flync_converter import (
    ConversionOutput,
    ConversionOutputError,
    ConversionRequest,
    ConversionSource,
    ConverterConfig,
    JsonConverter,
    ModelMergeConflictError,
    OnConflict,
    YamlConverter,
    convert_many,
    convert_request,
)
from flync_converter.base.converter_config import converter_config_file
from flync_converter.converters.dbc import DbcConverterConfig
from flync_converter.converters.dbc.converter import DbcConverter
from flync_converter.reporting import LOG_FILENAME, MAIN_LOGGER, report_dir, reports_root

from .API.test_dbc_converter import _BUS_A_DBC, _BUS_B_DBC


@pytest.fixture
def converters():
    """Registry holding the real converters, restored afterwards."""
    registered = {"dbc": DbcConverter(), "json": JsonConverter(), "yaml": YamlConverter()}
    with patch("flync_converter.registry", registered), patch("flync_converter.utils.registry", registered):
        yield registered


@pytest.fixture
def loggers():
    """Restore the level and handlers of the loggers a conversion captures."""
    names = [MAIN_LOGGER, "cantools"]
    saved = {name: (logging.getLogger(name).level, list(logging.getLogger(name).handlers)) for name in names}
    yield
    for name, (level, handlers) in saved.items():
        logging.getLogger(name).setLevel(level)
        logging.getLogger(name).handlers[:] = handlers


@pytest.fixture
def buses(tmp_path):
    """Two DBC folders sharing the node NODE3."""
    for name, content in (("a", _BUS_A_DBC), ("b", _BUS_B_DBC)):
        (tmp_path / name).mkdir()
        (tmp_path / name / f"bus_{name}.dbc").write_text(content, encoding="utf-8")
    return [ConversionSource(path=tmp_path / "a", converter_type="dbc"), ConversionSource(path=tmp_path / "b", converter_type="dbc")]


def _yaml(path):
    return yaml_io.safe_load(path.read_text(encoding="utf-8"))


# region request validation


def test_empty_sources_are_rejected():
    outputs = [ConversionOutput(path="out")]

    with pytest.raises(ValidationError):
        ConversionRequest(sources=[], outputs=outputs)


def test_empty_outputs_are_rejected():
    sources = [ConversionSource(path="in", converter_type="yaml")]

    with pytest.raises(ValidationError):
        ConversionRequest(sources=sources, outputs=[])


def test_source_needs_a_converter_type():
    with pytest.raises(ValidationError, match="converter_type"):
        ConversionSource(path="in")


def test_config_object_pointing_elsewhere_is_rejected(tmp_path):
    config = DbcConverterConfig(config_path=str(tmp_path / "b"))

    with pytest.raises(ValidationError, match="differs from the config_path"):
        ConversionSource(path=tmp_path / "a", converter_type="dbc", config=config)


def test_endpoint_listed_twice_is_rejected(tmp_path):
    source = ConversionSource(path=tmp_path / "a", converter_type="dbc")
    outputs = [ConversionOutput(path=tmp_path / "out")]

    with pytest.raises(ValidationError, match="listed twice"):
        ConversionRequest(sources=[source, source], outputs=outputs)


def test_two_converters_may_write_to_one_folder(tmp_path):
    outputs = [ConversionOutput(path=tmp_path / "out", converter_type="json"), ConversionOutput(path=tmp_path / "out", converter_type="yaml")]

    assert ConversionRequest(sources=[ConversionSource(path=tmp_path / "a", converter_type="dbc")], outputs=outputs)


@pytest.mark.parametrize("output", ["a", "a/export", "."])
def test_source_overlapping_an_output_is_rejected(tmp_path, output):
    sources = [ConversionSource(path=tmp_path / "a", converter_type="dbc")]
    outputs = [ConversionOutput(path=tmp_path / output, converter_type="json")]

    with pytest.raises(ValidationError, match="overlap"):
        ConversionRequest(sources=sources, outputs=outputs)


def test_unknown_converter_type_names_the_side(tmp_path, converters):
    sources = [ConversionSource(path=tmp_path / "a", converter_type="nope")]
    outputs = [ConversionOutput(path=tmp_path / "out", converter_type="json")]

    with pytest.raises(ValueError, match="Unknown source converter type: 'nope'"):
        convert_many(sources, outputs)


# endregion
# region conversion


def test_two_sources_are_merged_and_written_to_every_output(tmp_path, converters, loggers, buses):
    outputs = [
        ConversionOutput(path=tmp_path / "as_json", converter_type="json"),
        ConversionOutput(path=tmp_path / "as_yaml", converter_type="yaml"),
    ]

    result = convert_many(buses, outputs)

    assert result.ok
    assert result.written == outputs
    assert result.decoded == buses
    assert [ecu.name for ecu in result.model.ecus] == ["NODE1", "NODE2", "NODE3", "NODE4"]
    written_json = json.loads((tmp_path / "as_json" / "FLYNCModel.json").read_text(encoding="utf-8"))
    written_yaml = _yaml(tmp_path / "as_yaml" / "FLYNCModel.yaml")
    assert [ecu["name"] for ecu in written_json["ecus"]] == ["NODE1", "NODE2", "NODE3", "NODE4"]
    assert written_yaml == written_json


def test_registered_converters_are_left_untouched(tmp_path, converters, loggers, buses):
    convert_many(buses, [ConversionOutput(path=tmp_path / "out", converter_type="json")])

    assert all(converter.config is None and converter.report_dir is None for converter in converters.values())


def test_outputs_of_one_converter_run_with_their_own_configuration(tmp_path, converters, loggers, buses):
    """One output takes its configuration from its folder, the other from the request."""
    ConverterConfig(config_path="unused", report_min_log_level="DEBUG").to_yaml_file(converter_config_file(tmp_path / "stored", "json"))
    outputs = [
        ConversionOutput(path=tmp_path / "stored", converter_type="json"),
        ConversionOutput(path=tmp_path / "given", converter_type="json", config={"report_min_log_level": "ERROR"}),
    ]

    convert_many(buses, outputs)

    assert _yaml(report_dir(tmp_path / "stored", "json") / "config.yaml")["report_min_log_level"] == "DEBUG"
    assert _yaml(report_dir(tmp_path / "given", "json") / "config.yaml")["report_min_log_level"] == "ERROR"
    # The resolved configuration is stored in its own output, for the next conversion into it.
    assert _yaml(converter_config_file(tmp_path / "given", "json"))["report_min_log_level"] == "ERROR"
    assert not converter_config_file(tmp_path / "a", "dbc").exists()


# endregion
# region reports


def test_every_endpoint_gets_its_own_report(tmp_path, converters, loggers, buses):
    outputs = [
        ConversionOutput(path=tmp_path / "as_json", converter_type="json"),
        ConversionOutput(path=tmp_path / "as_yaml", converter_type="yaml"),
    ]

    convert_many(buses, outputs)

    for name in ("a", "b"):
        assert _yaml(report_dir(tmp_path / name, "dbc") / "config.yaml")["config_path"] == str(tmp_path / name)
    assert (report_dir(tmp_path / "as_json", "json") / "report.yaml").exists()
    assert (report_dir(tmp_path / "as_yaml", "yaml") / "report.yaml").exists()
    # A source holds its own converter's report only, not the report of the conversion.
    assert not (reports_root(tmp_path / "a") / "report.yaml").exists()


def test_conversion_report_is_written_to_every_output(tmp_path, converters, loggers, buses):
    outputs = [
        ConversionOutput(path=tmp_path / "as_json", converter_type="json"),
        ConversionOutput(path=tmp_path / "as_yaml", converter_type="yaml"),
    ]

    convert_many(buses, outputs)

    shared = _yaml(reports_root(tmp_path / "as_json") / "report.yaml")
    assert shared == _yaml(reports_root(tmp_path / "as_yaml") / "report.yaml")
    assert shared["inputs"] == [
        {"converter": "dbc", "path": str(tmp_path / name), "report": str(report_dir(tmp_path / name, "dbc"))} for name in ("a", "b")
    ]
    assert [output["converter"] for output in shared["outputs"]] == ["json", "yaml"]
    assert shared["merge"] == {"policy": "first", "conflicts": []}
    assert shared["model"]["ecus"] == 4
    assert shared["status"] == "succeeded"


def test_sources_of_one_converter_keep_separate_logs(tmp_path, converters, loggers, buses):
    """The decoder's records land in the conversion log and in the log of the source they belong to."""
    for name in ("a", "b"):
        ConverterConfig(config_path="unused", report_min_log_level="DEBUG").to_yaml_file(converter_config_file(tmp_path / name, "dbc"))
    output = ConversionOutput(path=tmp_path / "out", converter_type="json", config={"report_min_log_level": "DEBUG"})

    convert_many(buses, [output])

    log_a = (report_dir(tmp_path / "a", "dbc") / LOG_FILENAME).read_text(encoding="utf-8")
    log_b = (report_dir(tmp_path / "b", "dbc") / LOG_FILENAME).read_text(encoding="utf-8")
    shared = (reports_root(tmp_path / "out") / LOG_FILENAME).read_text(encoding="utf-8")
    assert "bus_a" in log_a
    assert "bus_b" not in log_a
    assert "bus_b" in log_b
    assert "bus_a" not in log_b
    assert "bus_a" in shared
    assert "bus_b" in shared


def test_report_dir_moves_the_report_of_an_endpoint(tmp_path, converters, loggers, buses):
    sources = [buses[0], ConversionSource(path=tmp_path / "b", converter_type="dbc", config={"report_dir": str(tmp_path / "elsewhere")})]

    convert_many(sources, [ConversionOutput(path=tmp_path / "out", converter_type="json")])

    assert (tmp_path / "elsewhere" / "dbc" / "config.yaml").exists()
    assert not reports_root(tmp_path / "b").exists()


def test_two_converters_sharing_a_report_folder_are_rejected(tmp_path, converters, buses):
    shared = {"report_dir": str(tmp_path / "reports")}
    sources = [ConversionSource(path=source.path, converter_type="dbc", config=shared) for source in buses]
    outputs = [ConversionOutput(path=tmp_path / "out", converter_type="json")]

    with pytest.raises(ValueError, match="own report_dir"):
        convert_many(sources, outputs)

    assert not (tmp_path / "out").exists()


def test_unwritable_report_folder_is_skipped_with_a_warning(tmp_path, converters, loggers, buses, caplog):
    (tmp_path / "blocked").write_text("a file where a folder is needed", encoding="utf-8")
    sources = [buses[0], ConversionSource(path=tmp_path / "b", converter_type="dbc", config={"report_dir": str(tmp_path / "blocked" / "reports")})]

    with caplog.at_level(logging.WARNING, logger=MAIN_LOGGER):
        result = convert_many(sources, [ConversionOutput(path=tmp_path / "out", converter_type="json")])

    assert result.ok
    assert "Report of converter dbc skipped" in caplog.text


def test_disabled_report_writes_nothing_for_that_endpoint(tmp_path, converters, loggers, buses):
    sources = [buses[0], ConversionSource(path=tmp_path / "b", converter_type="dbc", config={"report_enabled": False})]

    convert_many(sources, [ConversionOutput(path=tmp_path / "out", converter_type="json")])

    assert report_dir(tmp_path / "a", "dbc").exists()
    assert not reports_root(tmp_path / "b").exists()


# endregion
# region merge conflicts


@pytest.fixture
def conflicting(tmp_path, buses):
    """The two buses, the second declaring a signal of the first with another scale."""
    (tmp_path / "b" / "bus_b.dbc").write_text(_BUS_A_DBC.replace("(0.01,0)", "(0.5,0)"), encoding="utf-8")
    (tmp_path / "b" / "bus_b.dbc").rename(tmp_path / "b" / "bus_a.dbc")
    return buses


def test_conflicts_are_returned_and_recorded_in_the_conversion_report(tmp_path, converters, loggers, conflicting):
    result = convert_many(conflicting, [ConversionOutput(path=tmp_path / "out", converter_type="json")])

    assert result.conflicts
    assert all(conflict.kept_source == str(tmp_path / "a") for conflict in result.conflicts)
    merge = _yaml(reports_root(tmp_path / "out") / "report.yaml")["merge"]
    assert merge["policy"] == "first"
    assert [conflict["path"] for conflict in merge["conflicts"]] == [conflict.path for conflict in result.conflicts]
    assert "Merge conflict at" in (reports_root(tmp_path / "out") / LOG_FILENAME).read_text(encoding="utf-8")


def test_error_policy_fails_before_any_output_is_written(tmp_path, converters, loggers, conflicting):
    outputs = [ConversionOutput(path=tmp_path / "out", converter_type="json")]

    with pytest.raises(ModelMergeConflictError):
        convert_many(conflicting, outputs, on_conflict=OnConflict.ERROR)

    assert not (tmp_path / "out" / "FLYNCModel.json").exists()
    shared = _yaml(reports_root(tmp_path / "out") / "report.yaml")
    assert shared["status"] == "failed"
    assert shared["error"].startswith("ModelMergeConflictError")


# endregion
# region failures


def test_failing_source_writes_no_output(tmp_path, converters, loggers, buses):
    (tmp_path / "b" / "bus_b.dbc").write_text("this is not a DBC file", encoding="utf-8")

    outputs = [ConversionOutput(path=tmp_path / "out", converter_type="json")]

    with pytest.raises(UnsupportedDatabaseFormatError):
        convert_many(buses, outputs)

    assert not (tmp_path / "out" / "FLYNCModel.json").exists()
    assert _yaml(reports_root(tmp_path / "out") / "report.yaml")["status"] == "failed"


def _break_json_encoder(converters):
    converters["json"].encode = lambda model: (_ for _ in ()).throw(RuntimeError("disk full"))


def test_failing_output_does_not_stop_the_others(tmp_path, converters, loggers, buses):
    _break_json_encoder(converters)
    outputs = [
        ConversionOutput(path=tmp_path / "as_json", converter_type="json"),
        ConversionOutput(path=tmp_path / "as_yaml", converter_type="yaml"),
    ]

    with pytest.raises(ConversionOutputError, match="1 of 2 output") as error:
        convert_many(buses, outputs)

    result = error.value.result
    assert result.written == [outputs[1]]
    assert [(failure.output, str(failure.error)) for failure in result.failures] == [(outputs[0], "disk full")]
    assert (tmp_path / "as_yaml" / "FLYNCModel.yaml").exists()
    shared = _yaml(reports_root(tmp_path / "as_yaml") / "report.yaml")
    assert shared["status"] == "failed"
    assert [output.get("error") for output in shared["outputs"]] == ["RuntimeError: disk full", None]


def test_fail_fast_raises_the_first_output_failure(tmp_path, converters, loggers, buses):
    _break_json_encoder(converters)
    outputs = [
        ConversionOutput(path=tmp_path / "as_json", converter_type="json"),
        ConversionOutput(path=tmp_path / "as_yaml", converter_type="yaml"),
    ]

    with pytest.raises(RuntimeError, match="disk full"):
        convert_many(buses, outputs, fail_fast=True)

    assert not (tmp_path / "as_yaml" / "FLYNCModel.yaml").exists()


# endregion
# region manifest


def test_manifest_runs_a_conversion_with_paths_relative_to_it(tmp_path, converters, loggers, buses):
    manifest = tmp_path / "conversion.yaml"
    manifest.write_text(
        """\
on_conflict: last
sources:
  - {path: a, converter_type: dbc}
  - {path: b, converter_type: dbc, config: {baud_rate_default: 250000}}
outputs:
  - {path: out, converter_type: json}
""",
        encoding="utf-8",
    )

    request = ConversionRequest.from_yaml_file(manifest)
    result = convert_request(manifest)

    assert request.on_conflict is OnConflict.LAST
    assert [str(source.path) for source in request.sources] == [str(tmp_path / "a"), str(tmp_path / "b")]
    assert request.sources[1].config == {"baud_rate_default": 250000}
    assert result.written == request.outputs
    assert (tmp_path / "out" / "FLYNCModel.json").exists()
    assert {bus.name: bus.baud_rate for bus in result.model.communication.channels.can_buses} == {"bus_a": 500000, "bus_b": 250000}


def test_manifest_with_an_unknown_key_is_rejected(tmp_path):
    manifest = tmp_path / "conversion.yaml"
    manifest.write_text("sources: [{path: a, converter_type: dbc}]\noutputs: [{path: out}]\non_conflicts: first\n", encoding="utf-8")

    with pytest.raises(ValidationError, match="on_conflicts"):
        ConversionRequest.from_yaml_file(manifest)


def test_manifest_that_is_not_a_mapping_is_rejected(tmp_path):
    manifest = tmp_path / "conversion.yaml"
    manifest.write_text("- a\n- b\n", encoding="utf-8")

    with pytest.raises(ValueError, match="must contain a mapping"):
        ConversionRequest.from_yaml_file(manifest)


# endregion
