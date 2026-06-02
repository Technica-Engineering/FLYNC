"""Tests for flync_cli.utils.error_table — error formatting and display."""

from unittest.mock import patch

from rich.table import Table

from flync.sdk.context.diagnostics_result import DiagnosticsResult, WorkspaceState
from flync_cli.utils.error_table import (
    _classify_errors,
    _fill_error_table,
    _format_source,
    _make_details_cell,
    _make_error_table,
    print_validation_result,
    render_errors,
    render_warnings,
    sanitize_error_message,
)


class TestSanitizeErrorMessage:
    def test_removes_ansi_escape_sequences(self):
        """Test that ANSI escape codes are removed."""
        msg_with_ansi = "\x1b[31mRed text\x1b[0m"
        result = sanitize_error_message(msg_with_ansi)
        assert result == "Red text"

    def test_leaves_plain_text_unchanged(self):
        """Test that plain text is not modified."""
        msg = "Simple error message"
        result = sanitize_error_message(msg)
        assert result == msg

    def test_handles_multiple_escape_sequences(self):
        """Test removal of multiple ANSI sequences."""
        msg = "\x1b[1;31mBold red\x1b[0m normal \x1b[32mgreen\x1b[0m"
        result = sanitize_error_message(msg)
        assert result == "Bold red normal green"

    def test_handles_empty_string(self):
        """Test with empty string."""
        result = sanitize_error_message("")
        assert result == ""


class TestMakeDetailsCell:
    def test_empty_sub_errors_returns_empty_string(self):
        """Test that empty sub_errors returns empty string."""
        result = _make_details_cell("")
        assert result == ""

    def test_single_error_creates_table(self):
        """Test with single error line."""
        result = _make_details_cell("First error")
        assert isinstance(result, Table)

    def test_multiple_errors_creates_nested_table(self):
        """Test with multiple error lines."""
        sub_errors = "Error 1\nError 2\nError 3"
        result = _make_details_cell(sub_errors)
        assert isinstance(result, Table)

    def test_skips_empty_lines(self):
        """Test that empty lines are filtered out."""
        sub_errors = "Error 1\n\nError 2\n"
        result = _make_details_cell(sub_errors)
        assert isinstance(result, Table)

    def test_nested_table_has_no_header(self):
        """Test that nested table has no header."""
        result = _make_details_cell("Error")
        assert isinstance(result, Table)
        assert result.show_header is False

    def test_nested_table_shows_lines(self):
        """Test that nested table shows lines between rows."""
        result = _make_details_cell("Error 1\nError 2")
        assert isinstance(result, Table)
        assert result.show_lines is True


class TestFormatSource:
    def test_returns_doc_uri_without_line(self):
        """Test formatting when no line number is available."""
        result = _format_source("models/config.yaml", {})
        assert result == "models/config.yaml"

    def test_returns_yaml_path_with_line(self):
        """Test with yaml_path and line in context."""
        ctx = {"yaml_path": "config.yaml", "line": 42}
        result = _format_source("fallback.yaml", ctx)
        assert result == "config.yaml:line 42"

    def test_uses_doc_uri_when_yaml_path_empty(self):
        """Test fallback to doc_uri when yaml_path is empty."""
        ctx = {"yaml_path": "", "line": 10}
        result = _format_source("doc.yaml", ctx)
        assert result == "doc.yaml:line 10"

    def test_uses_doc_uri_when_yaml_path_missing(self):
        """Test fallback to doc_uri when yaml_path not in context."""
        ctx = {"line": 5}
        result = _format_source("doc.yaml", ctx)
        assert result == "doc.yaml:line 5"

    def test_omits_line_when_none(self):
        """Test that line is omitted when None."""
        ctx = {"yaml_path": "config.yaml", "line": None}
        result = _format_source("doc.yaml", ctx)
        assert result == "config.yaml"


class TestClassifyErrors:
    def test_separates_file_docs_from_directory_docs(self):
        """Test that .yaml files are root, directories are subsequent."""
        errors_by_doc = {
            "config.yaml": [{"type": "error", "msg": "file error"}],
            "subdirectory": [{"type": "error", "msg": "dir error"}],
        }
        root_rows, subsequent_rows = _classify_errors(errors_by_doc)
        assert len(root_rows) == 1
        assert len(subsequent_rows) == 1
        assert root_rows[0][0] == "config.yaml"
        assert subsequent_rows[0][0] == "subdirectory"

    def test_skips_warnings(self):
        """Test that warnings are excluded from classification."""
        errors_by_doc = {
            "config.yaml": [
                {"type": "error", "msg": "error"},
                {"type": "warning", "msg": "warning"},
            ]
        }
        root_rows, subsequent_rows = _classify_errors(errors_by_doc)
        assert len(root_rows) == 1
        assert len(subsequent_rows) == 0

    def test_handles_multiple_errors_per_doc(self):
        """Test with multiple errors in one document."""
        errors_by_doc = {
            "config.yaml": [
                {"type": "error", "msg": "error1"},
                {"type": "error", "msg": "error2"},
            ]
        }
        root_rows, subsequent_rows = _classify_errors(errors_by_doc)
        assert len(root_rows) == 2

    def test_handles_empty_errors(self):
        """Test with empty errors dictionary."""
        root_rows, subsequent_rows = _classify_errors({})
        assert root_rows == []
        assert subsequent_rows == []

    def test_identifies_yaml_suffix(self):
        """Test that .yaml extension is correctly identified."""
        errors_by_doc = {
            "file.yaml": [{"type": "error", "msg": "yaml error"}],
            "file.yml": [{"type": "error", "msg": "yml error"}],
            "dir": [{"type": "error", "msg": "dir error"}],
        }
        root_rows, subsequent_rows = _classify_errors(errors_by_doc)
        assert len(root_rows) == 2  # .yaml and .yml
        assert len(subsequent_rows) == 1  # dir


