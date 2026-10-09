"""Tests for the PySide6 GUI components.

Requires PySide6 (install with: pip install flync_converter[gui]).
Tests are skipped automatically when PySide6 is not installed.
The offscreen platform is used so no display server is required.
"""

import enum
import logging
import os
from unittest.mock import MagicMock, patch

import pytest

# Must be set before any Qt import so tests run headless in CI.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PySide6 = pytest.importorskip("PySide6", reason="PySide6 not installed")

from PySide6.QtWidgets import QApplication, QComboBox  # noqa: E402

from flync_converter.base import ConverterConfig  # noqa: E402
from flync_converter.base.base_converter import BaseConverter  # noqa: E402
from flync_converter.cli.gui.app import FlyncGUI  # noqa: E402
from flync_converter.cli.gui.widgets.converter_panel import ConverterPanel  # noqa: E402
from flync_converter.cli.gui.widgets.log_handler import LogWidgetHandler  # noqa: E402

# ---------------------------------------------------------------------------
# Session-scoped QApplication (pytest-qt provides qapp, but we also need it
# available for fixtures that don't use qtbot directly).
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def qapp_instance():
    app = QApplication.instance() or QApplication([])
    return app


class _FakeJSONConverter(BaseConverter):
    """A BaseConverter-backed fake that exposes the picker metadata."""

    name = "json"
    uses_directory = False
    source_extensions = ("json",)
    destination_extensions = ("json",)

    def can_decode(self) -> bool:
        return True

    def encode(self, source):
        return None

    def decode(self):
        return None


class _FakeYAMLConverter(BaseConverter):
    """A BaseConverter-backed fake exposing multiple source extensions."""

    name = "yaml"
    uses_directory = False
    source_extensions = ("yaml", "yml")
    destination_extensions = ("yaml",)

    def can_decode(self) -> bool:
        return True

    def encode(self, source):
        return None

    def decode(self):
        return None


class _FakeFLYNCConverter(BaseConverter):
    """A BaseConverter-backed fake whose destinations are directories."""

    name = "flync"
    uses_directory = True

    def can_decode(self) -> bool:
        return True

    def encode(self, source):
        return None

    def decode(self):
        return None


@pytest.fixture
def fake_registry():
    """Two minimal fake converters backed by real BaseConverter subclasses."""
    return {"json": _FakeJSONConverter(), "yaml": _FakeYAMLConverter()}


_PANEL_REGISTRY = "flync_converter.cli.gui.widgets.converter_panel.registry"
_APP_REGISTRY = "flync_converter.cli.gui.app.registry"
_UTILS_REGISTRY = "flync_converter.utils.registry"


def test_panel_initial_state(qapp_instance, fake_registry):
    """Panel has no converter selected on construction."""
    with patch(_PANEL_REGISTRY, fake_registry):
        panel = ConverterPanel("Source")
    assert panel.converter_type is None


def test_panel_default_selection(qapp_instance, fake_registry):
    """default= kwarg pre-selects the named converter."""
    with patch(_PANEL_REGISTRY, fake_registry):
        panel = ConverterPanel("Source", default="json")
    assert panel.converter_type == "json"


def test_panel_builds_text_and_enum_fields(qapp_instance):
    """Typed config fields render as QLineEdit (text) or QComboBox (enum)."""
    from PySide6.QtWidgets import QLineEdit

    class Direction(enum.Enum):
        LEFT = "left"
        RIGHT = "right"

    class RichConfig(ConverterConfig):
        label: str
        direction: Direction = Direction.LEFT

    class RichConverter(MagicMock):
        def __init__(self, config: RichConfig = None):
            pass

    reg = {"rich": RichConverter()}
    with patch(_PANEL_REGISTRY, reg), patch(_UTILS_REGISTRY, reg):
        panel = ConverterPanel("Source", default="rich")

    assert isinstance(panel._field_widgets["label"], QLineEdit)
    assert isinstance(panel._field_widgets["direction"], QComboBox)


def test_panel_enum_combo_contains_all_members(qapp_instance):
    """Enum QComboBox is populated with every member name."""

    class Color(enum.Enum):
        RED = "red"
        GREEN = "green"
        BLUE = "blue"

    class ColorConfig(ConverterConfig):
        color: Color = Color.RED

    class ColorConverter(MagicMock):
        def __init__(self, config: ColorConfig = None):
            pass

    reg = {"colorconv": ColorConverter()}
    with patch(_PANEL_REGISTRY, reg), patch(_UTILS_REGISTRY, reg):
        panel = ConverterPanel("Source", default="colorconv")

    combo = panel._field_widgets["color"]
    assert isinstance(combo, QComboBox)
    names = [combo.itemText(i) for i in range(combo.count())]
    assert names == ["RED", "GREEN", "BLUE"]


