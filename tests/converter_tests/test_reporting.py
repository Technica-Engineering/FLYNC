"""Tests for flync_converter.reporting — the per-conversion report."""

import json
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from flync.model import FLYNCModel
from flync_converter import Converter, ConverterConfig
from flync_converter.base import BaseConverter, BaseReporter, ConverterReport, JsonReporter, YamlReporter
from flync_converter.base.converter_config import converter_config_file
from flync_converter.base.converter_report import INACTIVE_REPORT
from flync_converter.reporting import (
    LOG_FILENAME,
    MAIN_LOGGER,
    ConversionReport,
    model_counts,
    report_dir,
    reports_root,
)

SRC_LOGGER = f"{MAIN_LOGGER}.converters.json"
DST_LOGGER = f"{MAIN_LOGGER}.converters.flync"
LIBRARY_LOGGER = "some_library"


class _Converter:
    """Minimal stand-in exposing what the report reads and sets on a converter."""

    def __init__(self, name, report_loggers=(), config=None, reporters=(YamlReporter(),)):
        self.name = name
        self.report_loggers = tuple(report_loggers)
        self.report_dir = None
        self.config = config
        self.reporters = reporters
        self.report = INACTIVE_REPORT


@pytest.fixture
def loggers():
    """Restore the level and handlers of every logger a test touches."""
    names = [MAIN_LOGGER, SRC_LOGGER, DST_LOGGER, LIBRARY_LOGGER, "flync_converter.converters"]
    saved = {name: (logging.getLogger(name).level, list(logging.getLogger(name).handlers)) for name in names}
    yield {name: logging.getLogger(name) for name in names}
    for name, (level, handlers) in saved.items():
        logging.getLogger(name).setLevel(level)
        logging.getLogger(name).handlers[:] = handlers


def _converters(source_loggers=(SRC_LOGGER,), destination_loggers=(DST_LOGGER,)):
    return _Converter("json", source_loggers), _Converter("flync", destination_loggers)


def _read(path):
    return path.read_text(encoding="utf-8")


# region paths


def test_reports_root(tmp_path):
    assert reports_root(tmp_path) == tmp_path / ".flync" / "reports"


def test_report_dir(tmp_path):
    assert report_dir(tmp_path, "flync") == tmp_path / ".flync" / "reports" / "flync"


def test_report_dir_accepts_string_destination():
    assert report_dir("/out/ws", "flync") == Path("/out/ws/.flync/reports/flync")


# endregion
# region shared log


def test_shared_log_is_at_reports_root(tmp_path, loggers):
    with ConversionReport(tmp_path, *_converters()) as report:
        logging.getLogger(DST_LOGGER).info("hello report")

    assert report.path == reports_root(tmp_path) / LOG_FILENAME
    assert "hello report" in _read(report.path)


def test_shared_log_captures_every_converter_and_the_driver(tmp_path, loggers):
    source, destination = _converters(source_loggers=(LIBRARY_LOGGER,))
    with ConversionReport(tmp_path, source, destination) as report:
        logging.getLogger(MAIN_LOGGER).info("driver record")
        logging.getLogger(f"{LIBRARY_LOGGER}.loader").info("source library record")
        logging.getLogger(DST_LOGGER).info("destination record")

    content = _read(report.path)
    assert "driver record" in content
    assert "source library record" in content
    assert "destination record" in content


def test_disabled_report_does_nothing(tmp_path, loggers):
    source, destination = _converters()
    handlers = list(loggers[MAIN_LOGGER].handlers)
    with ConversionReport(tmp_path, source, destination, enabled=False):
        assert loggers[MAIN_LOGGER].handlers == handlers
        assert destination.report_dir is None
    assert not reports_root(tmp_path).exists()


def test_report_replaces_previous_files(tmp_path, loggers):
    with ConversionReport(tmp_path, *_converters()):
        logging.getLogger(DST_LOGGER).info("first run")
    with ConversionReport(tmp_path, *_converters()) as report:
        logging.getLogger(DST_LOGGER).info("second run")

    for path in (report.path, report_dir(tmp_path, "flync") / LOG_FILENAME):
        content = _read(path)
        assert "second run" in content
        assert "first run" not in content


