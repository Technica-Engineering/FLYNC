from textwrap import dedent
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from flync.core.utils.exceptions import Severity
from flync_cli.commands.errors import app
from flync_cli.utils import errors
from flync_cli.utils.errors import (
    CatalogueReport,
    ErrorRecord,
    next_error_number,
    parse_catalogue_ids,
    render_catalogue,
    validate_catalogue,
)

runner = CliRunner()


def rec(
    number="001",
    category=1,
    bad_category=None,
    error_id="FLYNC-ECU-MAJ-VAL-001",
    severity=Severity.MAJ,
    module="ECU",
    location="mod.fn",
    message="'boom'",
):
    return ErrorRecord(
        error_id=error_id,
        module=module,
        severity=severity,
        category=category,
        number=number,
        location=location,
        message=message,
        file="src/flync/mod.py",
        lineno=1,
        bad_category=bad_category,
    )


@pytest.fixture
def scan(tmp_path, monkeypatch):
    def _run(code, relpath="pkg/mod.py"):
        root = tmp_path / "srcroot"
        path = root / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(dedent(code))
        monkeypatch.setattr(errors, "SRC_ROOT", root)
        return errors.scan_error_calls(root)

    return _run


class TestScanner:
    def test_finds_every_factory_with_correct_severity(self, scan):
        records = scan("""
            from flync.core.utils.exceptions import err_minor, err_major, err_fatal, warn, Category

            def a():
                raise err_minor("m", category=Category.VALUE_RANGE, error_number="001")
            def b():
                raise err_major("m", error_number="002")
            def c():
                raise err_fatal("m", error_number="003")
            def d():
                warn("m", error_number="004")
            """)
        assert [r.severity for r in records] == [Severity.MIN, Severity.MAJ, Severity.FAT, Severity.WARN]
        assert [r.number for r in records] == ["001", "002", "003", "004"]
        assert records[0].category == 1
        assert records[1].category == 0

    def test_skips_files_not_importing_the_factories(self, scan):
        records = scan("""
            import warnings

            def f():
                warnings.warn("not ours")
            """)
        assert records == []

    def test_resolves_aliased_import(self, scan):
        records = scan("""
            from flync.core.utils.exceptions import err_major as boom, Category

            def f():
                raise boom("x", category=Category.REQUIRED, error_number="009")
            """)
        assert len(records) == 1
        assert records[0].severity == Severity.MAJ
        assert records[0].category == 2

    def test_flags_invalid_category(self, scan):
        records = scan("""
            from flync.core.utils.exceptions import err_minor, Category

            def f():
                raise err_minor("x", category=Category.NOPE, error_number="001")
            """)
        assert records[0].category == 0
        assert records[0].bad_category == "Category.NOPE"

    def test_location_uses_class_and_function(self, scan):
        records = scan("""
            from flync.core.utils.exceptions import err_minor

            class Foo:
                def bar(self):
                    raise err_minor("x", error_number="001")

            def baz():
                raise err_minor("y", error_number="002")
            """)
        locations = {r.number: r.location for r in records}
        assert locations["001"] == "mod.Foo.bar"
        assert locations["002"] == "mod.baz"

    def test_message_and_missing_number(self, scan):
        records = scan("""
            from flync.core.utils.exceptions import warn

            def f():
                warn("hello", error_number="001")
            def g():
                warn(error_number="002")
            def h():
                warn("no number")
            """)
        by_number = {r.number: r.message for r in records}
        assert by_number["001"] == "'hello'"
        assert by_number["002"] == ""
        assert None in by_number


class TestNextErrorNumber:
    def test_starts_at_one_when_empty(self):
        assert next_error_number([]) == "001"

    def test_returns_highest_plus_one_ignoring_unnumbered(self):
        records = [rec(number="001"), rec(number="005"), rec(number=None)]
        assert next_error_number(records) == "006"


class TestCategoryNameAndTitle:
    def test_category_name(self):
        assert errors._category_name(1) == "VALUE_RANGE"
        assert errors._category_name(9) == "LIFECYCLE"
        assert errors._category_name(0) == "UNCATEGORISED"

    def test_title_strips_prefix_and_quotes(self):
        assert errors._title("f'hello world'") == "hello world"

    def test_title_truncates_long_message(self):
        title = errors._title("x" * 200)
        assert title.endswith("...")
        assert len(title) == 80

    def test_title_empty_message(self):
        assert errors._title("''") == "(no message)"