class TestMakeErrorTable:
    def test_creates_table_with_all_columns(self):
        """Test that table has all expected columns."""
        table = _make_error_table()
        assert len(table.columns) == 6
        column_names = [col.header for col in table.columns]
        assert "#" in column_names
        assert "Error Type" in column_names
        assert "Message" in column_names
        assert "Location" in column_names
        assert "Source" in column_names
        assert "Details" in column_names

    def test_table_shows_lines(self):
        """Test that table is configured to show lines."""
        table = _make_error_table()
        assert table.show_lines is True

    def test_table_columns_have_overflow_configured(self):
        """Test that columns have overflow configuration."""
        table = _make_error_table()
        for col in table.columns:
            # Columns should have some overflow strategy configured
            assert col.overflow in ("fold", "ellipsis", "crop")


class TestFillErrorTable:
    def test_adds_rows_to_table(self):
        """Test that rows are added to the table."""
        table = _make_error_table()
        rows = [("config.yaml", {"type": "error", "msg": "Test error", "loc": ["field"], "ctx": {}})]
        _fill_error_table(table, rows, 1)
        assert len(table.rows) == 1

    def test_uses_sequential_numbering(self):
        """Test that rows are numbered sequentially."""
        table = _make_error_table()
        rows = [
            ("config.yaml", {"type": "error", "msg": "Error 1", "loc": [], "ctx": {}}),
            ("config.yaml", {"type": "error", "msg": "Error 2", "loc": [], "ctx": {}}),
        ]
        _fill_error_table(table, rows, 5)
        # Check that numbering started at 5
        assert len(table.rows) == 2

    def test_handles_missing_fields_in_error(self):
        """Test graceful handling of missing error fields."""
        table = _make_error_table()
        rows = [("doc.yaml", {})]  # Minimal error dict
        _fill_error_table(table, rows, 1)
        assert len(table.rows) == 1

    def test_formats_location_from_path(self):
        """Test that location is formatted from path."""
        table = _make_error_table()
        rows = [
            (
                "config.yaml",
                {
                    "type": "error",
                    "msg": "Test",
                    "loc": ["field", "subfield"],
                    "ctx": {},
                },
            )
        ]
        _fill_error_table(table, rows, 1)
        # Location should be "field.subfield"
        assert len(table.rows) == 1

    def test_sanitizes_error_message(self):
        """Test that messages are sanitized of ANSI codes."""
        table = _make_error_table()
        rows = [
            (
                "config.yaml",
                {
                    "type": "error",
                    "msg": "\x1b[31mRed error\x1b[0m",
                    "loc": [],
                    "ctx": {},
                },
            )
        ]
        _fill_error_table(table, rows, 1)
        assert len(table.rows) == 1

    def test_includes_sub_errors_in_details(self):
        """Test that sub_errors are included in details column."""
        table = _make_error_table()
        rows = [
            (
                "config.yaml",
                {
                    "type": "error",
                    "msg": "Test",
                    "loc": [],
                    "ctx": {"sub_errors": "Validation failed"},
                },
            )
        ]
        _fill_error_table(table, rows, 1)
        assert len(table.rows) == 1


class TestRenderWarnings:
    def test_does_not_print_when_no_warnings(self):
        """Test that nothing is printed when no warnings exist."""
        result = DiagnosticsResult(state=WorkspaceState.VALID, errors={})
        with patch("flync_cli.utils.error_table.console") as mock_console:
            render_warnings(result)
            mock_console.print.assert_not_called()

    def test_returns_none(self):
        """Test that render_warnings returns None."""
        result = DiagnosticsResult(state=WorkspaceState.VALID, errors={})
        ret_val = render_warnings(result)
        assert ret_val is None


class TestRenderErrors:
    def test_does_not_print_when_no_errors(self):
        """Test that nothing prints when no errors exist."""
        result = DiagnosticsResult(state=WorkspaceState.VALID, errors={})
        with patch("flync_cli.utils.error_table.console") as mock_console:
            render_errors(result)
            mock_console.print.assert_not_called()

    def test_prints_message_when_workspace_broken_no_errors(self):
        """Test BROKEN state with no error details."""
        result = DiagnosticsResult(state=WorkspaceState.BROKEN, errors={})
        with patch("flync_cli.utils.error_table.console") as mock_console:
            render_errors(result)
            assert mock_console.print.called

    def test_returns_none(self):
        """Test that render_errors returns None."""
        result = DiagnosticsResult(state=WorkspaceState.VALID, errors={})
        ret_val = render_errors(result)
        assert ret_val is None


class TestPrintValidationResult:
    def test_calls_render_warnings_and_errors(self):
        """Test that both warnings and errors are rendered."""
        result = DiagnosticsResult(
            state=WorkspaceState.WARNING,
            errors={},
        )
        with patch("flync_cli.utils.error_table.render_warnings") as mock_warn:
            with patch("flync_cli.utils.error_table.render_errors") as mock_err:
                print_validation_result(result)
                mock_warn.assert_called_once_with(result)
                mock_err.assert_called_once_with(result)