def test_report_honours_min_level(tmp_path, loggers):
    with ConversionReport(tmp_path, *_converters(), min_level=logging.ERROR) as report:
        logging.getLogger(DST_LOGGER).info("info record")
        logging.getLogger(DST_LOGGER).error("error record")

    for path in (report.path, report_dir(tmp_path, "flync") / LOG_FILENAME):
        content = _read(path)
        assert "error record" in content
        assert "info record" not in content


def test_report_restores_logger_levels_and_handlers(tmp_path, loggers):
    loggers[MAIN_LOGGER].setLevel(logging.WARNING)
    loggers[LIBRARY_LOGGER].setLevel(logging.WARNING)
    before = {name: list(log.handlers) for name, log in loggers.items()}

    with ConversionReport(tmp_path, *_converters(source_loggers=(LIBRARY_LOGGER,)), min_level=logging.DEBUG):
        assert loggers[MAIN_LOGGER].level == logging.DEBUG
        assert loggers[LIBRARY_LOGGER].level == logging.DEBUG

    assert loggers[MAIN_LOGGER].level == logging.WARNING
    assert loggers[LIBRARY_LOGGER].level == logging.WARNING
    assert {name: list(log.handlers) for name, log in loggers.items()} == before


def test_report_keeps_a_more_permissive_level(tmp_path, loggers):
    loggers[MAIN_LOGGER].setLevel(logging.DEBUG)
    with ConversionReport(tmp_path, *_converters(), min_level=logging.ERROR):
        assert loggers[MAIN_LOGGER].level == logging.DEBUG


def test_report_leaves_root_logger_untouched(tmp_path, loggers):
    root = logging.getLogger()
    level, handlers = root.level, list(root.handlers)
    with ConversionReport(tmp_path, *_converters(), min_level=logging.DEBUG):
        assert root.level == level
        assert root.handlers == handlers


def test_report_ignores_undeclared_loggers(tmp_path, loggers):
    with ConversionReport(tmp_path, *_converters()) as report:
        logging.getLogger("some.other.library").warning("foreign record")
        logging.getLogger(DST_LOGGER).warning("converter record")

    content = _read(report.path)
    assert "converter record" in content
    assert "foreign record" not in content


# endregion
# region per-converter folders


def test_each_converter_gets_its_folder_as_report_dir(tmp_path, loggers):
    source, destination = _converters()
    with ConversionReport(tmp_path, source, destination):
        assert source.report_dir == report_dir(tmp_path, "json")
        assert destination.report_dir == report_dir(tmp_path, "flync")
        assert source.report_dir.is_dir()
        assert destination.report_dir.is_dir()

    assert source.report_dir is None
    assert destination.report_dir is None


def test_converter_log_holds_only_its_own_records(tmp_path, loggers):
    with ConversionReport(tmp_path, *_converters()) as report:
        logging.getLogger(MAIN_LOGGER).info("driver record")
        logging.getLogger(SRC_LOGGER).info("source record")
        logging.getLogger(DST_LOGGER).info("destination record")

    source_log = _read(report_dir(tmp_path, "json") / LOG_FILENAME)
    destination_log = _read(report_dir(tmp_path, "flync") / LOG_FILENAME)
    assert "source record" in source_log
    assert "destination record" not in source_log
    assert "driver record" not in source_log
    assert "destination record" in destination_log
    assert "source record" not in destination_log
    assert "driver record" not in destination_log


def test_converter_folder_records_the_config_it_ran_with(tmp_path, loggers):
    destination = _Converter("flync", config=ConverterConfig(config_path=str(tmp_path), report_min_log_level="DEBUG"))
    with ConversionReport(tmp_path, _Converter("json"), destination):
        pass

    record = yaml.safe_load(_read(report_dir(tmp_path, "flync") / "config.yaml"))
    # Every value, defaults and config_path included.
    assert record["config_path"] == str(tmp_path)
    assert record["report_min_log_level"] == "DEBUG"
    assert record["report_enabled"] is True
    assert "version" in record
    # A converter without a configuration object gets no record.
    assert not (report_dir(tmp_path, "json") / "config.yaml").exists()