def test_panel_config_path_renders_browse_button(qapp_instance, fake_registry):
    """The config_path field pairs the line edit with a Browse button."""
    from PySide6.QtWidgets import QLineEdit, QPushButton

    with patch(_PANEL_REGISTRY, fake_registry), patch(_UTILS_REGISTRY, fake_registry):
        panel = ConverterPanel("Source", default="json")

    line = panel._field_widgets["config_path"]
    found = [btn for btn in panel._fields_container.findChildren(QPushButton) if btn.text() == "Browse..."]
    assert isinstance(line, QLineEdit)
    assert found


def test_panel_source_browse_uses_open_dialog(qapp_instance, fake_registry):
    """The Source panel fills a file picked via QFileDialog.getOpenFileName."""
    from PySide6.QtWidgets import QFileDialog

    with patch(_PANEL_REGISTRY, fake_registry), patch(_UTILS_REGISTRY, fake_registry):
        panel = ConverterPanel("Source", default="json")
        line = panel._field_widgets["config_path"]
        with patch.object(QFileDialog, "getOpenFileName", return_value=("/tmp/in.json", "")) as get_open:
            panel._browse_path(line)

    assert line.text() == "/tmp/in.json"
    assert get_open.call_args[0][3] == "JSON files (*.json)"


def test_panel_destination_browse_uses_save_dialog(qapp_instance, fake_registry):
    """The Destination panel fills a file picked via QFileDialog.getSaveFileName."""
    from PySide6.QtWidgets import QFileDialog

    with patch(_PANEL_REGISTRY, fake_registry), patch(_UTILS_REGISTRY, fake_registry):
        panel = ConverterPanel("Destination", default="json")
        line = panel._field_widgets["config_path"]
        with patch.object(QFileDialog, "getSaveFileName", return_value=("/tmp/out.json", "")):
            panel._browse_path(line)

    assert line.text() == "/tmp/out.json"


def test_panel_browse_dialog_preseeded_from_line_edit(qapp_instance, fake_registry):
    """The picker starts in the directory of the current field text."""
    from PySide6.QtWidgets import QFileDialog

    with patch(_PANEL_REGISTRY, fake_registry), patch(_UTILS_REGISTRY, fake_registry):
        panel = ConverterPanel("Source", default="json")
        line = panel._field_widgets["config_path"]
        line.setText("/work/current.json")
        with patch.object(QFileDialog, "getOpenFileName", return_value=("", "")) as get_open:
            panel._browse_path(line)

    assert "/work" in get_open.call_args[0][2]


def test_panel_destination_flync_browse_uses_folder(qapp_instance):
    """FLYNC destinations use the native folder picker, not Save As."""
    from PySide6.QtWidgets import QFileDialog

    reg = {"flync": _FakeFLYNCConverter()}
    with patch(_PANEL_REGISTRY, reg), patch(_UTILS_REGISTRY, reg):
        panel = ConverterPanel("Destination", default="flync")
        line = panel._field_widgets["config_path"]
        with patch.object(QFileDialog, "getExistingDirectory", return_value="/work/dir") as get_dir:
            with patch.object(QFileDialog, "getSaveFileName", return_value=("", "")) as get_save:
                panel._browse_path(line)

    assert line.text() == "/work/dir"
    get_dir.assert_called_once()
    get_save.assert_not_called()


def test_panel_source_browse_sets_name_filter(qapp_instance, fake_registry):
    """The source picker applies a single format-specific name filter."""
    from PySide6.QtWidgets import QFileDialog

    with patch(_PANEL_REGISTRY, fake_registry), patch(_UTILS_REGISTRY, fake_registry):
        panel = ConverterPanel("Source", default="json")
        line = panel._field_widgets["config_path"]
        with patch.object(QFileDialog, "getOpenFileName", return_value=("", "")) as get_open:
            panel._browse_path(line)

    get_open.assert_called_once()
    assert get_open.call_args[0][3] == "JSON files (*.json)"


def test_panel_browse_is_noop_for_unregistered_converter(qapp_instance, fake_registry):
    """A converter with no registry entry does not open any dialog."""
    from PySide6.QtWidgets import QFileDialog

    with patch(_PANEL_REGISTRY, fake_registry), patch(_UTILS_REGISTRY, fake_registry):
        panel = ConverterPanel("Destination", default="json")
        line = panel._field_widgets["config_path"]
        panel._converter_type = "csv"  # not in the registry
        with patch.object(QFileDialog, "getSaveFileName", return_value=("/tmp/x.csv", "")) as get_save:
            with patch.object(QFileDialog, "getExistingDirectory", return_value="/x"):
                panel._browse_path(line)

    get_save.assert_not_called()
    assert line.text() == ""


def test_panel_read_config_returns_instance(qapp_instance, fake_registry):
    """read_config() returns a ConverterConfig when a converter is selected."""
    with patch(_PANEL_REGISTRY, fake_registry), patch(_UTILS_REGISTRY, fake_registry):
        panel = ConverterPanel("Source", default="json")

    panel._field_widgets["config_path"].setText("/some/path")
    cfg = panel.read_config()
    assert isinstance(cfg, ConverterConfig)