class TestRenderAndParse:
    def test_render_contains_all_fields(self):
        out = render_catalogue([rec(error_id="FLYNC-ECU-MAJ-VAL-001", location="m.f")])
        assert ".. err:: boom" in out
        assert ":id: FLYNC-ECU-MAJ-VAL-001" in out
        assert ":module: ECU" in out
        assert ":severity: MAJ" in out
        assert ":category: VALUE_RANGE" in out
        assert ":number: 001" in out
        assert ":location: m.f" in out
        assert "needtable" in out

    def test_parse_ids_roundtrip(self):
        records = [
            rec(error_id="FLYNC-ECU-MAJ-VAL-001", number="001"),
            rec(error_id="FLYNC-BUS-MIN-REQ-002", number="002"),
        ]
        assert parse_catalogue_ids(render_catalogue(records)) == [
            "FLYNC-ECU-MAJ-VAL-001",
            "FLYNC-BUS-MIN-REQ-002",
        ]


class TestValidateCatalogue:
    def test_clean_is_ok(self):
        records = [rec(error_id="FLYNC-ECU-MAJ-VAL-001", number="001", category=1)]
        report = validate_catalogue(records, render_catalogue(records))
        assert report.ok

    def test_detects_unnumbered(self):
        report = validate_catalogue([rec(number=None)], "")
        assert len(report.unnumbered) == 1

    def test_detects_uncategorised(self):
        report = validate_catalogue([rec(category=0)], None)
        assert len(report.uncategorised) == 1
        assert report.invalid_category == []

    def test_detects_invalid_category_separately(self):
        report = validate_catalogue([rec(category=0, bad_category="Category.NOPE")], None)
        assert len(report.invalid_category) == 1
        assert report.uncategorised == []

    def test_detects_duplicate_numbers(self):
        records = [rec(number="001"), rec(number="001")]
        report = validate_catalogue(records, None)
        assert "001" in report.duplicate_numbers

    def test_missing_from_catalogue_when_file_absent(self):
        records = [rec(error_id="FLYNC-ECU-MAJ-VAL-001", number="001")]
        report = validate_catalogue(records, None)
        assert report.missing_from_catalogue == ["FLYNC-ECU-MAJ-VAL-001"]

    def test_orphaned_ids_in_catalogue(self):
        text = render_catalogue([rec(error_id="FLYNC-ECU-MAJ-VAL-999", number="999")])
        report = validate_catalogue([], text)
        assert report.orphaned_in_catalogue == ["FLYNC-ECU-MAJ-VAL-999"]

    def test_empty_report_is_ok(self):
        assert CatalogueReport([], [], [], {}, [], []).ok


class TestGetNextNumberCommand:
    def test_prints_next_number(self):
        with patch("flync_cli.commands.errors.scan_error_calls", return_value=[rec(number="007")]):
            result = runner.invoke(app, ["get-next-number"])
        assert result.exit_code == 0
        assert "008" in result.stdout


class TestValidateCatalogueCommand:
    def test_clean_exits_zero(self, tmp_path):
        records = [rec(error_id="FLYNC-ECU-MAJ-VAL-001", number="001", category=1)]
        catalogue = tmp_path / "cat.rst"
        catalogue.write_text(render_catalogue(records))
        with patch("flync_cli.commands.errors.scan_error_calls", return_value=records), patch("flync_cli.commands.errors.CATALOGUE_PATH", catalogue):
            result = runner.invoke(app, ["validate-catalogue"])
        assert result.exit_code == 0
        assert "in sync" in result.stdout

    def test_drift_exits_one(self, tmp_path):
        records = [rec(error_id="FLYNC-ECU-MAJ-VAL-001", number=None, category=0, bad_category="Category.NOPE")]
        with (
            patch("flync_cli.commands.errors.scan_error_calls", return_value=records),
            patch("flync_cli.commands.errors.CATALOGUE_PATH", tmp_path / "does_not_exist.rst"),
        ):
            result = runner.invoke(app, ["validate-catalogue"])
        assert result.exit_code == 1


class TestGenerateCatalogueCommand:
    def test_refuses_when_call_sites_incomplete(self):
        with patch("flync_cli.commands.errors.scan_error_calls", return_value=[rec(number=None)]):
            result = runner.invoke(app, ["generate-catalogue"])
        assert result.exit_code == 1
        assert "Cannot generate" in result.stdout

    def test_writes_catalogue_when_clean(self, tmp_path):
        records = [rec(error_id="FLYNC-ECU-MAJ-VAL-001", number="001", category=1)]
        catalogue = tmp_path / "out.rst"
        with patch("flync_cli.commands.errors.scan_error_calls", return_value=records), patch("flync_cli.commands.errors.CATALOGUE_PATH", catalogue):
            result = runner.invoke(app, ["generate-catalogue"])
        assert result.exit_code == 0
        assert catalogue.exists()
        assert "FLYNC-ECU-MAJ-VAL-001" in catalogue.read_text()