def test_converter_without_loggers_gets_a_folder_but_no_log(tmp_path, loggers):
    source, destination = _converters(source_loggers=())
    with ConversionReport(tmp_path, source, destination):
        pass

    assert report_dir(tmp_path, "json").is_dir()
    assert not (report_dir(tmp_path, "json") / LOG_FILENAME).exists()


def test_nested_logger_records_are_written_once(tmp_path, loggers):
    nested = (LIBRARY_LOGGER, f"{LIBRARY_LOGGER}.loader", "flync_converter.converters")
    with ConversionReport(tmp_path, *_converters(destination_loggers=nested)) as report:
        logging.getLogger(f"{LIBRARY_LOGGER}.loader").warning("library record")
        logging.getLogger(DST_LOGGER).warning("converter record")

    for path in (report.path, report_dir(tmp_path, "flync") / LOG_FILENAME):
        content = _read(path)
        assert content.count("library record") == 1
        assert content.count("converter record") == 1


def test_logger_listed_by_both_converters_reaches_both_folders(tmp_path, loggers):
    shared = (LIBRARY_LOGGER,)
    with ConversionReport(tmp_path, *_converters(source_loggers=shared, destination_loggers=shared)) as report:
        logging.getLogger(LIBRARY_LOGGER).warning("library record")

    assert _read(report.path).count("library record") == 1
    assert "library record" in _read(report_dir(tmp_path, "json") / LOG_FILENAME)
    assert "library record" in _read(report_dir(tmp_path, "flync") / LOG_FILENAME)


# endregion
# region failures


def test_report_records_the_exception_in_the_shared_log(tmp_path, loggers):
    report = ConversionReport(tmp_path, *_converters())
    boom = RuntimeError("boom")
    with pytest.raises(RuntimeError), report:
        raise boom

    content = _read(report.path)
    assert "[ERROR] flync_converter: Conversion failed: boom" in content
    assert "Traceback (most recent call last)" in content
    assert "Conversion failed" not in _read(report_dir(tmp_path, "flync") / LOG_FILENAME)


def test_report_cleans_up_when_conversion_raises(tmp_path, loggers):
    source, destination = _converters()
    handlers = list(loggers[MAIN_LOGGER].handlers)
    report = ConversionReport(tmp_path, source, destination)
    boom = RuntimeError("boom")
    with pytest.raises(RuntimeError), report:
        raise boom
    assert loggers[MAIN_LOGGER].handlers == handlers
    assert destination.report_dir is None


def test_report_exception_does_not_reach_other_handlers(tmp_path, loggers):
    seen = []
    other = logging.Handler()
    other.emit = seen.append  # type: ignore[method-assign]
    loggers[MAIN_LOGGER].addHandler(other)

    report = ConversionReport(tmp_path, *_converters())
    boom = RuntimeError("boom")
    with pytest.raises(RuntimeError), report:
        raise boom

    assert not seen


def test_report_without_exception_has_no_failure_line(tmp_path, loggers):
    with ConversionReport(tmp_path, *_converters()) as report:
        logging.getLogger(DST_LOGGER).info("all good")

    assert "Conversion failed" not in _read(report.path)


# endregion
# region Converter.convert


def _fake_registry(encode=None, source_report_loggers=(SRC_LOGGER,), reporters=(YamlReporter(),)):
    src_conv = MagicMock()
    src_conv.name = "json"
    src_conv.report_loggers = source_report_loggers
    src_conv.decode.side_effect = lambda: logging.getLogger(SRC_LOGGER).info("decoded") or MagicMock(name="decoded_model")
    dst_conv = MagicMock()
    dst_conv.name = "flync"
    dst_conv.report_loggers = (DST_LOGGER,)
    dst_conv.reporters = reporters
    if encode is not None:
        dst_conv.encode.side_effect = encode
    fake = {"json": src_conv, "flync": dst_conv}
    fake_reg = MagicMock()
    fake_reg.__getitem__.side_effect = fake.__getitem__
    return fake_reg, dst_conv


def _log_encoded(model):
    logging.getLogger(DST_LOGGER).info("encoded %s", model)


def _run(tmp_path, encode=_log_encoded, destination_config=None, source_report_loggers=(SRC_LOGGER,), reporters=(YamlReporter(),)):
    fake_reg, dst_conv = _fake_registry(encode, source_report_loggers, reporters)
    with patch("flync_converter.registry", fake_reg):
        Converter.convert(
            str(tmp_path / "src"),
            str(tmp_path / "dst"),
            source_type="json",
            destination_type="flync",
            destination_config=destination_config,
        )
    return dst_conv