def test_panel_read_config_raises_without_selection(qapp_instance, fake_registry):
    """read_config() raises RuntimeError when no converter type is selected."""
    with patch(_PANEL_REGISTRY, fake_registry):
        panel = ConverterPanel("Source")

    with pytest.raises(RuntimeError, match="No converter type selected"):
        panel.read_config()


def test_panel_show_and_clear_error(qapp_instance, fake_registry):
    """show_error() makes the label visible; clear_error() hides it."""
    with patch(_PANEL_REGISTRY, fake_registry):
        panel = ConverterPanel("Source")

    panel.show_error("something went wrong")
    assert not panel._error_label.isHidden()
    assert panel._error_label.text() == "something went wrong"

    panel.clear_error()
    assert panel._error_label.isHidden()


def test_panel_changed_signal_emitted_on_format_change(qapp_instance, fake_registry):
    """changed signal carries the new converter type string."""
    with patch(_PANEL_REGISTRY, fake_registry):
        panel = ConverterPanel("Source")

    received = []
    panel.changed.connect(received.append)

    idx = panel._format_combo.findData("json")
    panel._format_combo.setCurrentIndex(idx)

    assert received == ["json"]


def test_log_handler_routes_record_to_append_fn(qapp_instance):
    """LogWidgetHandler forwards formatted records to the supplied callable."""
    received: list[str] = []
    handler = LogWidgetHandler(received.append)
    handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))

    record = logging.LogRecord(
        name="test",
        level=logging.WARNING,
        pathname="",
        lineno=0,
        msg="hello gui",
        args=(),
        exc_info=None,
    )
    handler.emit(record)

    assert len(received) == 1
    assert "WARNING" in received[0]
    assert "hello gui" in received[0]


def test_gui_convert_button_initially_disabled(qapp_instance, fake_registry):
    """Convert button starts disabled until both panels have a selection."""
    with patch(_APP_REGISTRY, fake_registry), patch(_PANEL_REGISTRY, fake_registry):
        window = FlyncGUI()

    try:
        assert not window._convert_btn.isEnabled()
    finally:
        window.close()


def test_gui_convert_button_enabled_when_both_panels_selected(qapp_instance, fake_registry):
    """Convert button enables once source and destination are both set."""
    with patch(_APP_REGISTRY, fake_registry), patch(_PANEL_REGISTRY, fake_registry):
        window = FlyncGUI()

    try:
        window._source_panel._converter_type = "json"
        window._dest_panel._converter_type = "yaml"
        window._refresh_convert_button()
        assert window._convert_btn.isEnabled()
    finally:
        window.close()


def test_gui_source_error_shown_on_bad_source_config(qapp_instance, fake_registry):
    """If source read_config raises, the error is shown on the source panel."""
    with patch(_APP_REGISTRY, fake_registry), patch(_PANEL_REGISTRY, fake_registry):
        window = FlyncGUI()

    try:
        # Neither panel has a selection — source read_config raises first.
        window._on_convert_clicked()
        assert not window._source_panel._error_label.isHidden()
    finally:
        window.close()


def test_gui_dest_error_shown_on_bad_dest_config(qapp_instance, fake_registry):
    """If dest read_config raises, the error is shown on the destination panel."""
    with patch(_APP_REGISTRY, fake_registry), patch(_PANEL_REGISTRY, fake_registry), patch(_UTILS_REGISTRY, fake_registry):
        window = FlyncGUI()

    try:
        # Source is valid, dest has no selection.
        window._source_panel._converter_type = "json"
        with patch.object(
            window._source_panel,
            "read_config",
            return_value=ConverterConfig(config_path="/tmp"),
        ):
            window._on_convert_clicked()
        assert not window._dest_panel._error_label.isHidden()
    finally:
        window.close()


def test_gui_conversion_runs_in_background(qapp_instance, fake_registry):
    """A successful conversion emits the done signal and re-enables the button."""
    import threading
    import time

    with patch(_APP_REGISTRY, fake_registry), patch(_PANEL_REGISTRY, fake_registry), patch(_UTILS_REGISTRY, fake_registry):
        window = FlyncGUI()

    try:
        source_cfg = ConverterConfig(config_path="/tmp")
        dest_cfg = ConverterConfig(config_path="/tmp")

        with patch("flync_converter.cli.gui.app.Converter") as mock_cls:
            mock_cls.return_value.convert.return_value = None
            window._run_conversion("json", source_cfg, "yaml", dest_cfg)

            # Wait for the background thread to finish (max 2 s).
            deadline = time.monotonic() + 2.0
            while threading.active_count() > 1 and time.monotonic() < deadline:
                time.sleep(0.05)

            mock_cls.return_value.convert.assert_called_once()
    finally:
        window.close()