def test_convert_writes_shared_and_converter_logs(tmp_path, loggers):
    handlers = list(loggers[MAIN_LOGGER].handlers)
    dst_conv = _run(tmp_path)

    dst_conv.encode.assert_called_once()
    shared = _read(reports_root(tmp_path / "dst") / LOG_FILENAME)
    assert "decoded" in shared
    assert "encoded" in shared
    assert "decoded" in _read(report_dir(tmp_path / "dst", "json") / LOG_FILENAME)
    assert "encoded" in _read(report_dir(tmp_path / "dst", "flync") / LOG_FILENAME)
    assert loggers[MAIN_LOGGER].handlers == handlers


def test_convert_records_both_configs(tmp_path, loggers):
    _run(tmp_path, destination_config=ConverterConfig(config_path=str(tmp_path / "dst"), report_min_log_level="DEBUG"))

    source_record = yaml.safe_load(_read(report_dir(tmp_path / "dst", "json") / "config.yaml"))
    destination_record = yaml.safe_load(_read(report_dir(tmp_path / "dst", "flync") / "config.yaml"))
    assert source_record["config_path"] == str(tmp_path / "src")
    assert destination_record["config_path"] == str(tmp_path / "dst")
    assert destination_record["report_min_log_level"] == "DEBUG"


def test_convert_gives_converters_their_report_dir(tmp_path, loggers):
    def write_own_report(model):
        (dst_conv.report_dir / "summary.txt").write_text("custom", encoding="utf-8")

    fake_reg, dst_conv = _fake_registry(encode=write_own_report)
    with patch("flync_converter.registry", fake_reg):
        Converter.convert(str(tmp_path / "src"), str(tmp_path / "dst"), source_type="json", destination_type="flync")

    assert _read(report_dir(tmp_path / "dst", "flync") / "summary.txt") == "custom"
    assert dst_conv.report_dir is None


def test_convert_records_failure_in_shared_log(tmp_path, loggers):
    handlers = list(loggers[MAIN_LOGGER].handlers)

    def fail(model):
        raise RuntimeError("encode failed")

    with pytest.raises(RuntimeError, match="encode failed"):
        _run(tmp_path, encode=fail)
    assert loggers[MAIN_LOGGER].handlers == handlers
    assert "Conversion failed: encode failed" in _read(reports_root(tmp_path / "dst") / LOG_FILENAME)


def test_convert_captures_source_converter_library_loggers(tmp_path, loggers):
    _run(
        tmp_path,
        encode=lambda model: logging.getLogger(f"{LIBRARY_LOGGER}.loader").info("logged by the source library"),
        source_report_loggers=(LIBRARY_LOGGER,),
    )

    assert "logged by the source library" in _read(reports_root(tmp_path / "dst") / LOG_FILENAME)
    assert "logged by the source library" in _read(report_dir(tmp_path / "dst", "json") / LOG_FILENAME)


def test_convert_respects_report_disabled(tmp_path, loggers):
    _run(tmp_path, destination_config=ConverterConfig(config_path=str(tmp_path / "dst"), report_enabled=False))
    assert not reports_root(tmp_path / "dst").exists()


def test_convert_report_level_from_config(tmp_path, loggers):
    _run(tmp_path, destination_config=ConverterConfig(config_path=str(tmp_path / "dst"), report_min_log_level="ERROR"))

    log_file = reports_root(tmp_path / "dst") / LOG_FILENAME
    assert log_file.exists()
    # The INFO record from the destination converter is below the config level.
    assert "encoded" not in _read(log_file)


def test_convert_persists_destination_config(tmp_path, loggers):
    _run(tmp_path, destination_config=ConverterConfig(config_path=str(tmp_path / "dst"), report_min_log_level="DEBUG"))

    stored = ConverterConfig.from_workspace(tmp_path / "dst", "flync")
    assert stored.report_min_log_level == "DEBUG"


def test_convert_does_not_persist_when_disabled(tmp_path, loggers):
    _run(tmp_path, destination_config=ConverterConfig(config_path=str(tmp_path / "dst"), persist_config=False))
    assert not converter_config_file(tmp_path / "dst", "flync").exists()


def test_convert_uses_stored_config_without_explicit_one(tmp_path, loggers):
    ConverterConfig(config_path="unused", report_enabled=False).to_yaml_file(converter_config_file(tmp_path / "dst", "flync"))

    dst_conv = _run(tmp_path)

    assert dst_conv.config.report_enabled is False
    assert not reports_root(tmp_path / "dst").exists()


def test_convert_explicit_values_override_stored_config(tmp_path, loggers):
    ConverterConfig(config_path="unused", report_enabled=False, report_min_log_level="ERROR").to_yaml_file(
        converter_config_file(tmp_path / "dst", "flync")
    )

    dst_conv = _run(tmp_path, destination_config=ConverterConfig(config_path=str(tmp_path / "dst"), report_enabled=True))

    # Set explicitly: wins over the file.
    assert dst_conv.config.report_enabled is True
    # Not set explicitly: taken from the file, not from the field default.
    assert dst_conv.config.report_min_log_level == "ERROR"


# endregion
# region reporters


def test_yaml_reporter_writes_report_yaml(tmp_path):
    path = YamlReporter().write({"custom": {"ecus": 2, "apps": 1}}, tmp_path)

    assert path == tmp_path / "report.yaml"
    assert yaml.safe_load(path.read_text(encoding="utf-8")) == {"custom": {"ecus": 2, "apps": 1}}


def test_json_reporter_writes_report_json(tmp_path):
    path = JsonReporter().write({"custom": {"ecus": 2}}, tmp_path)

    assert path == tmp_path / "report.json"
    assert json.loads(path.read_text(encoding="utf-8")) == {"custom": {"ecus": 2}}


@pytest.mark.parametrize("reporter", [YamlReporter(), JsonReporter()])
def test_reporters_write_unserialisable_values_as_strings(tmp_path, reporter):
    path = reporter.write({"custom": {"output": tmp_path / "model.yaml", "level": logging.INFO}}, tmp_path)

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data == {"custom": {"output": str(tmp_path / "model.yaml"), "level": logging.INFO}}


def test_custom_reporter_is_a_subclass(tmp_path):
    class TextReporter(BaseReporter):
        filename = "report.txt"

        def dump(self, data, stream):
            for group, values in data.items():
                for key, value in values.items():
                    stream.write(f"{group}.{key}={value}\n")

    path = TextReporter().write({"custom": {"ecus": 3}}, tmp_path)

    assert path.read_text(encoding="utf-8") == "custom.ecus=3\n"


# endregion
# region converter report


def test_converter_report_groups():
    report = ConverterReport()
    report.skipped("ecus.body_ecu", "no CAN interface")
    report.unsupported("pdus.diag", "Ethernet PDUs have no DBC equivalent")
    report.add("dbc_files", ["CAN1.dbc"])

    assert report.as_mapping() == {
        "skipped": [{"item": "ecus.body_ecu", "reason": "no CAN interface"}],
        "unsupported": [{"item": "pdus.diag", "reason": "Ethernet PDUs have no DBC equivalent"}],
        "custom": {"dbc_files": ["CAN1.dbc"]},
    }


def test_converter_report_leaves_out_empty_groups():
    report = ConverterReport()
    report.add("schema", "AUTOSAR_00049.xsd")

    assert report.as_mapping() == {"custom": {"schema": "AUTOSAR_00049.xsd"}}


def test_inactive_report_records_nothing():
    report = ConverterReport(active=False)
    report.skipped("ecus.body_ecu", "no CAN interface")
    report.unsupported("pdus.diag", "unsupported")
    report.add("key", "value")

    assert report.is_empty()


def test_converter_report_writes_with_each_reporter(tmp_path):
    report = ConverterReport()
    report.skipped("ecus.body_ecu", "no CAN interface")

    written = report.write([YamlReporter(), JsonReporter()], tmp_path / "dbc")

    assert {path.name for path in written} == {"report.yaml", "report.json"}
    assert yaml.safe_load((tmp_path / "dbc" / "report.yaml").read_text(encoding="utf-8")) == {
        "skipped": [{"item": "ecus.body_ecu", "reason": "no CAN interface"}]
    }


def test_empty_converter_report_writes_nothing(tmp_path):
    assert ConverterReport().write([YamlReporter()], tmp_path / "dbc") == []
    assert not (tmp_path / "dbc").exists()


def test_converter_report_logs_and_skips_a_failing_reporter(tmp_path, caplog):
    class BrokenReporter(BaseReporter):
        filename = "broken.txt"

        def dump(self, data, stream):
            raise RuntimeError("cannot write")

    report = ConverterReport()
    report.add("ecus", 1)

    with caplog.at_level(logging.ERROR, logger="flync_converter.base.converter_report"):
        written = report.write([BrokenReporter(), YamlReporter()], tmp_path)

    assert [path.name for path in written] == ["report.yaml"]
    assert "BrokenReporter failed" in caplog.text


def test_base_converter_defaults():
    assert [type(reporter) for reporter in BaseConverter.reporters] == [YamlReporter]
    assert BaseConverter.report is INACTIVE_REPORT


# endregion
# region conversion report


def test_converters_get_an_active_report_during_the_conversion(tmp_path, loggers):
    source, destination = _converters()
    with ConversionReport(tmp_path, source, destination):
        assert source.report.active
        assert destination.report.active
        assert source.report is not destination.report

    assert source.report is INACTIVE_REPORT
    assert destination.report is INACTIVE_REPORT


def test_each_converter_report_goes_to_its_folder(tmp_path, loggers):
    source, destination = _converters()
    destination.reporters = (JsonReporter(),)
    with ConversionReport(tmp_path, source, destination):
        source.report.unsupported("BO_ 512", "multiplexed message without selector")
        destination.report.add("written", 3)

    assert yaml.safe_load((report_dir(tmp_path, "json") / "report.yaml").read_text(encoding="utf-8")) == {
        "unsupported": [{"item": "BO_ 512", "reason": "multiplexed message without selector"}]
    }
    assert json.loads((report_dir(tmp_path, "flync") / "report.json").read_text(encoding="utf-8")) == {"custom": {"written": 3}}


def test_converter_that_reports_nothing_gets_no_report_file(tmp_path, loggers):
    with ConversionReport(tmp_path, *_converters()):
        pass

    assert not (report_dir(tmp_path, "json") / "report.yaml").exists()


def test_disabled_report_keeps_converters_inactive(tmp_path, loggers):
    source, destination = _converters()
    with ConversionReport(tmp_path, source, destination, enabled=False):
        destination.report.add("written", 3)
        assert destination.report is INACTIVE_REPORT

    assert not reports_root(tmp_path).exists()


def test_shared_report_records_a_successful_conversion(tmp_path, loggers):
    source = _Converter("json", config=ConverterConfig(config_path="in"))
    destination = _Converter("flync")
    with ConversionReport(tmp_path, source, destination):
        pass

    shared = yaml.safe_load((reports_root(tmp_path) / "report.yaml").read_text(encoding="utf-8"))
    assert shared == {
        "source": {"converter": "json", "path": "in"},
        "destination": {"converter": "flync", "path": str(tmp_path)},
        "status": "succeeded",
    }


def test_shared_report_records_a_failure(tmp_path, loggers):
    report = ConversionReport(tmp_path, *_converters())
    boom = RuntimeError("boom")
    with pytest.raises(RuntimeError), report:
        raise boom

    shared = yaml.safe_load((reports_root(tmp_path) / "report.yaml").read_text(encoding="utf-8"))
    assert shared["status"] == "failed"
    assert shared["error"] == "RuntimeError: boom"


def test_shared_report_is_written_by_the_given_reporters(tmp_path, loggers):
    with ConversionReport(tmp_path, *_converters(), reporters=(JsonReporter(),)):
        pass

    root = reports_root(tmp_path)
    assert not (root / "report.yaml").exists()
    assert json.loads((root / "report.json").read_text(encoding="utf-8"))["status"] == "succeeded"


def test_convert_passes_the_shared_reporters(tmp_path, loggers):
    fake_reg, _ = _fake_registry(reporters=())
    with patch("flync_converter.registry", fake_reg):
        Converter.convert(
            str(tmp_path / "src"),
            str(tmp_path / "dst"),
            source_type="json",
            destination_type="flync",
            destination_config=ConverterConfig(config_path=str(tmp_path / "dst")),
            reporters=(YamlReporter(), JsonReporter()),
        )

    root = reports_root(tmp_path / "dst")
    assert (root / "report.yaml").is_file()
    assert (root / "report.json").is_file()


def test_shared_report_records_the_model_counts(tmp_path, loggers, flync_object):
    with ConversionReport(tmp_path, *_converters()) as report:
        report.record_model(flync_object)

    shared = yaml.safe_load((reports_root(tmp_path) / "report.yaml").read_text(encoding="utf-8"))
    assert shared["model"] == model_counts(flync_object)


def test_model_counts(flync_object):
    counts = model_counts(flync_object)

    assert counts["ecus"] == len(flync_object.ecus)
    assert counts["can_buses"] == len(flync_object.communication.channels.can_buses)
    assert set(counts) == {"ecus", "apps", "can_buses", "lin_buses", "shared_pdus", "ethernet_pdus"}


def test_model_counts_without_communication():
    model = FLYNCModel.model_construct(ecus=[], apps=[], communication=None)

    assert model_counts(model) == {"ecus": 0, "apps": 0, "can_buses": 0, "lin_buses": 0, "shared_pdus": 0, "ethernet_pdus": 0}


def test_reporter_failure_reaches_the_shared_log(tmp_path, loggers):
    class BrokenReporter(BaseReporter):
        filename = "broken.txt"

        def dump(self, data, stream):
            raise RuntimeError("cannot write")

    source, destination = _converters()
    destination.reporters = (BrokenReporter(),)
    with ConversionReport(tmp_path, source, destination) as report:
        destination.report.add("written", 3)

    assert "BrokenReporter failed" in (report.path).read_text(encoding="utf-8")


# endregion
# region reports from real converters


class _ReportingConverter(BaseConverter):
    """Converter recording report data on both sides of a conversion."""

    def __init__(self, name, fail=False):
        super().__init__()
        self.name = name
        self.fail = fail

    def can_decode(self):
        return True

    def decode(self):
        self.report.unsupported("BO_ 512", "multiplexed message without selector")
        return FLYNCModel.model_construct(ecus=[], apps=[], communication=None)

    def encode(self, source):
        self.report.skipped("ecus.body_ecu", "no CAN interface")
        self.report.add("output_file", Path("out") / "model.dst")
        if self.fail:
            raise RuntimeError("the real encode error")


def _convert_with(tmp_path, source, destination):
    with patch("flync_converter.registry", {source.name: source, destination.name: destination}):
        Converter.convert(str(tmp_path / "src"), str(tmp_path / "dst"), source_type=source.name, destination_type=destination.name)


def test_convert_writes_both_converter_reports_and_the_shared_report(tmp_path, loggers):
    _convert_with(tmp_path, _ReportingConverter("src"), _ReportingConverter("dst"))

    reports = reports_root(tmp_path / "dst")
    source_report = yaml.safe_load((reports / "src" / "report.yaml").read_text(encoding="utf-8"))
    destination_report = yaml.safe_load((reports / "dst" / "report.yaml").read_text(encoding="utf-8"))
    shared = yaml.safe_load((reports / "report.yaml").read_text(encoding="utf-8"))
    assert source_report == {"unsupported": [{"item": "BO_ 512", "reason": "multiplexed message without selector"}]}
    # The destination recorded a Path; it is written in its string form.
    assert destination_report == {
        "skipped": [{"item": "ecus.body_ecu", "reason": "no CAN interface"}],
        "custom": {"output_file": str(Path("out") / "model.dst")},
    }
    assert shared["status"] == "succeeded"
    assert shared["model"]["ecus"] == 0


def test_failing_conversion_keeps_its_own_exception_and_report(tmp_path, loggers):
    source, destination = _ReportingConverter("src"), _ReportingConverter("dst", fail=True)
    with pytest.raises(RuntimeError, match="the real encode error"):
        _convert_with(tmp_path, source, destination)

    reports = reports_root(tmp_path / "dst")
    assert yaml.safe_load((reports / "report.yaml").read_text(encoding="utf-8"))["status"] == "failed"
    assert (reports / "dst" / "report.yaml").exists()


# endregion
